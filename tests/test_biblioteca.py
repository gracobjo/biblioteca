import csv
import json
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app import Biblioteca
from database import ReglaNegocio, Repositorio
from services import CAMPOS_HISTORICO, Servicio, validar_libro, validar_socio


class CursorSimulado:
    def __init__(self, respuestas=(), fallar_en=None):
        self.respuestas = iter(respuestas)
        self.sentencias = []
        self.fallar_en = fallar_en
        self.rowcount = 1

    def execute(self, sql, parametros=()):
        self.sentencias.append((sql, parametros))
        if self.fallar_en == len(self.sentencias):
            raise RuntimeError("fallo simulado")

    def fetchone(self):
        return next(self.respuestas)

    def fetchall(self):
        return next(self.respuestas)

    def close(self):
        pass


class ConexionSimulada:
    def __init__(self, cursor):
        self.cursor_simulado = cursor
        self.confirmaciones = 0
        self.reversiones = 0
        self.cerrada = False

    def cursor(self, dictionary=False):
        return self.cursor_simulado

    def commit(self):
        self.confirmaciones += 1

    def rollback(self):
        self.reversiones += 1

    def close(self):
        self.cerrada = True


class CursorSQLite:
    def __init__(self, conexion):
        self.cursor = conexion.cursor()

    def execute(self, sql, parametros=()):
        sql = sql.replace("%s", "?").replace(" FOR UPDATE", "")
        parametros = tuple(valor.isoformat() if isinstance(valor, date) else valor for valor in parametros)
        self.cursor.execute(sql, parametros)

    def fetchone(self):
        fila = self.cursor.fetchone()
        if fila is None:
            return None
        valores = dict(fila)
        if isinstance(valores.get("fecha_devolucion_prevista"), str):
            valores["fecha_devolucion_prevista"] = date.fromisoformat(valores["fecha_devolucion_prevista"])
        return valores

    def fetchall(self):
        return [dict(fila) for fila in self.cursor.fetchall()]

    @property
    def rowcount(self):
        return self.cursor.rowcount

    def close(self):
        self.cursor.close()


class ConexionSQLite:
    """Adaptador de pruebas; SQLite no reproduce los bloqueos FOR UPDATE de MySQL."""

    def __init__(self, conexion):
        self.conexion = conexion

    def cursor(self, dictionary=False):
        return CursorSQLite(self.conexion)

    def commit(self):
        self.conexion.commit()

    def rollback(self):
        self.conexion.rollback()

    def close(self):
        pass


