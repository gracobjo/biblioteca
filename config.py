"""Configuración de MySQL mediante .env y variables de entorno."""

import os
from pathlib import Path

from dotenv import dotenv_values


RUTA_ENV = Path(__file__).resolve().with_name(".env")


def configuracion():
    valores = {
        "BIBLIOTECA_DB_HOST": "localhost",
        "BIBLIOTECA_DB_PORT": "3306",
        "BIBLIOTECA_DB_USER": "root",
        "BIBLIOTECA_DB_PASSWORD": "",
        "BIBLIOTECA_DB_NAME": "biblioteca",
    }
    valores.update({clave: valor for clave, valor in dotenv_values(RUTA_ENV, interpolate=False).items()
                    if valor is not None})
    valores.update(os.environ)
    return {
        "host": valores["BIBLIOTECA_DB_HOST"],
        "port": int(valores["BIBLIOTECA_DB_PORT"]),
        "user": valores["BIBLIOTECA_DB_USER"],
        "password": valores["BIBLIOTECA_DB_PASSWORD"],
        "database": valores["BIBLIOTECA_DB_NAME"],
        "charset": "utf8mb4",
        "connection_timeout": 10,
        "read_timeout": 30,
        "write_timeout": 30,
    }
