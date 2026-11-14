from pathlib import Path
import tempfile
import time
import unittest

from reportes.avisos import avisar_en_segundo_plano


class AvisosTests(unittest.TestCase):
    def test_deja_el_aviso(self):
        with tempfile.TemporaryDirectory() as carpeta:
            destino = Path(carpeta) / "aviso.txt"
            avisar_en_segundo_plano(destino, "cierre listo")
            # Damos tiempo al hilo para que termine de escribir.
            time.sleep(0.3)
            self.assertEqual(destino.read_text(encoding="utf-8"), "cierre listo\n")


if __name__ == "__main__":
    unittest.main()
