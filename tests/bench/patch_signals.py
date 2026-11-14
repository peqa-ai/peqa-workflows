#!/usr/bin/env python3
"""Read-only list of the comments and patch signals a change adds. A measuring instrument of the bench.

Scans only the lines the change adds, in files with a known code extension,
between the merge base and HEAD or, when asked, the working tree. Reports as
JSON every whole-line comment added, and the lines that look like a patch over
a problem instead of its fix: a silenced check, a skipped or focused test, a
timer or sleep, a swallowed error, a comment that justifies a shortcut.

A signal is a prompt to look, not a defect: a timer can be the right code and
a comment can say what the code cannot. Nothing is changed, no filter or hook
runs and no remote is reached.
"""
import argparse
import json
import os
import re
import stat
import subprocess
import sys

MAX_FILES = 300  # changed files scanned
MAX_SIGNALS = 200  # signals listed; counts stay exact
MAX_LINE = 400  # characters of an added line that are matched
MAX_TEXT = 160  # characters of a line shown in a signal
MAX_FILE = 1024 * 1024  # bytes read from an untracked file
MAX_OUTPUT = 8 * 1024 * 1024  # bytes used from one Git call
TIMEOUT = 20  # seconds for one Git call

GIT = ['git', '--no-pager', '--no-optional-locks', '--literal-pathspecs', '-c', 'core.fsmonitor=',
       '-c', 'core.hooksPath=' + os.devnull, '-c', 'core.quotePath=false', '-c', 'protocol.allow=never']
