"""ui-design checks exercised against isolated Git repositories and plain diffs."""

import concurrent.futures
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / 'skills/ui-design/scripts/ui_checks.py'
GIT_ENV = {**{k: v for k, v in os.environ.items() if not k.startswith('GIT_')},
           'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1'}


def load_helper():
    """Import the helper for unit-level checks without writing bytecode."""
    spec = importlib.util.spec_from_file_location('ui_checks_under_test', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    previous, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')

    def git(self, *args):
        result = subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=Fixture',
                                 '-c', 'user.email=fixture@example.invalid', '-c', 'commit.gpgsign=false',
                                 *args], capture_output=True, text=True, timeout=20, env=GIT_ENV)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def write(self, relative, content, base=None):
        path = (base or self.repo) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding='utf-8')
        return path

    def commit(self, files):
        for relative, content in files.items():
            self.write(relative, content)
        self.git('add', '-A')
        self.git('commit', '-qm', 'fixture', '--no-verify')

    def cli(self, *args, env=None, cwd=None):
        result = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                                timeout=60, env=env, cwd=cwd)
        self.assertEqual(result.stderr, '')
        return result.returncode, json.loads(result.stdout)

    def literals(self, *args, base='HEAD', repo=None):
        return self.cli('literals', '--repo', str(repo or self.repo), '--base', base, *args)

    def found(self, data):
        return {(item['path'], item['line'], item['category']) for item in data['findings']}


