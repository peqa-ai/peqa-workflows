import unittest

from reportes.reporte import generar_reporte, total_general


class ReporteTests(unittest.TestCase):
    def test_una_fila_por_venta(self):
        self.assertEqual(len(generar_reporte()), 4)

    def test_total_por_fila(self):
        filas = generar_reporte([{"fecha": "2026-01-01", "cliente": "c", "producto": "p", "unidades": 3, "precio": 1.5}])
        self.assertEqual(filas[0]["total"], 4.5)

    def test_total_general(self):
        self.assertEqual(total_general([{"total": 1.25}, {"total": 2.5}]), 3.75)


if __name__ == "__main__":
    unittest.main()