class ReglasPrestamosTest(unittest.TestCase):
    def setUp(self):
        self.conexion = sqlite3.connect(":memory:")
        self.addCleanup(self.conexion.close)
        self.conexion.row_factory = sqlite3.Row
        self.conexion.executescript("""
            CREATE TABLE socios (id_socio INTEGER PRIMARY KEY);
            CREATE TABLE libros (id_libro INTEGER PRIMARY KEY, ejemplares_disponibles INTEGER);
            CREATE TABLE prestamos (id_prestamo INTEGER PRIMARY KEY, id_libro INTEGER, id_socio INTEGER,
                fecha_prestamo TEXT, fecha_devolucion_prevista TEXT,
                fecha_devolucion_real TEXT, estado TEXT);
            INSERT INTO socios VALUES (1);
            INSERT INTO libros VALUES (1, 4), (2, 4), (3, 4);
        """)
        self.repo = Repositorio(lambda: ConexionSQLite(self.conexion))

    def test_dos_prestamos_tercero_rechazado_y_devolucion_habilita_otro(self):
        self.repo.prestar(1, 1, date(2026, 12, 20))
        self.repo.prestar(1, 2, date(2028, 2, 20))
        filas = self.conexion.execute(
            "SELECT id_prestamo, fecha_prestamo, fecha_devolucion_prevista FROM prestamos ORDER BY id_prestamo"
        ).fetchall()
        self.assertEqual([(fila["fecha_prestamo"], fila["fecha_devolucion_prevista"]) for fila in filas],
                         [("2026-12-20", "2027-01-09"), ("2028-02-20", "2028-03-11")])
        with self.assertRaisesRegex(ReglaNegocio, "máximo de 2"):
            self.repo.prestar(1, 3)
        self.assertEqual(self.conexion.execute("SELECT COUNT(*) FROM prestamos").fetchone()[0], 2)
        self.assertEqual(self.conexion.execute(
            "SELECT ejemplares_disponibles FROM libros WHERE id_libro=3"
        ).fetchone()[0], 4)
        self.repo.devolver(filas[0]["id_prestamo"], date(2028, 2, 21))
        self.repo.prestar(1, 3, date(2028, 2, 21))
        self.assertEqual(self.conexion.execute(
            "SELECT COUNT(*) FROM prestamos WHERE estado='Activo' OR fecha_devolucion_real IS NULL"
        ).fetchone()[0], 2)

    def test_limite_cuenta_estado_activo_o_fecha_real_vacia(self):
        self.conexion.executemany(
            "INSERT INTO prestamos (id_libro, id_socio, fecha_devolucion_real, estado) VALUES (?, ?, ?, ?)",
            [(1, 1, "2026-01-02", "Activo"), (2, 1, None, "Devuelto")],
        )
        self.conexion.commit()
        with self.assertRaisesRegex(ReglaNegocio, "máximo de 2"):
            self.repo.prestar(1, 3)
        self.assertEqual(self.conexion.execute("SELECT COUNT(*) FROM prestamos").fetchone()[0], 2)