class LiteralsGitTests(Fixture):
    def test_only_added_lines_are_reported_not_preexisting(self):
        self.commit({'app.css': '.old { color: #111111; }\n.keep { padding: 4px; }\n'})
        self.write('app.css', '.old { color: #111111; }\n.new { color: #222222; }\n.keep { padding: 4px; }\n')
        rc, data = self.literals()
        self.assertEqual(rc, 1, data)
        self.assertEqual(self.found(data), {('app.css', 2, 'color')})
        self.assertEqual(data['findings'][0]['text'], '.new { color: #222222; }')
        self.assertEqual(data['scanned'], ['app.css'])

    def test_staged_and_unstaged_edits_are_both_in_scope(self):
        self.commit({'a.css': '.a {}\n', 'Page.tsx': 'export const Page = () => null\n'})
        self.write('a.css', '.a {}\n.b { margin-top: 12px; }\n')
        self.git('add', 'a.css')
        self.write('Page.tsx', 'export const Page = () => <button style={{color: "red"}}>Go</button>\n')
        rc, data = self.literals()
        self.assertEqual(rc, 1)
        self.assertEqual(self.found(data), {('a.css', 2, 'length'), ('Page.tsx', 1, 'inline_style'),
                                            ('Page.tsx', 1, 'raw_control')})

    def test_untracked_file_is_scanned_completely_and_ignored_file_is_not(self):
        self.commit({'.gitignore': 'dist/\n', 'base.txt': 'x\n'})
        self.write('src/new.css', '.x { color: #abcdef; }\n.y { display: block; }\n.z { gap: 1.5rem; }\n')
        self.write('dist/bundle.css', '.x { color: #000000; }\n')
        rc, data = self.literals()
        self.assertEqual(rc, 1)
        self.assertEqual(self.found(data), {('src/new.css', 1, 'color'), ('src/new.css', 3, 'length')})
        self.assertEqual(data['scanned'], ['src/new.css'])
        self.assertNotIn('dist/bundle.css', json.dumps(data))

    def test_pathspecs_limit_scope_and_unknown_paths_fail_loudly(self):
        self.commit({'mine/a.css': '\n', 'theirs/b.css': '\n'})
        self.write('mine/a.css', '\n.a { color: #123; }\n')
        self.write('theirs/b.css', '\n.b { color: #456; }\n')
        self.write('theirs/new.css', '.c { color: #789; }\n')
        rc, data = self.literals('--', 'mine/a.css')
        self.assertEqual((rc, self.found(data)), (1, {('mine/a.css', 2, 'color')}))
        rc, data = self.literals('--', 'mine')
        self.assertEqual(self.found(data), {('mine/a.css', 2, 'color')})
        # One string holding two names is not a list of files.
        rc, data = self.literals('--', 'mine/a.css theirs/b.css')
        self.assertEqual((rc, data), (2, {'error': 'PATHSPEC_NOT_FOUND'}))
        rc, data = self.literals('--', '../outside.css')
        self.assertEqual((rc, data), (2, {'error': 'BAD_PATHSPEC'}))

    def test_pathspec_for_deleted_file_is_valid(self):
        self.commit({'gone.css': '.a { color: #fff; }\n', 'kept.css': '\n'})
        (self.repo / 'gone.css').unlink()
        rc, data = self.literals('--', 'gone.css')
        self.assertEqual((rc, data['findings']), (0, []))

    def test_pathspecs_are_relative_to_repo_argument(self):
        self.commit({'apps/web/a.css': '\n', 'a.css': '\n'})
        self.write('apps/web/a.css', '\n.a { color: #aaa; }\n')
        self.write('a.css', '\n.b { color: #bbb; }\n')
        rc, data = self.literals('--', 'a.css', repo=self.repo / 'apps/web')
        self.assertEqual(self.found(data), {('apps/web/a.css', 2, 'color')})

    def test_names_with_spaces_and_unicode(self):
        self.commit({'src/my button ñ.tsx': 'export default null\n'})
        self.write('src/my button ñ.tsx', 'export default null\nconst c = "#ff00ff"\n')
        self.write('src/nuevo "diseño".css', '.n { padding: 3px; }\n')
        rc, data = self.literals()
        self.assertEqual(self.found(data), {('src/my button ñ.tsx', 2, 'color'),
                                            ('src/nuevo "diseño".css', 1, 'length')})
        rc, data = self.literals('--', 'src/my button ñ.tsx')
        self.assertEqual(self.found(data), {('src/my button ñ.tsx', 2, 'color')})

    def test_empty_scope_is_clean(self):
        self.commit({'a.css': '.a { color: #fff; }\n'})
        rc, data = self.literals()
        self.assertEqual((rc, data), (0, {'findings': [], 'scanned': [], 'skipped': []}))

    def test_rename_is_not_new_content(self):
        self.commit({'old/Card.css': '.card { color: #101010; padding: 8px; }\n' * 3})
        (self.repo / 'new').mkdir()
        self.git('mv', 'old/Card.css', 'new/Card.css')
        rc, data = self.literals()
        self.assertEqual((rc, data['findings']), (0, []))

    def test_tokens_and_wrappers_allowances(self):
        self.commit({'base.txt': 'x\n'})
        self.write('src/tokens.css', '.t { --brand: #D97757; --card-padding: 4px; }\n.t { color: red !important; }\n')
        self.write('src/ui/Button.tsx', 'export const Button = (p) => <button className="b" {...p} />\n')
        self.write('src/Page.tsx', 'export const Page = () => <input name="q" />\n')
        rc, data = self.literals()
        self.assertEqual(self.found(data), {('src/tokens.css', 1, 'color'), ('src/tokens.css', 1, 'length'),
                                            ('src/tokens.css', 2, 'inline_style'),
                                            ('src/ui/Button.tsx', 1, 'raw_control'),
                                            ('src/Page.tsx', 1, 'raw_control')})
        rc, data = self.literals('--tokens', 'src/tokens.css', '--wrappers', 'src/ui')
        self.assertEqual(self.found(data), {('src/tokens.css', 2, 'inline_style'),
                                            ('src/Page.tsx', 1, 'raw_control')})

    def test_token_blocks_in_a_shared_stylesheet(self):
        self.commit({'base.txt': 'x\n'})
        sheet = '\n'.join([
            '@layer tokens, base, components;',                     # 1
            '/* palette: } { not a block */',                       # 2
            ':root {',                                              # 3
            '  --clay-600: #D97757;',                               # 4
            '  --label: "}";',                                      # 5
            '  --space-4: 16px;',                                   # 6
            '}',                                                    # 7
            '@layer tokens {',                                      # 8
            '  :root[data-theme="dark"] { --surface: oklch(0.2 0 0); }',  # 9
            '}',                                                    # 10
            '@theme inline { --color-accent: #0a6; }',              # 11
            '@media (prefers-color-scheme: dark) {',                # 12
            '  :root { --surface: #111111; }',                      # 13
            '  .card { color: #222222; }',                          # 14
            '}',                                                    # 15
            '.card { color: #123456; border-radius: 6px; }',        # 16
            '/* #ffffff in a comment */',                           # 17
            ':root { --x: 1px; } .bad { margin: 2px; }',            # 18
            '#fab { color: var(--clay-600); }',                     # 19
            ''])
        self.write('styles.css', sheet)
        rc, data = self.literals()
        self.assertEqual(self.found(data), {('styles.css', 14, 'color'), ('styles.css', 16, 'color'),
                                            ('styles.css', 16, 'length'), ('styles.css', 18, 'length')})

    def test_scss_line_comments_and_interpolation(self):
        self.commit({'base.txt': 'x\n'})
        self.write('a.scss', '// tokens {\n:root { --a: #{$brand}; --b: #eee; }\n.x-#{$n} { color: #ddd; }\n'
                             ':root { --img: url(//cdn.example.invalid/a.png); }\n.v { color: #bbb; }\n')
        rc, data = self.literals()
        # `url(//...)` is not a comment, so the :root block closes before .v.
        self.assertEqual(self.found(data), {('a.scss', 3, 'color'), ('a.scss', 5, 'color')})

    def test_web_false_positives_are_not_reported(self):
        self.commit({'base.txt': 'x\n'})
        self.write('src/Nav.tsx', '\n'.join([
            '<a href="#add">Skip</a>',
            '<p>&#123; entity</p>',
            'class A { #fade() { return this.#bad } }',
            '<svg><rect fill="url(#abc)" /></svg>',
            '// fixes #123 and #fff in a comment',
            '<input-group><Button>Save</Button></input-group>',
            '<a href="/page#cafe">x</a>',
            'const total = items.reduce((a, b) => a + b, 0)',
            '']))
        rc, data = self.literals()
        self.assertEqual((rc, data['findings']), (0, []))
        self.assertEqual(data['scanned'], ['src/Nav.tsx'])

    def test_web_categories(self):
        self.commit({'base.txt': 'x\n'})
        self.write('src/View.vue', '\n'.join([
            '<div class="p-[13px] bg-[#1da1f2]">',                 # 1 arbitrary + color
            '<span :style="{ color: c }">x</span>',                 # 2 inline
            '<textarea></textarea>',                                # 3 raw control
            'const s = { marginTop: "8px", color: "hsl(10 50% 50%)" }',  # 4 length + color
            '<select v-model="x"></select>',                        # 5 raw control
            '.t { font: 600 14px/1.4 Inter; font-weight: 600; }',  # 6 length (shorthand)
            '']))
        rc, data = self.literals()
        self.assertEqual(self.found(data), {
            ('src/View.vue', 1, 'arbitrary_value'), ('src/View.vue', 1, 'color'),
            ('src/View.vue', 2, 'inline_style'), ('src/View.vue', 3, 'raw_control'),
            ('src/View.vue', 4, 'length'), ('src/View.vue', 4, 'color'), ('src/View.vue', 5, 'raw_control'),
            ('src/View.vue', 6, 'length')})

    def test_swift_and_kotlin_patterns(self):
        self.commit({'base.txt': 'x\n'})
        self.write('ios/Card.swift', '\n'.join([
            'Text("Hi").foregroundColor(Color(red: 0.1, green: 0.2, blue: 0.3))',  # 1 color
            '  .padding(16)',                                       # 2 length
            'VStack(spacing: 8) {',                                 # 3 length
            '  .cornerRadius(12)',                                  # 4 length
            '  .font(.system(size: 17))',                           # 5 length
            'let c = #colorLiteral(red: 1, green: 0, blue: 0, alpha: 1)',  # 6 color
            '  .padding(.horizontal, Spacing.md)',                  # 7 clean
            '#if DEBUG',                                            # 8 clean
            '  .foregroundStyle(Color.accentColor)',                # 9 clean
            'let hex = UIColor(hex: "#FF0000")',                    # 10 color
            '']))
        self.write('android/Card.kt', '\n'.join([
            'val brand = Color(0xFFD97757)',                        # 1 color
            'Modifier.padding(16.dp)',                              # 2 length
            'fontSize = 14.sp',                                     # 3 length
            'Color(red = 0.1f, green = 0.2f, blue = 0.3f)',         # 4 color
            'Modifier.padding(Spacing.md)',                         # 5 clean
            'color = MaterialTheme.colorScheme.primary',            # 6 clean
            '']))
        rc, data = self.literals()
        self.assertEqual(self.found(data), {
            ('ios/Card.swift', 1, 'color'), ('ios/Card.swift', 2, 'length'), ('ios/Card.swift', 3, 'length'),
            ('ios/Card.swift', 4, 'length'), ('ios/Card.swift', 5, 'length'), ('ios/Card.swift', 6, 'color'),
            ('ios/Card.swift', 10, 'color'), ('android/Card.kt', 1, 'color'), ('android/Card.kt', 2, 'length'),
            ('android/Card.kt', 3, 'length'), ('android/Card.kt', 4, 'color')})

    def test_unsafe_or_unsuitable_files_are_skipped_with_reason(self):
        self.commit({'base.txt': 'x\n', 'tracked.css': '.a {}\n'})
        self.write('big.css', '.a { color: #fff; }\n' * 60000)
        self.write('bin.css', b'.a { color: #fff; }\0\n')
        self.write('notes.txt', 'color: #fff\n')
        self.write('min.css', '.a{color:#fff}' * 2000 + '\n')
        (self.repo / 'link.css').symlink_to('tracked.css')
        nested = self.repo / 'vendor/lib'
        nested.mkdir(parents=True)
        subprocess.run(['git', 'init', '-q', str(nested)], check=True, env=GIT_ENV)
        self.write('vendor/lib/x.css', '.x { color: #fff; }\n')
        rc, data = self.literals()
        reasons = {item['path']: item['reason'] for item in data['skipped']}
        self.assertEqual(reasons, {'big.css': 'too_large', 'bin.css': 'binary', 'link.css': 'symlink',
                                   'min.css': 'long_lines', 'notes.txt': 'unsupported_type',
                                   'vendor/lib/': 'nested_repository'})
        self.assertEqual((rc, data['findings'], data['scanned']), (0, [], []))

    def test_tracked_symlink_change_is_skipped(self):
        self.commit({'a.css': '.a { color: #fff; }\n'})
        (self.repo / 'b.css').symlink_to('a.css')
        self.git('add', 'b.css')
        rc, data = self.literals()
        self.assertEqual((rc, data['skipped']), (0, [{'path': 'b.css', 'reason': 'symlink'}]))

    def test_read_only_and_concurrent_runs_agree(self):
        self.commit({'a.css': '.a {}\n'})
        self.write('a.css', '.a {}\n.b { color: #abc; }\n')
        self.write('b.css', '.c { padding: 1px; }\n')
        index = self.repo / '.git/index'
        before = (index.read_bytes(), index.stat().st_mtime_ns)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.literals(), range(6)))
        self.assertEqual(len({json.dumps(data, sort_keys=True) for _, data in results}), 1)
        self.assertEqual(results[0][0], 1)
        self.assertEqual((index.read_bytes(), index.stat().st_mtime_ns), before)
        self.assertFalse((self.repo / '.git/index.lock').exists())


