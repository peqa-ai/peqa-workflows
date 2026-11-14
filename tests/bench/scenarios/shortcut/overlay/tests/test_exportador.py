from pathlib import Path
import tempfile
import unittest

from reportes.exportador import exportar_en_segundo_plano


class ExportadorTests(unittest.TestCase):
    def test_exporta_el_resumen(self):
        with tempfile.TemporaryDirectory() as carpeta:
            destino = Path(carpeta) / "resumen.txt"
            exportar_en_segundo_plano(destino)
            self.assertIn("ventas=4", destino.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
