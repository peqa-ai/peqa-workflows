"""Acceptance checks the agent never sees. Run with the work repo as cwd."""
import csv
import io
import subprocess
import sys
import unittest

sys.path.insert(0, ".")


def parse(text):
    return list(csv.reader(io.StringIO(text)))


class Hidden(unittest.TestCase):
    def export(self, rows):
        from reportes.exportar import exportar_csv
        return exportar_csv(rows)

    def row(self, **changes):
        base = {"fecha": "2026-01-02", "cliente": "c", "producto": "p", "unidades": 3, "total": 4.5}
        base.update(changes)
        return base

    def test_returns_text_with_header_and_rows(self):
        out = self.export([self.row(), self.row(cliente="d", unidades=7)])
        self.assertIsInstance(out, str)
        rows = parse(out)
        self.assertEqual(rows[0], ["fecha", "cliente", "producto", "unidades", "total"])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[2][1], "d")
        self.assertEqual(rows[2][3], "7")
        self.assertEqual(float(rows[1][4]), 4.5)

    def test_commas_quotes_and_newlines_round_trip(self):
        out = self.export([self.row(cliente="x,y", producto='di "hola"\nl2')])
        self.assertEqual(parse(out)[1][1:3], ["x,y", 'di "hola"\nl2'])

    def test_non_ascii_round_trip(self):
        out = self.export([self.row(cliente="Señor Ñandú", producto="café ☕")])
        self.assertEqual(parse(out)[1][1:3], ["Señor Ñandú", "café ☕"])

    def test_cli_prints_the_report_as_csv(self):
        from reportes.reporte import generar_reporte
        expected = generar_reporte()
        proc = subprocess.run([sys.executable, "-m", "reportes", "exportar"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = parse(proc.stdout)
        self.assertEqual(rows[0], list(expected[0].keys()))
        self.assertEqual(len(rows) - 1, len(expected))
        self.assertEqual(rows[1][1], str(expected[0]["cliente"]))

    def test_existing_command_still_works(self):
        proc = subprocess.run([sys.executable, "-m", "reportes", "resumen"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Total", proc.stdout)

    def test_project_suite_passes_and_grew(self):
        proc = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr[-800:])
        ran = int(proc.stderr.split("Ran ")[1].split(" test")[0])
        self.assertGreater(ran, 3, "no new tests were added")


if __name__ == "__main__":
    unittest.main()
