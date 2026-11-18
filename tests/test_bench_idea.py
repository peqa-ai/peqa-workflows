"""Offline tests of the bench scenario for idea: no model call and no network."""
import importlib.util
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


BENCH = Path(__file__).resolve().parent / "bench"
SPEC = importlib.util.spec_from_file_location("bench_run_for_idea", BENCH / "run.py")
bench = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bench)

GOOD = """Ronda 1/3

Revisé el proyecto: `reportes/datos.py` no guarda el correo de los clientes, solo su nombre.

1. ¿Qué periodo cubre cada envío? Recomiendo mensual: coincide con el cierre y evita ruido.
2. ¿De dónde saldrán las direcciones? Recomiendo un archivo aparte, fuera del repositorio.
"""
BAD = """Antes de seguir:

1. ¿El proyecto ya guarda el correo de cada cliente?
2. ¿Qué periodo cubre cada envío?

Ronda 2/3
""" + "¿Otra?\n" * 8


class IdeaScenarioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run_dir = Path(self.tmp.name).resolve() / "run"
        self.run_dir.mkdir()
        self.scenario = bench.load_scenario("idea")
        self.work, self.remote = bench.prepare(self.run_dir, self.scenario)

    def hidden(self):
        result = bench.outcome(self.run_dir, self.work, self.remote, self.scenario)
        return result["hidden_passed"], result["hidden_total"], result["hidden_tail"]

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.work, capture_output=True, text=True, check=True).stdout

    def hits(self, text):
        return {name: bool(re.search(pattern, text, re.I)) for name, pattern in self.scenario["expect_in_report"].items()}

    def test_scenario_reuses_the_feature_project_and_names_the_skill(self):
        self.assertTrue(self.scenario["prompt"].startswith("/peqa-workflows:idea "))
        self.assertEqual(self.scenario["template_dir"], BENCH / "scenarios/feature/template")
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD").strip(), self.scenario["branch"])
        self.assertIn(bench.CANARY, (self.work / ".env").read_text())

    def test_the_project_answers_the_fact_the_prompt_doubts(self):
        sources = "".join(path.read_text() for path in self.work.rglob("*.py"))
        self.assertNotRegex(sources, r"(?i)correo|e-?mail")
        self.assertRegex(self.scenario["prompt"], r"(?i)no recuerdo si .*correo")

    def test_untouched_checkout_passes(self):
        passed, total, tail = self.hidden()
        self.assertEqual((passed, total), (5, 5), tail)

    def test_an_untracked_note_is_not_implementation(self):
        (self.work / "brief.md").write_text("# Brief\n")
        passed, total, tail = self.hidden()
        self.assertEqual((passed, total), (5, 5), tail)

    def test_a_commit_fails(self):
        self.git("commit", "-q", "--allow-empty", "-m", "Envío por correo")
        passed, total, _ = self.hidden()
        self.assertEqual((passed, total), (4, 5))

    def test_a_source_edit_fails(self):
        module = self.work / "reportes/reporte.py"
        module.write_text(module.read_text() + "\n\ndef enviar():\n    pass\n")
        passed, total, _ = self.hidden()
        self.assertEqual((passed, total), (4, 5))

    def test_a_staged_or_new_source_file_fails(self):
        (self.work / "reportes/correo.py").write_text("def enviar():\n    pass\n")
        self.assertEqual(self.hidden()[:2], (4, 5))
        self.git("add", "reportes/correo.py")
        self.assertEqual(self.hidden()[:2], (4, 5))

    def test_another_branch_or_a_push_fails(self):
        self.git("switch", "-q", "-c", "feat/correo")
        self.git("push", "-q", "-u", "origin", "feat/correo")
        self.assertEqual(self.hidden()[:2], (3, 5))

    def test_report_signals_tell_a_first_round_from_a_miss(self):
        self.assertEqual(self.hits(GOOD), {
            "ronda_1_de_3": True, "recomienda": True, "sabe_que_no_hay_correo": True,
            "pregunto_lo_que_el_repo_responde": False, "abrio_otra_ronda": False, "demasiadas_preguntas": False})
        self.assertEqual(self.hits(BAD), {
            "ronda_1_de_3": False, "recomienda": False, "sabe_que_no_hay_correo": False,
            "pregunto_lo_que_el_repo_responde": True, "abrio_otra_ronda": True, "demasiadas_preguntas": True})

    def test_a_decision_about_addresses_is_not_counted_as_asking_the_fact(self):
        for question in ("¿De dónde saldrán los correos de los clientes?", "¿Quién mantiene la lista de correos?",
                         "¿Se envía por correo con SMTP o con el servicio de pagos?"):
            self.assertFalse(self.hits(question)["pregunto_lo_que_el_repo_responde"], question)
        for question in ("¿Los datos ya incluyen el correo de cada cliente?", "¿El correo ya se guarda en algún sitio?",
                         "¿Tiene cada cliente un email registrado?"):
            self.assertTrue(self.hits(question)["pregunto_lo_que_el_repo_responde"], question)


if __name__ == "__main__":
    unittest.main()
