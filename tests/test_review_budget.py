import concurrent.futures
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'skills/peqa-revisa/scripts/review_budget.py'
PR = 'https://github.com/team/project/pull/42'


class ReviewBudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        (self.repo / 'fixture.txt').write_text('fixture\n')
        subprocess.run(['git', '-C', str(self.repo), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture'], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, action, identity=PR, *extra, repo=None):
        result = subprocess.run([sys.executable, str(SCRIPT), action, '--repo', str(repo or self.repo), *(['--pr-url', identity] if identity.startswith('https://') else ['--id', identity]), *extra], capture_output=True, text=True)
        return result.returncode, json.loads(result.stdout)

    def initialize(self, identity=PR, used=0):
        rc, data = self.call('init', identity, '--prior-used', str(used))
        self.assertEqual(rc, 0, data)

    def test_unknown_history_is_not_automatically_zero(self):
        rc, data = self.call('reserve', PR, '--head', 'a' * 40)
        self.assertNotEqual(rc, 0)
        self.assertEqual(data['error'], 'LEDGER_UNINITIALIZED')

    def test_three_passes_across_different_heads_exhaust_budget(self):
        self.initialize()
        for n in range(3):
            rc, data = self.call('reserve', PR, '--head', str(n) * 40)
            self.assertEqual(rc, 0, data)
            self.assertEqual(data['used'], n + 1)
        rc, data = self.call('reserve', PR, '--head', 'f' * 40)
        self.assertNotEqual(rc, 0)
        self.assertEqual(data['error'], 'BUDGET_EXHAUSTED')

    def test_failed_pass_is_not_refunded(self):
        self.initialize(used=2)
        _, reserved = self.call('reserve', PR, '--head', 'a' * 40)
        rc, data = self.call('finish', PR, '--token', reserved['token'], '--status', 'failed')
        self.assertEqual(rc, 0, data)
        self.assertEqual(data['used'], 3)
        self.assertNotEqual(self.call('reserve', PR, '--head', 'b' * 40)[0], 0)

    def test_verify_checks_receipt_without_consuming_or_creating_state(self):
        self.assertNotEqual(self.call('verify', PR, '--head', 'a' * 40, '--token', 'unknown')[0], 0)
        self.assertFalse((self.repo / '.git/peqa').exists())
        self.initialize(used=2)
        _, reserved = self.call('reserve', PR, '--head', 'a' * 40)
        ledger = Path(reserved['ledger'])
        before = ledger.read_bytes()
        for _ in range(2):
            rc, receipt = self.call('verify', PR, '--head', 'a' * 40, '--token', reserved['token'])
            self.assertEqual(rc, 0, receipt)
            self.assertEqual(receipt['used'], 3)
        self.assertEqual(ledger.read_bytes(), before)
        self.assertNotEqual(self.call('verify', PR, '--head', 'b' * 40, '--token', reserved['token'])[0], 0)
        self.call('finish', PR, '--token', reserved['token'], '--status', 'completed')
        self.assertNotEqual(self.call('verify', PR, '--head', 'a' * 40, '--token', reserved['token'])[0], 0)

    def test_verify_rejects_symlinked_ledger(self):
        self.initialize()
        ledger = self.repo / '.git/peqa/reviews/budget.json'
        outside = self.root / 'outside.json'
        ledger.rename(outside)
        ledger.symlink_to(outside)
        before = outside.read_bytes()
        self.assertNotEqual(self.call('verify', PR, '--head', 'a' * 40, '--token', 'unknown')[0], 0)
        self.assertEqual(outside.read_bytes(), before)

    def test_claim_is_atomic_and_cannot_reuse_token_across_worktrees(self):
        self.initialize(used=2)
        _, reservation = self.call('reserve', PR, '--head', 'a' * 40)
        token = reservation['token']
        def claim(_):
            return self.call('claim', PR, '--head', 'a' * 40, '--token', token)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            attempts = list(pool.map(claim, range(4)))
        self.assertEqual(sum(rc == 0 for rc, _ in attempts), 1)
        self.assertEqual(self.call('inspect', PR)[1]['used'], 3)
        worktree = self.root / 'claim-worktree'
        subprocess.run(['git', '-C', str(self.repo), 'worktree', 'add', '-q', '--detach', str(worktree)], check=True)
        self.assertNotEqual(self.call('claim', PR, '--head', 'a' * 40, '--token', token, repo=worktree)[0], 0)
        self.assertNotEqual(self.call('verify', PR, '--head', 'a' * 40, '--token', token)[0], 0)
        self.assertEqual(self.call('finish', PR, '--token', token, '--status', 'completed')[0], 0)

    def test_parallel_parents_cannot_reserve_a_fourth_review(self):
        self.initialize()
        def reserve(_):
            return self.call('reserve', PR, '--head', 'a' * 40)
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(reserve, range(6)))
        self.assertEqual(sum(rc == 0 for rc, _ in results), 3)
        self.assertEqual(len({r['token'] for rc, r in results if rc == 0}), 3)

    def test_linked_worktrees_share_the_same_budget(self):
        self.initialize(used=3)
        worktree = self.root / 'worktree'
        subprocess.run(['git', '-C', str(self.repo), 'worktree', 'add', '-q', '--detach', str(worktree)], check=True)
        rc, data = self.call('reserve', PR, '--head', 'b' * 40, repo=worktree)
        self.assertNotEqual(rc, 0)
        self.assertEqual(data['error'], 'BUDGET_EXHAUSTED')

    def test_attaching_a_local_change_preserves_both_counters(self):
        self.initialize('change-feature', used=2)
        self.initialize(PR, used=1)
        rc, data = self.call('attach', PR, '--from-id', 'change-feature')
        self.assertEqual(rc, 0, data)
        self.assertEqual(data['used'], 3)
        self.assertEqual(self.call('inspect', 'change-feature')[1]['used'], 3)
        self.assertNotEqual(self.call('reserve', 'change-feature', '--head', 'a' * 40)[0], 0)
        other = 'https://github.com/fork/project/pull/42'
        self.initialize(other)
        self.assertNotEqual(self.call('attach', other, '--from-id', 'change-feature')[0], 0)
        self.assertEqual(self.call('inspect', other)[1]['used'], 0)
        self.assertEqual(self.call('inspect', PR)[1]['used'], 3)

    def test_same_number_in_different_repositories_and_hosts_is_independent(self):
        self.initialize(used=3)
        for other in ('https://github.com/fork/project/pull/42',
                      'https://git.example.invalid/team/project/pull/42'):
            self.initialize(other)
            rc, receipt = self.call('reserve', other, '--head', 'a' * 40)
            self.assertEqual(rc, 0, receipt)
            self.assertEqual(receipt['used'], 1)
            self.assertEqual(receipt['pr_url'], other)
        self.assertEqual(self.call('inspect', PR)[1]['used'], 3)

    def test_canonical_url_variants_share_one_counter(self):
        self.initialize(used=3)
        variant = 'https://GITHUB.COM:443/Team/Project/pull/42/?view=all#discussion'
        rc, receipt = self.call('reserve', variant, '--head', 'a' * 40)
        self.assertNotEqual(rc, 0)
        self.assertEqual(receipt['error'], 'BUDGET_EXHAUSTED')
        self.assertEqual(self.call('inspect', variant)[1]['pr_url'], PR)

    def test_bare_number_and_credential_urls_are_rejected(self):
        for identity in ('pr-42', 'https://user:password@github.com/team/project/pull/42'):
            rc, data = self.call('init', identity, '--prior-used', '0')
            self.assertNotEqual(rc, 0, data)
        self.assertFalse((self.repo / '.git/peqa/reviews/budget.json').exists())

    def test_legacy_count_requires_explicit_association_and_is_preserved(self):
        location = self.repo / '.git/peqa/reviews'
        location.mkdir(parents=True)
        legacy = {'identity': 'pr-42', 'created_at': 'fixture',
                  'passes': [{'token': f'legacy-{n}', 'status': 'imported'} for n in range(3)]}
        (location / 'budget.json').write_text(json.dumps({'schema': 1, 'entries': {'pr-42': legacy}}))
        rc, error = self.call('init', PR, '--prior-used', '0')
        self.assertNotEqual(rc, 0)
        self.assertEqual(error['error'], 'LEGACY_PR_ASSOCIATION_REQUIRED')
        rc, migrated = self.call('migrate', PR, '--from-id', 'pr-42')
        self.assertEqual(rc, 0, migrated)
        self.assertEqual(migrated['used'], 3)
        self.assertEqual(migrated['pr_url'], PR)
        self.assertEqual(self.call('reserve', PR, '--head', 'a' * 40)[1]['error'], 'BUDGET_EXHAUSTED')
        self.assertEqual(self.call('migrate', PR, '--from-id', 'pr-42')[1]['used'], 3)
        other = 'https://github.com/fork/project/pull/42'
        self.assertNotEqual(self.call('migrate', other, '--from-id', 'pr-42')[0], 0)
        self.initialize(other)
        self.assertEqual(self.call('inspect', other)[1]['used'], 0)

    def test_legacy_change_alias_cannot_move_history_to_a_different_pr(self):
        location = self.repo / '.git/peqa/reviews'
        location.mkdir(parents=True)
        entries = {
            'change-feature': {'redirect': 'pr-42'},
            'pr-42': {'identity': 'pr-42', 'created_at': 'fixture',
                      'passes': [{'token': f'legacy-{n}', 'status': 'imported'} for n in range(3)]}}
        ledger = location / 'budget.json'
        ledger.write_text(json.dumps({'schema': 1, 'entries': entries}))
        other = 'https://github.com/team/project/pull/43'
        self.initialize(other)
        before = ledger.read_bytes()
        rc, error = self.call('attach', other, '--from-id', 'change-feature')
        self.assertNotEqual(rc, 0)
        self.assertEqual(error['error'], 'LEGACY_PR_ASSOCIATION_REQUIRED')
        self.assertEqual(ledger.read_bytes(), before)
        rc, migrated = self.call('migrate', PR, '--from-id', 'pr-42')
        self.assertEqual(rc, 0, migrated)
        for identity in (PR, 'change-feature'):
            self.assertEqual(self.call('inspect', identity)[1]['used'], 3)
            self.assertEqual(self.call('reserve', identity, '--head', 'a' * 40)[1]['error'], 'BUDGET_EXHAUSTED')
        self.assertEqual(self.call('inspect', other)[1]['used'], 0)

    def test_initialization_cannot_reset_an_existing_budget(self):
        self.initialize(used=3)
        rc, data = self.call('init', PR, '--prior-used', '0')
        self.assertNotEqual(rc, 0)
        self.assertEqual(data['error'], 'LEDGER_ALREADY_EXISTS')


if __name__ == '__main__':
    unittest.main()
