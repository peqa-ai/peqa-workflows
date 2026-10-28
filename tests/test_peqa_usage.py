"""Behavior and privacy tests using real local Git repositories and processes."""
import concurrent.futures
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/peqa_usage.py"


class UsageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "private-project-name"
        self.repo.mkdir()
        self.git("init", "-q")
        self.location = self.repo / ".git/peqa/usage"
        self.state_path = self.location / "state.json"

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def invoke(self, action, *args, repo=None, env=None):
        self.assertTrue(SCRIPT.is_file(), "The opt-in usage CLI is not implemented")
        result = subprocess.run([sys.executable, str(SCRIPT), action, "--repo",
                                 str(repo or self.repo), *args],
                                capture_output=True, text=True, env=env, timeout=15)
        output = result.stdout if result.returncode == 0 else result.stderr
        self.assertTrue(output.strip(), result)
        self.assertNotIn("Traceback", output)
        return result.returncode, json.loads(output)

    def ok(self, action, *args, **kwargs):
        code, result = self.invoke(action, *args, **kwargs)
        self.assertEqual(code, 0, result)
        return result

    def record(self, invocation=None, phase="started", skill="dirige",
               runtime="codex", **kwargs):
        return self.invoke("record", "--invocation-id", invocation or str(uuid.uuid4()),
                           "--skill", skill, "--runtime", runtime, "--phase", phase,
                           **kwargs)

    def state(self):
        return json.loads(self.state_path.read_text())

    def snapshot(self):
        return {str(p.relative_to(self.repo)): (p.stat().st_mode, p.stat().st_mtime_ns,
                                                p.read_bytes() if p.is_file() else None)
                for p in self.repo.rglob("*")}

    def test_disabled_commands_create_nothing(self):
        before = self.snapshot()
        self.assertEqual(self.record(), (0, {"status": "skipped", "reason": "disabled"}))
        self.assertFalse(self.ok("status")["enabled"])
        summary = self.ok("summary")
        self.assertEqual(summary["totals"], {"started": 0, "completed": 0, "failed": 0})
        self.assertEqual(summary["scope"], "observed_events_only")
        self.ok("disable")
        self.assertEqual(self.snapshot(), before)

    def test_enable_disable_preserve_history_and_project_id(self):
        self.ok("enable")
        project = self.state()["project_id"]
        self.assertEqual(uuid.UUID(project).version, 4)
        invocation = str(uuid.uuid4())
        self.assertEqual(self.record(invocation)[0], 0)
        self.ok("enable")
        self.ok("disable")
        before = self.snapshot()
        self.assertEqual(self.record(), (0, {"status": "skipped", "reason": "disabled"}))
        self.assertFalse(self.ok("status")["enabled"])
        self.assertEqual(self.ok("summary")["totals"]["started"], 1)
        self.assertEqual(self.snapshot(), before)
        self.ok("enable")
        self.assertEqual(self.state()["project_id"], project)
        self.assertEqual(len(self.state()["events"]), 1)

    def test_read_commands_do_not_touch_enabled_state(self):
        self.ok("enable")
        self.record()
        before = self.snapshot()
        self.ok("status")
        self.ok("summary")
        self.assertEqual(self.snapshot(), before)

    def test_deduplicates_invocation_phase_without_changing_timestamp(self):
        self.ok("enable")
        invocation = str(uuid.uuid4())
        self.assertEqual(self.record(invocation)[1]["status"], "recorded")
        before = self.state_path.read_bytes()
        self.assertEqual(self.record(invocation)[1]["status"], "duplicate")
        self.assertEqual(self.state_path.read_bytes(), before)
        self.assertEqual(self.record(invocation, "completed")[0], 0)
        self.assertEqual(len(self.state()["events"]), 2)

    def test_invocation_identity_cannot_change(self):
        self.ok("enable")
        invocation = str(uuid.uuid4())
        self.record(invocation)
        before = self.state_path.read_bytes()
        for options in ({"skill": "idea"}, {"runtime": "claude"}):
            with self.subTest(options=options):
                code, result = self.record(invocation, "completed", **options)
                self.assertEqual(code, 2)
                self.assertEqual(result["error"], "INVOCATION_MISMATCH")
        self.assertEqual(self.state_path.read_bytes(), before)

    def test_summary_groups_and_counts_only_observed_events(self):
        self.ok("enable")
        invocation = str(uuid.uuid4())
        self.record(invocation)
        self.record(invocation, "completed")
        self.record(phase="failed", skill="idea", runtime="t3-claude")
        result = self.ok("summary")
        self.assertEqual(result["totals"], {"started": 1, "completed": 1, "failed": 1})
        self.assertEqual(result["groups"], [
            {"skill": "dirige", "runtime": "codex", "started": 1, "completed": 1, "failed": 0},
            {"skill": "idea", "runtime": "t3-claude", "started": 0, "completed": 0, "failed": 1}])
        self.assertNotIn("tokens", json.dumps(result))

    def test_legacy_history_remains_readable_and_new_phases_use_canonical_names(self):
        self.ok("enable")
        invocation = str(uuid.uuid4())
        self.record(invocation)
        data = self.state()
        data["events"][0]["skill"] = "peqa-dirige"
        self.state_path.write_text(json.dumps(data))
        before = self.state_path.read_bytes()
        self.assertEqual(self.ok("status")["event_count"], 1)
        self.assertEqual(self.ok("summary")["groups"][0]["skill"], "dirige")
        self.assertEqual(self.state_path.read_bytes(), before)
        self.assertEqual(self.record(invocation)[1]["status"], "duplicate")
        self.assertEqual(self.record(invocation, "completed")[1]["status"], "recorded")
        self.assertEqual([event["skill"] for event in self.state()["events"]],
                         ["peqa-dirige", "dirige"])
        group = self.ok("summary")["groups"][0]
        self.assertEqual((group["started"], group["completed"]), (1, 1))
        self.assertEqual(self.record(skill="peqa-dirige")[0], 2)

    def test_date_filter_is_inclusive_utc_and_validated(self):
        self.ok("enable")
        self.record()
        self.record(phase="completed")
        data = self.state()
        data["events"][0]["timestamp"] = "2026-10-25T23:59:59.000000Z"
        data["events"][1]["timestamp"] = "2026-10-26T00:00:00.000000Z"
        self.state_path.write_text(json.dumps(data))
        result = self.ok("summary", "--since", "2026-10-26")
        self.assertEqual(result["since"], "2026-10-26")
        self.assertEqual(result["totals"], {"started": 0, "completed": 1, "failed": 0})
        for invalid in ("2026-02-30", "20261026", "yesterday", "2026-10-26T00:00:00Z"):
            self.assertEqual(self.invoke("summary", "--since", invalid)[0], 2)

    def test_all_supported_skills_and_runtimes_are_accepted(self):
        self.ok("enable")
        for skill in ("dirige", "idea", "revisa",
                      "memoria-recuerda", "memoria-extraer"):
            for runtime in ("t3-codex", "t3-claude", "codex", "claude"):
                self.assertEqual(self.record(skill=skill, runtime=runtime)[0], 0)
        self.assertEqual(self.ok("status")["event_count"], 20)

    def test_invalid_input_cannot_persist_or_echo_private_values(self):
        for options in ({"invocation": "secret-account-session"},
                        {"invocation": str(uuid.uuid1())},
                        {"invocation": "../outside"},
                        {"skill": "secret-prompt"}, {"runtime": "secret-machine"},
                        {"phase": "secret-error"}, {"skill": "x" * 5000}):
            with self.subTest(options=list(options)):
                code, result = self.record(**options)
                self.assertEqual(code, 2)
                self.assertEqual(result, {"error": "INVALID_ARGUMENTS"})
        code, result = self.invoke("record", "--prompt", "secret-prompt")
        self.assertEqual((code, result), (2, {"error": "INVALID_ARGUMENTS"}))
        self.assertFalse((self.repo / ".git/peqa").exists())

    def test_state_has_only_allowed_data_and_private_permissions(self):
        self.git("remote", "add", "origin", "https://secret-user:secret-token@example.invalid/private-repo")
        self.ok("enable")
        self.record()
        data = self.state()
        self.assertEqual(set(data), {"schema", "enabled", "project_id", "events"})
        self.assertEqual(set(data["events"][0]),
                         {"timestamp", "invocation_id", "skill", "runtime", "phase"})
        serialized = self.state_path.read_text()
        for forbidden in (str(self.repo), "secret-user", "secret-token", "example.invalid", "private-project-name"):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(stat.S_IMODE(self.location.stat().st_mode), 0o700)
        for item in self.location.iterdir():
            self.assertEqual(stat.S_IMODE(item.stat().st_mode), 0o600)

    def test_concurrent_initialization_and_records_lose_no_events(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            enabled = list(pool.map(lambda _: self.invoke("enable"), range(8)))
        self.assertTrue(all(code == 0 for code, _ in enabled), enabled)
        project = self.state()["project_id"]
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            records = list(pool.map(lambda _: self.record(), range(24)))
        self.assertTrue(all(code == 0 for code, _ in records), records)
        self.assertEqual(len(self.state()["events"]), 24)
        self.assertEqual(self.state()["project_id"], project)

    def test_concurrent_duplicate_records_are_counted_once(self):
        self.ok("enable")
        invocation = str(uuid.uuid4())
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            records = list(pool.map(lambda _: self.record(invocation), range(16)))
        self.assertTrue(all(code == 0 for code, _ in records), records)
        self.assertEqual(sum(r["status"] == "recorded" for _, r in records), 1)
        self.assertEqual(len(self.state()["events"]), 1)

    def test_worktrees_share_consent_history_and_deduplication(self):
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "--allow-empty", "-qm", "fixture")
        worktree = self.root / "worktree"
        self.git("worktree", "add", "-q", "--detach", str(worktree))
        self.ok("enable", repo=worktree)
        invocation = str(uuid.uuid4())
        self.record(invocation, repo=worktree)
        self.assertEqual(self.record(invocation)[1]["status"], "duplicate")
        self.assertEqual(self.ok("summary", repo=worktree)["totals"]["started"], 1)
        self.ok("disable", repo=worktree)
        self.assertEqual(self.record()[1]["reason"], "disabled")

    def test_git_environment_cannot_redirect_repo(self):
        outside = self.root / "other"
        subprocess.run(["git", "init", "-q", str(outside)], check=True)
        env = dict(os.environ, GIT_DIR=str(outside / ".git"), GIT_WORK_TREE=str(outside))
        self.ok("enable", env=env)
        self.assertTrue(self.state_path.exists())
        self.assertFalse((outside / ".git/peqa").exists())

    def test_symlink_directories_cannot_redirect_writes(self):
        for part in ("peqa", "usage"):
            with self.subTest(part=part):
                outside = self.root / ("outside-" + part)
                outside.mkdir()
                target = self.repo / ".git/peqa"
                if part == "usage":
                    target.mkdir(exist_ok=True)
                    target = target / "usage"
                target.symlink_to(outside, target_is_directory=True)
                self.assertEqual(self.invoke("enable")[0], 2)
                self.assertEqual(list(outside.iterdir()), [])
                target.unlink()

    def test_symlink_git_directory_is_rejected(self):
        outside = self.root / "outside-git"
        (self.repo / ".git").rename(outside)
        (self.repo / ".git").symlink_to(outside, target_is_directory=True)
        self.assertEqual(self.invoke("enable")[0], 2)
        self.assertFalse((outside / "peqa").exists())

    def test_gitfile_symlink_target_is_rejected(self):
        outside = self.root / "outside-git"
        alias = self.root / "alias-git"
        (self.repo / ".git").rename(outside)
        alias.symlink_to(outside, target_is_directory=True)
        (self.repo / ".git").write_text("gitdir: " + str(alias) + "\n")
        self.assertEqual(self.invoke("enable")[0], 2)
        self.assertFalse((outside / "peqa").exists())

    def test_worktree_symlink_common_directory_pointer_is_rejected(self):
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "--allow-empty", "-qm", "fixture")
        worktree = self.root / "worktree"
        self.git("worktree", "add", "-q", "--detach", str(worktree))
        pointer = self.repo / ".git/worktrees/worktree/commondir"
        outside = self.root / "outside-pointer"
        outside.write_bytes(pointer.read_bytes())
        pointer.unlink()
        pointer.symlink_to(outside)
        self.assertEqual(self.invoke("enable", repo=worktree)[0], 2)
        self.assertFalse((self.repo / ".git/peqa").exists())

    def test_missing_lock_does_not_recreate_it_without_enable(self):
        self.ok("enable")
        (self.location / "usage.lock").unlink()
        before = self.snapshot()
        for action in ("status", "summary", "disable"):
            self.assertEqual(self.invoke(action)[0], 2)
        self.assertEqual(self.record()[0], 2)
        self.assertEqual(self.snapshot(), before)

    def test_waiting_record_rechecks_consent_inside_lock(self):
        self.ok("enable")
        with (self.location / "usage.lock").open("rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            process = subprocess.Popen([
                sys.executable, str(SCRIPT), "record", "--repo", str(self.repo),
                "--skill", "dirige", "--runtime", "codex", "--phase", "started",
                "--invocation-id", str(uuid.uuid4())], stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True)
            try:
                # The process cannot finish while the exclusive lock is held.
                time.sleep(0.15)
                self.assertIsNone(process.poll())
                data = self.state()
                data["enabled"] = False
                self.state_path.write_text(json.dumps(data))
                fcntl.flock(lock, fcntl.LOCK_UN)
                output, errors = process.communicate(timeout=10)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
        self.assertEqual(process.returncode, 0, errors)
        self.assertEqual(json.loads(output), {"status": "skipped", "reason": "disabled"})
        self.assertEqual(self.state()["events"], [])

    def test_symlink_state_and_lock_cannot_write_outside(self):
        self.ok("enable")
        for filename in ("state.json", "usage.lock"):
            with self.subTest(filename=filename):
                original = self.location / filename
                content = original.read_bytes()
                outside = self.root / (filename + ".outside")
                outside.write_bytes(content)
                original.unlink()
                original.symlink_to(outside)
                self.assertEqual(self.invoke("enable")[0], 2)
                self.assertEqual(self.record()[0], 2)
                self.assertEqual(outside.read_bytes(), content)
                original.unlink()
                original.write_bytes(content)
                original.chmod(0o600)

    def test_hardlink_state_and_lock_are_rejected(self):
        self.ok("enable")
        for filename in ("state.json", "usage.lock"):
            with self.subTest(filename=filename):
                original = self.location / filename
                outside = self.root / (filename + ".outside")
                os.link(original, outside)
                before = outside.read_bytes()
                self.assertEqual(self.record()[0], 2)
                self.assertEqual(outside.read_bytes(), before)
                outside.unlink()

    def test_fifo_state_is_rejected_without_blocking(self):
        self.ok("enable")
        self.state_path.unlink()
        os.mkfifo(self.state_path, 0o600)
        self.assertEqual(self.invoke("status")[0], 2)

    def test_insecure_state_or_directory_is_rejected(self):
        self.ok("enable")
        for path, original in ((self.state_path, 0o600), (self.location, 0o700)):
            path.chmod(0o777)
            self.assertEqual(self.record()[0], 2)
            path.chmod(original)

    def test_corrupt_or_unknown_state_is_not_overwritten(self):
        self.ok("enable")
        valid = self.state_path.read_bytes()
        for broken in (b"{", b'{"enabled":true,"enabled":false}',
                       json.dumps({**json.loads(valid), "private_prompt": "secret"}).encode(),
                       json.dumps({**json.loads(valid), "enabled": 1}).encode()):
            self.state_path.write_bytes(broken)
            for action in ("enable", "disable", "summary", "status"):
                self.assertEqual(self.invoke(action)[0], 2)
            self.assertEqual(self.state_path.read_bytes(), broken)

    def test_oversized_state_is_rejected_without_loading_it(self):
        self.ok("enable")
        with self.state_path.open("wb") as stream:
            stream.truncate(32 * 1024 * 1024)
        self.assertEqual(self.invoke("status")[0], 2)

    def test_record_limit_preserves_existing_history(self):
        spec = importlib.util.spec_from_file_location("peqa_usage", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        with patch.object(sys, "path", [str(SCRIPT.parent), *sys.path]):
            spec.loader.exec_module(module)
        self.ok("enable")
        self.record()
        before = self.state_path.read_bytes()
        with patch.object(module, "MAX_EVENTS", 1):
            with self.assertRaises(module.UsageError) as error:
                module.execute("record", str(self.repo), skill="dirige", runtime="codex",
                               phase="started", invocation_id=str(uuid.uuid4()))
        self.assertEqual(str(error.exception), "EVENT_LIMIT_REACHED")
        self.assertEqual(self.state_path.read_bytes(), before)

    def test_shared_git_marker_validator_rejects_alias_without_writing(self):
        helper = SCRIPT.with_name("git_paths.py")
        self.assertTrue(helper.is_file(), "Shared Git marker validation is not extracted")
        spec = importlib.util.spec_from_file_location("git_paths", helper)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        before = self.snapshot()
        self.assertIsNone(module.check_git_marker(self.repo))
        self.assertEqual(self.snapshot(), before)
        outside = self.root / "outside-git"
        alias = self.root / "alias-git"
        (self.repo / ".git").rename(outside)
        alias.symlink_to(outside, target_is_directory=True)
        (self.repo / ".git").write_text("gitdir: " + str(alias) + "\n")
        with self.assertRaises(module.GitPathError) as error:
            module.check_git_marker(self.repo)
        self.assertEqual(str(error.exception), "UNSAFE_STORAGE")
        self.assertFalse((outside / "peqa").exists())

    def test_non_git_repo_errors_without_creating_storage(self):
        self.assertEqual(self.invoke("enable", repo=self.root)[0], 2)
        self.assertFalse((self.root / "peqa").exists())


if __name__ == "__main__":
    unittest.main()