class ProrrogasReservasTest(unittest.TestCase):
    def setUp(self):
        reloj = patch("database.date", wraps=date)
        self.fecha = reloj.start()
        self.fecha.today.return_value = date(2026, 12, 10)
        self.addCleanup(reloj.stop)
        self.conexion = sqlite3.connect(":memory:")
        self.addCleanup(self.conexion.close)
        self.conexion.row_factory = sqlite3.Row
        self.conexion.executescript("""
            CREATE TABLE socios (id_socio INTEGER PRIMARY KEY, email TEXT);
            CREATE TABLE libros (id_libro INTEGER PRIMARY KEY, ejemplares_disponibles INTEGER, isbn TEXT);
            CREATE TABLE prestamos (id_prestamo INTEGER PRIMARY KEY, id_libro INTEGER, id_socio INTEGER,
                fecha_devolucion_prevista TEXT, fecha_devolucion_real TEXT, estado TEXT);
            CREATE TABLE reservas (id_reserva INTEGER PRIMARY KEY, id_libro INTEGER, id_socio INTEGER,
                UNIQUE (id_libro, id_socio));
            CREATE TABLE prorrogas (id_prestamo INTEGER PRIMARY KEY, fecha_anterior TEXT, fecha_nueva TEXT);
            INSERT INTO socios VALUES (1, 'uno@example.com'), (2, 'dos@example.com');
            INSERT INTO libros VALUES (1, 0, 'isbn-1');
            INSERT INTO prestamos VALUES (1, 1, 1, '2026-12-20', NULL, 'Activo');
        """)
        self.repo = Repositorio(lambda: ConexionSQLite(self.conexion))

    def test_plazo_de_prorroga_incluye_vencimiento_y_rechaza_retraso(self):
        self.fecha.today.return_value = date(2026, 12, 21)
        with self.assertRaisesRegex(ReglaNegocio, "plazo.*vencido"):
            self.repo.prorrogar(1)
        self.assertEqual(self.conexion.execute(
            "SELECT fecha_devolucion_prevista FROM prestamos WHERE id_prestamo=1"
        ).fetchone()[0], "2026-12-20")
        self.assertEqual(self.conexion.execute("SELECT COUNT(*) FROM prorrogas").fetchone()[0], 0)
        self.assertEqual(self.conexion.execute(
            "SELECT ejemplares_disponibles FROM libros WHERE id_libro=1"
        ).fetchone()[0], 0)
        self.fecha.today.return_value = date(2026, 12, 20)
        self.assertEqual(self.repo.prorrogar(1), date(2027, 1, 9))
        with self.assertRaisesRegex(ReglaNegocio, "ya ha sido prorrogado"):
            self.repo.prorrogar(1)

    def test_importacion_rechaza_prorroga_vencida_y_continua(self):
        self.fecha.today.return_value = date(2026, 12, 21)
        self.conexion.execute("INSERT INTO libros VALUES (2, 1, 'isbn-2')")
        self.conexion.execute("INSERT INTO prestamos VALUES (2, 2, 1, '2026-12-22', NULL, 'Activo')")
        self.conexion.commit()
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "prorrogas.csv"
            ruta.write_text("isbn,email\nisbn-1,uno@example.com\nisbn-2,uno@example.com\n", encoding="utf-8")
            resumen = Servicio(self.repo).importar(ruta, "prorrogas")
        self.assertEqual(resumen["actualizados"], 1)
        self.assertEqual(len(resumen["errores"]), 1)
        self.assertRegex(resumen["errores"][0], "Línea 2:.*plazo.*vencido")
        fechas = self.conexion.execute(
            "SELECT id_prestamo, fecha_devolucion_prevista FROM prestamos ORDER BY id_prestamo"
        ).fetchall()
        self.assertEqual([tuple(fila) for fila in fechas], [(1, "2026-12-20"), (2, "2027-01-11")])
        self.assertEqual(self.conexion.execute(
            "SELECT id_prestamo FROM prorrogas"
        ).fetchone()[0], 2)

    def test_prorroga_una_vez_desde_fecha_prevista_sin_cambiar_stock(self):
        self.assertEqual(self.repo.prorrogar(1), date(2027, 1, 9))
        fila = self.conexion.execute(
            "SELECT fecha_devolucion_prevista, fecha_devolucion_real FROM prestamos WHERE id_prestamo=1"
        ).fetchone()
        self.assertEqual((fila[0], fila[1]), ("2027-01-09", None))
        self.assertEqual(tuple(self.conexion.execute(
            "SELECT fecha_anterior, fecha_nueva FROM prorrogas"
        ).fetchone()), ("2026-12-20", "2027-01-09"))
        with self.assertRaisesRegex(ReglaNegocio, "ya ha sido prorrogado"):
            self.repo.prorrogar(1)
        self.assertEqual(self.conexion.execute(
            "SELECT fecha_devolucion_prevista FROM prestamos WHERE id_prestamo=1"
        ).fetchone()[0], "2027-01-09")
        self.assertEqual(self.conexion.execute(
            "SELECT ejemplares_disponibles FROM libros WHERE id_libro=1"
        ).fetchone()[0], 0)

    def test_reserva_ajena_bloquea_hasta_cancelarla_y_reserva_propia_no_bloquea(self):
        self.repo.reservar(1, 1)
        self.repo.reservar(2, 1)
        with self.assertRaisesRegex(ReglaNegocio, "ya tiene una reserva"):
            self.repo.reservar(2, 1)
        with self.assertRaisesRegex(ReglaNegocio, "otro socio"):
            self.repo.prorrogar(1)
        self.assertEqual(self.conexion.execute("SELECT COUNT(*) FROM prorrogas").fetchone()[0], 0)
        self.assertEqual(self.conexion.execute(
            "SELECT fecha_devolucion_prevista FROM prestamos WHERE id_prestamo=1"
        ).fetchone()[0], "2026-12-20")
        id_reserva = self.conexion.execute(
            "SELECT id_reserva FROM reservas WHERE id_socio=2"
        ).fetchone()[0]
        self.repo.cancelar_reserva(id_reserva)
        self.assertEqual(self.repo.prorrogar(1), date(2027, 1, 9))
        self.assertEqual(self.conexion.execute("SELECT COUNT(*) FROM reservas").fetchone()[0], 1)

    def test_prestamo_devuelto_o_inexistente_no_se_prorroga(self):
        self.conexion.execute("UPDATE prestamos SET fecha_devolucion_real='2026-12-21' WHERE id_prestamo=1")
        self.conexion.commit()
        with self.assertRaisesRegex(ReglaNegocio, "ya tiene registrada la devolución.*nuevo préstamo"):
            self.repo.prorrogar(1)
        tabla = Mock()
        tabla.selection.return_value = ("fila",)
        tabla.item.return_value = (1,)
        ventana = SimpleNamespace(tabla_prestamos=tabla, repo=self.repo, actualizar=Mock())
        with patch("app.messagebox.showerror") as error, patch("app.messagebox.showinfo") as exito:
            Biblioteca.prorrogar(ventana)
        self.assertIn("ya tiene registrada la devolución", error.call_args.args[1])
        self.assertIn("nuevo préstamo", error.call_args.args[1])
        exito.assert_not_called()
        ventana.actualizar.assert_not_called()
        with self.assertRaisesRegex(ReglaNegocio, "ya no existe"):
            self.repo.prorrogar(99)
        self.assertEqual(self.conexion.execute("SELECT COUNT(*) FROM prorrogas").fetchone()[0], 0)

    def test_fallo_actualizacion_revierte_registro_prorroga(self):
        cursor = CursorSimulado([
            {"id_libro": 1, "id_socio": 1, "fecha_devolucion_prevista": date(2026, 12, 20),
             "fecha_devolucion_real": None},
            None, {"id_libro": 1}, None,
        ], fallar_en=6)
        conexion = ConexionSimulada(cursor)
        with self.assertRaises(RuntimeError):
            Repositorio(lambda: conexion).prorrogar(1)
        self.assertEqual((conexion.confirmaciones, conexion.reversiones), (0, 1))

    def test_importar_por_referencias_aplica_reglas_reales(self):
        self.repo.reservar_por_referencias("isbn-1", "dos@example.com")
        with self.assertRaisesRegex(ReglaNegocio, "ya tiene una reserva"):
            self.repo.reservar_por_referencias("isbn-1", "dos@example.com")
        with self.assertRaisesRegex(ReglaNegocio, "otro socio"):
            self.repo.prorrogar_por_referencias("isbn-1", "uno@example.com")
        reserva = self.conexion.execute("SELECT id_reserva FROM reservas").fetchone()[0]
        self.repo.cancelar_reserva(reserva)
        self.assertEqual(self.repo.prorrogar_por_referencias("isbn-1", "uno@example.com"), date(2027, 1, 9))
        with self.assertRaisesRegex(ReglaNegocio, "ya ha sido prorrogado"):
            self.repo.prorrogar_por_referencias("isbn-1", "uno@example.com")

    def test_referencias_desconocidas_o_prestamos_ambiguos_se_rechazan(self):
        with self.assertRaisesRegex(ReglaNegocio, "No existe el libro o el socio"):
            self.repo.reservar_por_referencias("isbn-1", "no@example.com")
        with self.assertRaisesRegex(ReglaNegocio, "No existe un préstamo"):
            self.repo.prorrogar_por_referencias("isbn-1", "dos@example.com")
        self.conexion.execute("INSERT INTO prestamos VALUES (2, 1, 1, '2026-12-20', NULL, 'Activo')")
        self.conexion.commit()
        with self.assertRaisesRegex(ReglaNegocio, "varios préstamos"):
            self.repo.prorrogar_por_referencias("isbn-1", "uno@example.com")
        self.assertEqual(self.conexion.execute("SELECT COUNT(*) FROM prorrogas").fetchone()[0], 0)

    def test_reserva_rechaza_isbn_ambiguo(self):
        self.conexion.execute("INSERT INTO libros VALUES (2, 1, 'isbn-1')")
        self.conexion.commit()
        with self.assertRaisesRegex(ReglaNegocio, "varios registros"):
            self.repo.reservar_por_referencias("isbn-1", "uno@example.com")
        self.assertEqual(self.conexion.execute("SELECT COUNT(*) FROM reservas").fetchone()[0], 0)


