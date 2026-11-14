import unittest

from reportes.reporte import generar_reporte, importe_general


class ReporteTests(unittest.TestCase):
    def test_una_fila_por_venta(self):
        self.assertEqual(len(generar_reporte()), 4)

    def test_importe_por_fila(self):
        filas = generar_reporte([{"fecha": "2026-01-01", "cliente": "c", "producto": "p", "unidades": 3, "precio": 1.5}])
        self.assertEqual(filas[0]["importe"], 4.5)

    def test_importe_general(self):
        self.assertEqual(importe_general([{"importe": 1.25}, {"importe": 2.5}]), 3.75)


if __name__ == "__main__":
    unittest.main()