SHA = re.compile(r'[0-9a-f]{40,64}')
FILTER_KEY = re.compile(rb'filter\.([\s\S]*)\.(?:clean|smudge|process|required)')
HUNK = re.compile(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@')
TEST_FOLDERS = {'test', 'tests', '__tests__', 'spec', 'specs', 'e2e'}
TEST_NAME = re.compile(r'^(test_|conftest\.)|[._-](test|spec|e2e)\.|(Test|Tests|Spec)\.[A-Za-z]+$')

HASH = {'.py', '.pyi', '.rb', '.sh', '.bash', '.zsh', '.pl', '.ex', '.exs'}
SLASH = {'.js', '.jsx', '.mjs', '.cjs', '.ts', '.tsx', '.java', '.kt', '.kts', '.swift', '.go', '.rs', '.c', '.h',
         '.cc', '.cpp', '.hpp', '.cs', '.php', '.scala', '.dart', '.scss', '.less', '.vue', '.svelte'}
BLOCK = SLASH | {'.css'}
DASH = {'.sql', '.lua'}
MARKUP = {'.html', '.vue', '.svelte'}
CODE = HASH | BLOCK | DASH | MARKUP
SHELL = {'.sh', '.bash', '.zsh'}

SUPPRESSION = re.compile(
    r'eslint-disable|@ts-ignore|@ts-expect-error|@ts-nocheck|biome-ignore|#\s*noqa\b|#\s*type:\s*ignore|'
    r'pylint:\s*disable|pragma:\s*no cover|#\s*nosec\b|mypy:\s*ignore|//\s*nolint\b|\bNOLINT\b|#\[allow\(|'
    r'@SuppressWarnings|@Suppress\(|rubocop:disable|swiftlint:disable|shellcheck disable|istanbul ignore|'
    r'c8 ignore|phpcs:ignore')
SKIPPED_TEST = re.compile(
    r'\b(?:it|test|describe|context)\.(?:skip|only)\b|\bx(?:it|describe|test)\(|\bf(?:it|describe)\(|'
    r'@pytest\.mark\.(?:skip|skipif|xfail)\b|@unittest\.(?:skip|skipIf|skipUnless|expectedFailure)\b|'
    r'\bpytest\.skip\(|\.skipTest\(|@Ignore\b|@Disabled\b|\bt\.Skip(?:f|Now)?\(|#\[ignore')
TIMING = re.compile(
    r'\b(?:setTimeout|setInterval|requestAnimationFrame|requestIdleCallback|waitForTimeout|usleep)\(|'
    r'\b(?:time|asyncio|Thread|Task)\.(?:sleep|Sleep|Delay)\(|\bsleep\(')
SHELL_SLEEP = re.compile(r'(?:^|[;&|]\s*)sleep\s+[\d.$]')
SWALLOWED = re.compile(
    r'\bexcept\b[^:]*:\s*pass\b|\bcatch\s*(?:\([^)]*\))?\s*\{\s*\}|\.catch\(\s*\(?\s*\w*\s*\)?\s*=>\s*\{\s*\}\s*\)')
SHELL_SWALLOWED = re.compile(r'\|\|\s*(?:true|:)\s*(?:$|[;#)])')
EXCEPT_OPEN = re.compile(r'^except\b[^:]*:\s*$')
JUSTIFIES = re.compile(
    r'\b(?:TODO|FIXME|HACK|XXX)\b|(?i:\bwork\s?around|\btemporar|\bprovisional|\bpor ahora\b|\bfor now\b|'
    r'\bquick fix|\barreglo rápido|\bparche\b|\bhack\b|\bflaky\b|\binestable\b|\bstopgap\b|\bhasta que\b|'
    r'\buntil\b.{0,40}\b(?:fixed|lands|resolved)|\bto avoid (?:the |a )?(?:failure|error|flak|race)|'
    r'\bpara evitar (?:el |la |un |una )?(?:fallo|error|carrera)|\bshould not be needed|\bno debería hacer falta)')
ORDER = ('suppression', 'skipped_test', 'swallowed_error', 'timing', 'justification_comment', 'comment')
LIMITS = ['A_SIGNAL_IS_A_PROMPT_TO_LOOK_NOT_A_DEFECT', 'ONLY_KNOWN_CODE_EXTENSIONS_SCANNED',
          'DOCSTRINGS_AND_TRAILING_COMMENTS_NOT_LISTED', 'MARKDOWN_AND_CONFIGURATION_NOT_SCANNED']


class CheckError(Exception):
    """Only fixed codes cross the CLI boundary."""


def environment():
    """Caller GIT_* variables dropped; no global configuration, prompt or transport."""
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env.update(GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0', GIT_CONFIG_NOSYSTEM='1',
               GIT_CONFIG_GLOBAL=os.devnull, GIT_ATTR_NOSYSTEM='1', GIT_NO_REPLACE_OBJECTS='1',
               GIT_NO_LAZY_FETCH='1', GIT_ALLOW_PROTOCOL='', LC_ALL='C')
    return env


def git(top, *args, ok=(0,)):
    try:
        proc = subprocess.run([*GIT, '-C', top, *args], capture_output=True, stdin=subprocess.DEVNULL,
                              env=environment(), timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        raise CheckError('TIMEOUT') from None
    except OSError:
        raise CheckError('GIT_UNAVAILABLE') from None
    if len(proc.stdout) > MAX_OUTPUT:
        raise CheckError('GIT_OUTPUT_TOO_LARGE')
    if proc.returncode not in ok:
        raise CheckError('GIT_COMMAND_FAILED')
    return proc.stdout


def commit(top, ref, error):
    try:
        sha = git(top, 'rev-parse', '--verify', '--quiet', ref + '^{commit}').decode('ascii', 'replace').strip()
    except CheckError:
        raise CheckError(error) from None
    if not SHA.fullmatch(sha):
        raise CheckError(error)
    return sha


def blank_filters(top):
    """Options that empty every filter driver, so comparing working files runs none."""
    listed = git(top, 'config', '-z', '--name-only', '--get-regexp', r'^filter\.', ok=(0, 1)).split(b'\0')
    names = {match.group(1) for match in map(FILTER_KEY.fullmatch, (key.rstrip(b'\n') for key in listed)) if match}
    options = []
    for name in sorted(names):
        if b'=' in name or b'\n' in name:  # `-c` splits at the first `=`
            raise CheckError('FILTER_UNSUPPORTED')
        for setting in ('clean=', 'smudge=', 'process=', 'required=false'):
            options += ['-c', 'filter.' + os.fsdecode(name) + '.' + setting]
    return options


def changed_files(top, target):
    """[(path, previous path or None)] of files the change adds, modifies or renames."""
    fields = git(top, *target, '--name-status', '-z', '-M').split(b'\0')[:-1]
    files, position = [], 0
    while position < len(fields):
        status = fields[position].decode('ascii', 'replace')
        paired = status[:1] in ('R', 'C')
        names = [os.fsdecode(name) for name in fields[position + 1:position + (3 if paired else 2)]]
        if not status or len(names) != (2 if paired else 1):
            raise CheckError('GIT_OUTPUT_INVALID')
        position += 1 + len(names)
        if status[:1] != 'D':
            files.append((names[-1], names[0] if paired else None))
    return files


def added_from_diff(top, target, path, previous):
    """[(line number, text)] that the change adds to one file."""
    paths = [previous, path] if previous else [path]
    data = git(top, *target, '-M', '--no-color', '--no-ext-diff', '--no-textconv', '--unified=0', '--', *paths)
    added, number = [], None
    for line in data.decode('utf-8', 'replace').split('\n'):
        hunk = HUNK.match(line)
        if hunk:
            number = int(hunk.group(1))
        elif number is not None and line.startswith('+'):
            added.append((number, line[1:]))
            number += 1
    return added


def added_from_file(top, path):
    """Every line of an untracked regular file; a link or an oversized file adds nothing."""
    try:
        fd = os.open(os.path.join(top, path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return []
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            return []
        raw = stream.read(MAX_FILE + 1)
    if len(raw) > MAX_FILE or b'\0' in raw:
        return []
    return list(enumerate(raw.decode('utf-8', 'replace').split('\n'), 1))


def comment_text(line, extension):
    """Text of a whole-line comment, or None when the line is code."""
    if extension in HASH and line.startswith('#') and not line.startswith('#!'):
        return line[1:].strip()
    if extension in SLASH and line.startswith('//'):
        return line[2:].strip()
    if extension in BLOCK and (line.startswith(('/*', '*/')) or line == '*' or line.startswith('* ')):
        return line.strip('/* ').strip()
    if extension in DASH and line.startswith('--'):
        return line[2:].strip()
    if extension in MARKUP and line.startswith('<!--'):
        return line[4:].replace('-->', '').strip()
    return None


def is_test(path):
    parts = path.split('/')
    return bool(TEST_FOLDERS.intersection(parts[:-1]) or TEST_NAME.search(parts[-1]))


def classify(lines, extension):
    """[(kind, line number, text)] for the added lines of one file."""
    found, previous = [], None
    for number, raw in lines:
        line = raw.strip()[:MAX_LINE]
        if not line:
            continue
        comment = comment_text(line, extension)
        shell = extension in SHELL
        if SUPPRESSION.search(line):
            kind = 'suppression'
        elif comment is not None:
            kind = 'justification_comment' if JUSTIFIES.search(comment) else 'comment' if comment else None
        elif SKIPPED_TEST.search(line):
            kind = 'skipped_test'
        elif SWALLOWED.search(line) or (shell and SHELL_SWALLOWED.search(line)):
            kind = 'swallowed_error'
        elif TIMING.search(line) or (shell and SHELL_SLEEP.search(line)):
            kind = 'timing'
        else:
            kind = None
        # `except ...:` followed by a bare `pass`, both added, swallows the error too.
        if line == 'pass' and previous and previous[0] == number - 1 and EXCEPT_OPEN.match(previous[1]):
            found.append(('swallowed_error', previous[0], previous[1]))
        if kind:
            found.append((kind, number, line))
        previous = (number, line)
    return found


def scan(repo, base, uncommitted=False):
    if not repo or not os.path.isdir(repo):
        raise CheckError('GIT_REPOSITORY_REQUIRED')
    try:
        top = os.fsdecode(git(os.path.realpath(repo), 'rev-parse', '--show-toplevel')).rstrip('\n')
    except CheckError as exc:
        raise CheckError('GIT_REPOSITORY_REQUIRED' if str(exc) == 'GIT_COMMAND_FAILED' else str(exc)) from None
    if not os.path.isabs(top):
        raise CheckError('GIT_REPOSITORY_REQUIRED')
    # An option-looking ref never reaches Git.
    if base.startswith('-') or not 0 < len(base) <= 256 or any(ord(char) < 32 or ord(char) == 127 for char in base):
        raise CheckError('BAD_BASE')
    base_sha, head = commit(top, base, 'BAD_BASE'), commit(top, 'HEAD', 'HEAD_COMMIT_REQUIRED')
    merge_base = git(top, 'merge-base', base_sha, head, ok=(0, 1)).decode('ascii', 'replace').strip()
    if not SHA.fullmatch(merge_base):
        raise CheckError('MERGE_BASE_NOT_FOUND')
    target = [*blank_filters(top), 'diff', merge_base] if uncommitted else ['diff', merge_base, head]
    files = [(path, previous, False) for path, previous in changed_files(top, target)]
    if uncommitted:
        untracked = git(top, 'ls-files', '-z', '--others', '--exclude-standard').split(b'\0')[:-1]
        files += [(os.fsdecode(name), None, True) for name in untracked if not name.endswith(b'/')]
    files = sorted(item for item in files if os.path.splitext(item[0])[1].lower() in CODE)
    truncated = ['CHANGED_FILES'] if len(files) > MAX_FILES else []
    signals, lines_added = [], 0
    for path, previous, untracked in files[:MAX_FILES]:
        lines = added_from_file(top, path) if untracked else added_from_diff(top, target, path, previous)
        lines_added += len(lines)
        tested = is_test(path)
        for kind, number, text in classify(lines, os.path.splitext(path)[1].lower()):
            signals.append({'kind': kind, 'path': path, 'line': number, 'text': text[:MAX_TEXT], 'in_test': tested})
    counts = {kind: sum(1 for signal in signals if signal['kind'] == kind) for kind in ORDER}
    signals.sort(key=lambda signal: (ORDER.index(signal['kind']), signal['path'], signal['line']))
    if len(signals) > MAX_SIGNALS:
        truncated.append('SIGNALS')
    return {
        'schema_version': 1,
        'base': base_sha,
        'merge_base': merge_base,
        'head': head,
        'uncommitted': uncommitted,
        'files_scanned': min(len(files), MAX_FILES),
        'lines_added': lines_added,
        'counts': counts,
        'signals': signals[:MAX_SIGNALS],
        'truncated': truncated,
        'limits': LIMITS + (['WORKING_FILES_INCLUDED'] if uncommitted else ['UNCOMMITTED_AND_UNTRACKED_CHANGES_NOT_INCLUDED']),
        'notice': 'Read-only. A signal is a prompt to look, not a defect.',
    }


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise CheckError('INVALID_ARGUMENTS')


def main(argv=None):
    parser = Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', choices=['scan'])
    parser.add_argument('--repo', required=True, help='checkout that holds the change')
    parser.add_argument('--base', required=True, help='ref the change will merge into; its merge base with HEAD is used')
    parser.add_argument('--uncommitted', action='store_true',
                        help='scan the working tree: staged, unstaged and untracked files too')
    try:
        args = parser.parse_args(argv)
        print(json.dumps(scan(args.repo, args.base, args.uncommitted), indent=2, ensure_ascii=False))
        return 0
    except CheckError as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
