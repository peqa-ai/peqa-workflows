"""Offline tests of the triggering evals: no model call and no network."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parent / "evals" / "triggering"
SPEC = importlib.util.spec_from_file_location("trigger_eval", HERE / "trigger_eval.py")
trigger = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trigger)

SKILLS = trigger.all_skills()
SETS = trigger.load_sets()
PLUGIN_DIR = "/tmp/out/plugins/actual"


def tool(name, data, parent=None):
    return json.dumps({"type": "assistant", "parent_tool_use_id": parent,
                       "message": {"content": [{"type": "tool_use", "name": name, "input": data}]}})


def ended(cost=0.12, error=False):
    return json.dumps({"type": "result", "subtype": "success", "is_error": error, "total_cost_usd": cost})


class FakeProcess:
    """Stands in for a session: yields a prepared stream and records whether it was stopped."""
    started = []

    def __init__(self, command, lines, **options):
        self.command, self.options, self.stdout, self.terminated = command, options, iter(lines), False
        FakeProcess.started.append(self)

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0


class QuerySetTests(unittest.TestCase):
    def test_shipped_sets_are_valid_balanced_and_bilingual(self):
        self.assertEqual(sorted(SETS), ["dirige", "idea", "lenguaje-claro-formal-es", "memoria-extraer", "memoria-guardar"])
        self.assertEqual(trigger.validate(SETS, SKILLS), [])
        for skill, queries in SETS.items():
            hits = [query for query in queries if query["should_trigger"]]
            self.assertGreaterEqual(len(queries), 18, skill)
            self.assertLessEqual(abs(len(hits) * 2 - len(queries)), 2, skill)
            spanish = sum(query["lang"] == "es" for query in queries)
            self.assertGreater(spanish, len(queries) - spanish, skill)
            self.assertGreaterEqual(len(queries) - spanish, 4, skill)

    def test_negatives_are_near_misses_among_the_sibling_skills(self):
        for skill, queries in SETS.items():
            expected = [query["expected"] for query in queries if not query["should_trigger"]]
            self.assertTrue(set(filter(None, expected)) <= set(SKILLS) - {skill}, skill)
            self.assertIn(None, expected, f"{skill}: needs a near miss where no skill should load")
            self.assertGreaterEqual(len(set(filter(None, expected))), 1, skill)
        siblings = {query["expected"] for skill in ("dirige", "idea") for query in SETS[skill] if not query["should_trigger"]}
        self.assertTrue({"revisa", "ui-design", "memoria-guardar", "memoria-extraer"} <= siblings)
        self.assertIn("idea", {query["expected"] for query in SETS["dirige"] if not query["should_trigger"]})
        self.assertIn("dirige", {query["expected"] for query in SETS["idea"] if not query["should_trigger"]})

    def test_both_memory_sets_carry_the_remember_and_recall_pair(self):
        def count(skill, hit, pattern, expected=None):
            return sum(1 for query in SETS[skill] if query["should_trigger"] is hit and re.search(pattern, query["query"], re.I)
                       and (hit or query["expected"] == expected))
        for store, ask in ((r"\brecuerda que\b", r"¿recuerdas\b"), (r"\bremember (that|this)\b", r"\bdo you remember\b")):
            self.assertGreaterEqual(count("memoria-guardar", True, store), 1, store)
            self.assertGreaterEqual(count("memoria-guardar", False, ask, "memoria-extraer"), 1, ask)
            self.assertGreaterEqual(count("memoria-extraer", True, ask), 1, ask)
            self.assertGreaterEqual(count("memoria-extraer", False, store, "memoria-guardar"), 1, store)
        phrasings = [query for skill in ("memoria-guardar", "memoria-extraer") for query in SETS[skill]
                     if re.search(r"recuerda que|¿recuerdas|recuérdame|te acuerdas|remember|recall", query["query"], re.I)]
        self.assertGreaterEqual(len(phrasings), 12)

    def test_validation_reports_broken_sets(self):
        queries = [dict(query) for query in SETS["dirige"]]
        queries[0]["id"] = queries[1]["id"]
        queries[-1]["expected"] = "no-existe"
        queries[-2]["expected"] = "dirige"
        queries[2]["query"] = "Revisa esto."
        queries[3]["query"] = "/peqa-workflows:dirige " + queries[3]["query"]
        problems = "\n".join(trigger.validate({"dirige": queries}, SKILLS))
        for text in ("id is repeated", "another real skill or null", "cannot be the skill under test", "at least 120",
                     "invokes a skill explicitly"):
            self.assertIn(text, problems)
        lopsided = [query for query in SETS["idea"] if query["should_trigger"] or query["lang"] == "en"]
        problems = "\n".join(trigger.validate({"idea": lopsided}, SKILLS))
        self.assertIn("unbalanced", problems)
        self.assertIn("at least 16", problems)
        self.assertIn("is not a skill", "\n".join(trigger.validate({"otro": SETS["idea"]}, SKILLS)))


class SplitTests(unittest.TestCase):
    def test_split_is_deterministic_stratified_and_sixty_forty(self):
        for skill, queries in SETS.items():
            assignment = trigger.split_of(queries)
            self.assertEqual(assignment, trigger.split_of(list(reversed(queries))), "order of the file must not matter")
            holdout = [query for query in queries if assignment[query["id"]] == "holdout"]
            self.assertAlmostEqual(len(holdout) / len(queries), 0.4, delta=0.1, msg=skill)
            for hit in (True, False):
                for lang in ("es", "en"):
                    stratum = [query for query in queries if (query["should_trigger"], query["lang"]) == (hit, lang)]
                    held = [query for query in stratum if query in holdout]
                    self.assertTrue(held, f"{skill}: holdout lacks {hit}/{lang}")
                    self.assertAlmostEqual(len(held) / len(stratum), 0.4, delta=0.2, msg=skill)
        self.assertNotEqual(trigger.split_of(SETS["dirige"]), trigger.split_of(SETS["dirige"], seed="otra"))

    def test_adding_a_query_moves_at_most_the_one_at_the_cut_of_its_stratum(self):
        queries = SETS["memoria-guardar"]
        before = trigger.split_of(queries)
        for number in range(25):
            extra = {"id": f"nueva-{number}", "should_trigger": True, "lang": "es", "query": "x"}
            after = trigger.split_of(queries + [extra])
            moved = [query for query in queries if before[query["id"]] != after[query["id"]]]
            self.assertLessEqual(len(moved), 1)
            self.assertTrue(all((query["should_trigger"], query["lang"]) == (True, "es") for query in moved))

    def test_split_command_prints_the_assignment(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            trigger.main(["split", "--skill", "idea", "--json"])
        self.assertEqual(json.loads(output.getvalue()), {"idea": trigger.split_of(SETS["idea"])})


class DetectionTests(unittest.TestCase):
    def loaded(self, *lines, **limits):
        return trigger.detect(lines, SKILLS, PLUGIN_DIR, **limits)

    def test_skill_tool_with_and_without_the_plugin_prefix(self):
        self.assertEqual(self.loaded(tool("Skill", {"skill": "peqa-workflows:dirige"}))["loaded"], ["dirige"])
        self.assertEqual(self.loaded(tool("Skill", {"skill": "memoria-guardar"}))["loaded"], ["memoria-guardar"])
        other = self.loaded(tool("Skill", {"skill": "superpowers:brainstorming"}))
        self.assertEqual((other["loaded"], other["other_tools"]), ([], 1))

    def test_opening_the_skill_file_with_read_or_a_shell_command(self):
        self.assertEqual(self.loaded(tool("Read", {"file_path": f"{PLUGIN_DIR}/skills/idea/SKILL.md"}))["loaded"], ["idea"])
        self.assertEqual(self.loaded(tool("Bash", {"command": f"cat '{PLUGIN_DIR}/skills/revisa/SKILL.md' | head -80"}))["loaded"],
                         ["revisa"])
        self.assertEqual(self.loaded(tool("Bash", {"command": "sed -n 1,40p \"$CLAUDE_PLUGIN_ROOT/skills/memoria-extraer/SKILL.md\""}))
                         ["loaded"], ["memoria-extraer"])
        for miss in (tool("Read", {"file_path": f"{PLUGIN_DIR}/skills/idea/references/questions.md"}),
                     tool("Read", {"file_path": "/home/dev/.claude/plugins/cache/peqa/skills/idea/SKILL.md"}),
                     tool("Bash", {"command": "cat otros-skills/idea/SKILL.md"}),
                     tool("Read", {"file_path": f"{PLUGIN_DIR}/README.md"})):
            self.assertEqual(self.loaded(miss)["loaded"], [], miss)

    def test_subagents_are_ignored_and_order_is_kept(self):
        outcome = self.loaded(
            tool("Bash", {"command": "ls"}),
            tool("Skill", {"skill": "revisa"}, parent="toolu_1"),
            tool("Skill", {"skill": "peqa-workflows:idea"}),
            tool("Read", {"file_path": f"{PLUGIN_DIR}/skills/dirige/SKILL.md"}),
            tool("Skill", {"skill": "idea"}),
            "not json", json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "content": "skills/revisa/SKILL.md"}]}}),
            ended(0.3))
        self.assertEqual(outcome["loaded"], ["idea", "dirige"])
        self.assertEqual((outcome["other_tools"], outcome["stop"], outcome["cost_usd"]), (1, "ended", 0.3))

    def test_the_outcome_is_known_at_the_first_skill_or_after_a_few_other_tools(self):
        lines = [tool("Bash", {"command": "ls"}), tool("Skill", {"skill": "idea"}), tool("Skill", {"skill": "dirige"})]
        first = self.loaded(*lines, max_tools=3, max_skills=1)
        self.assertEqual((first["loaded"], first["stop"], first["cost_usd"]), (["idea"], "skill", None))
        none = self.loaded(*[tool("Read", {"file_path": f"reportes/{name}.py"}) for name in "abcd"], max_tools=3, max_skills=1)
        self.assertEqual((none["loaded"], none["stop"], none["other_tools"]), ([], "tools", 3))
        self.assertEqual(self.loaded(ended(error=True))["error"], True)


class DescriptionTests(unittest.TestCase):
    def test_a_variant_rewrites_only_the_description_of_the_exported_copy(self):
        original = (trigger.REPO / "skills/dirige/SKILL.md").read_text(encoding="utf-8")
        text = 'Use when: a change has several parts, "coordinated" through agents # not a comment'
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "plugin"
            trigger.export_variant(".", copy, {"dirige": text, "idea": "Use when a plan needs challenging"})
            changed = (copy / "skills/dirige/SKILL.md").read_text(encoding="utf-8")
            self.assertEqual(trigger.description_of(copy / "skills/dirige/SKILL.md"), text)
            self.assertEqual(trigger.description_of(copy / "skills/idea/SKILL.md"), "Use when a plan needs challenging")
            self.assertEqual([line for line in changed.split("\n") if not line.startswith("description:")],
                             [line for line in original.split("\n") if not line.startswith("description:")])
            self.assertEqual((copy / "skills/revisa/SKILL.md").read_text(encoding="utf-8"),
                             (trigger.REPO / "skills/revisa/SKILL.md").read_text(encoding="utf-8"))
        self.assertEqual((trigger.REPO / "skills/dirige/SKILL.md").read_text(encoding="utf-8"), original)

    def test_variant_files_are_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "variants.json"
            path.write_text(json.dumps({"corta": {"dirige": "Use when coordinating agents"}}))
            self.assertEqual(list(trigger.load_variants(path, SKILLS)), ["actual", "corta"])
            for broken in ({"actual": {"dirige": "x"}}, {"corta": {"no-existe": "x"}}, {"corta": {"dirige": "dos\nlíneas"}}):
                path.write_text(json.dumps(broken))
                with self.assertRaises(SystemExit):
                    trigger.load_variants(path, SKILLS)


def row(query, rep, loaded, variant="actual", model="m"):
    return {"id": query["id"], "skill": query["skill"], "rep": rep, "variant": variant, "model": model, "loaded": loaded,
            "valid": True, "cost_usd": None}


class ScoreTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = Path(tmp.name).resolve()

    def save(self, rows):
        for item in rows:
            path = self.out / "results" / item["model"] / item["variant"] / item["skill"] / f"{item['id']}-r{item['rep']}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(item))

    def command(self, *argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            trigger.main([*argv, "--out", str(self.out)])
        return output.getvalue()

    def test_metrics_of_a_small_set(self):
        queries = [{"id": "h1", "skill": "idea", "should_trigger": True}, {"id": "h2", "skill": "idea", "should_trigger": True},
                   {"id": "n1", "skill": "idea", "should_trigger": False, "expected": "dirige"},
                   {"id": "n2", "skill": "idea", "should_trigger": False, "expected": None}]
        fired = {"h1": [["idea"], ["idea"], []],                      # 2/3: passes
                 "h2": [[], ["revisa"], ["idea"]],                    # 1/3: fails, a miss
                 "n1": [["idea"], ["idea", "dirige"], ["dirige"]],    # 2/3: fails, a false trigger
                 "n2": [[], ["idea"], []]}                            # 1/3: passes
        rows = [row(query, rep + 1, fired[query["id"]][rep]) for query in queries for rep in range(3)]
        got = trigger.measure(queries, rows + [dict(rows[0], id="unknown")])
        self.assertEqual((got["tp"], got["fn"], got["fp"], got["tn"], got["queries"], got["reps"]), (1, 1, 1, 1, 4, 3))
        self.assertEqual((got["precision"], got["recall"], got["accuracy"]), (0.5, 0.5, 0.5))
        self.assertEqual(got["rep_accuracy"], [0.5, 0.25, 0.75])
        self.assertEqual((got["rep_mean"], got["rep_stdev"]), (0.5, 0.25))
        self.assertEqual(got["expected_loaded"], [2, 3])
        failing = {item["id"]: item for item in got["failing"]}
        self.assertEqual(sorted(failing), ["h2", "n1"])
        self.assertEqual(failing["h2"]["loaded"], {"ninguno": 1, "revisa": 1, "idea": 1})
        self.assertEqual((failing["n1"]["loaded"], failing["n1"]["expected"]), ({"idea": 2, "dirige": 1}, "dirige"))
        even = trigger.measure(queries[2:3], [row(queries[2], 1, ["idea"]), row(queries[2], 2, [])])
        self.assertEqual((even["fp"], even["tn"]), (1, 0), "an exact half does not pass")

    def test_score_reports_splits_failing_queries_and_ignores_invalid_sessions(self):
        queries = SETS["dirige"]
        assignment = trigger.split_of(queries)
        wrong = next(query for query in queries if not query["should_trigger"] and query["expected"])
        rows = [row(query, rep, ["dirige"] if query["should_trigger"] or query is wrong else
                    [query["expected"]] if query.get("expected") else []) for query in queries for rep in (1, 2, 3)]
        self.save(rows + [dict(row(queries[0], 4, []), valid=False)])
        data = {item["split"]: item for item in json.loads(self.command("score", "--json"))}
        self.assertEqual((data["all"]["queries"], data["all"]["fp"], data["all"]["recall"], data["all"]["reps"]), (20, 1, 1.0, 3))
        self.assertEqual(data["train"]["queries"] + data["holdout"]["queries"], 20)
        self.assertEqual([item["id"] for item in data[assignment[wrong["id"]]]["failing"]], [wrong["id"]])
        text = self.command("score")
        self.assertIn("| m | dirige | actual | holdout |", text)
        self.assertIn(f"| {wrong['id']} | no | 3/3 | {wrong['expected']} | dirige ×3 |", text)
        self.assertIn("Sesiones válidas: 60. Inválidas: 1.", text)

    def variant_rows(self, variant, wrong_train, wrong_holdout):
        """Sessions that are right everywhere except on the given number of queries per repetition and split."""
        queries, rows = SETS["dirige"], []
        assignment = trigger.split_of(queries)
        for rep, (in_train, in_holdout) in enumerate(zip(wrong_train, wrong_holdout), 1):
            left = {"train": in_train, "holdout": in_holdout}
            for query in queries:
                right = left[assignment[query["id"]]] <= 0
                left[assignment[query["id"]]] -= 1
                rows.append(row(query, rep, ["dirige"] if query["should_trigger"] == right else [], variant))
        return rows

    def test_select_chooses_by_holdout_even_when_train_disagrees(self):
        self.save(self.variant_rows("actual", (0, 0, 0), (2, 2, 3)) + self.variant_rows("nueva", (6, 6, 6), (0, 0, 0)))
        decision = json.loads(self.command("select", "--json"))[0]
        self.assertEqual((decision["skill"], decision["selected"], decision["verdicts"]), ("dirige", "nueva", {"nueva": "gana"}))
        text = self.command("select")
        self.assertIn("solo el holdout", text)
        self.assertIn("una desviación estándar", text)
        self.assertRegex(text, r"\| m \| dirige \| nueva \| 1\.00 ± 0\.00 \| 3 \| \+0\.29 \| 0\.50 ± 0\.00 \| gana \| sí \|")
        self.assertRegex(text, r"\| m \| dirige \| actual \| 0\.71 ± 0\.07 \| 3 \| – \| 1\.00 ± 0\.00 \| referencia \|  \|")

    def test_select_reports_a_tie_within_one_standard_deviation_and_keeps_actual(self):
        self.save(self.variant_rows("actual", (6, 6, 6), (0, 1, 2)) + self.variant_rows("nueva", (0, 0, 0), (0, 0, 1)))
        decision = json.loads(self.command("select", "--json"))[0]
        self.assertEqual((decision["selected"], decision["verdicts"]), ("actual", {"nueva": "empate"}))
        self.assertIn("| empate |", self.command("select"))

    def test_choose_needs_three_repetitions_and_a_real_margin(self):
        def cell(mean, deviation, reps=3):
            return {"rep_mean": mean, "rep_stdev": deviation, "reps": reps}
        self.assertEqual(trigger.choose({"actual": cell(0.7, 0.05), "a": cell(0.8, 0.02), "b": cell(0.9, 0.04)}),
                         ("b", {"a": "gana", "b": "gana"}))
        self.assertEqual(trigger.choose({"actual": cell(0.7, 0.1), "a": cell(0.8, 0.02)}), ("actual", {"a": "empate"}))
        self.assertEqual(trigger.choose({"actual": cell(0.7, 0.02), "a": cell(0.8, 0.1)}), ("actual", {"a": "empate"}))
        self.assertEqual(trigger.choose({"actual": cell(0.9, 0.02), "a": cell(0.5, 0.02)}), ("actual", {"a": "peor"}))
        winner, verdicts = trigger.choose({"actual": cell(0.5, 0.0, 2), "a": cell(1.0, 0.0, 2)})
        self.assertEqual(winner, "actual")
        self.assertIn("faltan repeticiones", verdicts["a"])
        self.assertEqual(trigger.choose({"actual": cell(None, 0.0, 0), "a": cell(1.0, 0.0)})[0], "actual")


class RunTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = Path(tmp.name).resolve() / "out"
        FakeProcess.started = []
        self.streams = {}
        patcher = mock.patch.object(trigger, "launch", side_effect=self.launch)
        self.launched = patcher.start()
        self.addCleanup(patcher.stop)

    def launch(self, command, **options):
        query = command[command.index("-p") + 1]
        return FakeProcess(command, self.streams.get(query, [ended() + "\n"]), **options)

    def command(self, *argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            trigger.main(["run", "--model", "claude-test", "--out", str(self.out), *argv])
        return output.getvalue()

    def test_run_refuses_without_the_exact_number_of_sessions(self):
        for confirm in ((), ("--confirm-sessions", "23"), ("--confirm-sessions", "25")):
            with self.assertRaises(SystemExit) as refused, contextlib.redirect_stdout(io.StringIO()):
                trigger.main(["run", "--model", "claude-test", "--out", str(self.out), "--skill", "idea", "--split", "holdout",
                              *confirm])
            self.assertIn("--confirm-sessions 24", str(refused.exception))
        self.launched.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_run_refuses_an_output_folder_inside_a_repository(self):
        for extra in (("--confirm-sessions", "24"), ("--dry-run",)):
            with self.assertRaises(SystemExit) as refused:
                trigger.main(["run", "--model", "claude-test", "--out", str(trigger.REPO / "tmp-out"), "--skill", "idea", *extra])
            self.assertIn("outside any Git repository", str(refused.exception))
        self.launched.assert_not_called()

    def test_dry_run_prints_the_plan_and_the_isolated_commands(self):
        variants = self.out.parent / "variants.json"
        variants.write_text(json.dumps({"corta": {"idea": "Use when a plan needs challenging"}}))
        text = self.command("--skill", "idea", "--skill", "dirige", "--split", "holdout", "--reps", "2", "--dry-run",
                            "--descriptions", str(variants))
        lines = text.strip().split("\n")
        self.assertIn("Planned sessions: 48 (0 already saved, 48 to launch)", lines[0])  # 8 × 2 reps × (2 sets + idea again)
        self.assertEqual(len(lines), 49)
        self.assertEqual(sum(str(self.out / "plugins" / "corta") in line for line in lines[1:]), 16)
        for line in lines[1:]:
            self.assertTrue(line.startswith("claude -p "), line)
            self.assertIn("--model claude-test --plugin-dir " + str(self.out / "plugins"), line)
            self.assertTrue(line.endswith("--output-format stream-json --verbose --setting-sources project,local "
                                          "--strict-mcp-config --no-session-persistence --disallowedTools SendMessage "
                                          "--max-budget-usd 0.5"), line)
        self.launched.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_run_stops_each_session_early_saves_it_and_resumes(self):
        holdout = [query for query in SETS["idea"] if trigger.split_of(SETS["idea"])[query["id"]] == "holdout"]
        hit, miss, broken = holdout[0], holdout[1], holdout[2]
        later = tool("Bash", {"command": "echo too late"}) + "\n"
        self.streams[hit["query"]] = [tool("Read", {"file_path": "README.md"}) + "\n",
                                      tool("Skill", {"skill": "peqa-workflows:idea"}) + "\n", later, ended() + "\n"]
        self.streams[miss["query"]] = [tool("Bash", {"command": f"ls {number}"}) + "\n" for number in range(5)]
        self.streams[broken["query"]] = [ended(error=True) + "\n"]
        text = self.command("--skill", "idea", "--split", "holdout", "--reps", "1", "--confirm-sessions", "8", "--jobs", "3")
        self.assertEqual(len(FakeProcess.started), 8)
        folder = self.out / "results" / "claude-test" / "actual" / "idea"
        saved = {path.stem: json.loads(path.read_text()) for path in folder.glob("*.json")}
        self.assertEqual(len(saved), 8)
        first = saved[f"{hit['id']}-r1"]
        self.assertEqual((first["loaded"], first["triggered"], first["stop"], first["valid"], first["cost_usd"], first["rep"]),
                         (["idea"], True, "skill", True, None, 1))
        self.assertEqual((first["variant"], first["skill"], first["model"]), ("actual", "idea", "claude-test"))
        self.assertEqual(first["description"], trigger.description_of(trigger.REPO / "skills/idea/SKILL.md"))
        self.assertEqual(len(Path(first["stream"]).read_text().splitlines()), 2, "nothing is read after the skill loads")
        second = saved[f"{miss['id']}-r1"]
        self.assertEqual((second["loaded"], second["stop"], second["other_tools"], second["valid"]), ([], "tools", 3, True))
        self.assertEqual((saved[f"{broken['id']}-r1"]["valid"], saved[f"{broken['id']}-r1"]["stop"]), (False, "ended"))
        quiet = saved[f"{holdout[3]['id']}-r1"]
        self.assertEqual((quiet["stop"], quiet["cost_usd"], quiet["valid"], quiet["triggered"]), ("ended", 0.12, True, False))
        self.assertTrue(all(process.terminated for process in FakeProcess.started))
        self.assertEqual(text.count('"stop"'), 8)
        process = FakeProcess.started[0]
        self.assertEqual(Path(process.command[process.command.index("--plugin-dir") + 1]), self.out / "plugins" / "actual")
        self.assertTrue(trigger.bench().outside_repositories(Path(process.options["cwd"]).parent))
        self.assertFalse(Path(process.options["cwd"]).exists(), "the throwaway project is removed")
        self.assertFalse([key for key in process.options["env"] if key.startswith("CLAUDE")])
        self.assertTrue((self.out / "plugins/actual/skills/idea/SKILL.md").is_file())

        again = self.command("--skill", "idea", "--split", "holdout", "--reps", "1", "--confirm-sessions", "1")
        self.assertIn("(7 already saved, 1 to launch)", again)
        self.assertEqual(len(FakeProcess.started), 9, "only the invalid session runs again")
        self.assertIn("(7 already saved, 1 to launch)", self.command("--skill", "idea", "--split", "holdout", "--reps", "1", "--dry-run"))


if __name__ == "__main__":
    unittest.main()
