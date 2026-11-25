"""Validaciones, importación CSV y exportación del histórico."""

import csv
import json
import re
from datetime import date, datetime

from mysql.connector import Error

from database import ReglaNegocio


CAMPOS_HISTORICO = (
    "id_prestamo", "isbn", "titulo", "socio_nombre_completo", "email",
    "fecha_prestamo", "fecha_devolucion_prevista", "fecha_devolucion_real", "estado",
)


def texto(valor, campo):
    valor = (valor or "").strip()
    if not valor:
        raise ValueError(f"El campo {campo} es obligatorio.")
    return valor


def entero(valor, campo, minimo):
    try:
        numero = int(valor)
    except (ValueError, TypeError) as error:
        raise ValueError(f"{campo} debe ser un número entero.") from error
    if numero < minimo:
        raise ValueError(f"{campo} debe ser mayor o igual que {minimo}.")
    return numero


def validar_libro(datos):
    return (
        texto(datos["isbn"], "ISBN"), texto(datos["titulo"], "título"),
        texto(datos["autor"], "autor"), entero(datos["anio_publicacion"], "Año", 1),
        entero(datos["ejemplares_disponibles"], "Ejemplares", 0),
    )


def validar_email(valor):
    email = texto(valor, "email")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("Introduzca un email válido.")
    return email


def validar_socio(datos, incluir_fecha=True):
    email = validar_email(datos["email"])
    valores = (
        texto(datos["nombre"], "nombre"), texto(datos["apellidos"], "apellidos"),
        email, (datos["telefono"] or "").strip(),
    )
    if incluir_fecha:
        try:
            fecha = date.fromisoformat(datos["fecha_alta"].strip())
        except ValueError as error:
            raise ValueError("La fecha de alta debe tener formato AAAA-MM-DD.") from error
        valores += (fecha,)
    return valores


class Servicio:
    def __init__(self, repositorio):
        self.repo = repositorio

    def importar(self, ruta, tipo):
        if tipo == "libros":
            campos = ("isbn", "titulo", "autor", "anio_publicacion", "ejemplares")
        elif tipo == "socios":
            campos = ("nombre", "apellidos", "email", "telefono")
        elif tipo in ("reservas", "prorrogas"):
            campos = ("isbn", "email")
        else:
            raise ValueError("Tipo de importación no válido.")
        resultado = {"insertados": 0, "actualizados": 0, "duplicados": 0, "errores": []}
        with open(ruta, encoding="utf-8-sig", newline="") as archivo:
            lector = csv.DictReader(archivo, strict=True)
            if lector.fieldnames is None or tuple(lector.fieldnames) != campos:
                raise ValueError("Cabecera CSV incorrecta. Se esperaba: " + ",".join(campos))
            while True:
                try:
                    fila = next(lector)
                except StopIteration:
                    break
                except (csv.Error, UnicodeError) as error:
                    resultado["errores"].append(f"Error de lectura cerca de la línea {lector.line_num}: {error}")
                    break
                try:
                    if None in fila or any(valor is None for valor in fila.values()):
                        raise ValueError("Número de columnas incorrecto.")
                    if tipo == "libros":
                        datos = dict(fila)
                        datos["ejemplares_disponibles"] = datos.pop("ejemplares")
                        categoria = self.repo.importar_libro(validar_libro(datos))
                    elif tipo == "socios":
                        categoria = self.repo.importar_socio(validar_socio(fila, False))
                    else:
                        isbn, email = texto(fila["isbn"], "ISBN"), validar_email(fila["email"])
                        if tipo == "reservas":
                            self.repo.reservar_por_referencias(isbn, email)
                            categoria = "insertados"
                        else:
                            self.repo.prorrogar_por_referencias(isbn, email)
                            categoria = "actualizados"
                    resultado[categoria] += 1
                except (ValueError, Error) as error:
                    resultado["errores"].append(f"Línea {lector.line_num}: {error}")
        return resultado

    def exportar(self, ruta, formato):
        if formato not in ("csv", "json"):
            raise ValueError("Formato de exportación no válido.")
        filas = self.repo.historico()
        serializadas = [
            {campo: valor.isoformat() if isinstance(valor, (date, datetime)) else valor
             for campo, valor in fila.items()}
            for fila in filas
        ]
        with open(ruta, "w", encoding="utf-8-sig" if formato == "csv" else "utf-8", newline="") as archivo:
            if formato == "csv":
                escritor = csv.DictWriter(archivo, fieldnames=CAMPOS_HISTORICO)
                escritor.writeheader()
                escritor.writerows(serializadas)
            else:
                json.dump(serializadas, archivo, ensure_ascii=False, indent=2)
        return len(filas)
