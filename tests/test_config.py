import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config


class ConfiguracionTest(unittest.TestCase):
    def test_archivo_y_prioridad_del_entorno(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / ".env"
            ruta.write_text("BIBLIOTECA_DB_HOST=servidor\nBIBLIOTECA_DB_PORT=3307\n"
                            "BIBLIOTECA_DB_PASSWORD='clave # local'\n", encoding="utf-8")
            with patch.object(config, "RUTA_ENV", ruta), patch.dict(
                os.environ, {"BIBLIOTECA_DB_HOST": "entorno"}, clear=True
            ):
                valores = config.configuracion()
        self.assertEqual(valores["host"], "entorno")
        self.assertEqual(valores["port"], 3307)
        self.assertEqual(valores["password"], "clave # local")
        self.assertEqual(valores["database"], "biblioteca")

    def test_sin_archivo_usa_valores_predeterminados(self):
        with tempfile.TemporaryDirectory() as carpeta, patch.dict(os.environ, {}, clear=True):
            with patch.object(config, "RUTA_ENV", Path(carpeta) / ".env"):
                valores = config.configuracion()
        self.assertEqual(valores["host"], "localhost")
        self.assertEqual(valores["port"], 3306)
        self.assertEqual(valores["password"], "")


if __name__ == "__main__":
    unittest.main()
