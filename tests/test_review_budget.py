import concurrent.futures
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'skills/revisa/scripts/review_budget.py'
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

    def test_depth_model_and_effort_persist_in_ledger_and_across_lifecycle(self):
        self.initialize('change-depth', used=0)
        rc, first = self.call('reserve', 'change-depth', '--head', 'a' * 40,
                              '--depth', 'lite', '--model', 'Sol 6.2', '--effort', 'medium')
        self.assertEqual(rc, 0, first)
        self.assertEqual(first['depth'], 'lite')
        self.assertEqual(first['model'], 'Sol 6.2')
        self.assertEqual(first['effort'], 'medium')
        rc, verified = self.call('verify', 'change-depth', '--head', 'a' * 40, '--token', first['token'])
        self.assertEqual(rc, 0, verified)
        self.assertEqual(verified['depth'], 'lite')
        rc, claimed = self.call('claim', 'change-depth', '--head', 'a' * 40, '--token', first['token'])
        self.assertEqual(rc, 0, claimed)
        self.assertEqual(claimed['depth'], 'lite')
        rc, finished = self.call('finish', 'change-depth', '--token', first['token'], '--status', 'completed')
        self.assertEqual(rc, 0, finished)
        self.assertEqual(finished['passes'][0]['depth'], 'lite')
        self.assertEqual(finished['passes'][0]['model'], 'Sol 6.2')

        self.initialize(PR, used=0)
        rc, attached = self.call('attach', PR, '--from-id', 'change-depth')
        self.assertEqual(rc, 0, attached)
        self.assertEqual(attached['passes'][0]['depth'], 'lite')

        rc, second = self.call('reserve', PR, '--head', 'b' * 40,
                               '--depth', 'deep', '--model', 'Astra 6.2', '--effort', 'high')
        self.assertEqual(rc, 0, second)
        self.assertEqual(second['depth'], 'deep')
        inspected = self.call('inspect', PR)[1]
        self.assertEqual([p['depth'] for p in inspected['passes']], ['lite', 'deep'])
        self.assertEqual([p['model'] for p in inspected['passes']], ['Sol 6.2', 'Astra 6.2'])

    def test_invalid_depth_and_control_char_model_are_rejected(self):
        self.initialize(PR, used=0)
        bad_depth = subprocess.run(
            [sys.executable, str(SCRIPT), 'reserve', '--repo', str(self.repo),
             '--pr-url', PR, '--head', 'a' * 40, '--depth', 'full'],
            capture_output=True, text=True,
        )
        self.assertNotEqual(bad_depth.returncode, 0)
        rc, bad_model = self.call('reserve', PR, '--head', 'a' * 40, '--depth', 'deep', '--model', 'bad\nmodel')
        self.assertNotEqual(rc, 0)
        self.assertEqual(bad_model['error'], 'INVALID_MODEL')

    def ledger_path(self):
        return self.repo / '.git' / 'peqa' / 'reviews' / 'budget.json'

    def test_ledger_written_before_depth_existed_keeps_working(self):
        # Shape written by releases that knew nothing of depth, model or effort.
        self.initialize(PR, used=1)
        _, old = self.call('reserve', PR, '--head', 'a' * 40)
        ledger = json.loads(self.ledger_path().read_text())
        entry = next(iter(ledger['entries'].values()))
        for item in entry['passes']:
            self.assertFalse({'depth', 'model', 'effort'} & set(item))
        self.assertNotIn('depth', old)

        rc, verified = self.call('verify', PR, '--head', 'a' * 40, '--token', old['token'])
        self.assertEqual((rc, verified), (0, {'valid': True, 'identity': verified['identity'], 'used': 2, 'limit': 3}))
        rc, claimed = self.call('claim', PR, '--head', 'a' * 40, '--token', old['token'])
        self.assertEqual(rc, 0, claimed)
        self.assertNotIn('depth', claimed)
        rc, finished = self.call('finish', PR, '--token', old['token'], '--status', 'completed')
        self.assertEqual(rc, 0, finished)

        rc, new = self.call('reserve', PR, '--head', 'b' * 40, '--depth', 'deep', '--model', 'Astra 6.2')
        self.assertEqual(rc, 0, new)
        self.assertEqual((new['used'], new['remaining']), (3, 0))
        inspected = self.call('inspect', PR)[1]
        self.assertEqual([item.get('depth') for item in inspected['passes']], [None, None, 'deep'])
        self.assertEqual([item['status'] for item in inspected['passes']], ['imported', 'completed', 'reserved'])
        self.assertEqual(self.call('reserve', PR, '--head', 'c' * 40, '--depth', 'lite')[1]['error'], 'BUDGET_EXHAUSTED')

    def test_legacy_pr_number_ledger_migrates_without_new_fields(self):
        directory = self.ledger_path().parent
        directory.mkdir(parents=True)
        self.ledger_path().write_text(json.dumps({'schema': 1, 'entries': {'pr-42': {
            'identity': 'pr-42', 'pr_url': None, 'created_at': '2026-10-01T00:00:00+00:00',
            'passes': [{'token': 'legacy-token', 'status': 'completed', 'head': 'a' * 40,
                        'reserved_at': '2026-10-01T00:00:00+00:00'}]}}}))
        rc, migrated = self.call('migrate', PR, '--from-id', 'pr-42')
        self.assertEqual(rc, 0, migrated)
        self.assertEqual(migrated['used'], 1)
        rc, reserved = self.call('reserve', PR, '--head', 'b' * 40, '--depth', 'lite', '--effort', 'high')
        self.assertEqual(rc, 0, reserved)
        self.assertEqual([item.get('depth') for item in reserved['passes']], [None, 'lite'])
        self.assertEqual(reserved['passes'][1]['effort'], 'high')
        self.assertNotIn('model', reserved['passes'][1])

    def test_empty_model_or_effort_records_nothing_and_bad_labels_do_not_consume(self):
        self.initialize(PR, used=0)
        rc, reserved = self.call('reserve', PR, '--head', 'a' * 40, '--depth', 'deep', '--model', '', '--effort', '   ')
        self.assertEqual(rc, 0, reserved)
        self.assertEqual(reserved['depth'], 'deep')
        self.assertNotIn('model', reserved)
        self.assertNotIn('effort', reserved)
        self.assertFalse({'model', 'effort'} & set(reserved['passes'][0]))
        for flag, value, code in (('--model', 'x' * 257, 'INVALID_MODEL'), ('--effort', 'hi\x7fgh', 'INVALID_EFFORT'),
                                  ('--effort', 'a\tb', 'INVALID_EFFORT')):
            rc, data = self.call('reserve', PR, '--head', 'b' * 40, flag, value)
            with self.subTest(flag=flag, code=code):
                self.assertNotEqual(rc, 0)
                self.assertEqual(data['error'], code)
        self.assertEqual(self.call('inspect', PR)[1]['used'], 1)
        rc, trimmed = self.call('reserve', PR, '--head', 'b' * 40, '--model', '  Neon 4  ')
        self.assertEqual((rc, trimmed['model']), (0, 'Neon 4'))


if __name__ == '__main__':
    unittest.main()
