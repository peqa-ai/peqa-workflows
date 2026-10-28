import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / 'scripts/peqa_hooks.py'
BUDGET = ROOT / 'skills/revisa/scripts/review_budget.py'
CHECKS = ROOT / 'scripts/review_checks.py'
PR = 'https://github.com/fixture/repo/pull/1'


class HookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='peqa hooks ')
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name).resolve() / 'project with spaces'
        self.repo.mkdir()
        self.git('init', '-q')
        (self.repo / 'file.txt').write_text('fixture\n')
        self.git('add', '.')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 '-c', 'commit.gpgsign=false', 'commit', '-qm', 'fixture')
        self.head = self.git('rev-parse', 'HEAD').strip()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True)

    def command(self, action, *args, event=None, runtime='claude', mode='enforce', ok=True):
        proc = subprocess.run([sys.executable, str(HOOK), action, '--repo', str(self.repo),
                               '--runtime', runtime, '--mode', mode, *args],
                              input=json.dumps(event) if event is not None else None,
                              capture_output=True, text=True, timeout=25)
        self.assertEqual(proc.returncode == 0, ok, proc.stderr + proc.stdout)
        return json.loads(proc.stdout if ok else proc.stderr)

    def event(self, name, session='session-a', **extra):
        return {'hook_event_name': name, 'session_id': session, 'cwd': str(self.repo), **extra}

    def invalid_report(self):
        directory = Path(self.command('artifact-dir')['directory'])
        report = directory / 'report.json'
        report.write_text('{}')
        self.command('arm', '--session-id', 'session-a', '--report', str(report))
        return report

    def test_no_arm_is_noop_with_no_state_created(self):
        self.assertEqual(self.command('run', event=self.event('Stop')), {})
        self.assertEqual(self.command('run', event=self.event('PreToolUse', tool_name='Agent')), {})
        self.assertFalse((self.repo / '.git/peqa').exists())

    def test_config_is_read_only_and_quotes_paths(self):
        config = self.command('config', runtime='codex')
        command = config['hooks']['Stop'][0]['hooks'][0]['command']
        args = shlex.split(command)
        self.assertEqual(args[args.index('--repo') + 1], str(self.repo))
        self.assertEqual(args[args.index('--mode') + 1], 'warn')
        self.assertFalse((self.repo / '.git/peqa').exists())

    def test_claude_blocks_only_once_then_releases_invalid_report(self):
        self.invalid_report()
        self.assertEqual(self.command('run', event=self.event('Stop'))['decision'], 'block')
        second = self.command('run', event=self.event('Stop', stop_hook_active=True))
        self.assertIn('systemMessage', second)
        self.assertNotIn('decision', second)
        self.assertEqual(self.command('run', event=self.event('Stop')), {})

    def test_codex_only_warns_even_if_enforce_was_requested(self):
        self.invalid_report()
        result = self.command('run', runtime='codex', event=self.event('Stop'))
        self.assertIn('systemMessage', result)
        self.assertNotIn('decision', result)
        self.assertNotIn('continue', result)
        self.assertEqual(self.command('run', runtime='codex', event=self.event('Stop')), {})

    def test_scope_does_not_leak_to_other_sessions_or_subagents(self):
        self.invalid_report()
        self.assertEqual(self.command('run', event=self.event('Stop', session='other')), {})
        self.assertEqual(self.command('run', event=self.event('Stop', agent_id='child')), {})
        self.assertEqual(self.command('run', event=self.event('Stop'))['decision'], 'block')

    def test_unknown_and_malformed_events_do_not_block(self):
        self.assertEqual(self.command('run', event=self.event('NewUnknownEvent')), {})
        result = self.command('run', event={'hook_event_name': 'Stop', 'cwd': str(self.repo)})
        self.assertNotIn('decision', result)
        proc = subprocess.run([sys.executable, str(HOOK), 'run', '--repo', str(self.repo)],
                              input='{bad', capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertIn('systemMessage', json.loads(proc.stdout))

    def test_report_and_state_symlinks_rejected(self):
        directory = Path(self.command('artifact-dir')['directory'])
        outside = self.repo.parent / 'private.json'
        outside.write_text('{"secret":"SYNTHETIC_NOT_A_SECRET"}')
        report = directory / 'report.json'
        report.symlink_to(outside)
        self.command('arm', '--session-id', 'session-a', '--report', str(report), ok=False)
        self.assertIn('SYNTHETIC_NOT_A_SECRET', outside.read_text())
        hooks = self.repo / '.git/peqa/hooks'
        hooks.rename(hooks.with_name('hooks-original'))
        other = self.repo.parent / 'outside-state'
        other.mkdir()
        hooks.symlink_to(other, target_is_directory=True)
        result = self.command('run', event=self.event('Stop'))
        self.assertIn('systemMessage', result)
        self.assertEqual(list(other.iterdir()), [])

    def test_other_worktree_is_not_covered_by_session_registration(self):
        self.invalid_report()
        other = self.repo.parent / 'worktree'
        self.git('worktree', 'add', '-q', '--detach', str(other), 'HEAD')
        event = self.event('Stop')
        event['cwd'] = str(other)
        self.assertEqual(self.command('run', event=event), {})
        self.assertEqual(self.command('run', event=self.event('Stop'))['decision'], 'block')

    def test_clear_disarms_without_touching_report(self):
        report = self.invalid_report()
        before = report.read_bytes()
        self.command('clear', '--session-id', 'session-a')
        self.assertEqual(self.command('run', event=self.event('Stop')), {})
        self.assertEqual(report.read_bytes(), before)

    def test_git_environment_does_not_redirect_configured_repository(self):
        env = dict(os.environ, GIT_DIR=str(self.repo.parent / 'missing.git'))
        proc = subprocess.run([sys.executable, str(HOOK), 'config', '--repo', str(self.repo)],
                              env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        command = json.loads(proc.stdout)['hooks']['Stop'][0]['hooks'][0]['command']
        self.assertIn(str(self.repo), command)

    def test_symlinked_git_marker_does_not_create_state(self):
        gitdir = self.repo / '.git'
        moved = self.repo.parent / 'actual.git'
        gitdir.rename(moved)
        gitdir.symlink_to(moved, target_is_directory=True)
        self.command('artifact-dir', ok=False)
        self.assertFalse((moved / 'peqa').exists())

    def budget(self, action, *args):
        proc = subprocess.run([sys.executable, str(BUDGET), action, '--repo', str(self.repo),
                               '--pr-url', PR, *args], capture_output=True, text=True, check=True)
        return json.loads(proc.stdout)

    def guard(self):
        self.budget('init', '--prior-used', '2')
        receipt = self.budget('reserve', '--head', self.head)
        file = self.repo.parent / 'reservations.json'
        file.write_text(json.dumps([{'repo': '.', 'identity': PR, 'head': self.head, 'token': receipt['token']}]))
        self.command('guard', '--session-id', 'session-a', '--tool-name', 'Agent', '--reservations', str(file))
        return receipt

    def test_guard_checks_reserved_budget_without_double_reservation(self):
        receipt = self.guard()
        ledger = Path(receipt['ledger'])
        before = ledger.read_bytes()
        self.assertEqual(self.command('run', event=self.event('PreToolUse', tool_name='Bash')), {})
        self.assertEqual(self.command('run', event=self.event('PreToolUse', tool_name='Agent')), {})
        claimed = ledger.read_bytes()
        self.assertNotEqual(claimed, before)
        self.assertEqual(self.budget('inspect')['used'], 3)
        denied = self.command('run', event=self.event('PreToolUse', tool_name='Agent'))
        self.assertEqual(denied['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertEqual(ledger.read_bytes(), claimed)
        for session in ('session-a', 'session-b'):
            self.command('guard', '--session-id', session, '--tool-name', 'Agent',
                         '--reservations', str(self.repo.parent / 'reservations.json'), ok=False)
        self.command('clear', '--session-id', 'session-a')
        self.assertEqual(self.command('run', event=self.event('PreToolUse', tool_name='Agent')), {})

    def test_gitfile_through_symlink_cannot_create_storage(self):
        marker = self.repo / '.git'
        actual = self.repo.parent / 'actual.git'
        marker.rename(actual)
        alias = self.repo.parent / 'alias.git'
        alias.symlink_to(actual, target_is_directory=True)
        marker.write_text('gitdir: ' + str(alias) + '\n')
        self.command('artifact-dir', ok=False)
        self.assertFalse((actual / 'peqa').exists())

    def test_finished_reservation_cannot_pass_guard(self):
        receipt = self.guard()
        self.budget('finish', '--token', receipt['token'], '--status', 'completed')
        denied = self.command('run', event=self.event('PreToolUse', tool_name='Agent'))
        self.assertEqual(denied['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_valid_incomplete_report_can_finish(self):
        directory = Path(self.command('artifact-dir')['directory'])
        report = directory / 'report.json'
        proc = subprocess.run([sys.executable, str(CHECKS), 'template', '--repo', str(self.repo)],
                              capture_output=True, text=True, check=True)
        report.write_text(proc.stdout)
        self.command('arm', '--session-id', 'session-a', '--report', str(report))
        self.assertEqual(self.command('run', event=self.event('Stop')), {})
        self.assertEqual(self.command('run', event=self.event('Stop')), {})


if __name__ == '__main__':
    unittest.main()
