import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app import Biblioteca
from database import ReglaNegocio
from mysql.connector import Error


class ResumenImportacionTest(unittest.TestCase):
    def test_libros_nuevos_no_se_describen_como_stock_actualizado(self):
        resultado = {"insertados": 20, "actualizados": 0, "duplicados": 0, "errores": []}
        ventana = SimpleNamespace(
            servicio=SimpleNamespace(importar=Mock(return_value=resultado)), actualizar=Mock()
        )
        with patch("app.opciones_directorio", return_value={}), \
             patch("app.filedialog.askopenfilename", return_value="libros.csv"), \
             patch("app.messagebox.showinfo") as mensaje:
            Biblioteca.importar.__wrapped__(ventana, "libros")
        self.assertIn("Libros nuevos insertados: 20", mensaje.call_args.args[1])
        self.assertIn("Libros existentes con stock actualizado: 0", mensaje.call_args.args[1])
        ventana.actualizar.assert_called_once()

    def test_socios_muestra_total_consultado(self):
        resultado = {"insertados": 20, "actualizados": 0, "duplicados": 2, "errores": []}
        ventana = SimpleNamespace(
            servicio=SimpleNamespace(importar=Mock(return_value=resultado)),
            repo=SimpleNamespace(contar_socios=Mock(return_value=122)), actualizar=Mock()
        )
        with patch("app.opciones_directorio", return_value={}), \
             patch("app.filedialog.askopenfilename", return_value="socios.csv"), \
             patch("app.messagebox.showinfo") as mensaje:
            Biblioteca.importar.__wrapped__(ventana, "socios")
        texto = mensaje.call_args.args[1]
        self.assertIn("Socios nuevos insertados: 20", texto)
        self.assertIn("Socios duplicados omitidos: 2", texto)
        self.assertIn("Total de socios en la base de datos: 122", texto)

    def test_error_al_contar_conserva_resumen_de_la_importacion(self):
        resultado = {"insertados": 20, "actualizados": 0, "duplicados": 0, "errores": []}
        ventana = SimpleNamespace(
            servicio=SimpleNamespace(importar=Mock(return_value=resultado)),
            repo=SimpleNamespace(contar_socios=Mock(side_effect=Error("conexión perdida"))),
            actualizar=Mock()
        )
        with patch("app.opciones_directorio", return_value={}), \
             patch("app.filedialog.askopenfilename", return_value="socios.csv"), \
             patch("app.messagebox.showwarning") as mensaje:
            Biblioteca.importar.__wrapped__(ventana, "socios")
        texto = mensaje.call_args.args[1]
        self.assertIn("Socios nuevos insertados: 20", texto)
        self.assertIn("No se pudo consultar el total de socios: conexión perdida", texto)
        ventana.actualizar.assert_called_once()

    def test_resumen_reservas_y_prorrogas(self):
        resultado = {"insertados": 5, "actualizados": 3, "duplicados": 0, "errores": []}
        ventana = SimpleNamespace(
            servicio=SimpleNamespace(importar=Mock(return_value=resultado)), actualizar=Mock()
        )
        for tipo, esperado in (("reservas", "Reservas registradas: 5"),
                               ("prorrogas", "Préstamos prorrogados: 3")):
            with self.subTest(tipo=tipo), patch("app.opciones_directorio", return_value={}), \
                 patch("app.filedialog.askopenfilename", return_value="datos.csv"), \
                 patch("app.messagebox.showinfo") as mensaje:
                Biblioteca.importar.__wrapped__(ventana, tipo)
            self.assertIn(esperado, mensaje.call_args.args[1])


class ImportacionDirectorioTest(unittest.TestCase):
    def test_importar_propone_directorio_y_respeta_archivo_elegido(self):
        resultado = {"insertados": 1, "actualizados": 0, "duplicados": 0, "errores": []}
        ventana = SimpleNamespace(
            servicio=SimpleNamespace(importar=Mock(return_value=resultado)), actualizar=Mock()
        )
        with TemporaryDirectory() as carpeta:
            directorio = Path(carpeta) / "imports"
            with patch("app.DIRECTORIO_IMPORTACIONES", directorio), \
                 patch("app.filedialog.askopenfilename", return_value="otro.csv") as dialogo, \
                 patch("app.messagebox.showinfo"):
                Biblioteca.importar.__wrapped__(ventana, "libros")
            self.assertTrue(directorio.is_dir())
            self.assertEqual(dialogo.call_args.kwargs["initialdir"], str(directorio))
            ventana.servicio.importar.assert_called_once_with("otro.csv", "libros")

    def test_directorio_inaccesible_avisa_y_permite_otra_ubicacion(self):
        resultado = {"insertados": 1, "actualizados": 0, "duplicados": 0, "errores": []}
        ventana = SimpleNamespace(
            servicio=SimpleNamespace(importar=Mock(return_value=resultado)), actualizar=Mock()
        )
        with TemporaryDirectory() as carpeta:
            directorio = Path(carpeta) / "imports"
            directorio.write_text("archivo existente", encoding="utf-8")
            with patch("app.DIRECTORIO_IMPORTACIONES", directorio), \
                 patch("app.filedialog.askopenfilename", return_value="alternativo.csv") as dialogo, \
                 patch("app.messagebox.showwarning") as aviso, patch("app.messagebox.showinfo"):
                Biblioteca.importar.__wrapped__(ventana, "libros")
            aviso.assert_called_once()
            self.assertNotIn("initialdir", dialogo.call_args.kwargs)
            ventana.servicio.importar.assert_called_once_with("alternativo.csv", "libros")