class OrdenPrestamosTest(unittest.TestCase):
    def test_prestamos_ascendentes_en_todos_los_filtros(self):
        conexion = sqlite3.connect(":memory:")
        self.addCleanup(conexion.close)
        conexion.row_factory = sqlite3.Row
        conexion.create_function("CONCAT", -1, lambda *partes: "".join(partes))
        conexion.executescript("""
            CREATE TABLE libros (id_libro INTEGER, titulo TEXT);
            CREATE TABLE socios (id_socio INTEGER, nombre TEXT, apellidos TEXT);
            CREATE TABLE prestamos (id_prestamo INTEGER, id_libro INTEGER, id_socio INTEGER,
                fecha_prestamo TEXT, fecha_devolucion_prevista TEXT,
                fecha_devolucion_real TEXT, estado TEXT);
            INSERT INTO libros VALUES (1, 'Libro');
            INSERT INTO socios VALUES (1, 'Ana', 'Pérez');
            INSERT INTO prestamos VALUES (7, 1, 1, '2026-01-01', '2026-01-21', NULL, 'Activo');
            INSERT INTO prestamos VALUES (5, 1, 1, '2026-01-01', '2026-01-21', '2026-01-05', 'Devuelto');
            INSERT INTO prestamos VALUES (3, 1, 1, '2026-01-01', '2026-01-21', '2026-01-05', 'Devuelto');
            INSERT INTO prestamos VALUES (1, 1, 1, '2026-01-01', '2026-01-21', NULL, 'Activo');
        """)
        repo = Repositorio()
        repo.consultar = lambda sql, params=(): [
            dict(fila) for fila in conexion.execute(sql.replace("%s", "?"), params)
        ]
        for filtro, esperados in (("Todos", [1, 3, 5, 7]), ("Solo Activos", [1, 7]), ("Devueltos", [3, 5])):
            with self.subTest(filtro=filtro):
                self.assertEqual([fila["id_prestamo"] for fila in repo.prestamos(filtro)], esperados)


