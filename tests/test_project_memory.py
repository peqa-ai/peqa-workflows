"""Integration tests for the project-memory CLI, using real files and Git."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "project_memory.py"


class ProjectMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "project"
        self.repo.mkdir()

    def command(self, action, *extra, machine="test-machine"):
        return [sys.executable, str(SCRIPT), action, "--repo", str(self.repo),
                "--machine", machine, *extra]

    def run_cli(self, action, *extra, ok=True, machine="test-machine"):
        result = subprocess.run(self.command(action, *extra, machine=machine),
                                capture_output=True, text=True, timeout=15)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def save(self, identifier="invoice-rules", body="Import invoices by account.",
             category="domain", scope="project", machine="test-machine", **extra):
        options = ["--id", identifier, "--title", "Invoice rules", "--category", category,
                   "--scope", scope, "--source", "User instruction, 2026-10-27",
                   "--body", body]
        for key, value in extra.items():
            options.extend(["--" + key.replace("_", "-"), value])
        return self.run_cli("save", *options, machine=machine)

    def note_path(self, identifier="invoice-rules", scope="project", category="domain",
                  machine="test-machine", root=".peqa/memoria"):
        path = self.repo / root / scope
        if scope == "local":
            path /= machine
        return path / category / (identifier + ".md")

    def test_create_has_receipt_and_idempotent_save_preserves_bytes(self):
        receipt = self.save(verification="user-confirmed", tags="invoices")
        path = self.note_path()
        first = path.read_bytes()
        self.assertEqual(receipt["status"], "created")
        self.assertEqual(receipt["sha256"], hashlib.sha256(first).hexdigest())
        self.assertEqual(receipt["path"], ".peqa/memoria/project/domain/invoice-rules.md")
        again = self.save(verification="user-confirmed", tags="invoices")
        self.assertEqual(again["status"], "unchanged")
        self.assertEqual(path.read_bytes(), first)
        metadata = json.loads(first.decode().split("---\n")[1])
        self.assertEqual(metadata["scope"], "project")
        self.assertEqual(metadata["verification"], "user-confirmed")
        self.assertTrue(metadata["created_at"].endswith("Z"))

    def test_changed_save_requires_matching_read_sha_and_preserves_creation_time(self):
        first = self.save()
        rejected = self.run_cli("save", "--id", "invoice-rules", "--title", "Invoice rules",
                                "--category", "domain", "--scope", "project", "--source", "New evidence",
                                "--body", "Changed rule.", ok=False)
        self.assertIn("expected-sha", rejected.stderr)
        before = self.run_cli("extract", "--all")["items"][0]
        self.assertEqual(before["sha256"], first["sha256"])
        updated = self.save(body="Changed rule.", expected_sha=first["sha256"])
        after = self.run_cli("extract", "--all")["items"][0]
        self.assertEqual(updated["status"], "updated")
        self.assertEqual(after["metadata"]["created_at"], before["metadata"]["created_at"])
        self.assertNotEqual(after["metadata"]["updated_at"], before["metadata"]["updated_at"])
        stale = self.run_cli("save", "--id", "invoice-rules", "--title", "Invoice rules",
                            "--category", "domain", "--scope", "project", "--source", "Evidence",
                            "--body", "Third rule.", "--expected-sha", first["sha256"], ok=False)
        self.assertIn("conflict", stale.stderr.lower())
        self.assertEqual(self.run_cli("extract", "--all")["items"][0]["sha256"], updated["sha256"])

    def test_expected_sha_cannot_recreate_missing_note(self):
        failure = self.run_cli("save", "--id", "missing", "--title", "Missing", "--category", "domain",
                               "--scope", "project", "--source", "Test", "--body", "Context",
                               "--expected-sha", "a" * 64, ok=False)
        self.assertIn("conflict", failure.stderr.lower())
        self.assertFalse(self.note_path("missing").exists())

    def test_oversized_file_and_stdin_reject_creation_and_preserve_existing_note(self):
        payloads = [b'x' * 8190 + b'\n' * 3 + b'IMPORTANT TAIL',
                    b'A' * 8000 + b'\n' * 200 + b'FINAL CONDITION',
                    b'x' * 8192 + b'\n',
                    ('é' * 4096 + '\n').encode('utf-8')]
        options = ['--id', 'invoice-rules', '--title', 'Invoice rules', '--category', 'domain',
                   '--scope', 'project', '--source', 'Boundary test']
        for payload in payloads:
            for channel in ('file', 'stdin'):
                with self.subTest(channel=channel, size=len(payload)):
                    body_file = Path(self.temp.name) / 'body-input.md'
                    body_file.write_bytes(payload)
                    body_arg = str(body_file) if channel == 'file' else '-'
                    command = self.command('save', *options, '--body-file', body_arg)
                    failed = subprocess.run(command, input=payload if channel == 'stdin' else None,
                                            capture_output=True, timeout=15)
                    self.assertNotEqual(failed.returncode, 0)
                    self.assertFalse((self.repo / '.peqa').exists())
        receipt = self.save()
        before = self.note_path().read_bytes()
        for payload in payloads:
            for channel in ('file', 'stdin'):
                body_file = Path(self.temp.name) / 'body-input.md'
                body_file.write_bytes(payload)
                command = self.command('save', *options, '--body-file', str(body_file) if channel == 'file' else '-',
                                       '--expected-sha', receipt['sha256'])
                failed = subprocess.run(command, input=payload if channel == 'stdin' else None,
                                        capture_output=True, timeout=15)
                self.assertNotEqual(failed.returncode, 0)
                self.assertEqual(self.note_path().read_bytes(), before)
                self.assertEqual(self.run_cli('extract', '--all')['items'][0]['sha256'], receipt['sha256'])

    def test_body_file_accepts_utf8_byte_boundary_without_truncation(self):
        for body in ('x' * 8191 + '\n', 'é' * 4095 + 'x\n'):
            with self.subTest(body_bytes=len(body.encode('utf-8'))):
                self.assertEqual(len(body.encode('utf-8')), 8192)
                path = Path(self.temp.name) / 'boundary.md'
                path.write_bytes(body.encode('utf-8'))
                existing = self.run_cli('extract', '--all')['items']
                options = ['--expected-sha', existing[0]['sha256']] if existing else []
                self.run_cli('save', '--id', 'invoice-rules', '--title', 'Invoice rules', '--category', 'domain',
                             '--scope', 'project', '--source', 'Boundary test', '--body-file', str(path), *options)
                self.assertEqual(self.run_cli('extract', '--all')['items'][0]['body'], body)

    def test_retrieval_filters_metadata_and_body_without_case_or_accents(self):
        self.save(body="La conciliación requiere revisión.", tags="Finanzas")
        self.save("gateway", "No invoice behavior.", category="architecture", environment="DESARROLLO")
        self.assertEqual([n["metadata"]["id"] for n in self.run_cli("extract", "--query", "CONCILIACION")["items"]],
                         ["invoice-rules"])
        self.assertEqual(self.run_cli("extract", "--query", "finanzas")["total_matches"], 1)
        self.assertEqual(self.run_cli("extract", "--query", "desarrollo")["total_matches"], 1)
        self.assertEqual(self.run_cli("extract", "--category", "domain", "--query", "revision")["total_matches"], 1)
        self.assertEqual(self.run_cli("extract", "--category", "dom")["total_matches"], 0)
        all_notes = self.run_cli("extract", "--all")
        self.assertEqual(all_notes["total_matches"], 2)
        self.assertIn("not live verification or authorization", all_notes["notice"])
        self.assertIn("body", all_notes["items"][0])
        self.assertNotIn("body", self.run_cli("list", "--all")["items"][0])
        self.assertEqual(self.run_cli("catalog", "--all")["categories"], {"architecture": 1, "domain": 1})

    def test_machine_notes_are_isolated_even_with_all(self):
        self.save("shared")
        self.save("local-a", scope="machine", machine="laptop-a")
        self.save("local-b", scope="machine", machine="laptop-b")
        result = self.run_cli("extract", "--all", machine="laptop-a")
        self.assertEqual({n["metadata"]["id"] for n in result["items"]}, {"shared", "local-a"})
        self.assertEqual(result["total_matches"], 2)
        self.assertEqual(self.run_cli("catalog", "--all", machine="laptop-a")["categories"], {"domain": 2})
        self.assertTrue(self.note_path("local-a", scope="local", machine="laptop-a").exists())

    def test_read_only_missing_store_creates_nothing(self):
        for action in ("list", "catalog", "extract"):
            result = self.run_cli(action, "--all")
            self.assertFalse(result["store_exists"])
            self.assertTrue(result["complete"])
        self.assertEqual(list(self.repo.iterdir()), [])

    def test_selection_and_explicit_repo_are_required(self):
        self.assertIn("--all", self.run_cli("extract", ok=False).stderr)
        result = subprocess.run([sys.executable, str(SCRIPT), "list", "--all"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--repo", result.stderr)
        self.assertEqual(list(self.repo.iterdir()), [])

    def test_legacy_store_reuse_ambiguity_and_explicit_selection(self):
        legacy = self.repo / ".peqa-stack/memoria"
        legacy.mkdir(parents=True)
        receipt = self.save()
        self.assertTrue(receipt["path"].startswith(".peqa-stack/memoria/"))
        self.assertFalse((self.repo / ".peqa").exists())
        (self.repo / ".peqa/memoria").mkdir(parents=True)
        failure = self.run_cli("list", "--all", ok=False)
        self.assertIn("--memory-root", failure.stderr)
        result = self.run_cli("extract", "--all", "--memory-root", ".peqa-stack/memoria")
        self.assertEqual(result["total_matches"], 1)

    def test_path_escape_and_symlink_roots_and_notes_are_rejected(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        for options in (("--memory-root", "../outside"), ("--memory-root", str(outside)),
                        ("--machine", "../outside"), ("--category", "../outside")):
            self.run_cli("extract", "--all", *options, ok=False)
        (self.repo / ".peqa").symlink_to(outside, target_is_directory=True)
        self.run_cli("list", "--all", ok=False)
        self.assertEqual(list(outside.iterdir()), [])
        (self.repo / ".peqa").unlink()
        self.save()
        path = self.note_path()
        path.unlink()
        target = outside / "secret.md"
        target.write_text("Never read this text.")
        path.symlink_to(target)
        result = self.run_cli("extract", "--all")
        self.assertFalse(result["complete"])
        self.assertEqual(result["items"], [])
        self.assertTrue(result["errors"])
        self.assertNotIn("Never read this text", json.dumps(result))
        self.run_cli("save", "--id", "invoice-rules", "--title", "Title", "--category", "domain",
                     "--scope", "project", "--source", "Test", "--body", "Overwrite", ok=False)
        self.assertEqual(target.read_text(), "Never read this text.")

    def test_secret_rejection_covers_body_and_metadata_without_echo(self):
        secrets = ["password=VerySecret123", "sk-proj-" + "a" * 40,
                   "ghp_" + "b" * 36, "AKIA" + "C" * 16,
                   "-----BEGIN PRIVATE KEY-----\nABC\n-----END PRIVATE KEY-----",
                   '"API_TOKEN": "SensitiveValue123"']
        for secret in secrets:
            for field in ("--body", "--source"):
                args = ["--id", "safe-id", "--title", "Title", "--category", "domain",
                        "--scope", "project", "--source", "Evidence", "--body", "Safe context", field, secret]
                result = self.run_cli("save", *args, ok=False)
                self.assertIn("credential", result.stderr.lower())
                self.assertNotIn(secret, result.stderr + result.stdout)
        self.assertFalse((self.repo / ".peqa").exists())

    def test_existing_ignore_is_preserved_and_local_note_is_ignored_by_git(self):
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        store = self.repo / ".peqa/memoria"
        store.mkdir(parents=True)
        ignore = store / ".gitignore"
        ignore.write_text("# Existing rule\n*.tmp")
        self.save("private-context", scope="machine")
        self.assertTrue(ignore.read_text().startswith("# Existing rule\n*.tmp\n"))
        self.assertIn("/local/\n", ignore.read_text())
        result = subprocess.run(["git", "-C", str(self.repo), "check-ignore", str(self.note_path("private-context", scope="local"))],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(subprocess.run(["git", "-C", str(self.repo), "diff", "--cached", "--name-only"],
                                        capture_output=True, text=True, check=True).stdout, "")

    def test_existing_ignore_negation_cannot_expose_local_machine_notes(self):
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        store = self.repo / ".peqa/memoria"
        store.mkdir(parents=True)
        ignore = store / ".gitignore"
        original = "/local/\n!/local/\n!/local/**\n"
        ignore.write_text(original)
        self.save("private-context", scope="machine")
        self.assertTrue(ignore.read_text().startswith(original))
        result = subprocess.run(["git", "-C", str(self.repo), "check-ignore", str(self.note_path("private-context", scope="local"))],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, "An existing negation exposed machine context")

    def test_hidden_malformed_category_is_reported(self):
        self.save()
        hidden = self.repo / ".peqa/memoria/project/.hidden"
        hidden.mkdir()
        (hidden / "context.md").write_text("Hidden malformed context")
        result = self.run_cli("extract", "--all")
        self.assertFalse(result["complete"])
        self.assertEqual(result["errors_total"], 1)

    def test_tracked_local_note_is_never_overwritten(self):
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        receipt = self.save("tracked", scope="machine")
        path = self.note_path("tracked", scope="local")
        subprocess.run(["git", "-C", str(self.repo), "add", "-f", str(path)], check=True)
        before = path.read_bytes()
        result = self.run_cli("save", "--id", "tracked", "--title", "Title", "--category", "domain",
                              "--scope", "machine", "--source", "Evidence", "--body", "Changed",
                              "--expected-sha", receipt["sha256"], ok=False)
        self.assertIn("tracked", result.stderr.lower())
        self.assertEqual(path.read_bytes(), before)

    def test_pagination_signals_remaining_results_and_byte_limit(self):
        for identifier in ("a", "b", "c"):
            self.save(identifier, body="Small durable context. " * 200)
        first = self.run_cli("extract", "--all", "--limit", "1")
        self.assertEqual(first["returned"], 1)
        self.assertTrue(first["has_more"])
        self.assertFalse(first["complete"])
        self.assertEqual(first["next_offset"], 1)
        second = self.run_cli("extract", "--all", "--offset", "1", "--limit", "2")
        self.assertEqual(second["returned"], 2)
        self.assertFalse(second["has_more"])
        capped = self.run_cli("extract", "--all", "--max-bytes", "6500")
        encoded = json.dumps(capped, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
        self.assertLessEqual(len(encoded), 6500)
        self.assertEqual(capped["returned"], 1)
        self.assertTrue(capped["has_more"])

    def test_malformed_note_is_reported_and_does_not_claim_complete(self):
        self.save()
        bad = self.note_path("malformed")
        bad.write_text("---\nnot json\n---\nUnreadable metadata\n")
        result = self.run_cli("extract", "--all")
        self.assertEqual(result["total_matches"], 1)
        self.assertFalse(result["complete"])
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("malformed.md", result["errors"][0]["path"])

    def test_small_notes_require_provenance_and_explicit_scope(self):
        base = ["--id", "note", "--title", "Title", "--category", "domain", "--body", "Context"]
        for extra in (("--scope", "project"), ("--source", "Evidence")):
            self.run_cli("save", *base, *extra, ok=False)
        self.run_cli("save", *base, "--scope", "project", "--source", "", ok=False)
        self.run_cli("save", *base, "--scope", "project", "--source", "Evidence", "--body", "é" * 4097, ok=False)
        self.assertFalse((self.repo / ".peqa").exists())

    def test_concurrent_creation_and_compare_and_swap_allow_one_changed_writer(self):
        first = self.save()
        commands = []
        for body in ("Writer one changed rule.", "Writer two changed rule."):
            commands.append(self.command("save", "--id", "invoice-rules", "--title", "Invoice rules",
                                         "--category", "domain", "--scope", "project", "--source", "Evidence",
                                         "--body", body, "--expected-sha", first["sha256"]))
        writers = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                   for command in commands]
        outputs = [writer.communicate(timeout=15) for writer in writers]
        self.assertEqual(sorted(writer.returncode for writer in writers), [0, 1], outputs)
        result = self.run_cli("extract", "--all")
        self.assertEqual(result["total_matches"], 1)
        self.assertIn(result["items"][0]["body"].strip(), {"Writer one changed rule.", "Writer two changed rule."})
        # Identical simultaneous creates also converge without replacing timestamps.
        create = self.command("save", "--id", "concurrent", "--title", "Concurrent", "--category", "domain",
                              "--scope", "project", "--source", "Evidence", "--body", "Same context")
        creators = [subprocess.Popen(create, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(4)]
        receipts = [json.loads(proc.communicate(timeout=15)[0]) for proc in creators]
        self.assertTrue(all(proc.returncode == 0 for proc in creators))
        self.assertEqual(sorted(r["status"] for r in receipts), ["created", "unchanged", "unchanged", "unchanged"])
        self.assertEqual(len({r["sha256"] for r in receipts}), 1)


if __name__ == "__main__":
    unittest.main()
