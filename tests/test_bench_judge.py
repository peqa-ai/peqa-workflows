"""Offline tests of the blind judge: a fake judge callable, no model call and no network."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


BENCH = Path(__file__).resolve().parent / "bench"
SPEC = importlib.util.spec_from_file_location("bench_judge", BENCH / "judge.py")
judge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(judge)

ARMS = ["zafiro", "topacio"]
MODEL = "claude-opus-5-5"
REVISIONS = {"zafiro": "abc1234", "topacio": "def5678"}


class JudgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name).resolve() / "runs"

    def session(self, label, rep, passed=6, text=None, scenario="demo"):
        run_dir = self.out / scenario / f"{label}-{MODEL}-{rep}"
        run_dir.mkdir(parents=True)
        text = text or (f"Informe {label} {rep}: plugin en {run_dir}/plugin, revisión {REVISIONS[label]}, "
                        f"modelo {MODEL}, revisado con Opus 5.5. Marca-{'uno' if label == ARMS[0] else 'dos'}.")
        metrics = {"scenario": scenario, "label": label, "model": MODEL, "subagent_model": None, "rep": rep,
                   "plugin_ref": f"origin/{label}", "plugin_revision": REVISIONS[label], "final_text": text,
                   "outcome": {"hidden_passed": passed, "hidden_total": 6}}
        (run_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
        return run_dir

    def cell(self, reps, **kwargs):
        for rep in reps:
            for label in ARMS:
                self.session(label, rep, **kwargs)

    def plan(self, **kwargs):
        return judge.plan(judge.load_sessions(self.out, "demo"), ARMS, "Rúbrica de prueba.", "Encargo.", **kwargs)

    def main(self, *args, fake=None):
        with contextlib.redirect_stdout(io.StringIO()):
            return judge.main(["--out", str(self.out), "--scenario", "demo", "--arms", *ARMS, *args], judge=fake)

    def prefers(self, marker):
        """A fake judge that always picks the candidate whose report carries the marker."""
        def fake(prompt):
            first = prompt.index('<candidate id="A">') < prompt.index(marker) < prompt.index('<candidate id="B">')
            return json.dumps({"winner": "A" if first else "B", "reason": "prueba"})
        return fake

    def test_prompt_hides_labels_revisions_models_and_run_paths(self):
        self.cell([1, 2, 3])
        planned = self.plan(seed=7, both_orders=True)
        self.assertEqual(len(planned["prompts"]), 6)
        for name, prompt in planned["prompts"].items():
            for leak in (*ARMS, *REVISIONS.values(), MODEL, "opus", "Opus 5.5", str(self.out), "origin/"):
                self.assertNotIn(leak.lower(), prompt.lower(), name)
            self.assertIn("Marca-uno", prompt)
            self.assertIn("Marca-dos", prompt)
            self.assertIn("Rúbrica de prueba.", prompt)
            self.assertNotIn("pair-", prompt)

    def test_work_diff_reaches_the_prompt_without_the_label(self):
        self.cell([1])
        for label in ARMS:
            work = self.out / "demo" / f"{label}-{MODEL}-1" / "work"
            work.mkdir()
            git = ("git", "-c", "user.name=dev", "-c", "user.email=dev@example.invalid", "-c", "init.defaultBranch=main")
            (work / "a.py").write_text("x = 1\n")
            for command in (("init", "-q"), ("add", "-A"), ("commit", "-qm", "inicio"), ("switch", "-qc", "trabajo")):
                subprocess.run([*git, *command], cwd=work, check=True, capture_output=True)
            (work / "a.py").write_text(f"x = 2  # hecho por {label} en {work}\n")
            (work / "nuevo.py").write_text("y = 3\n")
        prompt = self.plan(seed=1)["prompts"]["pair-001-order-1"]
        self.assertIn("+x = 2  # hecho por [hidden] en [run]/work", prompt)
        self.assertIn("+y = 3", prompt)
        for label in ARMS:
            self.assertNotIn(label, prompt)

    def test_assignment_is_seeded_per_pair_and_kept_in_the_key_only(self):
        self.cell(range(1, 13))
        one, again, other = self.plan(seed=3), self.plan(seed=3), self.plan(seed=4)
        self.assertEqual(one, again)
        firsts = lambda planned: [pair["orders"]["1"]["A"] for pair in planned["key"]["pairs"].values()]
        self.assertEqual(set(firsts(one)), set(ARMS), "both arms take position A across twelve pairs")
        self.assertNotEqual(firsts(one), firsts(other))
        self.session(ARMS[0], 99)
        self.session(ARMS[1], 99)
        grown = self.plan(seed=3)["key"]["pairs"]
        by_session = lambda pairs: {pair["session_key"]: pair["orders"]["1"] for pair in pairs.values()}
        self.assertLessEqual(by_session(one["key"]["pairs"]).items(), by_session(grown).items())
        for name, pair in one["key"]["pairs"].items():
            prompt = one["prompts"][f"{name}-order-1"]
            marker = "Marca-uno" if pair["orders"]["1"]["A"] == ARMS[0] else "Marca-dos"
            self.assertLess(prompt.index(marker), prompt.index('<candidate id="B">'))

    def test_key_file_is_separate_from_the_prompts(self):
        self.cell([1, 2])
        status = self.main("--dry-run", "--both-orders")
        folder = Path(status["folder"])
        self.assertEqual(sorted(path.name for path in (folder / "prompts").iterdir()),
                         [f"pair-00{pair}-order-{order}.txt" for pair in (1, 2) for order in (1, 2)])
        key = json.loads((folder / "key.json").read_text())
        self.assertEqual(set(key["pairs"]["pair-001"]["orders"]["1"].values()), set(ARMS))
        self.assertEqual(key["pairs"]["pair-001"]["orders"]["1"]["A"], key["pairs"]["pair-001"]["orders"]["2"]["B"])
        self.assertFalse((folder / "verdicts.json").exists())
        self.assertEqual(status["calls"], 4)

    def test_pair_failing_acceptance_is_not_judged_unless_allowed(self):
        self.cell([1])
        self.session(ARMS[0], 2)
        self.session(ARMS[1], 2, passed=5)
        self.session(ARMS[0], 3)
        planned = self.plan(seed=0)
        self.assertEqual(sorted(planned["prompts"]), ["pair-001-order-1"])
        self.assertEqual(planned["not_applicable"], ["pair-002"])
        self.assertEqual(planned["key"]["pairs"]["pair-002"]["failed_acceptance"], [ARMS[1]])
        self.assertEqual(planned["unpaired"], [f"{ARMS[0]}-{MODEL}-3"])
        summary = self.main("--confirm-calls", "1", fake=self.prefers("Marca-uno"))
        self.assertEqual((summary["judged_pairs"], summary["not_applicable_pairs"]), (1, 1))
        self.assertEqual(summary["pairs"]["pair-002"]["result"], "not_applicable")
        self.assertEqual(len(self.plan(seed=0, allow_failing=True)["prompts"]), 2)
        self.assertFalse(judge.passes({"outcome": {"hidden_passed": 0, "hidden_total": 0}}))
        self.assertFalse(judge.passes({}))

    def test_calls_need_the_exact_confirmation(self):
        self.cell([1, 2])
        calls = []
        fake = lambda prompt: calls.append(prompt) or '{"winner": "tie"}'
        for args in ((), ("--confirm-calls", "1"), ("--confirm-calls", "4")):
            with self.assertRaises(SystemExit) as stop:
                self.main(*args, fake=fake)
            self.assertIn("--confirm-calls 2", str(stop.exception))
        with self.assertRaises(SystemExit) as stop:
            self.main("--both-orders", "--confirm-calls", "2", fake=fake)
        self.assertIn("4 judge calls", str(stop.exception))
        self.assertEqual(calls, [])
        self.main("--dry-run", fake=fake)
        self.assertEqual(calls, [])
        self.main("--confirm-calls", "2", fake=fake)
        self.assertEqual(len(calls), 2)

    def test_both_orders_disagreement_is_a_tie(self):
        self.cell([1, 2])
        always_a = lambda prompt: '{"winner": "A", "reason": "posición"}'
        summary = self.main("--both-orders", "--confirm-calls", "4", fake=always_a)
        self.assertEqual((summary["wins"], summary["ties"], summary["inconsistent_pairs"]),
                         ({ARMS[0]: 0, ARMS[1]: 0}, 2, 2))
        self.assertIsNone(summary["preferred"])
        steady = self.main("--both-orders", "--confirm-calls", "4", fake=self.prefers("Marca-dos"))
        self.assertEqual((steady["wins"], steady["ties"], steady["inconsistent_pairs"]),
                         ({ARMS[0]: 0, ARMS[1]: 2}, 0, 0))

    def test_no_arm_is_preferred_inside_the_noise_of_the_pair_count(self):
        self.cell(range(1, 6))
        five = self.main("--both-orders", "--confirm-calls", "10", fake=self.prefers("Marca-uno"))
        self.assertEqual((five["wins"][ARMS[0]], five["preferred"], five["sign_test_p"]), (5, None, 0.0625))
        self.cell([6])
        six = self.main("--both-orders", "--confirm-calls", "12", fake=self.prefers("Marca-uno"))
        self.assertEqual((six["wins"][ARMS[0]], six["preferred"], six["sign_test_p"]), (6, ARMS[0], 0.0312))
        self.assertIn("not a measured difference", six["note"])
        saved = json.loads((self.out / "_judge/demo" / f"{ARMS[0]}-vs-{ARMS[1]}-seed-0" / "summary.json").read_text())
        self.assertEqual(saved["preferred"], ARMS[0])

    def test_decision_rule_counts_ties_against_and_unusable_answers_as_ties(self):
        self.assertEqual(judge.sign_test_p(0, 0), 1.0)
        self.assertGreater(judge.sign_test_p(7, 1), judge.ALPHA)
        self.assertLessEqual(judge.sign_test_p(8, 1), judge.ALPHA)
        key = {"arms": ARMS, "pairs": {f"pair-{n:03d}": {"status": "judged", "failed_acceptance": [],
                                                       "orders": {"1": {"A": ARMS[0], "B": ARMS[1]}}} for n in range(1, 15)}}
        verdicts = {f"pair-{n:03d}-order-1": "A" for n in range(1, 7)}
        verdicts.update({f"pair-{n:03d}-order-1": "tie" for n in range(7, 14)})
        verdicts["pair-014-order-1"] = None
        summary = judge.aggregate(key, verdicts)
        self.assertEqual((summary["wins"][ARMS[0]], summary["ties"], summary["judged_pairs"]), (6, 8, 14))
        self.assertIsNone(summary["preferred"], "six wins among fourteen pairs is not a majority")
        self.assertEqual(summary["pairs"]["pair-014"]["picks"], ["invalid"])

    def test_verdict_parsing(self):
        self.assertEqual(judge.parse_verdict('Creo que {"winner": "b", "reason": "x"}'), "B")
        self.assertEqual(judge.parse_verdict('{"winner": "TIE"}'), "tie")
        self.assertIsNone(judge.parse_verdict('{"winner": "C"}'))
        self.assertIsNone(judge.parse_verdict("A es mejor"))
        self.assertIsNone(judge.parse_verdict(""))


if __name__ == "__main__":
    unittest.main()
