"""blast_radius exercised against real temporary Git repositories."""

import concurrent.futures
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / 'skills/revisa/scripts/blast_radius.py'
GIT_ENV = {**{k: v for k, v in os.environ.items() if not k.startswith('GIT_')},
           'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1'}
NO_REFERENCES = {'referenced_by': {}, 'tests': {}, 'references_found': 0, 'truncated': False}


def load_helper():
    """Import the helper for unit-level checks without writing bytecode."""
    spec = importlib.util.spec_from_file_location('blast_radius_under_test', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    previous, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


class Fixture(unittest.TestCase):
    """A repository on `main`; `branch()` starts the change under review."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('symbolic-ref', 'HEAD', 'refs/heads/main')

    def git(self, *args, repo=None):
        result = subprocess.run(['git', '-C', str(repo or self.repo), '-c', 'user.name=Fixture',
                                 '-c', 'user.email=fixture@example.invalid', '-c', 'commit.gpgsign=false',
                                 *args], capture_output=True, text=True, timeout=30, env=GIT_ENV)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def write(self, relative, content, base=None):
        path = (base or self.repo) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path

    def commit(self, files, repo=None):
        for relative, content in files.items():
            self.write(relative, content, base=repo)
        self.git('add', '-A', repo=repo)
        self.git('commit', '-qm', 'fixture', '--no-verify', repo=repo)
        return self.git('rev-parse', 'HEAD', repo=repo).strip()

    def branch(self, files=None):
        self.git('switch', '-qc', 'feature')
        if files:
            self.commit(files)

    def cli(self, *args, env=None):
        result = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                                timeout=120, env=env)
        return result.returncode, result.stdout, result.stderr

    def map(self, *extra, base='main', repo=None):
        code, out, err = self.cli('map', '--repo', str(repo or self.repo), '--base', base, *extra)
        self.assertEqual((code, err), (0, ''), out)
        self.out = out
        return json.loads(out)

    def error(self, *args, env=None):
        code, out, err = self.cli(*args, env=env)
        self.assertEqual((code, out), (2, ''), err)
        return json.loads(err)['error']

    def changed(self, data):
        return {item['path']: item for item in data['changed']}


class ReferenceTests(Fixture):
    def test_consumers_outside_the_diff_are_found_by_path_module_and_name(self):
        self.commit({'src/pkg/core.py': 'def load():\n    return 1\n',
                     'docs/guide.md': 'Read src/pkg/core.py first.\n',
                     'src/app.py': 'from pkg.core import load\n',
                     'src/web.js': "const core = require('../pkg/core')\n",
                     'src/other.py': 'from . import core\n',
                     'src/unrelated.py': 'score = 1  # encore, pkg/core2, mypkg/core_utils, pkg.cores\n'})
        self.branch({'src/pkg/core.py': 'def load():\n    return 2\n'})
        data = self.map()
        self.assertEqual(data['changed'], [{
            'path': 'src/pkg/core.py', 'status': 'modified',
            'referenced_by': {'path': ['docs/guide.md'], 'module': ['src/app.py', 'src/web.js'],
                              'name': ['src/other.py']},
            'tests': {}, 'references_found': 4, 'truncated': False}])
        self.assertEqual((data['removed_definitions'], data['submodules'], data['truncated']), ([], [], []))
        self.assertEqual(data['base'], self.git('rev-parse', 'main').strip())
        self.assertEqual(data['head'], self.git('rev-parse', 'HEAD').strip())
        for code in ('DYNAMIC_AND_GENERATED_REFERENCES_NOT_SEEN', 'NAME_MATCHES_CAN_BE_FALSE_POSITIVES',
                     'OTHER_REPOSITORIES_AND_SUBMODULE_CONTENTS_NOT_SEARCHED',
                     'UNCOMMITTED_AND_UNTRACKED_CHANGES_NOT_INCLUDED'):
            self.assertIn(code, data['limits'])

    def test_file_that_mentions_itself_and_files_inside_the_diff_do_not_count(self):
        self.commit({'core.py': '# core: the core module\n', 'helper.py': 'import core\n'})
        self.branch({'core.py': '# core: still the core module\n', 'helper.py': 'import core  # changed\n'})
        data = self.changed(self.map())
        self.assertEqual({key: data['core.py'][key] for key in NO_REFERENCES}, NO_REFERENCES)
        self.assertEqual(data['helper.py']['references_found'], 0)

    def test_only_the_change_since_the_merge_base_is_mapped(self):
        self.commit({'a.py': 'A = 1\n', 'b.py': 'B = 1\n'})
        fork = self.git('rev-parse', 'HEAD').strip()
        self.branch({'a.py': 'A = 2\n'})
        self.git('switch', '-q', 'main')
        self.commit({'b.py': 'B = 2\n'})
        self.git('switch', '-q', 'feature')
        data = self.map()
        self.assertEqual(list(self.changed(data)), ['a.py'])
        self.assertEqual((data['merge_base'], data['base']), (fork, self.git('rev-parse', 'main').strip()))
        # The map covers the whole repository even when --repo names a subfolder.
        self.write('sub/keep.txt', 'x\n')
        self.assertEqual(self.map(repo=self.repo / 'sub')['changed'], data['changed'])

    def test_statuses_and_index_files_named_after_their_folder(self):
        self.commit({'gone.py': 'x = 1\n', 'ui/Button/index.ts': 'export const Button = 1\n',
                     'page.ts': "import { Button } from './ui/Button'\n", 'keep.py': 'import gone\n'})
        self.branch({'ui/Button/index.ts': 'export const Button = 2\n', 'fresh.py': 'y = 1\n',
                     'keep.py': 'import gone  # fresh\n'})
        self.git('rm', '-q', 'gone.py')
        self.commit({})
        data = self.changed(self.map())
        self.assertEqual({path: item['status'] for path, item in data.items()},
                         {'fresh.py': 'added', 'gone.py': 'deleted', 'keep.py': 'modified',
                          'ui/Button/index.ts': 'modified'})
        self.assertEqual(data['ui/Button/index.ts']['referenced_by'], {'module': ['page.ts']})

    def test_test_files_are_listed_apart(self):
        self.commit({'pay.py': 'def charge():\n    pass\n', 'app.py': 'import pay\n',
                     'tests/test_pay.py': 'import pay\n', 'web/pay.spec.ts': "import './pay'\n",
                     'attest/latest.py': 'import pay\n'})
        self.branch({'pay.py': 'def charge():\n    return 1\n'})
        item = self.changed(self.map())['pay.py']
        self.assertEqual(item['referenced_by'], {'name': ['app.py', 'attest/latest.py']})
        self.assertEqual(item['tests'], {'name': ['tests/test_pay.py', 'web/pay.spec.ts']})
        helper = load_helper()
        for path in ('tests/test_a.py', 'src/a_test.go', 'web/a.test.tsx', 'app/__tests__/a.js', 'conftest.py',
                     'java/FooTest.java', 'Tests/Core/FooTests.swift', 'e2e/login.ts', 'spec/a_spec.rb'):
            self.assertTrue(helper.is_test(path), path)
        for path in ('src/contest.py', 'src/latest.py', 'src/testimonial.ts', 'attest/a.py', 'src/protest_utils.py'):
            self.assertFalse(helper.is_test(path), path)

    def test_renamed_file_is_searched_by_its_previous_path(self):
        body = ''.join('def step_%d():\n    return %d\n\n' % (n, n) for n in range(8))
        self.commit({'old_name.py': body + 'def beta():\n    return 0\n', 'user.py': 'from old_name import beta\n',
                     'docs.md': 'See old_name.py.\n'})
        self.branch()
        self.git('mv', 'old_name.py', 'new_name.py')
        self.commit({'new_name.py': body})
        data = self.map()
        self.assertEqual(data['changed'], [{
            'path': 'new_name.py', 'status': 'renamed', 'previous_path': 'old_name.py',
            'referenced_by': {'path': ['docs.md'], 'name': ['user.py']}, 'tests': {},
            'references_found': 2, 'truncated': False}])
        self.assertEqual(data['removed_definitions'], [{
            'name': 'beta', 'kind': 'def', 'path': 'old_name.py', 'referenced_by': {'name': ['user.py']},
            'tests': {}, 'references_found': 1, 'truncated': False}])

    def test_names_with_spaces_unicode_and_glob_characters(self):
        self.commit({'src/my module ñ.py': 'VALUE = 1\n', 'src/[id] page.ts': 'export function getProps() {}\n',
                     'use it.py': "load('src/my module ñ.py')\ngetProps()\n"})
        self.branch({'src/my module ñ.py': 'VALUE = 2\n', 'src/[id] page.ts': 'export function loadProps() {}\n'})
        self.write('new file.py', 'x = 1\n')
        data = self.map('--uncommitted')
        changed = self.changed(data)
        self.assertEqual(sorted(changed), ['new file.py', 'src/[id] page.ts', 'src/my module ñ.py'])
        self.assertEqual(changed['src/my module ñ.py']['referenced_by'], {'path': ['use it.py']})
        self.assertEqual([(item['name'], item['path'], item['referenced_by']) for item in data['removed_definitions']],
                         [('getProps', 'src/[id] page.ts', {'name': ['use it.py']})])


class DefinitionTests(Fixture):
    def test_removed_or_renamed_definition_that_is_still_used(self):
        self.commit({
            'lib.py': 'def keep():\n    pass\n\ndef gone():\n    pass\n\ndef before():\n    pass\n\n'
                      'class Unused:\n    def method(self):\n        pass\n\ndef moved():\n    pass\n',
            'app.py': 'from lib import gone, keep, before, moved\nprint(gone())  # CONTENT-NOT-TO-PRINT\nmethod()\n',
            'tests/test_lib.py': 'from lib import gone\n',
            'notes.md': 'class Prose\n', 'reader.py': 'Prose = 1\n'})
        self.branch({
            'lib.py': 'def moved():\n    pass\n\ndef keep():\n    return 1\n\ndef after():\n    pass\n',
            'notes.md': 'nothing\n'})
        data = self.map()
        self.assertEqual(data['removed_definitions'], [
            {'name': 'before', 'kind': 'def', 'path': 'lib.py', 'referenced_by': {'name': ['app.py']}, 'tests': {},
             'references_found': 1, 'truncated': False},
            {'name': 'gone', 'kind': 'def', 'path': 'lib.py', 'referenced_by': {'name': ['app.py']},
             'tests': {'name': ['tests/test_lib.py']}, 'references_found': 2, 'truncated': False}])
        # Paths and names only: no line of any file reaches the output.
        self.assertNotIn('CONTENT-NOT-TO-PRINT', self.out)
        self.assertNotIn('print(', self.out)

    def test_definition_keywords_of_common_languages(self):
        before = {
            'web.ts': 'export function fetchUser() {}\nexport const LIMIT = 3\nexport default class Widget {}\n'
                      'export async function loadAll() {}\ninterface Shape {}\n  function nested() {}\n',
            'srv.go': 'func (s *Server) Handle() {}\ntype Config struct {}\nfunc Start() {}\n',
            'lex.rs': 'pub(crate) fn parse() {}\npub struct Token;\npub enum Kind {}\n',
            'Repo.kt': 'data class Account(val id: Int)\nfun openRepo() {}\n',
            'gone.rb': 'module Billing\nend\n',
            'use.txt': 'fetchUser LIMIT Widget loadAll Shape nested Handle Config Start parse Token Kind Account '
                       'openRepo Billing\n'}
        self.commit(before)
        self.branch({name: '// emptied\n' for name in before if name not in ('use.txt', 'gone.rb')})
        self.git('rm', '-q', 'gone.rb')
        self.commit({})
        found = {(item['path'], item['name'], item['kind']) for item in self.map()['removed_definitions']}
        self.assertEqual(found, {
            ('web.ts', 'fetchUser', 'function'), ('web.ts', 'LIMIT', 'const'), ('web.ts', 'Widget', 'class'),
            ('web.ts', 'loadAll', 'function'), ('web.ts', 'Shape', 'interface'),
            ('srv.go', 'Handle', 'func'), ('srv.go', 'Config', 'type'), ('srv.go', 'Start', 'func'),
            ('lex.rs', 'parse', 'fn'), ('lex.rs', 'Token', 'struct'), ('lex.rs', 'Kind', 'enum'),
            ('Repo.kt', 'Account', 'class'), ('Repo.kt', 'openRepo', 'fun'), ('gone.rb', 'Billing', 'module')})

    def test_definition_nobody_else_mentions_is_not_reported(self):
        self.commit({'lib.py': 'def lonely():\n    pass\n\ndef ab():\n    pass\n', 'app.py': 'ab()\n'})
        self.branch({'lib.py': '# lonely and ab are gone\n'})
        self.assertEqual(self.map()['removed_definitions'], [])


class UncommittedTests(Fixture):
    def setUp(self):
        super().setUp()
        self.commit({'.gitignore': 'build/\n', 'staged.py': 'S = 1\n', 'dirty.py': 'def helper():\n    pass\n',
                     'removed.py': 'R = 1\n', 'moved.py': 'M = 1\n' * 20, 'committed.py': 'C = 1\n',
                     'use.py': 'import staged, dirty, removed, moved, committed\nhelper()\n'})
        self.branch({'committed.py': 'C = 2\n'})
        self.write('staged.py', 'S = 2\n')
        self.git('add', 'staged.py')
        self.write('dirty.py', 'def other():\n    pass\n')
        (self.repo / 'removed.py').unlink()
        self.git('mv', 'moved.py', 'moved_away.py')
        (self.repo / 'moved_away.py').unlink()
        self.write('never.py', 'N = 1\n')
        self.git('add', 'never.py')
        (self.repo / 'never.py').unlink()
        self.write('fresh.py', 'F = 1\n')
        self.write('build/out.py', 'import staged\n')

    def test_without_the_option_only_commits_are_mapped(self):
        data = self.map()
        self.assertEqual((list(self.changed(data)), data['uncommitted']), (['committed.py'], False))
        self.assertEqual(data['removed_definitions'], [])

    def test_staged_unstaged_and_untracked_changes_are_mapped(self):
        index = self.repo / '.git/index'
        status = self.git('status', '--porcelain')
        before = (index.read_bytes(), index.stat().st_mtime_ns)
        data = self.map('--uncommitted')
        changed = self.changed(data)
        self.assertEqual({path: item['status'] for path, item in changed.items()},
                         {'committed.py': 'modified', 'dirty.py': 'modified', 'fresh.py': 'added',
                          'moved.py': 'deleted', 'removed.py': 'deleted', 'staged.py': 'modified'})
        self.assertEqual([path for path, item in changed.items() if item.get('untracked')], ['fresh.py'])
        for path in ('committed.py', 'dirty.py', 'moved.py', 'removed.py', 'staged.py'):
            self.assertEqual(changed[path]['referenced_by'], {'name': ['use.py']}, path)
        self.assertEqual([(item['name'], item['path']) for item in data['removed_definitions']],
                         [('helper', 'dirty.py')])
        self.assertTrue(data['uncommitted'])
        self.assertIn('WORKING_FILES_COMPARED_BY_STAT_NOT_CONTENT', data['limits'])
        self.assertNotIn('build/out.py', self.out)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            runs = list(pool.map(lambda _: self.cli('map', '--repo', str(self.repo), '--base', 'main',
                                                    '--uncommitted'), range(4)))
        self.assertEqual({(code, json.dumps(json.loads(out), sort_keys=True), err) for code, out, err in runs},
                         {(0, json.dumps(data, sort_keys=True), '')})
        # Read-only, also with concurrent runs: the index and the working tree are as they were.
        self.assertEqual((index.read_bytes(), index.stat().st_mtime_ns), before)
        self.assertFalse((self.repo / '.git/index.lock').exists())
        self.assertEqual(self.git('status', '--porcelain'), status)

    def test_no_filter_or_fsmonitor_command_runs(self):
        marker = self.root / 'command-ran'
        probe = "printf ran >> '" + str(marker) + "'; "
        hook = self.write('fsmonitor-hook', '#!/bin/sh\n' + probe + 'exit 1\n', base=self.root)
        hook.chmod(0o755)
        self.write('.gitattributes', '* filter=probe\n')
        self.git('config', 'filter.probe.clean', probe + 'cat')
        self.git('config', 'filter.probe.required', 'true')
        subprocess.run(['git', '-C', str(self.repo), 'diff', 'HEAD'], capture_output=True, env=GIT_ENV, timeout=30)
        self.assertTrue(marker.exists(), 'the fixture does not trigger the filter')
        marker.unlink()
        self.git('config', 'core.fsmonitor', str(hook))
        # An index no newer than a clean file forces Git to read that file, which is when a filter would run.
        recent = (self.repo / 'staged.py').stat().st_mtime_ns
        os.utime(self.repo / '.git/index', ns=(recent, recent))
        data = self.map('--uncommitted')
        self.assertIn('dirty.py', self.changed(data))
        self.assertFalse(marker.exists(), 'a configured command ran')


class SubmoduleTests(Fixture):
    def test_changed_gitlink_is_listed_and_not_entered(self):
        library = self.root / 'library'
        library.mkdir()
        self.git('init', '-q', repo=library)
        old = self.commit({'inner.py': 'x = 1\n'}, repo=library)
        self.commit({'core.py': 'def run():\n    pass\n', 'app.py': 'import core\n'})
        self.git('-c', 'protocol.file.allow=always', 'submodule', '--quiet', 'add', str(library), 'vendor/lib')
        self.commit({})
        self.git('switch', '-qc', 'feature')
        new = self.commit({'consumer.py': 'import core\n'}, repo=self.repo / 'vendor/lib')
        self.commit({'core.py': 'def run():\n    return 1\n'})
        self.git('config', 'submodule.recurse', 'true')
        # Sanity: with this configuration a plain search does enter the submodule.
        self.assertIn('vendor/lib/consumer.py', self.git('grep', '-l', 'core', 'HEAD'))
        for extra in ((), ('--uncommitted',)):
            data = self.map(*extra)
            self.assertEqual(data['submodules'], [{'path': 'vendor/lib', 'status': 'modified', 'old': old, 'new': new}])
            self.assertEqual(data['changed'], [{'path': 'core.py', 'status': 'modified',
                                                'referenced_by': {'name': ['app.py']}, 'tests': {},
                                                'references_found': 1, 'truncated': False}])
            self.assertNotIn('consumer.py', self.out)

    def test_untracked_nested_repository_is_listed_without_its_files(self):
        self.commit({'core.py': 'x = 1\n'})
        self.branch()
        nested = self.repo / 'tools/nested'
        nested.mkdir(parents=True)
        self.git('init', '-q', repo=nested)
        self.write('tools/nested/inside.py', 'import core\n')
        data = self.map('--uncommitted')
        self.assertEqual(data['submodules'], [{'path': 'tools/nested', 'status': 'added', 'old': None, 'new': None,
                                               'untracked': True}])
        self.assertEqual(data['changed'], [])


class LimitTests(Fixture):
    def build(self, **constants):
        helper = load_helper()
        with patch.multiple(helper, **constants):
            return helper, helper.build(str(self.repo), 'main')

    def test_references_per_file_are_capped_and_counted(self):
        files = {'c%02d.py' % n: 'import target\n' for n in range(23)}
        self.commit({'target.py': 'T = 1\n', 'tests/test_a.py': 'import target\n',
                     'tests/test_b.py': 'import target\n', **files})
        self.branch({'target.py': 'T = 2\n'})
        data = self.map()
        item = data['changed'][0]
        self.assertEqual(item['referenced_by'], {'name': ['c%02d.py' % n for n in range(20)]})
        self.assertEqual((item['tests'], item['references_found'], item['truncated']), ({}, 25, True))
        self.assertEqual(data['truncated'], ['REFERENCES_PER_FILE'])

    def test_total_references_changed_files_and_definitions_are_capped(self):
        self.commit({'one.py': 'def first():\n    pass\n\ndef second():\n    pass\n', 'two.py': 'import one\n',
                     'a.py': 'import one, two\nfirst()\n', 'b.py': 'import one, two\nsecond()\n'})
        self.branch({'one.py': '# emptied\n', 'two.py': 'import one  # changed\n'})
        _, data = self.build(MAX_REFERENCES=3)
        self.assertEqual([(item['referenced_by'], item['references_found'], item['truncated'])
                          for item in data['changed']],
                         [({'name': ['a.py', 'b.py']}, 2, False), ({'name': ['a.py']}, 2, True)])
        self.assertEqual([(item['name'], item['references_found'], item['truncated'])
                          for item in data['removed_definitions']], [('first', 1, True), ('second', 1, True)])
        self.assertEqual(data['truncated'], ['REFERENCES_TOTAL'])
        _, data = self.build(MAX_CHANGED=1)
        # The file past the cap is still part of the diff, so it is no consumer of the first.
        self.assertEqual([(item['path'], item['referenced_by']) for item in data['changed']],
                         [('one.py', {'name': ['a.py', 'b.py']})])
        self.assertEqual(data['truncated'], ['CHANGED_FILES'])
        _, data = self.build(MAX_DEFINITIONS=1)
        self.assertEqual([item['name'] for item in data['removed_definitions']], ['first'])
        self.assertEqual(data['truncated'], ['REMOVED_DEFINITIONS'])

    def test_time_budget_stops_the_searches_and_says_so(self):
        self.commit({'one.py': 'def first():\n    pass\n', 'a.py': 'import one\nfirst()\n'})
        self.branch({'one.py': '# emptied\n'})
        _, data = self.build(MAX_SECONDS=-1)
        self.assertEqual(data['changed'], [{'path': 'one.py', 'status': 'modified', 'referenced_by': {}, 'tests': {},
                                            'references_found': None, 'truncated': True}])
        self.assertEqual((data['removed_definitions'], data['truncated']), ([], ['TIME_BUDGET']))

    def test_git_output_is_capped(self):
        consumers = {'consumer_%s_%02d.py' % ('x' * 40, n): 'import target\n' for n in range(30)}
        self.commit({'target.py': 'T = 1\n', **consumers})
        self.branch({'target.py': 'T = 2\n'})
        _, data = self.build(MAX_OUTPUT=600)
        item = data['changed'][0]
        listed = item['referenced_by']['name']
        self.assertTrue(0 < len(listed) < 30 and set(listed) <= set(consumers), listed)
        self.assertEqual((item['truncated'], data['truncated']), (True, ['GIT_OUTPUT']))
        self.commit({'extra_%02d.py' % n: 'x = 1\n' for n in range(10)})
        helper = load_helper()
        with patch.object(helper, 'MAX_OUTPUT', 600), self.assertRaises(helper.CheckError) as raised:
            helper.build(str(self.repo), 'main')
        self.assertEqual(str(raised.exception), 'GIT_OUTPUT_TOO_LARGE')

    def test_each_git_call_has_a_time_limit(self):
        self.commit({'a.py': 'x = 1\n'})
        fake = self.write('bin/git', '#!/bin/sh\nexec sleep 20\n', base=self.root)
        fake.chmod(0o755)
        helper = load_helper()
        started = time.monotonic()
        with patch.object(helper, 'TIMEOUT', 0.3), patch.dict(os.environ, {'PATH': str(fake.parent) + os.pathsep
                                                                              + os.environ.get('PATH', '')}):
            with self.assertRaises(helper.CheckError) as raised:
                helper.build(str(self.repo), 'main')
        self.assertEqual(str(raised.exception), 'TIMEOUT')
        self.assertLess(time.monotonic() - started, 10)


class ErrorTests(Fixture):
    def run_map(self, repo, base, env=None):
        return self.error('map', '--repo', str(repo), '--base=' + base, env=env)

    def test_repository_and_base_errors(self):
        plain = self.root / 'plain'
        plain.mkdir()
        self.assertEqual(self.run_map(plain, 'HEAD'), 'GIT_REPOSITORY_REQUIRED')
        self.assertEqual(self.run_map(self.root / 'absent', 'HEAD'), 'GIT_REPOSITORY_REQUIRED')
        self.assertEqual(self.run_map('', 'HEAD'), 'GIT_REPOSITORY_REQUIRED')
        self.assertEqual(self.run_map(self.repo, 'HEAD'), 'BAD_BASE')  # no commits yet
        self.commit({'a.py': 'x = 1\n'})
        for base in ('nope', 'HEAD..HEAD', '', 'ma\tin', 'x' * 257, '-x', '--output=' + str(self.root / 'written')):
            self.assertEqual(self.run_map(self.repo, base), 'BAD_BASE', base)
        self.assertFalse((self.root / 'written').exists())

    def test_option_looking_base_never_reaches_git(self):
        self.commit({'a.py': 'x = 1\n'})
        helper = load_helper()
        calls = []
        original = helper.run

        def recording(top, args):
            calls.append(list(args))
            return original(top, args)

        with patch.object(helper, 'run', recording), self.assertRaises(helper.CheckError) as raised:
            helper.build(str(self.repo), '--all')
        self.assertEqual(str(raised.exception), 'BAD_BASE')
        self.assertEqual(calls, [['rev-parse', '--show-toplevel']])

    def test_unrelated_history_has_no_merge_base(self):
        self.commit({'a.py': 'x = 1\n'})
        self.git('switch', '-q', '--orphan', 'island')
        self.commit({'b.py': 'y = 1\n'})
        self.assertEqual(self.run_map(self.repo, 'main'), 'MERGE_BASE_NOT_FOUND')

    def test_usage_errors(self):
        self.commit({'a.py': 'x = 1\n'})
        repo = str(self.repo)
        for args in ((), ('map',), ('map', '--repo', repo), ('map', '--base', 'main'),
                     ('other', '--repo', repo, '--base', 'main'), ('map', '--repo', repo, '--base', '-x'),
                     ('map', '--repo', repo, '--base', 'main', '--unknown'),
                     ('map', '--repo', repo, '--base', 'main', 'extra')):
            self.assertEqual(self.error(*args), 'INVALID_ARGUMENTS', args)

    def test_caller_git_variables_do_not_redirect_the_search(self):
        other = self.root / 'other'
        other.mkdir()
        self.git('init', '-q', repo=other)
        self.commit({'elsewhere.py': 'x = 1\n'}, repo=other)
        self.commit({'core.py': 'x = 1\n', 'app.py': 'import core\n'})
        self.branch({'core.py': 'x = 2\n'})
        expected = self.map()
        env = {**os.environ, 'GIT_DIR': str(other / '.git'), 'GIT_WORK_TREE': str(other)}
        code, out, err = self.cli('map', '--repo', str(self.repo), '--base', 'main', env=env)
        self.assertEqual((code, err, json.loads(out or 'null')), (0, '', expected))

    def test_git_unavailable(self):
        self.commit({'a.py': 'x = 1\n'})
        self.assertEqual(self.run_map(self.repo, 'main', env={'PATH': str(self.root / 'empty-bin')}),
                         'GIT_UNAVAILABLE')


class TransportTests(Fixture):
    """A lazy fetch from a promisor remote must not reach any transport."""

    def setUp(self):
        super().setUp()
        self.marker = self.root / 'remote-ran'
        self.commit({'core.py': 'x = 1\n', 'app.py': 'import core\n'})
        blob = self.git('rev-parse', 'HEAD:app.py').strip()
        self.branch({'core.py': 'x = 2\n'})
        probe = self.write('remote.sh', "#!/bin/sh\nprintf ran >> '" + str(self.marker) + "'\nexit 1\n",
                           base=self.root)
        probe.chmod(0o755)
        self.git('config', 'remote.origin.url', 'ext::' + str(probe))
        self.git('config', 'remote.origin.promisor', 'true')
        # A local per-protocol setting outranks protocol.allow=never.
        self.git('config', 'protocol.ext.allow', 'always')
        (self.repo / '.git/objects' / blob[:2] / blob[2:]).unlink()

    def test_helper_never_runs_the_remote(self):
        subprocess.run(['git', '-C', str(self.repo), '-c', 'protocol.allow=never', 'grep', '-l', 'core', 'HEAD'],
                       capture_output=True, env=GIT_ENV, timeout=30)
        self.assertTrue(self.marker.exists(), 'the fixture does not trigger a lazy fetch')
        self.marker.unlink()
        self.assertEqual(self.error('map', '--repo', str(self.repo), '--base', 'main'), 'GIT_COMMAND_FAILED')
        self.assertFalse(self.marker.exists(), 'the remote command ran')

    def test_transport_ban_holds_without_the_lazy_fetch_guard(self):
        # Git before 2.44 ignores GIT_NO_LAZY_FETCH; GIT_ALLOW_PROTOCOL must still stop the fetch.
        helper = load_helper()
        original = helper.environment

        def without(*names):
            def environment():
                env = original()
                for name in names:
                    env.pop(name)
                return env
            return environment

        with patch.object(helper, 'environment', without('GIT_NO_LAZY_FETCH')):
            with self.assertRaises(helper.CheckError):
                helper.build(str(self.repo), 'main')
        self.assertFalse(self.marker.exists())
        # Control: without both guards the same call does run the remote command.
        with patch.object(helper, 'environment', without('GIT_NO_LAZY_FETCH', 'GIT_ALLOW_PROTOCOL')):
            with self.assertRaises(helper.CheckError):
                helper.build(str(self.repo), 'main')
        self.assertTrue(self.marker.exists())


if __name__ == '__main__':
    unittest.main()
