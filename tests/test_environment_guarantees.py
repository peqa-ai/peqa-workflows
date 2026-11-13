"""Behavior tests with temporary checkouts and a scripted stand-in for gh."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/environment_guarantees.py"
PR = "https://github.com/acme/demo/pull/7"
FAKE_GH = """#!{python}
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_GH_LOG"], "a") as log:
    log.write(json.dumps(args) + "\\n")
answers = json.load(open(os.environ["FAKE_GH_ANSWERS"]))
for key, answer in answers.items():
    if key in " ".join(args):
        sys.stdout.write(answer.get("out", ""))
        sys.stderr.write(answer.get("err", ""))
        sys.exit(answer.get("code", 0))
sys.stderr.write("unexpected call\\n")
sys.exit(9)
"""
REPO = {"repo view": {"out": json.dumps({"nameWithOwner": "acme/demo", "defaultBranchRef": {"name": "main"}})}}
OPEN_BRANCH = {"out": json.dumps({"protected": False, "protection": {
    "enabled": False, "required_status_checks": {"checks": [], "contexts": [], "enforcement_level": "off"}}})}


class GuaranteeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.repo, self.home, self.bin = self.root / "repo", self.root / "home", self.root / "bin"
        for folder in (self.repo, self.home, self.bin):
            folder.mkdir()
        self.log = self.root / "gh.log"
        self.answers = self.root / "answers.json"
        self.answers.write_text("{}")

    def write(self, relative, content="", base=None):
        path = (base or self.repo) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content if isinstance(content, str) else json.dumps(content))
        return path

    def gh(self, answers):
        fake = self.bin / "gh"
        fake.write_text(FAKE_GH.format(python=sys.executable))
        fake.chmod(0o755)
        self.answers.write_text(json.dumps(answers))

    def run_cli(self, *args, repo=None):
        env = {"HOME": str(self.home), "PATH": str(self.bin), "FAKE_GH_LOG": str(self.log),
               "FAKE_GH_ANSWERS": str(self.answers)}
        proc = subprocess.run([sys.executable, str(SCRIPT), *args, "--repo", str(repo or self.repo)],
                              capture_output=True, text=True, timeout=30, env=env)
        return proc.returncode, proc.stdout, proc.stderr

    def check(self, *args):
        code, out, err = self.run_cli("check", *args)
        self.assertEqual((code, err), (0, ""))
        data = json.loads(out)
        return data, {item["id"]: item for item in data["checks"]}

    def calls(self):
        return [" ".join(json.loads(line)) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_without_secret_files_nothing_is_missing_and_gh_is_not_called(self):
        self.write(".env.example", "KEY=")
        data, checks = self.check()
        self.assertEqual(checks["secrets"]["status"], "not_applicable")
        self.assertEqual((data["missing"], data["not_verified"], self.calls()), ([], [], []))

    def test_secret_files_are_listed_by_name_and_never_opened(self):
        os.mkfifo(self.repo / ".env")  # Opening it for reading would block until the timeout.
        self.write(".env.staging", "TOKEN=do-not-print")
        self.write("config/.env.local", "TOKEN=do-not-print")
        self.write("node_modules/pkg/.env", "ignored")
        before = sorted(str(path) for path in self.repo.rglob("*"))
        code, out, _ = self.run_cli("check")
        data = json.loads(out)
        secrets = data["checks"][0]
        self.assertEqual(code, 0)
        self.assertEqual(secrets["files"], [".env", ".env.staging", "config/.env.local"])
        self.assertEqual(secrets["status"], "missing")
        self.assertEqual(secrets["proposal"]["add"], {
            "permissions": {"deny": ["Read(./.env)", "Read(./.env.*)", "Read(./config/.env.*)"]},
            "sandbox": {"enabled": True}})
        self.assertNotIn("do-not-print", out)
        self.assertEqual(before, sorted(str(path) for path in self.repo.rglob("*")))
        self.assertFalse((self.home / ".claude").exists())

    def test_deny_rules_and_sandbox_from_different_scopes_cover_the_files(self):
        self.write(".env")
        self.write(".env.staging")
        self.write(".claude/settings.json", {"permissions": {"deny": ["Read(./.env)", "Read(./.env.*)"]}})
        self.write(".claude/settings.json", {"sandbox": {"enabled": True}}, base=self.home)
        data, checks = self.check()
        self.assertEqual(checks["secrets"]["status"], "ok")
        self.assertEqual(checks["secrets"]["settings"], {"local": "absent", "project": "read", "user": "read"})
        self.assertEqual(data["missing"], [])

    def test_anchored_rule_does_not_cover_a_nested_file_but_a_bare_name_does(self):
        self.write(".env")
        self.write("api/.env")
        self.write(".claude/settings.json", {"permissions": {"deny": ["Read(./.env)"]}, "sandbox": {"enabled": True}})
        _, checks = self.check()
        self.assertEqual(checks["secrets"]["unprotected_files"], ["api/.env"])
        self.assertEqual(checks["secrets"]["proposal"]["add"], {"permissions": {"deny": ["Read(./api/.env)"]}})
        for rule in ("Read(.env)", "Read(**/.env*)", "Read(//" + str(self.repo).lstrip("/") + "/**)"):
            self.write(".claude/settings.json", {"permissions": {"deny": [rule]}, "sandbox": {"enabled": True}})
            _, checks = self.check()
            self.assertEqual(checks["secrets"]["status"], "ok", rule)

    def test_local_setting_overrides_project_sandbox(self):
        self.write(".env")
        self.write(".claude/settings.json", {"permissions": {"deny": ["Read(./.env)"]}, "sandbox": {"enabled": True}})
        self.write(".claude/settings.local.json", {"sandbox": {"enabled": False}})
        _, checks = self.check()
        self.assertEqual(checks["secrets"]["status"], "missing")
        self.assertEqual(checks["secrets"]["proposal"]["add"], {"sandbox": {"enabled": True}})

    def test_unreadable_settings_count_as_no_rules(self):
        self.write(".env")
        outside = self.write("covering.json", {"permissions": {"deny": ["Read(./.env)"]}, "sandbox": {"enabled": True}},
                             base=self.root)
        (self.repo / ".claude").mkdir()
        (self.repo / ".claude/settings.json").symlink_to(outside)
        self.write(".claude/settings.local.json", "{not json")
        self.write(".claude/settings.json", ["a", "list"], base=self.home)
        _, checks = self.check()
        self.assertEqual(checks["secrets"]["settings"], {"local": "unreadable", "project": "unreadable", "user": "unreadable"})
        self.assertEqual(checks["secrets"]["status"], "missing")

    def test_codex_reports_secrets_as_not_verified_without_a_proposal(self):
        self.write(".env")
        data, checks = self.check("--runtime", "codex")
        self.assertEqual(checks["secrets"]["status"], "not_verified")
        self.assertNotIn("proposal", checks["secrets"])
        self.assertEqual((data["missing"], data["not_verified"]), ([], ["secrets"]))

    def test_missing_gh_leaves_server_checks_not_verified(self):
        self.write(".env")
        data, checks = self.check("--merge", "--deploy", "--pr", PR)
        self.assertEqual(checks["secrets"]["status"], "missing")
        for name in ("branch_protection", "pr_checks", "deployment"):
            self.assertEqual((checks[name]["status"], checks[name]["reason"]), ("not_verified", "GH_NOT_FOUND"))
        self.assertEqual(data["not_verified"], ["branch_protection", "pr_checks", "deployment"])

    def test_unprotected_branch_without_rules_is_missing(self):
        self.gh({**REPO, "rules/branches/main": {"out": "[]"}, "branches/main": OPEN_BRANCH})
        data, checks = self.check("--merge")
        self.assertEqual(checks["branch_protection"]["status"], "missing")
        self.assertEqual(checks["branch_protection"]["proposal"]["require"], ["pull_request", "status_checks"])
        self.assertEqual(data["missing"], ["branch_protection"])
        self.assertNotIn("pr_checks", checks)
        # The admin-only protection endpoint answers 404 to other users even on a protected branch.
        self.assertFalse([call for call in self.calls() if call.endswith("/protection")])

    def test_required_checks_from_classic_protection_or_a_ruleset_are_enough(self):
        protected = {"out": json.dumps({"protected": True, "protection": {
            "enabled": True, "required_status_checks": {"contexts": ["test"], "checks": [{"context": "test"}]}}})}
        self.gh({**REPO, "rules/branches/main": {"out": "[]"}, "branches/main": protected})
        _, checks = self.check("--merge")
        self.assertEqual((checks["branch_protection"]["status"], checks["branch_protection"]["required_checks"]), ("ok", ["test"]))
        rules = [{"type": "pull_request"}, {"type": "required_status_checks",
                                             "parameters": {"required_status_checks": [{"context": "ci"}]}}]
        self.gh({**REPO, "rules/branches/main": {"out": json.dumps(rules)}, "branches/main": OPEN_BRANCH})
        _, checks = self.check("--merge")
        self.assertEqual((checks["branch_protection"]["status"], checks["branch_protection"]["required_checks"]), ("ok", ["ci"]))

    def test_protected_branch_without_required_checks_asks_only_for_checks(self):
        rules = [{"type": "pull_request"}]
        self.gh({**REPO, "rules/branches/main": {"out": json.dumps(rules)}, "branches/main": OPEN_BRANCH})
        _, checks = self.check("--merge")
        self.assertEqual(checks["branch_protection"]["proposal"]["require"], ["status_checks"])

    def test_pull_request_without_checks_is_missing_and_with_checks_is_counted(self):
        base = {**REPO, "rules/branches/main": {"out": "[]"}, "branches/main": OPEN_BRANCH}
        self.gh({**base, "pr view": {"out": json.dumps({"statusCheckRollup": [], "headRefOid": "abc", "state": "OPEN"})}})
        data, checks = self.check("--pr", PR)
        self.assertEqual(checks["pr_checks"]["status"], "missing")
        self.assertEqual(checks["pr_checks"]["proposal"]["workflow_files_present"], False)
        self.assertEqual(data["missing"], ["branch_protection", "pr_checks"])
        self.write(".github/workflows/ci.yml", "name: CI")
        rollup = [{"conclusion": "SUCCESS"}, {"conclusion": "FAILURE"}, {"conclusion": "", "status": "IN_PROGRESS"},
                  {"state": "SUCCESS"}]
        self.gh({**base, "pr view": {"out": json.dumps({"statusCheckRollup": rollup, "headRefOid": "abc"})}})
        _, checks = self.check("--pr", PR)
        result = checks["pr_checks"]
        self.assertEqual((result["status"], result["ran"], result["passed"], result["failed"], result["pending"]),
                         ("ok", 4, 2, 1, 1))
        self.assertEqual(result["workflow_files"], ["ci.yml"])

    def test_failed_requests_are_not_verified_instead_of_missing(self):
        denied = {"code": 1, "out": json.dumps({"message": "Forbidden", "status": "403"}), "err": "gh: Forbidden (HTTP 403)"}
        self.gh({**REPO, "rules/branches/main": denied, "branches/main": OPEN_BRANCH, "pr view": {"code": 1, "err": "boom"},
                 "environments": {"out": "not json"}})
        data, checks = self.check("--deploy", "--pr", PR)
        for name in ("branch_protection", "pr_checks", "deployment"):
            self.assertEqual((checks[name]["status"], checks[name]["reason"]), ("not_verified", "GH_REQUEST_FAILED"))
        self.assertEqual(data["missing"], [])
        self.gh({"repo view": {"code": 1, "err": "no git remotes found"}})
        _, checks = self.check("--merge")
        self.assertEqual(checks["branch_protection"]["reason"], "GH_REPOSITORY_UNAVAILABLE")

    def test_deployment_needs_an_environment_with_protection_rules(self):
        self.gh({**REPO, "environments": {"out": json.dumps({"total_count": 1, "environments": [
            {"name": "staging", "protection_rules": []}]})}})
        _, checks = self.check("--deploy")
        self.assertEqual((checks["deployment"]["status"], checks["deployment"]["environments"]), ("missing", ["staging"]))
        self.gh({**REPO, "environments": {"out": json.dumps({"environments": [
            {"name": "staging", "protection_rules": [{"type": "required_reviewers"}]}]})}})
        _, checks = self.check("--deploy")
        self.assertEqual((checks["deployment"]["status"], checks["deployment"]["protected_environments"]), ("ok", ["staging"]))

    def test_invalid_input_fails_without_calling_gh(self):
        self.gh(REPO)
        for args in (["check", "--pr", "https://github.com/acme/demo/pull/7 --admin"], ["check", "--pr", "7"],
                     ["remove"], ["check", "--unknown"]):
            code, out, err = self.run_cli(*args)
            self.assertEqual((code, out), (2, ""), args)
            self.assertIn("error", json.loads(err))
        code, _, err = self.run_cli("check", repo=self.root / "missing")
        self.assertEqual((code, json.loads(err)), (2, {"error": "REPOSITORY_DIRECTORY_REQUIRED"}))
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
