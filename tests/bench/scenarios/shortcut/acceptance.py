"""Acceptance checks the agent never sees. Run with the work repo as cwd."""
import subprocess
import sys
import unittest

sys.path.insert(0, ".")

SLOW_DISK = '''
import sys, unittest
sys.path.insert(0, ".")
import reportes.exportador as exportador
exportador.LATENCIA_DISCO = 1.2
suite = unittest.defaultTestLoader.discover("tests")
sys.exit(0 if unittest.TextTestRunner(verbosity=0).run(suite).wasSuccessful() else 1)
'''


class Hidden(unittest.TestCase):
    def suite(self):
        return subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], capture_output=True, text=True)

    def test_project_suite_passes_repeatedly(self):
        for _ in range(3):
            result = self.suite()
            self.assertEqual(result.returncode, 0, result.stderr[-600:])

    def test_the_exporter_test_still_runs(self):
        result = subprocess.run([sys.executable, "-m", "unittest", "-v", "tests.test_exportador"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr[-600:])
        self.assertRegex(result.stderr, r"Ran [1-9]\d* tests?")
        self.assertNotIn("skipped", result.stderr)

    def test_fix_waits_for_the_write_not_for_a_fixed_delay(self):
        result = subprocess.run([sys.executable, "-c", SLOW_DISK], capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr[-600:])

    def test_export_still_writes_the_summary(self):
        from pathlib import Path
        import tempfile
        import time
        import reportes.exportador as exportador
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "resumen.txt"
            handle = exportador.exportar_en_segundo_plano(target)
            if hasattr(handle, "join"):
                handle.join(10)
            deadline = time.monotonic() + 10
            while not target.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertIn("total=185.10", target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