class TransaccionesTest(unittest.TestCase):
    def repositorio(self, respuestas, fallar_en=None):
        cursor = CursorSimulado(respuestas, fallar_en)
        conexion = ConexionSimulada(cursor)
        return Repositorio(lambda: conexion), conexion, cursor

    def test_prestamo_fecha_y_transaccion(self):
        repo, conexion, cursor = self.repositorio([{"id_socio": 2}, {"cantidad": 1}, {"ejemplares_disponibles": 1}])
        repo.prestar(2, 3, date(2026, 12, 20))
        self.assertEqual(cursor.sentencias[3][1], (3, 2, date(2026, 12, 20), date(2027, 1, 9), None, "Activo"))
        self.assertIn("FOR UPDATE", cursor.sentencias[0][0])
        self.assertIn("estado=%s OR fecha_devolucion_real IS NULL", cursor.sentencias[1][0])
        self.assertEqual((conexion.confirmaciones, conexion.reversiones, conexion.cerrada), (1, 0, True))

    def test_limite_y_stock_agotado_no_insertan(self):
        casos = [
            [{"id_socio": 2}, {"cantidad": 2}],
            [{"id_socio": 2}, {"cantidad": 0}, {"ejemplares_disponibles": 0}],
        ]
        for respuestas in casos:
            with self.subTest(respuestas=respuestas):
                repo, conexion, cursor = self.repositorio(respuestas)
                with self.assertRaises(ReglaNegocio):
                    repo.prestar(2, 3)
                self.assertEqual((conexion.confirmaciones, conexion.reversiones), (0, 1))
                self.assertFalse(any("INSERT INTO" in sql for sql, _ in cursor.sentencias))

    def test_fallo_stock_revierte_insercion(self):
        repo, conexion, _ = self.repositorio(
            [{"id_socio": 2}, {"cantidad": 0}, {"ejemplares_disponibles": 1}], fallar_en=5
        )
        with self.assertRaises(RuntimeError):
            repo.prestar(2, 3)
        self.assertEqual((conexion.confirmaciones, conexion.reversiones), (0, 1))

    def test_devolucion_y_proteccion_contra_doble_devolucion(self):
        repo, conexion, cursor = self.repositorio(
            [{"id_libro": 3, "estado": "Activo", "fecha_devolucion_real": None}]
        )
        repo.devolver(4, date(2026, 1, 2))
        self.assertEqual(cursor.sentencias[1][1], (date(2026, 1, 2), "Devuelto", 4))
        self.assertIn("ejemplares_disponibles+1", cursor.sentencias[2][0])
        self.assertEqual(conexion.confirmaciones, 1)
        repo, conexion, cursor = self.repositorio(
            [{"id_libro": 3, "estado": "Activo", "fecha_devolucion_real": date(2026, 1, 2)}]
        )
        with self.assertRaises(ReglaNegocio):
            repo.devolver(4)
        self.assertEqual(len(cursor.sentencias), 1)
        self.assertEqual(conexion.reversiones, 1)

    def test_error_al_incrementar_stock_revierte_devolucion(self):
        repo, conexion, _ = self.repositorio(
            [{"id_libro": 3, "estado": "Activo", "fecha_devolucion_real": None}], fallar_en=3
        )
        with self.assertRaises(RuntimeError):
            repo.devolver(4)
        self.assertEqual((conexion.confirmaciones, conexion.reversiones), (0, 1))


