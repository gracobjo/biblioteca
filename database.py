"""Acceso parametrizado a MySQL y operaciones transaccionales."""

from contextlib import contextmanager
from datetime import date, timedelta

import mysql.connector

from config import configuracion


class ReglaNegocio(ValueError):
    """Una operación no cumple las reglas de la biblioteca."""


class Repositorio:
    def __init__(self, conectar=None):
        self.conectar = conectar or (lambda: mysql.connector.connect(**configuracion()))

    @contextmanager
    def sesion(self):
        conexion = self.conectar()
        try:
            cursor = conexion.cursor(dictionary=True)
            try:
                yield conexion, cursor
                conexion.commit()
            except BaseException:
                conexion.rollback()
                raise
            finally:
                cursor.close()
        finally:
            conexion.close()

    def consultar(self, sql, parametros=()):
        with self.sesion() as (_, cursor):
            cursor.execute(sql, parametros)
            return cursor.fetchall()

    def ejecutar(self, sql, parametros=()):
        with self.sesion() as (_, cursor):
            cursor.execute(sql, parametros)
            return cursor.rowcount

    def libros(self, busqueda="", limite=15, desplazamiento=0):
        patron = f"%{busqueda}%"
        return self.consultar(
            "SELECT id_libro, isbn, titulo, autor, anio_publicacion, ejemplares_disponibles "
            "FROM libros WHERE titulo LIKE %s OR autor LIKE %s OR isbn LIKE %s "
            "ORDER BY id_libro LIMIT %s OFFSET %s",
            (patron, patron, patron, limite, desplazamiento),
        )

    def socios(self, busqueda="", limite=15, desplazamiento=0):
        patron = f"%{busqueda}%"
        return self.consultar(
            "SELECT id_socio, nombre, apellidos, email, telefono, fecha_alta FROM socios "
            "WHERE nombre LIKE %s OR apellidos LIKE %s OR email LIKE %s "
            "ORDER BY id_socio LIMIT %s OFFSET %s",
            (patron, patron, patron, limite, desplazamiento),
        )

    def contar_socios(self):
        return self.consultar("SELECT COUNT(*) AS total FROM socios")[0]["total"]

    def guardar_libro(self, datos, identificador=None):
        if identificador is None:
            return self.ejecutar(
                "INSERT INTO libros (isbn, titulo, autor, anio_publicacion, ejemplares_disponibles) "
                "VALUES (%s, %s, %s, %s, %s)", datos,
            )
        return self.ejecutar(
            "UPDATE libros SET isbn=%s, titulo=%s, autor=%s, anio_publicacion=%s, "
            "ejemplares_disponibles=%s WHERE id_libro=%s", (*datos, identificador),
        )

    def guardar_socio(self, datos, identificador=None):
        if identificador is None:
            return self.ejecutar(
                "INSERT INTO socios (nombre, apellidos, email, telefono, fecha_alta) "
                "VALUES (%s, %s, %s, %s, %s)", datos,
            )
        return self.ejecutar(
            "UPDATE socios SET nombre=%s, apellidos=%s, email=%s, telefono=%s, fecha_alta=%s "
            "WHERE id_socio=%s", (*datos, identificador),
        )

    def eliminar_libro(self, identificador):
        return self.ejecutar("DELETE FROM libros WHERE id_libro=%s", (identificador,))

    def eliminar_socio(self, identificador):
        return self.ejecutar("DELETE FROM socios WHERE id_socio=%s", (identificador,))

    def opciones_libros(self):
        return self.consultar(
            "SELECT id_libro, isbn, titulo, ejemplares_disponibles FROM libros "
            "WHERE ejemplares_disponibles > %s ORDER BY titulo, id_libro", (0,),
        )

    def opciones_libros_reserva(self):
        return self.consultar(
            "SELECT id_libro, isbn, titulo, ejemplares_disponibles FROM libros ORDER BY titulo, id_libro"
        )

    def opciones_socios(self):
        return self.consultar(
            "SELECT id_socio, nombre, apellidos, email FROM socios ORDER BY apellidos, nombre, id_socio"
        )

    def prestamos(self, filtro="Todos"):
        condiciones = {
            "Todos": "1=1",
            "Solo Activos": "(p.estado = %s OR p.fecha_devolucion_real IS NULL)",
            "Devueltos": "(p.estado <> %s AND p.fecha_devolucion_real IS NOT NULL)",
        }
        if filtro not in condiciones:
            raise ValueError("Filtro de préstamos no válido.")
        parametros = () if filtro == "Todos" else ("Activo",)
        return self.consultar(
            "SELECT p.id_prestamo, l.titulo, CONCAT(s.nombre, ' ', s.apellidos) AS socio, "
            "p.fecha_prestamo, p.fecha_devolucion_prevista, p.fecha_devolucion_real, p.estado "
            "FROM prestamos p JOIN libros l ON l.id_libro=p.id_libro "
            "JOIN socios s ON s.id_socio=p.id_socio WHERE " + condiciones[filtro] +
            " ORDER BY p.id_prestamo ASC", parametros,
        )

    def prestar(self, id_socio, id_libro, hoy=None):
        hoy = hoy or date.today()
        with self.sesion() as (_, cursor):
            # La fila del socio serializa los préstamos concurrentes de ese socio.
            cursor.execute("SELECT id_socio FROM socios WHERE id_socio=%s FOR UPDATE", (id_socio,))
            if cursor.fetchone() is None:
                raise ReglaNegocio("El socio seleccionado ya no existe.")
            cursor.execute(
                "SELECT COUNT(*) AS cantidad FROM prestamos WHERE id_socio=%s "
                "AND (estado=%s OR fecha_devolucion_real IS NULL)", (id_socio, "Activo"),
            )
            if cursor.fetchone()["cantidad"] >= 2:
                raise ReglaNegocio("El socio ya tiene el máximo de 2 libros simultáneos.")
            cursor.execute(
                "SELECT ejemplares_disponibles FROM libros WHERE id_libro=%s FOR UPDATE", (id_libro,),
            )
            libro = cursor.fetchone()
            if libro is None or libro["ejemplares_disponibles"] <= 0:
                raise ReglaNegocio("El libro ya no está disponible.")
            cursor.execute(
                "INSERT INTO prestamos (id_libro, id_socio, fecha_prestamo, "
                "fecha_devolucion_prevista, fecha_devolucion_real, estado) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (id_libro, id_socio, hoy, hoy + timedelta(days=20), None, "Activo"),
            )
            cursor.execute(
                "UPDATE libros SET ejemplares_disponibles=ejemplares_disponibles-1 WHERE id_libro=%s",
                (id_libro,),
            )

    def devolver(self, id_prestamo, hoy=None):
        hoy = hoy or date.today()
        with self.sesion() as (_, cursor):
            cursor.execute(
                "SELECT id_libro, estado, fecha_devolucion_real FROM prestamos "
                "WHERE id_prestamo=%s FOR UPDATE", (id_prestamo,),
            )
            prestamo = cursor.fetchone()
            if prestamo is None:
                raise ReglaNegocio("El préstamo seleccionado ya no existe.")
            if prestamo["fecha_devolucion_real"] is not None:
                raise ReglaNegocio("El préstamo ya tiene una fecha de devolución; revise su estado.")
            cursor.execute(
                "UPDATE prestamos SET fecha_devolucion_real=%s, estado=%s WHERE id_prestamo=%s",
                (hoy, "Devuelto", id_prestamo),
            )
            cursor.execute(
                "UPDATE libros SET ejemplares_disponibles=ejemplares_disponibles+1 WHERE id_libro=%s",
                (prestamo["id_libro"],),
            )
            if cursor.rowcount != 1:
                raise ReglaNegocio("El libro del préstamo ya no existe.")

    def reservas(self):
        return self.consultar(
            "SELECT r.id_reserva, l.titulo, CONCAT(s.nombre, ' ', s.apellidos) AS socio, "
            "r.fecha_reserva FROM reservas r JOIN libros l ON l.id_libro=r.id_libro "
            "JOIN socios s ON s.id_socio=r.id_socio ORDER BY r.id_reserva"
        )

    def reservar(self, id_socio, id_libro):
        with self.sesion() as (_, cursor):
            self._reservar(cursor, id_socio, id_libro)

    def _reservar(self, cursor, id_socio, id_libro):
        cursor.execute("SELECT id_libro FROM libros WHERE id_libro=%s FOR UPDATE", (id_libro,))
        if cursor.fetchone() is None:
            raise ReglaNegocio("El libro seleccionado ya no existe.")
        cursor.execute("SELECT id_socio FROM socios WHERE id_socio=%s", (id_socio,))
        if cursor.fetchone() is None:
            raise ReglaNegocio("El socio seleccionado ya no existe.")
        cursor.execute(
            "SELECT id_reserva FROM reservas WHERE id_libro=%s AND id_socio=%s FOR UPDATE",
            (id_libro, id_socio),
        )
        if cursor.fetchone() is not None:
            raise ReglaNegocio("El socio ya tiene una reserva para este libro.")
        cursor.execute("INSERT INTO reservas (id_libro, id_socio) VALUES (%s, %s)", (id_libro, id_socio))

    def cancelar_reserva(self, id_reserva):
        with self.sesion() as (_, cursor):
            cursor.execute("SELECT id_libro FROM reservas WHERE id_reserva=%s", (id_reserva,))
            reserva = cursor.fetchone()
            if reserva is None:
                raise ReglaNegocio("La reserva seleccionada ya no existe.")
            cursor.execute("SELECT id_libro FROM libros WHERE id_libro=%s FOR UPDATE", (reserva["id_libro"],))
            if cursor.fetchone() is None:
                raise ReglaNegocio("El libro de la reserva ya no existe.")
            cursor.execute("DELETE FROM reservas WHERE id_reserva=%s", (id_reserva,))
            if cursor.rowcount != 1:
                raise ReglaNegocio("La reserva seleccionada ya no existe.")

    def prorrogar(self, id_prestamo):
        with self.sesion() as (_, cursor):
            return self._prorrogar(cursor, id_prestamo)

    def _prorrogar(self, cursor, id_prestamo):
        cursor.execute(
            "SELECT id_libro, id_socio, fecha_devolucion_prevista, fecha_devolucion_real "
            "FROM prestamos WHERE id_prestamo=%s FOR UPDATE", (id_prestamo,),
        )
        prestamo = cursor.fetchone()
        if prestamo is None:
            raise ReglaNegocio("El préstamo seleccionado ya no existe.")
        if prestamo["fecha_devolucion_real"] is not None:
            raise ReglaNegocio(
                "Este préstamo ya tiene registrada la devolución y no se puede prorrogar. "
                "Para volver a prestar el libro, registre un nuevo préstamo si se cumplen las condiciones."
            )
        cursor.execute("SELECT id_prestamo FROM prorrogas WHERE id_prestamo=%s FOR UPDATE", (id_prestamo,))
        if cursor.fetchone() is not None:
            raise ReglaNegocio("Este préstamo ya ha sido prorrogado una vez.")
        cursor.execute("SELECT id_libro FROM libros WHERE id_libro=%s FOR UPDATE", (prestamo["id_libro"],))
        if cursor.fetchone() is None:
            raise ReglaNegocio("El libro del préstamo ya no existe.")
        cursor.execute(
            "SELECT id_reserva FROM reservas WHERE id_libro=%s AND id_socio<>%s LIMIT 1 FOR UPDATE",
            (prestamo["id_libro"], prestamo["id_socio"]),
        )
        if cursor.fetchone() is not None:
            raise ReglaNegocio("No se puede prorrogar: otro socio tiene reservado este libro.")
        anterior = prestamo["fecha_devolucion_prevista"]
        if anterior < date.today():
            raise ReglaNegocio("No se puede prorrogar: el plazo de devolución ya ha vencido.")
        nueva = anterior + timedelta(days=20)
        cursor.execute(
            "INSERT INTO prorrogas (id_prestamo, fecha_anterior, fecha_nueva) VALUES (%s, %s, %s)",
            (id_prestamo, anterior, nueva),
        )
        cursor.execute(
            "UPDATE prestamos SET fecha_devolucion_prevista=%s WHERE id_prestamo=%s",
            (nueva, id_prestamo),
        )
        return nueva

    def reservar_por_referencias(self, isbn, email):
        with self.sesion() as (_, cursor):
            cursor.execute(
                "SELECT l.id_libro, s.id_socio FROM libros l CROSS JOIN socios s "
                "WHERE l.isbn=%s AND s.email=%s LIMIT 2 FOR UPDATE", (isbn, email),
            )
            filas = cursor.fetchall()
            if not filas:
                raise ReglaNegocio("No existe el libro o el socio indicados por ISBN y email.")
            if len(filas) != 1:
                raise ReglaNegocio("El ISBN o el email identifican varios registros; resuelva los duplicados.")
            self._reservar(cursor, filas[0]["id_socio"], filas[0]["id_libro"])

    def prorrogar_por_referencias(self, isbn, email):
        with self.sesion() as (_, cursor):
            cursor.execute(
                "SELECT p.id_prestamo FROM prestamos p JOIN libros l ON l.id_libro=p.id_libro "
                "JOIN socios s ON s.id_socio=p.id_socio "
                "WHERE l.isbn=%s AND s.email=%s AND p.fecha_devolucion_real IS NULL "
                "ORDER BY p.id_prestamo LIMIT 2 FOR UPDATE", (isbn, email),
            )
            filas = cursor.fetchall()
            if not filas:
                raise ReglaNegocio("No existe un préstamo sin devolución para el ISBN y email indicados.")
            if len(filas) != 1:
                raise ReglaNegocio("Hay varios préstamos para este ISBN y email; prorrogue el deseado manualmente.")
            return self._prorrogar(cursor, filas[0]["id_prestamo"])

    def importar_libro(self, datos):
        isbn, titulo, autor, anio, cantidad = datos
        with self.sesion() as (_, cursor):
            cursor.execute("SELECT id_libro FROM libros WHERE isbn=%s FOR UPDATE", (isbn,))
            filas = cursor.fetchall()
            if len(filas) > 1:
                raise ReglaNegocio("Hay varios libros con este ISBN; resuelva el duplicado.")
            if filas:
                cursor.execute(
                    "UPDATE libros SET ejemplares_disponibles=ejemplares_disponibles+%s WHERE id_libro=%s",
                    (cantidad, filas[0]["id_libro"]),
                )
                return "actualizados"
            cursor.execute(
                "INSERT INTO libros (isbn, titulo, autor, anio_publicacion, ejemplares_disponibles) "
                "VALUES (%s, %s, %s, %s, %s)", (isbn, titulo, autor, anio, cantidad),
            )
            return "insertados"

    def importar_socio(self, datos):
        with self.sesion() as (_, cursor):
            cursor.execute("SELECT id_socio FROM socios WHERE email=%s FOR UPDATE", (datos[2],))
            if cursor.fetchall():
                return "duplicados"
            cursor.execute(
                "INSERT INTO socios (nombre, apellidos, email, telefono, fecha_alta) "
                "VALUES (%s, %s, %s, %s, CURDATE())", datos,
            )
            return "insertados"

    def historico(self):
        return self.consultar(
            "SELECT p.id_prestamo, l.isbn, l.titulo, "
            "CONCAT(s.nombre, ' ', s.apellidos) AS socio_nombre_completo, s.email, "
            "p.fecha_prestamo, p.fecha_devolucion_prevista, p.fecha_devolucion_real, p.estado "
            "FROM prestamos p JOIN libros l ON l.id_libro=p.id_libro "
            "JOIN socios s ON s.id_socio=p.id_socio ORDER BY p.id_prestamo"
        )