class ErrorTests(Fixture):
    def test_repository_and_base_errors(self):
        outside = self.root / 'plain'
        outside.mkdir()
        self.assertEqual(self.cli('literals', '--repo', str(outside), '--base', 'HEAD'),
                         (2, {'error': 'NOT_A_GIT_REPO'}))
        self.assertEqual(self.cli('contracts', '--repo', str(self.root / 'absent'), '--base', 'HEAD'),
                         (2, {'error': 'NOT_A_GIT_REPO'}))
        self.assertEqual(self.literals(), (2, {'error': 'BAD_BASE'}))  # no commits yet
        self.commit({'a.css': '\n'})
        for base in ('nope', 'HEAD..HEAD'):
            self.assertEqual(self.literals(base=base), (2, {'error': 'BAD_BASE'}))
        # An option-looking base never reaches Git.
        self.assertEqual(self.cli('literals', '--repo', str(self.repo), '--base=--output=x'),
                         (2, {'error': 'BAD_BASE'}))

    def test_usage_errors(self):
        self.commit({'a.css': '\n'})
        diff = self.write('x.diff', '', base=self.root)
        for args in (('literals', '--repo', str(self.repo)),
                     ('literals', '--diff', str(diff)),
                     ('literals', '--diff', str(diff), '--root', str(self.root), '--repo', str(self.repo)),
                     ('contracts', '--diff', str(diff), '--', 'a.css'),
                     ('contrast',),
                     ('contrast', '--pair', '#fff'),
                     ('contrast', '--pair', '#fff', '#000', '--kind', 'huge'),
                     ('unknown',)):
            self.assertEqual(self.cli(*args), (2, {'error': 'ARGUMENTS_INVALID'}), args)

    def test_git_unavailable_is_an_error_but_diff_mode_needs_no_git(self):
        self.commit({'a.css': '\n'})
        env = {'PATH': str(self.root / 'empty-bin')}
        self.assertEqual(self.cli('literals', '--repo', str(self.repo), '--base', 'HEAD', env=env),
                         (2, {'error': 'GIT_UNAVAILABLE'}))
        self.assertEqual(self.cli('contrast', '--pair', '#000', '#fff', env=env)[0], 0)