class ExportacionTest(unittest.TestCase):
    def test_nombre_propuesto_y_destino_elegido(self):
        ventana = SimpleNamespace(servicio=SimpleNamespace(exportar=Mock(return_value=4)))
        with TemporaryDirectory() as carpeta:
            directorio = Path(carpeta) / "exports"
            for formato in ("csv", "json"):
                with self.subTest(formato=formato), \
                     patch("app.DIRECTORIO_EXPORTACIONES", directorio), \
                     patch("app.datetime") as reloj, \
                     patch("app.filedialog.asksaveasfilename", return_value=f"destino.{formato}") as dialogo, \
                     patch("app.messagebox.showinfo"):
                    reloj.now.return_value = datetime(2026, 11, 25, 20, 1, 2)
                    Biblioteca.exportar.__wrapped__(ventana, formato)
                    self.assertTrue(directorio.is_dir())
                    self.assertEqual(dialogo.call_args.kwargs["initialdir"], str(directorio))
                    self.assertEqual(dialogo.call_args.kwargs["initialfile"],
                                     f"prestamos_2026-11-25_20-01-02.{formato}")
                    ventana.servicio.exportar.assert_called_with(f"destino.{formato}", formato)

    def test_cancelar_no_exporta(self):
        ventana = SimpleNamespace(servicio=SimpleNamespace(exportar=Mock()))
        with TemporaryDirectory() as carpeta:
            with patch("app.DIRECTORIO_EXPORTACIONES", Path(carpeta) / "exports"), \
                 patch("app.filedialog.asksaveasfilename", return_value=""):
                Biblioteca.exportar.__wrapped__(ventana, "csv")
        ventana.servicio.exportar.assert_not_called()

    def test_error_de_carpeta_permite_elegir_otro_destino(self):
        ventana = SimpleNamespace(servicio=SimpleNamespace(exportar=Mock(return_value=0)))
        with TemporaryDirectory() as carpeta:
            directorio = Path(carpeta) / "exports"
            directorio.write_text("archivo existente", encoding="utf-8")
            with patch("app.DIRECTORIO_EXPORTACIONES", directorio), \
                 patch("app.filedialog.asksaveasfilename", return_value="alternativo.csv") as dialogo, \
                 patch("app.messagebox.showwarning") as aviso, patch("app.messagebox.showinfo"):
                Biblioteca.exportar.__wrapped__(ventana, "csv")
            aviso.assert_called_once()
            self.assertNotIn("initialdir", dialogo.call_args.kwargs)
            ventana.servicio.exportar.assert_called_once_with("alternativo.csv", "csv")


class ReservasProrrogasTest(unittest.TestCase):
    def test_prorrogar_muestra_fecha_y_actualiza(self):
        tabla = Mock()
        tabla.selection.return_value = ("fila",)
        tabla.item.return_value = (7,)
        ventana = SimpleNamespace(
            tabla_prestamos=tabla, repo=SimpleNamespace(prorrogar=Mock(return_value=datetime(2027, 1, 9).date())),
            actualizar=Mock()
        )
        with patch("app.messagebox.showinfo") as mensaje:
            Biblioteca.prorrogar.__wrapped__(ventana)
        ventana.repo.prorrogar.assert_called_once_with(7)
        self.assertIn("2027-01-09", mensaje.call_args.args[1])
        ventana.actualizar.assert_called_once()

    def test_prorroga_vencida_muestra_error_sin_confirmacion(self):
        tabla = Mock()
        tabla.selection.return_value = ("fila",)
        tabla.item.return_value = (7,)
        ventana = SimpleNamespace(
            tabla_prestamos=tabla,
            repo=SimpleNamespace(prorrogar=Mock(side_effect=ReglaNegocio("El plazo de devolución ya ha vencido."))),
            actualizar=Mock()
        )
        with patch("app.messagebox.showerror") as error, patch("app.messagebox.showinfo") as exito:
            Biblioteca.prorrogar(ventana)
        self.assertIn("plazo de devolución ya ha vencido", error.call_args.args[1])
        exito.assert_not_called()
        ventana.actualizar.assert_not_called()

    def test_reservar_usa_selectores_independientes(self):
        ventana = SimpleNamespace(
            selector_socio_reserva=SimpleNamespace(current=lambda: 0),
            selector_libro_reserva=SimpleNamespace(current=lambda: 0),
            ids_socios_reserva=[2], ids_libros_reserva=[3],
            repo=SimpleNamespace(reservar=Mock()), actualizar=Mock()
        )
        with patch("app.messagebox.showinfo"):
            Biblioteca.reservar.__wrapped__(ventana)
        ventana.repo.reservar.assert_called_once_with(2, 3)
        ventana.actualizar.assert_called_once()

    def test_cancelar_reserva_respeta_confirmacion(self):
        tabla = Mock()
        tabla.selection.return_value = ("fila",)
        tabla.item.return_value = (4,)
        ventana = SimpleNamespace(
            tabla_reservas=tabla, repo=SimpleNamespace(cancelar_reserva=Mock()), actualizar=Mock()
        )
        with patch("app.messagebox.askyesno", return_value=False):
            Biblioteca.cancelar_reserva.__wrapped__(ventana)
        ventana.repo.cancelar_reserva.assert_not_called()
        with patch("app.messagebox.askyesno", return_value=True), patch("app.messagebox.showinfo"):
            Biblioteca.cancelar_reserva.__wrapped__(ventana)
        ventana.repo.cancelar_reserva.assert_called_once_with(4)
        ventana.actualizar.assert_called_once()


if __name__ == "__main__":
    unittest.main()