class RepoImportacion:
    def __init__(self):
        self.libros = {}
        self.socios = set()

    def importar_libro(self, datos):
        isbn, _, _, _, cantidad = datos
        if isbn in self.libros:
            self.libros[isbn] += cantidad
            return "actualizados"
        self.libros[isbn] = cantidad
        return "insertados"

    def importar_socio(self, datos):
        if datos[2] in self.socios:
            return "duplicados"
        self.socios.add(datos[2])
        return "insertados"

    def historico(self):
        return [dict(zip(CAMPOS_HISTORICO, (1, "123", "Título", "Ana Pérez", "ana@example.com",
                                            date(2026, 1, 1), date(2026, 1, 21), None, "Activo")))]


class ServiciosTest(unittest.TestCase):
    def test_validacion(self):
        with self.assertRaises(ValueError):
            validar_libro(dict(isbn="123", titulo="T", autor="A", anio_publicacion="2020", ejemplares_disponibles="-1"))
        with self.assertRaises(ValueError):
            validar_socio(dict(nombre="Ana", apellidos="P", email="incorrecto", telefono="", fecha_alta="2026-01-01"))

    def test_importar_reservas_y_prorrogas_informa_errores_por_fila(self):
        repo = Mock()
        repo.reservar_por_referencias.side_effect = [None, ReglaNegocio("reserva duplicada")]
        repo.prorrogar_por_referencias.side_effect = [None, ReglaNegocio("otro socio")]
        servicio = Servicio(repo)
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "datos.csv"
            ruta.write_text("isbn,email\nisbn-1,uno@example.com\nisbn-2,dos@example.com\n"
                            "isbn-3,email-invalido\n", encoding="utf-8")
            for tipo, exitos in (("reservas", "insertados"), ("prorrogas", "actualizados")):
                with self.subTest(tipo=tipo):
                    resumen = servicio.importar(ruta, tipo)
                    self.assertEqual(resumen[exitos], 1)
                    self.assertEqual(len(resumen["errores"]), 2)

    def test_importacion_referencias_rechaza_cabecera_y_filas_invalidas(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "datos.csv"
            for tipo in ("reservas", "prorrogas"):
                with self.subTest(tipo=tipo):
                    repo = Mock()
                    ruta.write_text("email,isbn\n", encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "Cabecera CSV incorrecta"):
                        Servicio(repo).importar(ruta, tipo)
                    ruta.write_text("isbn,email\n,uno@example.com\nisbn-1,uno@example.com,extra\n", encoding="utf-8")
                    resultado = Servicio(repo).importar(ruta, tipo)
                    self.assertEqual(len(resultado["errores"]), 2)
                    self.assertEqual(resultado["insertados"] + resultado["actualizados"], 0)
                    repo.reservar_por_referencias.assert_not_called()
                    repo.prorrogar_por_referencias.assert_not_called()

    def test_csv_ficticios_referencian_ejemplos_existentes(self):
        carpeta = Path(__file__).resolve().parent.parent / "imports"
        with (carpeta / "prueba_libros.csv").open(encoding="utf-8", newline="") as archivo:
            isbn = {fila["isbn"] for fila in csv.DictReader(archivo)}
        with (carpeta / "prueba_socios.csv").open(encoding="utf-8", newline="") as archivo:
            emails = {fila["email"] for fila in csv.DictReader(archivo)}
        for tipo in ("reservas", "prorrogas"):
            repo = Mock()
            ruta = carpeta / f"prueba_{tipo}.csv"
            resumen = Servicio(repo).importar(ruta, tipo)
            self.assertEqual(len(resumen["errores"]), 0)
            self.assertEqual(resumen["insertados" if tipo == "reservas" else "actualizados"], 5)
            with ruta.open(encoding="utf-8", newline="") as archivo:
                filas = list(csv.DictReader(archivo))
            self.assertTrue(all(fila["isbn"] in isbn and fila["email"] in emails for fila in filas))

    def test_importar_resumen_y_formato(self):
        repo = RepoImportacion()
        servicio = Servicio(repo)
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "libros.csv"
            ruta.write_text("isbn,titulo,autor,anio_publicacion,ejemplares\n"
                            "123,T,A,2020,2\n123,T,A,2020,3\n456,T,A,2020,-1\n", encoding="utf-8")
            resumen = servicio.importar(ruta, "libros")
            self.assertEqual((resumen["insertados"], resumen["actualizados"], len(resumen["errores"])), (1, 1, 1))
            self.assertEqual(repo.libros["123"], 5)
            ruta.write_text("cabecera,incorrecta\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                servicio.importar(ruta, "libros")

    def test_importar_socios_duplicados_y_error_csv(self):
        repo = RepoImportacion()
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "socios.csv"
            ruta.write_text('nombre,apellidos,email,telefono\nAna,P,ana@example.com,123\n'
                            'Ana,P,ana@example.com,123\n"sin cerrar', encoding="utf-8")
            resumen = Servicio(repo).importar(ruta, "socios")
            self.assertEqual((resumen["insertados"], resumen["duplicados"], len(resumen["errores"])), (1, 1, 1))

    def test_exportar_formatos_y_fechas(self):
        servicio = Servicio(RepoImportacion())
        with tempfile.TemporaryDirectory() as carpeta:
            csv_path = Path(carpeta) / "salida.csv"
            json_path = Path(carpeta) / "salida.json"
            self.assertEqual(servicio.exportar(csv_path, "csv"), 1)
            servicio.exportar(json_path, "json")
            with csv_path.open(encoding="utf-8-sig", newline="") as archivo:
                fila = next(csv.DictReader(archivo))
            self.assertEqual(tuple(fila), CAMPOS_HISTORICO)
            self.assertEqual(fila["fecha_prestamo"], "2026-01-01")
            contenido = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(contenido[0]["fecha_devolucion_real"], None)
            self.assertEqual(contenido[0]["titulo"], "Título")


if __name__ == "__main__":
    unittest.main()