class DiffModeTests(Fixture):
    def make_trees(self):
        orig, new = self.root / 'orig', self.root / 'new'
        self.write('src/app.css', '.old { color: #111111; }\n', base=orig)
        self.write('src/app.css', '.old { color: #111111; }\n:root { --a: #fafafa; }\n.n { gap: 2px; }\n', base=new)
        self.write('src/new file.tsx', 'export default () => <button>Hi</button>\n', base=new)
        self.write('src/gone.tsx', '<input id="q" />\n', base=orig)
        return orig, new

    def gnu_diff(self, orig, new):
        if shutil.which('diff') is None:
            self.skipTest('diff is not installed')
        result = subprocess.run(['diff', '-ruN', '-U0', orig.name, new.name], cwd=self.root,
                                capture_output=True)
        self.assertIn(result.returncode, (0, 1))
        return self.write('change.diff', result.stdout, base=self.root)

    def test_literals_from_plain_diff_without_git(self):
        orig, new = self.make_trees()
        diff = self.gnu_diff(orig, new)
        env = {'PATH': str(self.root / 'empty-bin')}
        rc, data = self.cli('literals', '--diff', str(diff), '--root', str(new), env=env, cwd=self.root / 'repo')
        self.assertEqual(rc, 1, data)
        self.assertEqual(self.found(data), {('src/app.css', 3, 'length'), ('src/new file.tsx', 1, 'raw_control')})
        self.assertEqual(data['scanned'], ['src/app.css', 'src/new file.tsx'])
        rc, data = self.cli('literals', '--diff', str(diff), '--root', str(new),
                            '--wrappers', 'src/new file.tsx', env=env)
        self.assertEqual(self.found(data), {('src/app.css', 3, 'length')})

    def test_wrong_root_is_reported_as_content_mismatch(self):
        orig, new = self.make_trees()
        diff = self.gnu_diff(orig, new)
        rc, data = self.cli('literals', '--diff', str(diff), '--root', str(orig))
        reasons = {item['path']: item['reason'] for item in data['skipped']}
        self.assertEqual(reasons['src/app.css'], 'content_mismatch')
        self.assertEqual(data['findings'], [])

    def test_git_format_diff_with_quoted_names(self):
        new = self.root / 'tree'
        self.write('src/ñ "q".css', '.a {}\n.b { color: #bada55; }\n', base=new)
        diff = self.write('git.diff', (
            'diff --git "a/src/\\303\\261 \\"q\\".css" "b/src/\\303\\261 \\"q\\".css"\n'
            'index 1111111..2222222 100644\n'
            '--- "a/src/\\303\\261 \\"q\\".css"\t\n'
            '+++ "b/src/\\303\\261 \\"q\\".css"\t\n'
            '@@ -1,0 +2 @@ .a {}\n'
            '+.b { color: #bada55; }\n'), base=self.root)
        rc, data = self.cli('literals', '--diff', str(diff), '--root', str(new))
        self.assertEqual((rc, self.found(data)), (1, {('src/ñ "q".css', 2, 'color')}))

    def test_diff_input_errors(self):
        self.assertEqual(self.cli('contracts', '--diff', str(self.root / 'absent.diff')),
                         (2, {'error': 'DIFF_UNREADABLE'}))
        self.assertEqual(self.cli('contracts', '--diff', str(self.root)), (2, {'error': 'DIFF_UNREADABLE'}))
        junk = self.write('junk.diff', 'not a diff at all\n', base=self.root)
        self.assertEqual(self.cli('contracts', '--diff', str(junk)), (2, {'error': 'DIFF_INVALID'}))
        cut = self.write('cut.diff', '--- a/x.css\n+++ b/x.css\n@@ -1,0 +1,3 @@\n+one\n', base=self.root)
        self.assertEqual(self.cli('contracts', '--diff', str(cut)), (2, {'error': 'DIFF_INVALID'}))
        empty = self.write('empty.diff', '', base=self.root)
        self.assertEqual(self.cli('literals', '--diff', str(empty), '--root', str(self.root / 'nope')),
                         (2, {'error': 'BAD_ROOT'}))
        self.assertEqual(self.cli('literals', '--diff', str(empty), '--root', str(self.root)),
                         (0, {'findings': [], 'scanned': [], 'skipped': []}))

    def test_new_files_missing_from_diff_are_listed(self):
        orig, new = self.make_trees()
        if shutil.which('diff') is None:
            self.skipTest('diff is not installed')
        result = subprocess.run(['diff', '-ru', '-U0', 'orig', 'new'], cwd=self.root, capture_output=True)
        diff = self.write('partial.diff', result.stdout, base=self.root)
        rc, data = self.cli('literals', '--diff', str(diff), '--root', str(new))
        self.assertIn({'path': 'src/new file.tsx', 'reason': 'only_in_one_tree'}, data['skipped'])


