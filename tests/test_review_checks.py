"""Portable review checks exercised against real, isolated Git repositories."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/review_checks.py'


class ReviewChecksTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / 'repo'
        self.make_repo(self.repo)

    def git(self, *args, repo=None):
        result = subprocess.run(['git', '-C', str(repo or self.repo),
                                 '-c', 'protocol.file.allow=always',
                                 '-c', 'user.name=Fixture',
                                 '-c', 'user.email=fixture@example.invalid', *args],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def make_repo(self, path):
        path.mkdir()
        self.git('init', '-q', repo=path)
        (path / 'fixture.txt').write_text('fixture\n')
        self.git('add', '.', repo=path)
        self.git('commit', '-qm', 'fixture', repo=path)

    def cli(self, action, *args, report=None, ok=True):
        if report is not None:
            report_path = self.root / 'report.json'
            report_path.write_text(json.dumps(report))
            args = (*args, '--report', str(report_path))
        result = subprocess.run([sys.executable, str(SCRIPT), action, '--repo', str(self.repo), *args],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0 if ok else 2, result.stdout + result.stderr)
        return result

    def snapshot(self):
        return json.loads(self.cli('snapshot').stdout)

    def report(self):
        return {
            'schema_version': 1, 'language': 'es',
            'recommendation': 'approval_recommended', 'minimums': 'met',
            'requester': None, 'reason': 'Checks pertinentes completados.',
            'criteria': {key: {'status': 'met', 'evidence': 'Evidencia registrada.'}
                         for key in ('requirements', 'tests', 'security', 'compatibility')},
            'findings': [],
            'tests': [{'command': 'python3 -m unittest', 'cwd': '.',
                       'status': 'passed', 'evidence': '12 pruebas, código 0, fixture local.'}],
            'security': {'standards': ['NIST SSDF 1.1'],
                         'controls': ['PW.7: validación de rutas revisada.'], 'limitations': []},
            'impact': 'Acotado a la herramienta local.', 'scope': self.snapshot(),
            'trace': {'models': ['Fixture reviewer, esfuerzo declarado'],
                      'route': 'local', 'cr': ['change-fixture: CR 1/3']},
        }

    def validate(self, report, ok=True):
        return json.loads(self.cli('validate', report=report, ok=ok).stdout)

    def test_cli_and_api_accept_current_complete_report(self):
        report = self.report()
        self.assertEqual(self.validate(report), {'valid': True, 'errors': []})
        spec = importlib.util.spec_from_file_location('review_checks', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.snapshot(self.repo), report['scope'])
        self.assertTrue(module.validate_report(report, self.repo)['valid'])

    def test_approval_contradicts_failed_tests_and_open_material_findings(self):
        for field in ('tests', 'findings', 'criteria', 'minimums'):
            report = self.report()
            if field == 'tests':
                report['tests'][0]['status'] = 'failed'
            elif field == 'findings':
                report['findings'] = [{'id': 'F1', 'material': True, 'status': 'open',
                                       'evidence': 'Requisito incumplido.'}]
            elif field == 'criteria':
                report['criteria']['security']['status'] = 'not_verified'
            else:
                report['minimums'] = 'not_met'
            with self.subTest(field=field):
                self.assertIn('RECOMMENDATION_CONTRADICTION', self.validate(report, ok=False)['errors'])

    def test_documentary_change_can_justify_no_applicable_functional_tests(self):
        report = self.report()
        report['criteria']['tests'] = {'status': 'not_applicable',
                                      'evidence': 'Solo prosa; sin comandos ni cambios funcionales.'}
        report['tests'][0].update(status='no_tests', command='No applicable functional command',
                                  evidence='Inspección del diff y referencias; cambio solo documental.')
        self.assertTrue(self.validate(report)['valid'])
        report['criteria']['tests']['status'] = 'met'
        self.assertFalse(self.validate(report, ok=False)['valid'])
        report['criteria']['tests']['status'] = 'not_applicable'
        for status in ('partial', 'not_run'):
            report['tests'][0]['status'] = status
            self.assertFalse(self.validate(report, ok=False)['valid'])

    def test_git_metadata_symlink_is_not_followed(self):
        metadata = self.repo / '.git'
        actual = self.root / 'metadata'
        metadata.rename(actual)
        metadata.symlink_to(actual, target_is_directory=True)
        result = self.cli('snapshot', ok=False)
        self.assertIn('REPOSITORY_PATH_UNSAFE', json.loads(result.stdout)['errors'])

    def test_gitfile_cannot_redirect_through_a_symlink(self):
        metadata = self.repo / '.git'
        actual = self.root / 'metadata'
        metadata.rename(actual)
        redirect = self.root / 'redirect'
        redirect.symlink_to(actual, target_is_directory=True)
        metadata.write_text('gitdir: ../redirect\n')
        result = self.cli('snapshot', ok=False)
        self.assertIn('REPOSITORY_PATH_UNSAFE', json.loads(result.stdout)['errors'])

    def test_linked_worktree_metadata_outside_the_root_is_supported(self):
        worktree = self.root / 'worktree'
        self.git('worktree', 'add', '-q', '--detach', str(worktree))
        self.repo = worktree
        report = self.report()
        self.assertTrue(self.validate(report)['valid'])
        self.assertEqual(report['scope']['root'], str(worktree))

    def test_requires_security_and_minimum_evidence(self):
        for mutate in (lambda r: r.pop('security'),
                       lambda r: r['criteria']['security'].update(evidence='  '),
                       lambda r: r['security'].update(controls=[]),
                       lambda r: r['criteria'].pop('tests')):
            report = self.report()
            mutate(report)
            self.assertFalse(self.validate(report, ok=False)['valid'])

    def test_strict_schema_rejects_wrong_types_and_unknown_fields(self):
        for field, value in [('schema_version', True), ('language', 'fr'),
                             ('minimums', []), ('requester', {'name': 'X'}),
                             ('trace', []), ('findings', [{'material': 1, 'status': 'open'}]),
                             ('extra', 'ignored?')]:
            report = self.report()
            report[field] = value
            with self.subTest(field=field):
                self.assertFalse(self.validate(report, ok=False)['valid'])

    def test_content_index_head_and_untracked_each_invalidate_scope(self):
        for change in ('content', 'index', 'head', 'untracked'):
            report = self.report()
            if change == 'content':
                (self.repo / 'fixture.txt').write_text('changed\n')
            elif change == 'index':
                self.git('add', 'fixture.txt')
            elif change == 'head':
                self.git('commit', '-qm', 'changed')
            else:
                (self.repo / 'new.txt').write_text('untracked\n')
            with self.subTest(change=change):
                errors = self.validate(report, ok=False)['errors']
                self.assertIn('SCOPE_STALE', errors)

    def test_scope_stale_is_invalid_even_when_changes_required(self):
        report = self.report()
        report.update(recommendation='changes_required', minimums='not_met')
        report['criteria']['requirements']['status'] = 'not_met'
        (self.repo / 'fixture.txt').write_text('new state\n')
        self.assertIn('SCOPE_STALE', self.validate(report, ok=False)['errors'])

    def test_concurrent_untracked_creation_cannot_validate_old_evidence(self):
        report = self.report()
        spec = importlib.util.spec_from_file_location('review_checks_race', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original = module._git
        changed = False

        def race(root, args, *positional, **kwargs):
            nonlocal changed
            result = original(root, args, *positional, **kwargs)
            if '--others' in args and not changed:
                changed = True
                (self.repo / 'new.txt').write_text('created during capture\n')
            return result

        with patch.object(module, '_git', side_effect=race):
            result = module.validate_report(report, self.repo)
        self.assertFalse(result['valid'])
        self.assertIn('SNAPSHOT_CHANGED_DURING_READ', result['errors'])

    def test_concurrent_edit_after_file_read_cannot_validate_old_evidence(self):
        report = self.report()
        spec = importlib.util.spec_from_file_location('review_checks_race', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original = module._record_file

        def race(*args, **kwargs):
            result = original(*args, **kwargs)
            (self.repo / 'fixture.txt').write_text('edited after read\n')
            return result

        with patch.object(module, '_record_file', side_effect=race):
            result = module.validate_report(report, self.repo)
        self.assertFalse(result['valid'])
        self.assertIn('SNAPSHOT_CHANGED_DURING_READ', result['errors'])

    def test_final_check_covers_previously_captured_nested_submodules(self):
        nested = self.nested_submodules()
        report = self.report()
        spec = importlib.util.spec_from_file_location('review_checks_race', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original = module._capture_repository

        def race(root, relative, *args, **kwargs):
            result = original(root, relative, *args, **kwargs)
            if relative == '.':
                (nested / 'fixture.txt').write_text('late nested edit\n')
            return result

        with patch.object(module, '_capture_repository', side_effect=race):
            result = module.validate_report(report, self.repo)
        self.assertFalse(result['valid'])
        self.assertIn('SNAPSHOT_CHANGED_DURING_READ', result['errors'])

    def test_snapshot_is_content_stable_and_ignores_ignored_files_only(self):
        (self.repo / '.gitignore').write_text('ignored.txt\n')
        first = self.snapshot()
        os.utime(self.repo / 'fixture.txt', None)
        (self.repo / 'ignored.txt').write_text('secret fixture\n')
        self.assertEqual(self.snapshot(), first)
        self.assertIn('ignored_files', first['exclusions'])
        self.assertNotIn('secret fixture', json.dumps(first))
        (self.repo / '.peqa').mkdir()
        (self.repo / '.peqa' / 'ordinary.txt').write_text('must count\n')
        self.assertNotEqual(self.snapshot(), first)

    def nested_submodules(self):
        leaf = self.root / 'leaf'
        child = self.root / 'child'
        self.make_repo(leaf)
        self.make_repo(child)
        self.git('submodule', 'add', '-q', str(leaf), 'nested', repo=child)
        self.git('commit', '-qam', 'nested', repo=child)
        self.git('submodule', 'add', '-q', str(child), 'child')
        self.git('commit', '-qam', 'child')
        self.git('submodule', 'update', '--init', '--recursive')
        return self.repo / 'child' / 'nested'

    def test_nested_submodules_pin_current_sha_dirty_and_missing_state(self):
        nested = self.nested_submodules()
        report = self.report()
        self.assertTrue(report['scope']['coverage']['complete'])
        leaf = next(item for item in report['scope']['submodules'] if item['path'] == 'child/nested')
        self.assertEqual(leaf['pinned_head'], self.git('rev-parse', 'HEAD', repo=nested))
        (nested / 'fixture.txt').write_text('dirty nested\n')
        self.assertIn('SCOPE_STALE', self.validate(report, ok=False)['errors'])
        self.git('commit', '-qam', 'new nested', repo=nested)
        changed = self.snapshot()
        leaf = next(item for item in changed['submodules'] if item['path'] == 'child/nested')
        self.assertNotEqual(leaf['pinned_head'], leaf['current_head'])
        self.assertEqual(leaf['state'], 'changed')
        shutil.rmtree(nested)
        report['scope'] = self.snapshot()
        self.assertFalse(report['scope']['coverage']['complete'])
        self.assertIn('COVERAGE_INCOMPLETE', self.validate(report, ok=False)['errors'])
        report.update(recommendation='review_incomplete', minimums='not_verified')
        report['criteria']['compatibility']['status'] = 'not_verified'
        self.assertTrue(self.validate(report)['valid'])

    def test_uninitialized_nested_submodule_is_not_reported_as_complete(self):
        self.nested_submodules()
        self.git('submodule', 'deinit', '-f', '--', 'nested', repo=self.repo / 'child')
        state = self.snapshot()
        self.assertFalse(state['coverage']['complete'])
        leaf = next(item for item in state['submodules'] if item['path'] == 'child/nested')
        self.assertEqual(leaf['state'], 'missing')

    def test_document_paths_never_select_another_repository(self):
        report = self.report()
        outside = self.root / 'other'
        self.make_repo(outside)
        report['scope']['root'] = str(outside)
        self.assertIn('SCOPE_STALE', self.validate(report, ok=False)['errors'])
        for cwd in ('../other', str(outside), 'a/../../other', '.git'):
            report = self.report()
            report['tests'][0]['cwd'] = cwd
            self.assertFalse(self.validate(report, ok=False)['valid'])

    def test_symlink_outside_and_special_files_are_not_read(self):
        secret = self.root / 'secret.txt'
        secret.write_text('DO_NOT_OUTPUT_OR_HASH_THIS_SECRET\n')
        (self.repo / 'link').symlink_to(secret)
        (self.repo / 'dirlink').symlink_to(self.root, target_is_directory=True)
        os.mkfifo(self.repo / 'pipe')
        scope = self.snapshot()
        self.assertFalse(scope['coverage']['complete'])
        self.assertNotIn('DO_NOT_OUTPUT', json.dumps(scope))
        report = self.report()
        self.assertIn('COVERAGE_INCOMPLETE', self.validate(report, ok=False)['errors'])

    def test_tracked_parent_replaced_by_symlink_is_not_followed(self):
        directory = self.repo / 'data'
        directory.mkdir()
        (directory / 'item').write_text('tracked\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'data')
        shutil.rmtree(directory)
        directory.symlink_to(self.root, target_is_directory=True)
        (self.root / 'item').write_text('outside secret\n')
        scope = self.snapshot()
        self.assertFalse(scope['coverage']['complete'])
        self.assertNotIn('outside secret', json.dumps(scope))

    def test_render_es_en_has_attribution_and_explicit_limits(self):
        report = self.report()
        spanish = self.cli('render', '--language', 'es', report=report).stdout
        self.assertIn('Aprobación sugerida', spanish)
        self.assertIn('Persona solicitante no identificada', spanish)
        self.assertIn('ignorados', spanish)
        self.assertIn('no ejecuta', spanish)
        report['requester'] = '<script>alert(1)</script>'
        english = self.cli('render', '--language', 'en', report=report).stdout
        self.assertIn('Approval recommended', english)
        self.assertIn('AI-generated on behalf of', english)
        self.assertNotIn('<script>', english)
        report['tests'][0]['status'] = 'failed'
        invalid = self.cli('render', '--language', 'en', report=report, ok=False)
        self.assertNotIn('# Consolidated review', invalid.stdout)

    def test_render_preserves_unknown_file_coverage(self):
        (self.repo / 'unsafe-link').symlink_to(self.root / 'outside')
        report = json.loads(self.cli('template').stdout)
        rendered = self.cli('render', report=report).stdout
        self.assertIn('incompleta', rendered)
        self.assertIn('SYMLINK', rendered)

    def test_malformed_duplicate_and_oversized_json_fail_without_traceback(self):
        path = self.root / 'bad.json'
        for content in ('{', '{"schema_version":1,"schema_version":2}', 'x' * (1024 * 1024 + 1)):
            path.write_text(content)
            result = self.cli('validate', '--report', str(path), ok=False)
            self.assertFalse(json.loads(result.stdout)['valid'])
            self.assertNotIn('Traceback', result.stderr)

    def test_report_symlinks_and_fifo_cannot_supply_report_content(self):
        source = self.root / 'source.json'
        source.write_text(json.dumps(self.report()))
        link = self.root / 'link.json'
        link.symlink_to(source)
        parent = self.root / 'linked'
        parent.symlink_to(self.root, target_is_directory=True)
        pipe = self.root / 'report-pipe'
        os.mkfifo(pipe)
        for path in (link, parent / 'source.json', pipe):
            result = self.cli('validate', '--report', str(path), ok=False)
            self.assertFalse(json.loads(result.stdout)['valid'])

    def test_sparse_missing_content_and_standalone_repositories_are_unknown(self):
        self.git('update-index', '--skip-worktree', 'fixture.txt')
        (self.repo / 'fixture.txt').unlink()
        report = self.report()
        self.assertIn('COVERAGE_INCOMPLETE', self.validate(report, ok=False)['errors'])
        self.make_repo(self.repo / 'external')
        scope = self.snapshot()
        self.assertFalse(scope['coverage']['complete'])
        self.assertEqual(len(scope['repositories']), 1)

    def test_strict_types_are_enforced_inside_the_captured_scope(self):
        report = self.report()
        report['scope']['schema_version'] = True
        self.assertIn('SCOPE_STALE', self.validate(report, ok=False)['errors'])

    def test_environment_and_fsmonitor_cannot_redirect_or_execute(self):
        outside = self.root / 'other'
        self.make_repo(outside)
        monitor = self.root / 'monitor.sh'
        marker = self.root / 'should-not-exist'
        monitor.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\n')
        monitor.chmod(0o755)
        self.git('config', 'core.fsmonitor', str(monitor))
        env = dict(os.environ, GIT_DIR=str(outside / '.git'), GIT_WORK_TREE=str(outside))
        result = subprocess.run([sys.executable, str(SCRIPT), 'snapshot', '--repo', str(self.repo)],
                                env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['root'], str(self.repo))
        self.assertFalse(marker.exists())

    def test_template_is_valid_incomplete_and_does_not_write_repository(self):
        before = self.snapshot()
        report = json.loads(self.cli('template', '--language', 'en').stdout)
        self.assertEqual(report['recommendation'], 'review_incomplete')
        self.assertTrue(self.validate(report)['valid'])
        self.assertEqual(before, self.snapshot())


if __name__ == '__main__':
    unittest.main()