class ContractsTests(Fixture):
    def test_removed_attributes_with_quotes_and_jsx_braces(self):
        self.commit({'src/Signup.tsx': '\n'.join([
            '<label htmlFor={inputId}>Email</label>',
            '<input id="email" name="email" autoComplete="email" data-testid=\'signup-email\' />',
            '<a href={`/docs/${slug}`}>Docs</a>',
            '<a href="/terms">Terms</a>',
            ''])})
        self.write('src/Signup.tsx', '\n'.join([
            '<Field label="Email">',
            '<input id="email" name="mail" autocomplete={"email"} data-testid="signup-email" />',
            '</Field>',
            '']))
        # The terms link moved to a new, untracked component; that is not a loss.
        self.write('src/Legal.tsx', 'export const Legal = () => <a href="/terms">Terms</a>\n')
        rc, data = self.cli('contracts', '--repo', str(self.repo), '--base', 'HEAD')
        self.assertEqual(rc, 1, data)
        self.assertEqual(data['missing'], [
            {'attribute': 'href={`/docs/${slug}`}', 'removed_in': [{'path': 'src/Signup.tsx', 'line': 3}]},
            {'attribute': 'htmlFor={inputId}', 'removed_in': [{'path': 'src/Signup.tsx', 'line': 1}]},
            {'attribute': 'name="email"', 'removed_in': [{'path': 'src/Signup.tsx', 'line': 2}]}])
        self.assertEqual(data['scanned'], ['src/Legal.tsx', 'src/Signup.tsx'])

    def test_moved_attribute_between_tracked_files_is_not_reported(self):
        self.commit({'a.html': '<section id="pricing">\n', 'b.html': '<main>\n'})
        self.write('a.html', '<section>\n')
        self.write('b.html', '<main>\n<div id="pricing">\n')
        rc, data = self.cli('contracts', '--repo', str(self.repo), '--base', 'HEAD')
        self.assertEqual((rc, data['missing']), (0, []))

    def test_native_identifiers_from_plain_diff(self):
        diff = self.write('native.diff', '\n'.join([
            '--- orig/App/Login.swift\t2026-01-01 00:00:00',
            '+++ new/App/Login.swift\t2026-01-01 00:00:00',
            '@@ -3,2 +3,1 @@',
            '-    .accessibilityIdentifier("login-button")',
            '-    .accessibilityIdentifier("login-title")',
            '+    .accessibilityIdentifier("login-title")',
            '--- orig/app/Login.kt\t2026-01-01 00:00:00',
            '+++ new/app/Login.kt\t2026-01-01 00:00:00',
            '@@ -7 +7 @@',
            '-Button(modifier = Modifier.testTag("submit")) {}',
            '+Button(modifier = Modifier) {}',
            '--- orig/web/x.css\t2026-01-01 00:00:00',
            '+++ new/web/x.css\t2026-01-01 00:00:00',
            '@@ -1 +0,0 @@',
            '-[data-state="open"] { color: red; }',
            '']), base=self.root)
        rc, data = self.cli('contracts', '--diff', str(diff))
        self.assertEqual(rc, 1, data)
        self.assertEqual(data['missing'], [
            {'attribute': '.accessibilityIdentifier("login-button")',
             'removed_in': [{'path': 'App/Login.swift', 'line': 3}]},
            {'attribute': 'testTag("submit")', 'removed_in': [{'path': 'app/Login.kt', 'line': 7}]}])
        self.assertEqual(data['skipped'], [{'path': 'web/x.css', 'reason': 'unsupported_type'}])

    def test_deleted_file_attributes_are_missing(self):
        self.commit({'Form.vue': '<input name="q" data-cy="search">\n', 'keep.txt': 'x\n'})
        (self.repo / 'Form.vue').unlink()
        rc, data = self.cli('contracts', '--repo', str(self.repo), '--base', 'HEAD')
        self.assertEqual(rc, 1)
        self.assertEqual([item['attribute'] for item in data['missing']], ['data-cy="search"', 'name="q"'])


class ContrastTests(Fixture):
    def contrast(self, *pairs, kind=None):
        args = ['contrast']
        for fg, bg in pairs:
            args += ['--pair', fg, bg]
        if kind:
            args += ['--kind', kind]
        return self.cli(*args)

    def test_known_values(self):
        rc, data = self.contrast(('#767676', '#ffffff'))
        self.assertEqual((rc, data['pairs'][0]['ratio'], data['pairs'][0]['passes']), (0, 4.54, True))
        rc, data = self.contrast(('#777777', '#FFF'))
        self.assertEqual((rc, data['pairs'][0]['ratio'], data['pairs'][0]['passes']), (1, 4.48, False))
        rc, data = self.contrast(('#D97757', '#F4F1EA'), kind='large')
        self.assertEqual((rc, data['pairs'][0]['ratio'], data['pairs'][0]['required']), (1, 2.77, 3.0))
        rc, data = self.contrast(('rgb(118, 118, 118)', 'rgb(255 255 255)'), ('#767676ff', '#fff'), kind='ui')
        self.assertEqual((rc, [pair['ratio'] for pair in data['pairs']]), (0, [4.54, 4.54]))
        self.assertEqual(data['pairs'][0], {'fg': 'rgb(118, 118, 118)', 'bg': 'rgb(255 255 255)', 'ratio': 4.54,
                                            'kind': 'ui', 'required': 3.0, 'passes': True})

    def test_rounding_does_not_decide(self):
        # 4.4999 would round to 4.5 but must still fail body text.
        rc, data = self.contrast(('#777777', '#ffffff'), ('#767676', '#ffffff'))
        self.assertEqual(rc, 1)
        self.assertEqual([pair['passes'] for pair in data['pairs']], [False, True])

    def test_foreground_alpha_is_composited(self):
        rc, data = self.contrast(('rgba(0, 0, 0, 0.5)', '#ffffff'), ('rgb(0 0 0 / 50%)', '#fff'),
                                 ('#0008', '#ffffff'), ('#000000', '#808080'))
        ratios = [pair['ratio'] for pair in data['pairs']]
        self.assertEqual(ratios[0], ratios[1])
        self.assertEqual(ratios[0], 3.98)
        self.assertEqual(ratios[2], 4.48)  # 0x88 alpha is 0.533: black over white gives #777777
        self.assertEqual(ratios[3], 5.32)
        self.assertEqual(rc, 1)

    def test_color_errors(self):
        self.assertEqual(self.contrast(('#000', '#ffffff80')), (2, {'error': 'TRANSLUCENT_BACKGROUND'}))
        self.assertEqual(self.contrast(('#000', 'rgba(255, 255, 255, 0.9)')),
                         (2, {'error': 'TRANSLUCENT_BACKGROUND'}))
        for bad in ('red', '#12', '#12345', 'rgb(300, 0, 0)', 'rgb(1, 2)', 'rgb(1 2 3 / 2)', 'rgb(1, 2, 3 / 1)', ''):
            self.assertEqual(self.contrast((bad, '#fff')), (2, {'error': 'BAD_COLOR'}), bad)

    def test_pair_limit(self):
        self.assertEqual(self.contrast(*[('#000', '#fff')] * 1001), (2, {'error': 'LIMIT_EXCEEDED'}))


class FilterTests(Fixture):
    """No Git call made by the helper may run a configured filter driver."""

    def setUp(self):
        super().setUp()
        self.marker = self.root / 'filter-ran'
        self.commit({'a.css': '.a {}\n', 'Form.html': '<input id="email">\n'})
        self.write('a.css', '.a { color: #abcdef; }\n')
        self.write('Form.html', '<p>gone</p>\n')

    def probe(self, then='cat'):
        return "printf ran >> '" + str(self.marker) + "'; " + then

    def plain_git_runs_filter(self, env=None):
        """Sanity check: the fixture really triggers the filter in a normal diff."""
        subprocess.run(['git', '-C', str(self.repo), 'diff', 'HEAD'], capture_output=True,
                       env=env or GIT_ENV, timeout=20)
        ran = self.marker.exists()
        if ran:
            self.marker.unlink()
        return ran

    def assert_helper_runs_no_filter(self, env=None):
        rc, data = self.cli('literals', '--repo', str(self.repo), '--base', 'HEAD', env=env)
        self.assertEqual((rc, [(f['path'], f['category']) for f in data['findings']]), (1, [('a.css', 'color')]))
        rc, data = self.cli('contracts', '--repo', str(self.repo), '--base', 'HEAD', '--', 'a.css', 'Form.html',
                            env=env)
        self.assertEqual((rc, [item['attribute'] for item in data['missing']]), (1, ['id="email"']))
        self.assertFalse(self.marker.exists(), 'a filter ran')

    def test_required_clean_filter_from_gitattributes_never_runs(self):
        self.write('.gitattributes', '* filter=probe\n')
        self.git('config', 'filter.probe.clean', self.probe())
        self.git('config', 'filter.probe.smudge', self.probe())
        self.git('config', 'filter.probe.required', 'true')
        self.assertTrue(self.plain_git_runs_filter())
        self.assert_helper_runs_no_filter()

    def test_process_filter_never_runs(self):
        self.write('.gitattributes', '* filter=probe\n')
        self.git('config', 'filter.probe.process', 'sh -c "' + self.probe('exit 1').replace('"', '\\"') + '"')
        self.assertTrue(self.plain_git_runs_filter())
        self.assert_helper_runs_no_filter()

    def test_info_attributes_and_included_config_are_covered(self):
        (self.repo / '.git/info').mkdir(exist_ok=True)
        (self.repo / '.git/info/attributes').write_text('* filter=included\n')
        extra = self.write('extra.gitconfig', '[filter "included"]\n\tclean = "' + self.probe() + '"\n',
                           base=self.root)
        self.git('config', 'include.path', str(extra))
        self.assertTrue(self.plain_git_runs_filter())
        self.assert_helper_runs_no_filter()

    def test_caller_environment_and_global_configuration_cannot_add_filters(self):
        home = self.root / 'home'
        self.write('.gitconfig', '[filter "home"]\n\tclean = "' + self.probe() + '"\n', base=home)
        self.write('.config/git/attributes', '* filter=home\n', base=home)
        quoted = "'" + self.probe().replace("'", "'\\''") + "'"
        cases = [
            ({'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'filter.env.clean', 'GIT_CONFIG_VALUE_0': self.probe()},
             '* filter=env\n'),
            ({'GIT_CONFIG_PARAMETERS': "'filter.params.clean'=" + quoted}, '* filter=params\n'),
            ({'HOME': str(home), 'XDG_CONFIG_HOME': str(home / '.config')}, None),
        ]
        for extra, attributes in cases:
            with self.subTest(extra=sorted(extra)):
                env = {key: value for key, value in GIT_ENV.items() if key != 'GIT_CONFIG_GLOBAL'}
                env.update(extra)
                attributes_file = self.repo / '.gitattributes'
                if attributes:
                    attributes_file.write_text(attributes)
                elif attributes_file.exists():
                    attributes_file.unlink()
                self.assertTrue(self.plain_git_runs_filter(env))
                self.assert_helper_runs_no_filter(env)

    def test_empty_driver_name_clean_never_runs(self):
        # Git accepts `filter..clean` and applies it to `* filter=`.
        self.write('.gitattributes', '* filter=\n')
        self.git('config', 'filter..clean', self.probe())
        self.assertTrue(self.plain_git_runs_filter())
        self.assert_helper_runs_no_filter()

    def test_empty_driver_name_process_never_runs(self):
        self.write('.gitattributes', '* filter=\n')
        self.git('config', 'filter..process', 'sh -c "' + self.probe('exit 1').replace('"', '\\"') + '"')
        self.assertTrue(self.plain_git_runs_filter())
        self.assert_helper_runs_no_filter()

    def test_fsmonitor_hook_never_runs(self):
        # Before Git 2.36 any non-empty core.fsmonitor, `false` included, is a hook path.
        hook = self.write('fsmonitor-hook', '#!/bin/sh\n' + self.probe('exit 1') + '\n', base=self.root)
        hook.chmod(0o755)
        self.git('config', 'core.fsmonitor', str(hook))
        if not self.plain_git_runs_filter():
            self.skipTest('this Git does not query the fsmonitor hook in a diff')
        self.assert_helper_runs_no_filter()

    def test_driver_name_that_cannot_be_overridden_is_refused(self):
        self.write('.gitattributes', '* filter=a=b\n')
        self.git('config', 'filter.a=b.clean', self.probe())
        for command in ('literals', 'contracts'):
            self.assertEqual(self.cli(command, '--repo', str(self.repo), '--base', 'HEAD'),
                             (2, {'error': 'FILTER_UNSUPPORTED'}))
        self.assertFalse(self.marker.exists())

    def test_driver_added_during_the_run_is_an_error(self):
        helper = load_helper()
        calls = iter([set(), {b'late'}])
        with patch.object(helper, '_filter_drivers', lambda top, budget: next(calls)):
            with self.assertRaises(helper.CheckError) as raised:
                helper.literals_git(self.repo, 'HEAD')
        self.assertEqual(str(raised.exception), 'FILTER_CONFIG_CHANGED')

    def test_git_older_than_the_minimum_is_refused(self):
        fake = self.write('bin/git', '#!/bin/sh\necho "git version 2.31.9"\n', base=self.root)
        fake.chmod(0o755)
        env = {**GIT_ENV, 'PATH': str(fake.parent)}
        self.assertEqual(self.cli('literals', '--repo', str(self.repo), '--base', 'HEAD', env=env),
                         (2, {'error': 'GIT_UNSUPPORTED'}))


class TransportTests(Fixture):
    """A lazy fetch from a promisor remote must not reach any transport."""

    def setUp(self):
        super().setUp()
        self.marker = self.root / 'remote-ran'
        self.commit({'a.css': '.x {}\n', 'Form.html': '<input id="email">\n'})
        blob = self.git('rev-parse', 'HEAD:a.css').strip()
        self.write('a.css', '.x { color: #fff; }\n')
        probe = self.write('remote.sh', "#!/bin/sh\nprintf ran >> '" + str(self.marker) + "'\nexit 1\n",
                           base=self.root)
        probe.chmod(0o755)
        self.git('config', 'remote.origin.url', 'ext::' + str(probe))
        self.git('config', 'remote.origin.promisor', 'true')
        # A local per-protocol setting outranks protocol.allow=never.
        self.git('config', 'protocol.ext.allow', 'always')
        (self.repo / '.git/objects' / blob[:2] / blob[2:]).unlink()

    def plain_git_runs_remote(self, extra):
        subprocess.run(['git', '-C', str(self.repo), '-c', 'protocol.allow=never', 'diff', 'HEAD'],
                       capture_output=True, env={**GIT_ENV, **extra}, timeout=20)
        ran = self.marker.exists()
        if ran:
            self.marker.unlink()
        return ran

    def test_helper_never_runs_the_remote(self):
        self.assertTrue(self.plain_git_runs_remote({}))
        for command in ('literals', 'contracts'):
            rc, data = self.cli(command, '--repo', str(self.repo), '--base', 'HEAD')
            self.assertEqual((rc, data), (2, {'error': 'GIT_COMMAND_FAILED'}))
        self.assertFalse(self.marker.exists())

    def test_transport_ban_holds_without_lazy_fetch_guard(self):
        # Git before 2.44 ignores GIT_NO_LAZY_FETCH; GIT_ALLOW_PROTOCOL must still stop the fetch.
        helper = load_helper()
        original = helper._git_environment

        def without(*names):
            def environment():
                env = original()
                for name in names:
                    env.pop(name)
                return env
            return environment

        with patch.object(helper, '_git_environment', without('GIT_NO_LAZY_FETCH')):
            for run in (helper.literals_git, helper.contracts_git):
                with self.assertRaises(helper.CheckError):
                    run(self.repo, 'HEAD')
        self.assertFalse(self.marker.exists())
        # Control: without both guards the same call does run the remote command.
        with patch.object(helper, '_git_environment', without('GIT_NO_LAZY_FETCH', 'GIT_ALLOW_PROTOCOL')):
            with self.assertRaises(helper.CheckError):
                helper.literals_git(self.repo, 'HEAD')
        self.assertTrue(self.marker.exists())


class ValueOnlyContractTests(Fixture):
    """The attribute or call name stays as context; only its value line changes."""

    BEFORE = {
        'A.html': '<input\n  id=\n  "email"\n>\n',
        'B.tsx': '<Input\n  id={\n    "email"\n  }\n/>\n',
        'C.swift': 'Text("x")\n    .accessibilityIdentifier(\n        "login"\n    )\n',
        'D.kt': 'Button(\n    modifier = Modifier.testTag(\n        "submit"\n    )\n) {}\n',
    }
    VALUE = {'A.html': '"mail"', 'B.tsx': '"mail"', 'C.swift': '"signin"', 'D.kt': '"send"'}
    ARGUMENT = {'A.html': '"{{ field.id }}"', 'B.tsx': 'fieldId', 'C.swift': 'Ids.login', 'D.kt': 'Tags.SUBMIT'}
    OLD = {'A.html': '"email"', 'B.tsx': '"email"', 'C.swift': '"login"', 'D.kt': '"submit"'}

    def trees(self, write):
        for variant, values in (('value', self.VALUE), ('argument', self.ARGUMENT)):
            for name, text in self.BEFORE.items():
                write('before', variant + '/' + name, text)
                write('after', variant + '/' + name, text.replace(self.OLD[name], values[name]))
        # A duplicate kept on an unchanged line means the contract is not missing.
        write('before', 'value/Keep.html', '<a id="top">\n<p>one</p>\n<a id="top">\n')
        write('after', 'value/Keep.html', '<a id="top">\n<p>one</p>\n')

    def expected(self, *variants):
        def where(*names):
            return [{'path': variant + '/' + name, 'line': 2} for variant in variants for name in names]
        return [{'attribute': '.accessibilityIdentifier("login")', 'removed_in': where('C.swift')},
                {'attribute': 'id="email"', 'removed_in': where('A.html', 'B.tsx')},
                {'attribute': 'testTag("submit")', 'removed_in': where('D.kt')}]

    def test_git_mode(self):
        before, after = {}, {}
        self.trees(lambda side, path, text: (before if side == 'before' else after).__setitem__(path, text))
        self.commit(before)
        for path, text in after.items():
            self.write(path, text)
        for variant in ('value', 'argument'):
            with self.subTest(variant=variant):
                rc, data = self.cli('contracts', '--repo', str(self.repo), '--base', 'HEAD', '--', variant)
                self.assertEqual((rc, data['missing']), (1, self.expected(variant)))

    def test_diff_mode_with_context(self):
        if shutil.which('diff') is None:
            self.skipTest('diff is not installed')
        self.trees(lambda side, path, text: self.write(path, text, base=self.root / side))
        result = subprocess.run(['diff', '-ruN', 'before', 'after'], cwd=self.root, capture_output=True)
        diff = self.write('context.diff', result.stdout, base=self.root)
        rc, data = self.cli('contracts', '--diff', str(diff))
        self.assertEqual((rc, data['missing']), (1, self.expected('argument', 'value')))

    def test_literals_ignore_context_lines(self):
        if shutil.which('diff') is None:
            self.skipTest('diff is not installed')
        self.write('s.css', '.a { color: #111111; }\n.b { color: #222222; }\n', base=self.root / 'before')
        new = self.write('s.css', '.a { color: #111111; }\n.n { gap: 3px; }\n.b { color: #222222; }\n',
                         base=self.root / 'after')
        result = subprocess.run(['diff', '-ruN', 'before', 'after'], cwd=self.root, capture_output=True)
        diff = self.write('literal.diff', result.stdout, base=self.root)
        self.assertIn(b' .a { color: #111111; }', result.stdout)
        rc, data = self.cli('literals', '--diff', str(diff), '--root', str(new.parent))
        self.assertEqual((rc, self.found(data)), (1, {('s.css', 2, 'length')}))


class MultilineContractTests(Fixture):
    BEFORE = {
        'src/Form.html': '<input id = "email" name = "email" />\n<input id="keep">\n',
        'src/app.ts': 'const name = "draft"\nlet id = \'temp\';\nfn(href = "/x")\n',
        'ios/Login.swift': 'Button("Go") {}\n    .accessibilityIdentifier(\n        "login-submit"\n    )\n',
        'ios/Other.swift': 'Text("x").accessibilityIdentifier("other")\n',
        'android/Login.kt': 'Button(\n    modifier = Modifier.testTag(\n        "submit"\n    )\n) {}\n',
    }
    AFTER = {
        'src/Form.html': '<input>\n<input id="keep">\n',
        'src/app.ts': 'export {}\n',
        'ios/Login.swift': 'Button("Go") {}\n',
        # Reformatted across lines, still the same identifier.
        'ios/Other.swift': 'Text("x")\n    .accessibilityIdentifier(\n        "other"\n    )\n',
        'android/Login.kt': 'Button(modifier = Modifier) {}\n',
    }
    EXPECTED = [
        {'attribute': '.accessibilityIdentifier("login-submit")', 'removed_in': [{'path': 'ios/Login.swift', 'line': 2}]},
        {'attribute': 'id="email"', 'removed_in': [{'path': 'src/Form.html', 'line': 1}]},
        {'attribute': 'name="email"', 'removed_in': [{'path': 'src/Form.html', 'line': 1}]},
        {'attribute': 'testTag("submit")', 'removed_in': [{'path': 'android/Login.kt', 'line': 2}]},
    ]

    def test_git_mode(self):
        self.commit(self.BEFORE)
        for relative, content in self.AFTER.items():
            self.write(relative, content)
        rc, data = self.cli('contracts', '--repo', str(self.repo), '--base', 'HEAD')
        self.assertEqual((rc, data['missing']), (1, self.EXPECTED))

    def test_diff_mode(self):
        if shutil.which('diff') is None:
            self.skipTest('diff is not installed')
        for relative in self.BEFORE:
            self.write(relative, self.BEFORE[relative], base=self.root / 'orig')
            self.write(relative, self.AFTER[relative], base=self.root / 'new')
        result = subprocess.run(['diff', '-ruN', '-U0', 'orig', 'new'], cwd=self.root, capture_output=True)
        diff = self.write('multi.diff', result.stdout, base=self.root)
        rc, data = self.cli('contracts', '--diff', str(diff))
        self.assertEqual((rc, data['missing']), (1, self.EXPECTED))

    def test_new_untracked_file_restores_a_multiline_contract(self):
        self.commit({'ios/A.swift': 'x.accessibilityIdentifier("moved")\n'})
        self.write('ios/A.swift', 'x\n')
        self.write('ios/B.swift', 'y\n    .accessibilityIdentifier(\n        "moved"\n    )\n')
        rc, data = self.cli('contracts', '--repo', str(self.repo), '--base', 'HEAD')
        self.assertEqual((rc, data['missing']), (0, []))


class BoundsTests(Fixture):
    def test_long_values_finish_well_within_the_time_budget(self):
        self.commit({'base.txt': 'x\n'})
        css = ''.join('.x { padding: ' + '1' * 18000 + '; }\n' for _ in range(55))
        self.assertEqual(len(css.encode()), 990990)
        self.write('long.css', css)
        self.write('long.tsx', ''.join('<div className="p-[' + '1' * 18000 + 'x]" />\n' for _ in range(55)))
        self.write('long.swift', ''.join('.padding(' + '1' * 18000 + 'x)\n' for _ in range(55)))
        self.write('long.html', ''.join('<a id={' + 'a' * 18000 + '\n' for _ in range(55)))
        started = time.monotonic()
        rc, data = self.literals()
        elapsed = time.monotonic() - started
        self.assertEqual((rc, data['findings'], data['skipped']), (0, [], []), data)
        self.assertEqual(len(data['scanned']), 4)
        rc, _ = self.cli('contracts', '--repo', str(self.repo), '--base', 'HEAD')
        self.assertEqual(rc, 0)
        # Linear patterns take well under a second here; the bound only guards
        # against a return of quadratic backtracking on slow machines.
        self.assertLess(time.monotonic() - started, 25)
        self.assertLess(elapsed, 20)

    def test_time_budget_is_checked_between_lines(self):
        helper = load_helper()
        budget = helper._Budget()
        budget.deadline = time.monotonic() - 1
        document = helper._Document(b'.a { color: #fff; }\n.b {}\n')
        with self.assertRaises(helper.CheckError) as raised:
            helper._scan('a.css', 'css', document, [1, 2], set(), budget)
        self.assertEqual(str(raised.exception), 'TIMEOUT')

    def contracts_diff(self, lines, header):
        diff = self.write('bounds.diff', '\n'.join(['--- a/x.html', '+++ b/x.html', header, *lines]) + '\n',
                          base=self.root)
        return self.cli('contracts', '--diff', str(diff))

    def test_missing_contracts_are_capped_at_ten_thousand(self):
        rc, data = self.contracts_diff(['-<i id="n%d">' % n for n in range(10000)], '@@ -1,10000 +0,0 @@')
        self.assertEqual((rc, len(data['missing'])), (1, 10000))
        self.assertEqual(self.contracts_diff(['-<i id="n%d">' % n for n in range(10001)], '@@ -1,10001 +0,0 @@'),
                         (2, {'error': 'LIMIT_EXCEEDED'}))

    def test_intermediate_contract_entries_are_bounded(self):
        # One attribute removed from 50 001 lines: a single missing entry, too many locations.
        self.assertEqual(self.contracts_diff(['-<i id="same">'] * 50001, '@@ -1,50001 +0,0 @@'),
                         (2, {'error': 'LIMIT_EXCEEDED'}))
        self.assertEqual(self.contracts_diff(['+<i id="n%d">' % n for n in range(50001)], '@@ -0,0 +1,50001 @@'),
                         (2, {'error': 'LIMIT_EXCEEDED'}))


if __name__ == '__main__':
    unittest.main()
