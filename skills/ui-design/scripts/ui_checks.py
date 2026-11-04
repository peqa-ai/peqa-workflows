#!/usr/bin/env python3
"""Portable, read-only design-system checks for ui-design. Python 3.10+, macOS/Linux.

Commands print one JSON object on stdout. Exit 0: no findings, no missing
contracts, every pair passes. Exit 1: findings, missing contracts or a failing
pair. Exit 2: usage or input error, printed as {"error": "<CODE>"}.

    literals  --repo REPO --base BASE [--tokens PATH]... [--wrappers PATH]... [-- PATHSPEC...]
    literals  --diff FILE.diff --root DIR [--tokens PATH]... [--wrappers PATH]...
    contracts --repo REPO --base BASE [-- PATHSPEC...]
    contracts --diff FILE.diff
    contrast  --pair FG BG [--pair FG BG]... [--kind text|large|ui]

Public API (errors raise CheckError carrying only a fixed code):
    literals_git(repo, base, pathspecs=(), tokens=(), wrappers=()) -> {findings, scanned, skipped}
    literals_diff(diff_file, root, tokens=(), wrappers=()) -> {findings, scanned, skipped}
    contracts_git(repo, base, pathspecs=()) -> {missing, scanned, skipped}
    contracts_diff(diff_file) -> {missing, scanned, skipped}
    contrast(pairs, kind='text') -> {pairs}
    parse_color(text) -> (red, green, blue, alpha), channels 0-255 and alpha 0-1
    PATTERNS, EXTENSIONS: the single source of literal patterns and file routing.

Scope. Git mode compares BASE with the working tree, so staged and unstaged
edits count, and adds untracked files that Git does not ignore as if every line
were new. Only added lines are scanned; preexisting lines are not reported.
Renames are detected, so a moved file is not new. Pathspecs, --tokens and
--wrappers are literal paths, relative to --repo or absolute; a pathspec that
exists nowhere is PATHSPEC_NOT_FOUND. Output paths are relative to the
repository root (Git mode) or to --root (diff mode). Diff mode reads a unified
diff such as `diff -ruN -U0 orig new`; files without content in the diff
(`Only in` lines from a diff without -N) are listed as skipped.

Contracts compare an old side with a new side. In Git mode both sides are
whole files: the BASE blob of each changed path (read with `git cat-file`,
without conversion) against its working-tree file and every untracked file,
so a change to the value alone is seen and a contract kept on an unchanged
line is not missing. In diff mode the sides are the hunks with their context
lines; generate the diff with context (`diff -ruN`), since with -U0 a change
to a value split from its attribute or call name cannot be seen. A call or tag
split across consecutive lines counts once, at its first line; whitespace
around `=` is accepted, and assignments such as `const id = "x"` are not
attributes. `literals` scans added lines only, never context.

Guarantees. No Git writes or optional locks, hooks, external diff, textconv,
pager, fsmonitor, network or shell; nothing from the scanned files is
executed. Requires Git 2.32 or later (GIT_UNSUPPORTED otherwise). Global and
system Git configuration, the caller's GIT_* variables (GIT_CONFIG_PARAMETERS,
GIT_CONFIG_COUNT...) and global or system attributes are ignored.
GIT_ALLOW_PROTOCOL is set empty, which outranks any protocol.<name>.allow in
the repository, so a lazy fetch from a promisor remote cannot use any
transport (GIT_NO_LAZY_FETCH is also set, honored from Git 2.44); a missing
object is then GIT_COMMAND_FAILED. core.fsmonitor is set empty, which disables
it on every supported release. No Git filter runs: every filter driver defined
in the configuration Git reads (repository, worktree and included files),
including the driver with an empty name, is overridden with empty clean,
smudge and process commands and required=false on every Git call, whichever
attributes file selects it (.gitattributes, info/attributes). The driver list
is read again after the last Git call; a change is FILTER_CONFIG_CHANGED and a
driver name that cannot be overridden is FILTER_UNSUPPORTED, both exit 2.
Files are opened without following symlinks. Symlinks, submodules, nested
repositories, binaries, files over 1 MiB, lines over 20000 characters,
unsupported extensions and files whose content no longer matches the diff are
listed in "skipped" with a reason. Work is bounded in time (checked per line),
bytes, files, findings and contract entries, and patterns run in linear time
on long lines; exceeding a bound is an error, not a partial result. Findings
are lint evidence for the report, not a design review.
"""

from __future__ import annotations

import argparse
import bisect
import errno
import json
import os
import re
import selectors
import stat
import subprocess
import sys
import time


MAX_SECONDS = 30
GIT_SECONDS = 20
MAX_GIT_BYTES = 16 * 1024 * 1024
MAX_DIFF_BYTES = 16 * 1024 * 1024
MAX_FILE_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_FILES = 10000
MAX_FINDINGS = 10000
MAX_LINE_CHARS = 20000
MAX_ARGUMENTS = 1000
MAX_CONTRACT_ENTRIES = 50000
MAX_FILTER_DRIVERS = 256
MAX_TEXT = 200
MIN_GIT = (2, 32)
SHA = re.compile(r'(?:[0-9a-f]{40}|[0-9a-f]{64})\Z')
KINDS = {'text': 4.5, 'large': 3.0, 'ui': 3.0}
CATEGORIES = ('color', 'length', 'arbitrary_value', 'inline_style', 'raw_control')
TOKEN_CATEGORIES = frozenset(('color', 'length', 'arbitrary_value'))
WRAPPER_CATEGORIES = frozenset(('raw_control',))

# Literal patterns. A hex color needs 3, 4, 6 or 8 digits and is not part of a
# word, entity, URL fragment, private member or href; in web files a hex that
# starts a selector (`#fab {`) is not a color. NUMBER has a single way to match
# a digit run, so no pattern backtracks quadratically on long lines.
NUMBER = r'(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)'
HEX = (r'(?<![\w&./#])(?<!href=")(?<!href=\')(?<!href=\{")(?<!href=\{\')(?<!url\()'
       r'#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![\w(-])')
COLOR_FUNCTION = r'(?<![\w.$-])(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|color-mix)\('
# A declaration: a property (an identifier of at most 64 characters followed by
# `:`) whose name matches the first pattern, and whose value, up to the next `;`
# or `}`, matches the second.
CSS_LENGTH = (r'(?i:margin|padding|gap|font(?:-?size)?|border[a-z-]*?radius)[A-Za-z-]*\Z',
              r'(?<![\w.])' + NUMBER + r'(?:px|rem|em)\b')
TAILWIND_ARBITRARY = r'(?<=-)\[(?:#[0-9a-fA-F]{3,8}|-?' + NUMBER + r'(?:px|rem|em))(?![\w-])'
STYLE_ATTRIBUTE = r'''\bstyle=(?:\{\{|"|')'''
IMPORTANT = r'!\s*important\b'
RAW_CONTROL = r'<(?:button|input|select|textarea)(?![\w-])'
SWIFT_COLOR = (r'\b(?:UI|NS)?Color\(\s*(?:\.(?:sRGB|sRGBLinear|displayP3)\b|'
               r'(?:red|hue|white|hex|displayP3Red):)|#colorLiteral\(')
SWIFT_LENGTH = (r'\.padding\(\s*(?:(?:\.[A-Za-z]+|\[[^\]]{0,256}\])\s*,\s*)?-?' + NUMBER + r'\b'
                r'|\bspacing:\s*-?' + NUMBER + r'\b'
                r'|\bcornerRadius\s*[:(=]\s*' + NUMBER + r'\b'
                r'|\.system\(\s*size:\s*' + NUMBER + r'\b'
                r'|\bsystemFont\(\s*ofSize:\s*' + NUMBER + r'\b')
KOTLIN_COLOR = r'\bColor\(\s*(?:[0-9]|red\s*=)|\bColor\.(?:parseColor|rgb|argb)\('
KOTLIN_LENGTH = r'\b[0-9]+(?:\.[0-9]+)?\.(?:dp|sp)\b'

PATTERNS = {
    'css': {'color': (HEX, COLOR_FUNCTION), 'length': (CSS_LENGTH,),
            'arbitrary_value': (TAILWIND_ARBITRARY,), 'inline_style': (IMPORTANT,)},
    'web': {'color': (HEX, COLOR_FUNCTION), 'length': (CSS_LENGTH,),
            'arbitrary_value': (TAILWIND_ARBITRARY,), 'inline_style': (STYLE_ATTRIBUTE, IMPORTANT),
            'raw_control': (RAW_CONTROL,)},
    'swift': {'color': (HEX, SWIFT_COLOR), 'length': (SWIFT_LENGTH,)},
    'kotlin': {'color': (HEX, KOTLIN_COLOR), 'length': (KOTLIN_LENGTH,)},
}
EXTENSIONS = {
    **dict.fromkeys(('css', 'scss', 'sass', 'less', 'pcss', 'postcss'), 'css'),
    **dict.fromkeys(('html', 'htm', 'jsx', 'tsx', 'js', 'mjs', 'cjs', 'ts', 'mts', 'cts',
                     'vue', 'svelte', 'astro', 'mdx', 'erb', 'ejs', 'hbs', 'handlebars',
                     'njk', 'liquid', 'twig'), 'web'),
    'swift': 'swift', 'kt': 'kotlin', 'kts': 'kotlin',
}
LINE_COMMENT_EXTENSIONS = frozenset(('scss', 'sass', 'less'))
CONTRACT_KINDS = frozenset(('web', 'swift', 'kotlin'))
COMMENT_PREFIXES = ('//', '/*', '*', '<!--', '{/*')

_PROPERTY = re.compile(r'(?<![\w-])(-{0,2}[A-Za-z][\w-]*)\s*:')
_VALUE_END = re.compile(r'[;}]')


class _Declaration:
    """finditer() over declarations; each value is searched at most once."""

    def __init__(self, name, value):
        self.name, self.value = re.compile(name), re.compile(value)

    def finditer(self, line):
        searched = -1
        for match in _PROPERTY.finditer(line):
            # A property inside a value already searched has the same end, so
            # its value is a suffix of a region that was already examined.
            if match.start() < searched:
                continue
            name = match.group(1)
            if len(name) > 64 or not self.name.search(name):
                continue
            end = _VALUE_END.search(line, match.end())
            searched = end.start() if end else len(line)
            if self.value.search(line, match.end(), searched):
                yield match


def _compile(source):
    return _Declaration(*source) if isinstance(source, tuple) else re.compile(source)


_COMPILED = {kind: [(category, [(source is HEX, _compile(source)) for source in sources])
                    for category, sources in table.items()]
             for kind, table in PATTERNS.items()}
_SELECTOR_STOP = re.compile(r'[;{}()"\'`]')
_CSS_TOKEN = re.compile(r'/\*|//|[#@]\{|["\'{};]')
_STRING_BODY = {'"': re.compile(r'(?:[^"\\\n]|\\[\s\S])*'), "'": re.compile(r"(?:[^'\\\n]|\\[\s\S])*")}
_BLOCK_COMMENT = re.compile(r'/\*.*?(?:\*/|\Z)', re.S)
_LINE_COMMENT = re.compile(r'(?m)(?:^|(?<=\s))//.*$')
_ROOT_SELECTOR = re.compile(r':root(?![\w-])')
_THEME = re.compile(r'@theme(?![\w-])')
_TOKENS_LAYER = re.compile(r'@layer\s+tokens(?:\.[\w-]+)*')
_HUNK = re.compile(rb'@@ -([0-9]+)(?:,([0-9]+))? \+([0-9]+)(?:,([0-9]+))? @@')
_BINARY = re.compile(rb'Binary files (.+) and (.+) differ\Z')
_ONLY_IN = re.compile(rb'Only in (.+): (.+)\Z')
# Contract values are bounded (1024 characters, braces nested one level, eight
# inner groups) so matching stays linear in the length of a run of lines.
_ATTRIBUTE = re.compile(r'''(?<![\w.$-])(id|name|for|htmlFor|autocomplete|autoComplete|href|data-[A-Za-z0-9_-]{1,64})'''
                        r'''\s*=\s*("[^"\n]{0,1024}"|'[^'\n]{0,1024}'|'''
                        r'''\{[^{}]{0,1024}(?:\{[^{}]{0,1024}\}[^{}]{0,1024}){0,8}\})''')
_STATEMENT_BEFORE = re.compile(r'(?:\b(?:const|let|var|val|export|return)\s+|[(,\[{=!&|+?]\s*)\Z')
_STATEMENT_AFTER = re.compile(r'[ \t]*;')
_SWIFT_IDENTIFIER = re.compile(r'\.accessibilityIdentifier\(\s*"((?:[^"\\\n]|\\.){0,1024})"\s*\)')
_COMPOSE_TAG = re.compile(r'\btestTag\(\s*"((?:[^"\\\n]|\\.){0,1024})"\s*\)')
_FILTER_KEY = re.compile(rb'filter\.([\s\S]*)\.(?:clean|smudge|process|required)\Z')
_GIT_VERSION = re.compile(rb'git version ([0-9]+)\.([0-9]+)')
_STRING_EXPRESSION = re.compile(r'''"([^"]*)"|'([^']*)'|`([^`$]*)`''')
_CANONICAL = {'htmlFor': 'for', 'autoComplete': 'autocomplete'}
_HEX_COLOR = re.compile(r'#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})')
_RGB = re.compile(r'rgba?\((.*)\)', re.I | re.S)
_NUMBER = re.compile(r'\+?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(%?)')
_ESCAPES = {ord('a'): 7, ord('b'): 8, ord('t'): 9, ord('n'): 10, ord('v'): 11,
            ord('f'): 12, ord('r'): 13, ord('"'): 34, ord('\\'): 92}
_DIFF_FLAGS = ['-c', 'diff.relative=false', '-c', 'diff.noprefix=false',
               '-c', 'diff.mnemonicPrefix=false', '-c', 'diff.interHunkContext=0',
               'diff', '--no-color', '--no-ext-diff', '--no-textconv', '-M', '-U0',
               '--inter-hunk-context=0', '--src-prefix=a/', '--dst-prefix=b/',
               '--submodule=short', '--ignore-submodules=dirty']


class CheckError(Exception):
    """Only fixed codes cross the CLI boundary; raw paths and messages never do."""


class _Budget:
    def __init__(self):
        self.deadline = time.monotonic() + MAX_SECONDS
        self.bytes = 0
        self.files = 0
        self.git_config = []  # filter overrides added to every later Git call

    def check(self):
        if time.monotonic() > self.deadline:
            raise CheckError('TIMEOUT')

    def file(self, count=1):
        self.files += count
        if self.files > MAX_FILES:
            raise CheckError('LIMIT_EXCEEDED')

    def read(self, size):
        self.bytes += size
        if self.bytes > MAX_TOTAL_BYTES:
            raise CheckError('LIMIT_EXCEEDED')


class _Change:
    """One file pair from a unified diff; paths are str, None for /dev/null."""
    __slots__ = ('old', 'new', 'old_mode', 'new_mode', 'binary', 'only_in', 'unsafe', 'git_format',
                 'added', 'removed', 'old_lines', 'new_lines')

    def __init__(self, old=None, new=None):
        self.old, self.new = old, new
        self.old_mode = self.new_mode = None
        self.binary = self.only_in = self.unsafe = self.git_format = False
        self.added, self.removed = [], []
        # Each side of every hunk, context included: (line number, text).
        self.old_lines, self.new_lines = [], []


# Git -----------------------------------------------------------------------

def _git_environment():
    """Caller GIT_* variables dropped; config, attributes and transports locked down.

    GIT_ALLOW_PROTOCOL="" allows no transport and is checked before any
    protocol.<name>.allow setting (transport.c since Git 2.6), so a lazy fetch
    from a promisor remote cannot reach the network or run an ext:: command,
    also on Git releases that ignore GIT_NO_LAZY_FETCH (before 2.44).
    """
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env.update(GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0', GIT_CONFIG_NOSYSTEM='1',
               GIT_CONFIG_GLOBAL=os.devnull, GIT_ATTR_NOSYSTEM='1', GIT_NO_REPLACE_OBJECTS='1',
               GIT_NO_LAZY_FETCH='1', GIT_ALLOW_PROTOCOL='', LC_ALL='C')
    return env


def _git(cwd, args, budget, optional=False, allow=(), stdin=None):
    """No shell, bounded output and time; global config, helpers and filters disabled.

    Exit codes in `allow` return the output; any other failure returns None when
    optional, else raises. `stdin` bytes are written while output is read.
    """
    budget.check()
    # An empty core.fsmonitor disables it on every supported release; before
    # 2.36 any other value, `false` included, names a hook to run.
    command = ['git', '--no-pager', '--no-optional-locks', '--literal-pathspecs',
               '-c', 'core.fsmonitor=', '-c', 'core.hooksPath=' + os.devnull,
               '-c', 'core.attributesFile=' + os.devnull,
               '-c', 'core.quotePath=false', '-c', 'protocol.allow=never',
               *budget.git_config, '-C', cwd, *args]
    try:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL if stdin is None else subprocess.PIPE,
                                env=_git_environment())
    except OSError as exc:
        raise CheckError('GIT_UNAVAILABLE') from exc
    output = bytearray()
    pending = memoryview(stdin or b'')
    deadline = min(budget.deadline, time.monotonic() + GIT_SECONDS)
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout, selectors.EVENT_READ)
            if stdin is not None:
                os.set_blocking(proc.stdin.fileno(), False)
                if pending:
                    selector.register(proc.stdin, selectors.EVENT_WRITE)
                else:
                    proc.stdin.close()
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise CheckError('TIMEOUT')
                for key, _ in selector.select(min(remaining, 0.2)):
                    if key.fileobj is proc.stdin:
                        try:
                            pending = pending[os.write(proc.stdin.fileno(), pending[:65536]):]
                        except (BlockingIOError, InterruptedError):
                            continue
                        except BrokenPipeError:
                            pending = pending[:0]
                        if not pending:
                            selector.unregister(proc.stdin)
                            proc.stdin.close()
                        continue
                    block = os.read(key.fileobj.fileno(), 65536)
                    if not block:
                        selector.unregister(key.fileobj)
                    else:
                        output.extend(block)
                        if len(output) > MAX_GIT_BYTES:
                            raise CheckError('LIMIT_EXCEEDED')
            try:
                status = proc.wait(timeout=max(0.01, deadline - time.monotonic()))
            except subprocess.TimeoutExpired as exc:
                raise CheckError('TIMEOUT') from exc
        if status and status not in allow:
            if optional:
                return None
            raise CheckError('GIT_COMMAND_FAILED')
        return bytes(output)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        proc.stdout.close()
        if proc.stdin is not None and not proc.stdin.closed:
            try:
                proc.stdin.close()
            except BrokenPipeError:
                pass


def _toplevel(repo, budget):
    try:
        start = os.path.realpath(os.fspath(repo))
    except (TypeError, ValueError, OSError) as exc:
        raise CheckError('NOT_A_GIT_REPO') from exc
    if not os.path.isdir(start):
        raise CheckError('NOT_A_GIT_REPO')
    version = _GIT_VERSION.match(_git(start, ['version'], budget, optional=True) or b'')
    if not version or (int(version.group(1)), int(version.group(2))) < MIN_GIT:
        raise CheckError('GIT_UNSUPPORTED')
    output = _git(start, ['rev-parse', '--show-toplevel'], budget, optional=True)
    top = os.fsdecode(output or b'').rstrip('\n')
    if not top or not os.path.isabs(top):
        raise CheckError('NOT_A_GIT_REPO')
    return os.path.realpath(top), start


def _filter_drivers(top, budget):
    """Names of every filter driver in the configuration Git reads here.

    `git config` reads the same sources as the later commands (repository and
    worktree files with their includes; global, system and environment
    configuration are excluded by _git) and runs no filter itself.
    """
    output = _git(top, ['config', '-z', '--name-only', '--get-regexp', r'^filter\.'], budget, allow=(1,))
    names = set()
    for key in output.split(b'\0'):
        match = _FILTER_KEY.fullmatch(key.rstrip(b'\n'))
        if match:
            names.add(match.group(1))
    return names


def _neutralize_filters(top, budget):
    """Override every driver so no clean, smudge or process command can run."""
    names = _filter_drivers(top, budget)
    if len(names) > MAX_FILTER_DRIVERS:
        raise CheckError('LIMIT_EXCEEDED')
    overrides = []
    for raw in sorted(names):
        # `-c` splits at the first `=`, so such a name cannot be overridden.
        if b'=' in raw or b'\n' in raw or b'\0' in raw:
            raise CheckError('FILTER_UNSUPPORTED')
        name = os.fsdecode(raw)
        overrides += ['-c', 'filter.' + name + '.clean=', '-c', 'filter.' + name + '.smudge=',
                      '-c', 'filter.' + name + '.process=', '-c', 'filter.' + name + '.required=false']
    budget.git_config = overrides
    return names


def _resolve_base(top, base, budget):
    if (type(base) is not str or not base or base.startswith('-') or len(base) > 256
            or any(ord(char) < 32 or ord(char) == 127 for char in base)):
        raise CheckError('BAD_BASE')
    output = _git(top, ['rev-parse', '--verify', '--quiet', base + '^{commit}'], budget, optional=True)
    sha = (output or b'').decode('ascii', 'replace').strip()
    if not SHA.fullmatch(sha):
        raise CheckError('BAD_BASE')
    return sha


def _contained(top, base, value, code):
    """Lexical path relative to top, resolving ancestors but not the final name."""
    if type(value) is not str or not value or '\0' in value or len(value) > 4096:
        raise CheckError(code)
    joined = os.path.normpath(os.path.join(base, value))
    head, tail = os.path.split(joined)
    resolved = os.path.join(os.path.realpath(head), tail) if tail else os.path.realpath(joined)
    relative = os.path.relpath(resolved, top)
    if relative == os.curdir:
        return '.'
    parts = relative.split(os.sep)
    if os.path.isabs(relative) or parts[0] in (os.pardir, '.git'):
        raise CheckError(code)
    return '/'.join(parts)


def _check_pathspecs(top, sha, specs, budget):
    """A pathspec must name something now, in the index or in BASE."""
    absent = [spec for spec in specs if spec != '.' and not os.path.lexists(os.path.join(top, spec))]
    if not absent:
        return
    known = set()
    for args in (['ls-tree', '-r', '-z', '--name-only', '--full-tree', sha, '--', *absent],
                 ['ls-files', '-z', '--cached', '--', *absent]):
        known.update(os.fsdecode(item) for item in _git(top, args, budget).split(b'\0') if item)
    for spec in absent:
        if not any(path == spec or path.startswith(spec + '/') for path in known):
            raise CheckError('PATHSPEC_NOT_FOUND')


def _git_scope(repo, base, pathspecs, budget):
    top, start = _toplevel(repo, budget)
    drivers = _neutralize_filters(top, budget)
    sha = _resolve_base(top, base, budget)
    if len(pathspecs) > MAX_ARGUMENTS:
        raise CheckError('LIMIT_EXCEEDED')
    specs = sorted({_contained(top, start, value, 'BAD_PATHSPEC') for value in pathspecs})
    _check_pathspecs(top, sha, specs, budget)
    changes = _changes(_parse_patch(_git(top, [*_DIFF_FLAGS, sha, '--', *specs], budget),
                                    'GIT_OUTPUT_INVALID'), git=True)
    others = _git(top, ['ls-files', '-z', '--others', '--exclude-standard', '--', *specs], budget)
    untracked = sorted({os.fsdecode(item) for item in others.split(b'\0') if item})
    _confirm_filters(top, drivers, budget)
    budget.file(len(changes) + len(untracked))
    return top, start, sha, drivers, changes, untracked


def _confirm_filters(top, drivers, budget):
    """A driver defined while Git was running would not have been overridden."""
    if _filter_drivers(top, budget) != drivers:
        raise CheckError('FILTER_CONFIG_CHANGED')


def _base_blobs(top, sha, paths, budget):
    """{path: (skip_reason, bytes)} for paths in BASE, read as stored objects.

    `cat-file --batch` without --filters or --textconv applies no conversion.
    Names travel on stdin, one per line, so a path may not contain a newline.
    """
    if not paths:
        return {}
    names = b''.join(sha.encode('ascii') + b':' + os.fsencode(path) + b'\n' for path in paths)
    checks = _git(top, ['cat-file', '--batch-check'], budget, stdin=names).split(b'\n')
    if len(checks) < len(paths):
        raise CheckError('GIT_OUTPUT_INVALID')
    result, wanted = {}, []
    for path, line in zip(paths, checks):
        fields = line.split(b' ')
        if len(fields) != 3 or not SHA.fullmatch(fields[0].decode('ascii', 'replace')) or not fields[2].isdigit():
            result[path] = ('missing', None)
        elif fields[1] != b'blob':
            result[path] = ('not_regular', None)
        elif int(fields[2]) > MAX_FILE_BYTES:
            result[path] = ('too_large', None)
        else:
            wanted.append((path, fields[0], int(fields[2])))
    if not wanted:
        return result
    output = _git(top, ['cat-file', '--batch'], budget, stdin=b''.join(oid + b'\n' for _, oid, _ in wanted))
    position = 0
    for path, oid, size in wanted:
        end = output.find(b'\n', position)
        if end < 0 or output[position:end] != oid + b' blob ' + str(size).encode('ascii'):
            raise CheckError('GIT_OUTPUT_INVALID')
        data = output[end + 1:end + 1 + size]
        position = end + 2 + size
        if len(data) != size:
            raise CheckError('GIT_OUTPUT_INVALID')
        budget.read(size)
        result[path] = ('binary', None) if b'\0' in data[:8000] else (None, data)
    return result


# Unified diff parsing ------------------------------------------------------

class _Section:
    __slots__ = ('header', 'minus', 'plus', 'has_paths', 'hunks', 'rename_from', 'rename_to',
                 'old_mode', 'new_mode', 'created', 'deleted', 'binary', 'only_in', 'added', 'removed',
                 'old_lines', 'new_lines')

    def __init__(self, header=None):
        self.header = header
        self.minus = self.plus = self.rename_from = self.rename_to = None
        self.old_mode = self.new_mode = None
        self.has_paths = self.hunks = self.created = self.deleted = self.binary = self.only_in = False
        self.added, self.removed = [], []
        self.old_lines, self.new_lines = [], []


def _unquote(raw):
    """Decode a C-quoted Git or diff path; return (bytes, rest)."""
    output = bytearray()
    index = 1
    while index < len(raw):
        char = raw[index]
        if char == 0x22:
            return bytes(output), raw[index + 1:]
        if char == 0x5c:
            following = raw[index + 1:index + 2]
            octal = raw[index + 1:index + 4]
            if len(octal) == 3 and all(0x30 <= digit <= 0x37 for digit in octal):
                output.append(int(octal, 8) & 0xFF)
                index += 4
                continue
            if following and following[0] in _ESCAPES:
                output.append(_ESCAPES[following[0]])
                index += 2
                continue
            raise ValueError('bad escape')
        output.append(char)
        index += 1
    raise ValueError('unterminated quote')


def _header_path(raw):
    """Path from a ---/+++ line: quoted, or up to a tab (Git or timestamp)."""
    raw = raw.rstrip(b'\r')
    if raw.startswith(b'"'):
        raw = _unquote(raw)[0]
    elif b'\t' in raw:
        raw = raw.split(b'\t', 1)[0]
    return None if raw == b'/dev/null' else raw


def _git_header_paths(rest):
    """Both paths from `diff --git A B`, needed only without ---/+++ lines."""
    try:
        if rest.startswith(b'"'):
            first, tail = _unquote(rest)
            tail = tail[1:]
            second = _unquote(tail)[0] if tail.startswith(b'"') else tail
            return first, second
        if b' "' in rest:
            first, tail = rest.split(b' "', 1)
            return first, _unquote(b'"' + tail)[0]
    except ValueError:
        return None, None
    if len(rest) % 2 == 1:
        half = len(rest) // 2
        first, second = rest[:half], rest[half + 1:]
        if rest[half:half + 1] == b' ' and first[2:] == second[2:]:
            return first, second
    return None, None


def _parse_patch(data, code):
    """Sections of a Git or GNU unified diff; hunks are consumed by line count."""
    lines = data.split(b'\n')
    if lines and lines[-1] == b'':
        lines.pop()
    sections = []
    current = None
    index = 0
    try:
        while index < len(lines):
            line = lines[index]
            index += 1
            if line.startswith(b'diff --git '):
                current = _Section(line[11:].rstrip(b'\r'))
                sections.append(current)
            elif line.startswith(b'--- ') and index < len(lines) and lines[index].startswith(b'+++ '):
                if current is None or current.has_paths or current.hunks or current.header is None:
                    current = _Section()
                    sections.append(current)
                current.minus, current.plus = _header_path(line[4:]), _header_path(lines[index][4:])
                current.has_paths = True
                index += 1
            elif line.startswith(b'@@ '):
                match = _HUNK.match(line)
                if current is None or match is None:
                    raise CheckError(code)
                old_line, new_line = int(match.group(1)), int(match.group(3))
                old_left = int(match.group(2) or b'1')
                new_left = int(match.group(4) or b'1')
                while old_left > 0 or new_left > 0:
                    if index >= len(lines):
                        raise CheckError(code)
                    body = lines[index]
                    index += 1
                    tag = body[:1]
                    if tag == b'+':
                        current.added.append((new_line, body[1:]))
                        current.new_lines.append((new_line, body[1:]))
                        new_line += 1
                        new_left -= 1
                    elif tag == b'-':
                        current.removed.append((old_line, body[1:]))
                        current.old_lines.append((old_line, body[1:]))
                        old_line += 1
                        old_left -= 1
                    elif tag == b' ' or body in (b'', b'\r'):
                        current.old_lines.append((old_line, body[1:]))
                        current.new_lines.append((new_line, body[1:]))
                        old_line += 1
                        new_line += 1
                        old_left -= 1
                        new_left -= 1
                    elif tag != b'\\':
                        raise CheckError(code)
                    if old_left < 0 or new_left < 0:
                        raise CheckError(code)
                current.hunks = True
            elif (line.startswith(b'Binary files ') and current is not None
                  and current.header is not None and not current.has_paths):
                current.binary = True
            elif line.startswith(b'Binary files ') or line.startswith(b'Only in '):
                stripped = line.rstrip(b'\r')
                binary = _BINARY.match(stripped)
                only = _ONLY_IN.match(stripped)
                if not (binary or only):
                    continue
                current = _Section()
                sections.append(current)
                current.has_paths = True
                if binary:
                    current.binary = True
                    current.minus = None if binary.group(1) == b'/dev/null' else binary.group(1)
                    current.plus = None if binary.group(2) == b'/dev/null' else binary.group(2)
                else:
                    current.only_in = True
                    current.plus = only.group(1).rstrip(b'/') + b'/' + only.group(2)
            elif current is not None and current.header is not None and not current.has_paths and not current.hunks:
                _extended_header(current, line.rstrip(b'\r'))
    except ValueError as exc:
        raise CheckError(code) from exc
    return sections


def _extended_header(section, line):
    for prefix, field in ((b'new file mode ', 'new_mode'), (b'deleted file mode ', 'old_mode'),
                          (b'old mode ', 'old_mode'), (b'new mode ', 'new_mode')):
        if line.startswith(prefix):
            setattr(section, field, line[len(prefix):].decode('ascii', 'replace').strip())
            section.created = section.created or prefix == b'new file mode '
            section.deleted = section.deleted or prefix == b'deleted file mode '
            return
    if line.startswith(b'index '):
        parts = line.split()
        if len(parts) == 3:
            mode = parts[2].decode('ascii', 'replace')
            section.old_mode = section.old_mode or mode
            section.new_mode = section.new_mode or mode
        return
    for prefix, field in ((b'rename from ', 'rename_from'), (b'copy from ', 'rename_from'),
                          (b'rename to ', 'rename_to'), (b'copy to ', 'rename_to')):
        if line.startswith(prefix):
            value = line[len(prefix):]
            setattr(section, field, _unquote(value)[0] if value.startswith(b'"') else value)
            return


def _strip(raw, prefix):
    if raw is None:
        return None
    return raw[len(prefix):] if raw.startswith(prefix) else raw


def _changes(sections, git):
    """File pairs with decoded paths. Git sections drop their a/ and b/ prefixes."""
    changes = []
    for section in sections:
        if section.header is not None:
            old, new = (section.minus, section.plus) if section.has_paths else _git_header_paths(section.header)
            old, new = _strip(old, b'a/'), _strip(new, b'b/')
            if not section.has_paths:
                old = section.rename_from if section.rename_from is not None else old
                new = section.rename_to if section.rename_to is not None else new
                if section.created:
                    old = None
                if section.deleted:
                    new = None
            if old is None and new is None and not (section.created or section.deleted):
                raise CheckError('GIT_OUTPUT_INVALID' if git else 'DIFF_INVALID')
        else:
            old, new = section.minus, section.plus
        change = _Change(None if old is None else os.fsdecode(old), None if new is None else os.fsdecode(new))
        change.old_mode, change.new_mode = section.old_mode, section.new_mode
        change.binary, change.only_in = section.binary, section.only_in
        change.git_format = section.header is not None
        change.added = [(number, _text(raw)) for number, raw in section.added]
        change.removed = [(number, _text(raw)) for number, raw in section.removed]
        change.old_lines = [(number, _text(raw)) for number, raw in section.old_lines]
        change.new_lines = [(number, _text(raw)) for number, raw in section.new_lines]
        changes.append(change)
    return changes


def _text(raw):
    text = raw.decode('utf-8', 'replace')
    return text[:-1] if text.endswith('\r') else text


def _read_diff(path):
    try:
        descriptor = os.open(os.fspath(path), os.O_RDONLY | os.O_NONBLOCK)
    except (OSError, TypeError, ValueError) as exc:
        raise CheckError('DIFF_UNREADABLE') from exc
    try:
        with os.fdopen(descriptor, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise CheckError('DIFF_UNREADABLE')
            if info.st_size > MAX_DIFF_BYTES:
                raise CheckError('LIMIT_EXCEEDED')
            data = stream.read(MAX_DIFF_BYTES + 1)
    except OSError as exc:
        raise CheckError('DIFF_UNREADABLE') from exc
    if len(data) > MAX_DIFF_BYTES:
        raise CheckError('LIMIT_EXCEEDED')
    sections = _parse_patch(data, 'DIFF_INVALID')
    if data.strip() and not sections:
        raise CheckError('DIFF_INVALID')
    return _changes(sections, git=False)


def _safe_relative(value):
    parts = value.split('/')
    return bool(value) and not value.startswith('/') and all(part not in ('', '.', '..') for part in parts)


def _inside(root, path):
    head, tail = os.path.split(os.path.normpath(path))
    resolved = os.path.join(os.path.realpath(head), tail)
    relative = os.path.relpath(resolved, root)
    relative = '/'.join(relative.split(os.sep))
    return relative if _safe_relative(relative) else None


def _map_to_root(value, root, cwd):
    """Pick the diff path that names a file under --root (like patch -pN)."""
    candidates = []
    within = _inside(root, value if os.path.isabs(value) else os.path.join(cwd, value))
    if within:
        candidates.append(within)
    parts = [part for part in value.split('/') if part not in ('', '.')]
    if not os.path.isabs(value):
        candidates.extend('/'.join(parts[index:]) for index in range(len(parts)))
    for candidate in candidates:
        if _safe_relative(candidate) and os.path.lexists(os.path.join(root, candidate)):
            return candidate
    if within:
        return within
    fallback = '/'.join(parts[1:]) if len(parts) > 1 else '/'.join(parts)
    return fallback if not os.path.isabs(value) and _safe_relative(fallback) else None


def _strip_one(value):
    if value is None or os.path.isabs(value):
        return value
    parts = [part for part in value.split('/') if part not in ('', '.')]
    return '/'.join(parts[1:]) if len(parts) > 1 else '/'.join(parts)


# Files ---------------------------------------------------------------------

def _read_file(root, relative, budget):
    """Return (skip_reason, bytes) without following any symlink below root."""
    if not _safe_relative(relative):
        return 'outside_root', None
    parts = relative.split('/')
    directory = descriptor = None
    try:
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        info = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
        if stat.S_ISLNK(info.st_mode):
            return 'symlink', None
        if not stat.S_ISREG(info.st_mode):
            return 'not_regular', None
        if info.st_size > MAX_FILE_BYTES:
            return 'too_large', None
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(descriptor, 'rb') as stream:
            descriptor = None
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                return 'not_regular', None
            data = stream.read(MAX_FILE_BYTES + 1)
    except FileNotFoundError:
        return 'missing', None
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            return 'symlink', None
        return ('missing' if exc.errno == errno.ENOTDIR else 'unreadable'), None
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if directory is not None:
            os.close(directory)
    if len(data) > MAX_FILE_BYTES:
        return 'too_large', None
    budget.read(len(data))
    if b'\0' in data[:8000]:
        return 'binary', None
    return None, data


def _extension(path):
    name = path.rsplit('/', 1)[-1]
    return name.rsplit('.', 1)[1].lower() if '.' in name.lstrip('.') else ''


def _kind(path):
    return EXTENSIONS.get(_extension(path))


class _Document:
    """Decoded file with lines numbered as Git numbers them (split on LF only)."""

    def __init__(self, data):
        self.text = data.decode('utf-8', 'replace')
        raw = self.text.split('\n')
        self.lines = [line[:-1] if line.endswith('\r') else line for line in raw]
        self.starts = []
        offset = 0
        for line in raw:
            self.starts.append(offset)
            offset += len(line) + 1


def _listed(path, entries):
    return any(entry == '.' or path == entry or path.startswith(entry + '/') for entry in entries)


def _comment_line(line):
    return line.lstrip().startswith(COMMENT_PREFIXES)


# CSS token blocks ----------------------------------------------------------

def _token_prelude(prelude, line_comments):
    cleaned = _BLOCK_COMMENT.sub(' ', prelude)
    if line_comments:
        cleaned = _LINE_COMMENT.sub(' ', cleaned)
    cleaned = ' '.join(cleaned.split())
    if _THEME.match(cleaned) or _TOKENS_LAYER.fullmatch(cleaned):
        return True
    return any(_ROOT_SELECTOR.match(part.strip()) for part in cleaned.split(','))


def _css_regions(text, line_comments, budget):
    """Intervals inside :root/@theme/@layer tokens blocks, and comment intervals.

    A small brace tracker: comments and strings are skipped, Sass and Less
    interpolation (#{...}, @{...}) does not open blocks, nesting is honored.
    """
    allowed_starts, allowed_ends, comment_starts, comment_ends = [], [], [], []
    stack = []
    interpolation = 0
    prelude = 0
    position = 0
    length = len(text)
    tokens = 0
    while True:
        match = _CSS_TOKEN.search(text, position)
        if match is None:
            break
        tokens += 1
        if tokens % 4096 == 0:
            budget.check()
        token, start = match.group(), match.start()
        position = match.end()
        if token == '/*':
            end = text.find('*/', position)
            end = length if end < 0 else end + 2
            comment_starts.append(start)
            comment_ends.append(end)
            position = end
        elif token == '//':
            if line_comments and (start == 0 or text[start - 1] in ' \t\r\n;{}'):
                end = text.find('\n', position)
                end = length if end < 0 else end
                comment_starts.append(start)
                comment_ends.append(end)
                position = end
        elif token in ('"', "'"):
            # The string ends at its quote or, unescaped, at the end of the line.
            position = min(_STRING_BODY[token].match(text, position).end() + 1, length)
        elif token in ('#{', '@{'):
            interpolation += 1
        elif token == '{':
            if interpolation:
                interpolation += 1
                continue
            outer = bool(stack) and stack[-1]
            inside = outer or _token_prelude(text[prelude:start], line_comments)
            if inside and not outer:
                allowed_starts.append(position)
            stack.append(inside)
            prelude = position
        elif token == '}':
            if interpolation:
                interpolation -= 1
                continue
            if stack:
                inside = stack.pop()
                if inside and not (bool(stack) and stack[-1]):
                    allowed_ends.append(start)
            prelude = position
        elif not interpolation:
            prelude = position
    if len(allowed_ends) < len(allowed_starts):
        allowed_ends.append(length)
    return (allowed_starts, allowed_ends), (comment_starts, comment_ends)


def _within(intervals, offset):
    starts, ends = intervals
    index = bisect.bisect_right(starts, offset) - 1
    return index >= 0 and offset < ends[index]


# literals ------------------------------------------------------------------

def _scan(path, kind, document, numbers, allowed, budget):
    """Findings for the given line numbers, or a skip reason."""
    if any(len(document.lines[number - 1]) > MAX_LINE_CHARS for number in numbers):
        return 'long_lines'
    regions = None
    if kind == 'css':
        regions = _css_regions(document.text, _extension(path) in LINE_COMMENT_EXTENSIONS, budget)
    findings = []
    for number in numbers:
        budget.check()
        line = document.lines[number - 1]
        if regions is None and _comment_line(line):
            continue
        for category, regexes in _COMPILED[kind]:
            if category in allowed:
                continue
            if any(_reported(line, rx, is_hex, kind, regions, document.starts[number - 1], category)
                   for is_hex, rx in regexes):
                findings.append({'path': path, 'line': number, 'category': category,
                                 'text': line.strip()[:MAX_TEXT]})
    return findings


def _reported(line, regex, is_hex, kind, regions, line_start, category):
    selector = is_hex and kind in ('css', 'web')
    stop, brace = -1, False
    for match in regex.finditer(line):
        if selector:
            # A hex is a selector when the next of ; { } ( ) quote or backtick
            # is `{`. Matches advance, so the stop found last is reused.
            if match.end() > stop:
                found = _SELECTOR_STOP.search(line, match.end())
                stop = found.start() if found else len(line)
                brace = found is not None and found.group() == '{'
            if brace:
                continue
        if regions is not None:
            offset = line_start + match.start()
            if _within(regions[1], offset):
                continue
            if category in TOKEN_CATEGORIES and _within(regions[0], offset):
                continue
        return True
    return False


def _literals(changes, untracked, read, tokens, wrappers, budget):
    findings, scanned, skipped = [], set(), {}

    def scan(path, numbers, lines=None):
        kind = _kind(path)
        if kind is None:
            skipped.setdefault(path, 'unsupported_type')
            return
        reason, data = read(path)
        if reason:
            skipped.setdefault(path, reason)
            return
        document = _Document(data)
        if lines is not None:
            if any(number < 1 or number > len(document.lines) or document.lines[number - 1] != text
                   for number, text in lines):
                skipped.setdefault(path, 'content_mismatch')
                return
            numbers = [number for number, _ in lines]
        elif numbers is None:
            numbers = range(1, len(document.lines) + 1)
        allowed = set()
        if _listed(path, tokens):
            allowed |= TOKEN_CATEGORIES
        if _listed(path, wrappers):
            allowed |= WRAPPER_CATEGORIES
        result = _scan(path, kind, document, numbers, allowed, budget)
        if isinstance(result, str):
            skipped.setdefault(path, result)
            return
        scanned.add(path)
        findings.extend(result)
        if len(findings) > MAX_FINDINGS:
            raise CheckError('LIMIT_EXCEEDED')

    for change in changes:
        budget.check()
        path = change.new
        if path is None:
            continue
        if change.unsafe:
            skipped.setdefault(path, 'outside_root')
        elif change.only_in:
            skipped.setdefault(path, 'only_in_one_tree')
        elif change.new_mode == '120000':
            skipped.setdefault(path, 'symlink')
        elif change.new_mode == '160000':
            skipped.setdefault(path, 'submodule')
        elif change.binary:
            skipped.setdefault(path, 'binary' if _kind(path) else 'unsupported_type')
        elif change.added:
            scan(path, None, change.added)
    for path in untracked:
        budget.check()
        if path.endswith('/'):
            skipped.setdefault(path, 'nested_repository')
        else:
            scan(path, None)
    order = {category: index for index, category in enumerate(CATEGORIES)}
    findings.sort(key=lambda item: (item['path'], item['line'], order[item['category']]))
    return {'findings': findings, 'scanned': sorted(scanned),
            'skipped': [{'path': path, 'reason': reason} for path, reason in sorted(skipped.items())]}


def _listed_paths(values, resolve):
    if len(values) > MAX_ARGUMENTS:
        raise CheckError('LIMIT_EXCEEDED')
    return sorted({resolve(value) for value in values})


def literals_git(repo, base, pathspecs=(), tokens=(), wrappers=()):
    """Literal findings in lines added since BASE and in untracked files."""
    budget = _Budget()
    top, start, _, _, changes, untracked = _git_scope(repo, base, list(pathspecs), budget)
    resolve = lambda value: _contained(top, start, value, 'BAD_PATH')
    return _literals(changes, untracked, lambda path: _read_file(top, path, budget),
                     _listed_paths(list(tokens), resolve), _listed_paths(list(wrappers), resolve), budget)


def _diff_root(root):
    try:
        resolved = os.path.realpath(os.fspath(root))
    except (TypeError, ValueError, OSError) as exc:
        raise CheckError('BAD_ROOT') from exc
    if not os.path.isdir(resolved):
        raise CheckError('BAD_ROOT')
    return resolved


def literals_diff(diff_file, root, tokens=(), wrappers=()):
    """Literal findings in the added lines of a unified diff of a tree at root."""
    budget = _Budget()
    root = _diff_root(root)
    cwd = os.path.realpath(os.getcwd())
    changes = _read_diff(diff_file)
    budget.file(len(changes))
    for change in changes:
        if change.new is not None:
            mapped = _map_to_root(change.new, root, cwd)
            if mapped is None:
                change.unsafe = True
            else:
                change.new = mapped

    def resolve(value):
        if type(value) is not str or not value or '\0' in value:
            raise CheckError('BAD_PATH')
        if os.path.isabs(value):
            relative = _inside(root, value)
        else:
            relative = os.path.normpath(value).replace(os.sep, '/')
            if not os.path.lexists(os.path.join(root, relative)):
                relative = _inside(root, os.path.join(cwd, value)) or relative
        if relative in ('.', ''):
            return '.'
        if relative is None or not _safe_relative(relative):
            raise CheckError('BAD_PATH')
        return relative
    return _literals(changes, [], lambda path: _read_file(root, path, budget),
                     _listed_paths(list(tokens), resolve), _listed_paths(list(wrappers), resolve), budget)


# contracts -----------------------------------------------------------------

def _attributes(text, kind):
    """(key, display, offset) for contract attributes in text, which may span lines."""
    if kind == 'swift':
        return [(('accessibilityIdentifier', 'str', match.group(1)),
                 '.accessibilityIdentifier("' + match.group(1) + '")', match.start())
                for match in _SWIFT_IDENTIFIER.finditer(text)]
    if kind == 'kotlin':
        return [(('testTag', 'str', match.group(1)), 'testTag("' + match.group(1) + '")', match.start())
                for match in _COMPOSE_TAG.finditer(text)]
    result = []
    for match in _ATTRIBUTE.finditer(text):
        name, raw, start = match.group(1), match.group(2), match.start()
        line_start = text.rfind('\n', max(0, start - 32), start) + 1
        # `const id = "x"`, `f(name = "x")` and `href = "/x";` are code, not attributes.
        if (_STATEMENT_BEFORE.search(text, max(line_start, start - 32), start)
                or _STATEMENT_AFTER.match(text, match.end())):
            continue
        if raw[0] == '{':
            inner = raw[1:-1].strip()
            literal = _STRING_EXPRESSION.fullmatch(inner)
            if literal:
                kind_, value = 'str', next(group for group in literal.groups() if group is not None)
            else:
                kind_, value = 'expr', ' '.join(inner.split())
        else:
            kind_, value = 'str', raw[1:-1]
        display = name + ('="' + value + '"' if kind_ == 'str' else '={' + value + '}')
        result.append(((_CANONICAL.get(name, name), kind_, value), display, start))
    return result


def _runs(lines):
    """Split (number, text) pairs into runs of consecutive line numbers."""
    run = []
    for number, text in lines:
        if run and number != run[-1][0] + 1:
            yield run
            run = []
        run.append((number, text))
    if run:
        yield run


class _Contracts:
    """Contract keys on the old side and on the new side, with limits."""

    def __init__(self, budget):
        self.budget = budget
        self.removed, self.added = {}, set()
        self.scanned, self.skipped = set(), {}
        self.locations = 0

    def skip(self, path, reason):
        self.skipped.setdefault(path, reason)

    def side(self, path, mode):
        """Skip reason for one side of a change, or None if it can be read."""
        if mode == '120000':
            return 'symlink'
        if mode == '160000':
            return 'submodule'
        return None if _kind(path) in CONTRACT_KINDS else 'unsupported_type'

    def collect(self, path, lines, side):
        kind = _kind(path)
        if kind not in CONTRACT_KINDS:
            self.skip(path, 'unsupported_type')
            return
        if any(len(text) > MAX_LINE_CHARS for _, text in lines):
            self.skip(path, 'long_lines')
            return
        self.scanned.add(path)
        for run in _runs(lines):
            self.budget.check()
            # Comment lines keep their place so offsets still map to line numbers.
            texts = ['' if _comment_line(text) else text for _, text in run]
            starts, offset = [], 0
            for text in texts:
                starts.append(offset)
                offset += len(text) + 1
            for key, display, start in _attributes('\n'.join(texts), kind):
                number = run[bisect.bisect_right(starts, start) - 1][0]
                if side == 'new':
                    self.added.add(key)
                    if len(self.added) > MAX_CONTRACT_ENTRIES:
                        raise CheckError('LIMIT_EXCEEDED')
                    continue
                entry = self.removed.setdefault(key, {'display': display, 'where': set()})
                if (path, number) not in entry['where']:
                    entry['where'].add((path, number))
                    self.locations += 1
                    if self.locations > MAX_CONTRACT_ENTRIES:
                        raise CheckError('LIMIT_EXCEEDED')

    def collect_file(self, path, reason, data, side):
        if reason:
            self.skip(path, reason)
        else:
            self.collect(path, list(enumerate(_Document(data).lines, 1)), side)

    def result(self):
        missing = []
        for key, entry in self.removed.items():
            if key not in self.added:
                if len(missing) == MAX_FINDINGS:
                    raise CheckError('LIMIT_EXCEEDED')
                where = [{'path': path, 'line': number} for path, number in sorted(entry['where'])]
                missing.append({'attribute': entry['display'], 'removed_in': where})
        missing.sort(key=lambda item: (item['attribute'], item['removed_in'][0]['path'],
                                       item['removed_in'][0]['line']))
        return {'missing': missing, 'scanned': sorted(self.scanned),
                'skipped': [{'path': path, 'reason': reason} for path, reason in sorted(self.skipped.items())]}


def contracts_git(repo, base, pathspecs=()):
    """Contracts of changed files at BASE that no changed or untracked file still has.

    Both sides are whole files: the BASE blob of every changed path and its
    working-tree file, plus untracked files. A contract kept on an unchanged
    line, or whose name stays while only its value changes, is compared too.
    """
    budget = _Budget()
    top, _, sha, drivers, changes, untracked = _git_scope(repo, base, list(pathspecs), budget)
    found = _Contracts(budget)
    old_paths = []
    for change in changes:
        budget.check()
        path = change.new or change.old
        if change.binary:
            found.skip(path, 'binary' if _kind(path) in CONTRACT_KINDS else 'unsupported_type')
            continue
        if change.old is not None:
            reason = found.side(change.old, change.old_mode)
            if reason is None and '\n' in change.old:
                reason = 'unsupported_path'
            if reason:
                found.skip(change.old, reason)
            else:
                old_paths.append(change.old)
        if change.new is not None:
            reason = found.side(change.new, change.new_mode)
            if reason:
                found.skip(change.new, reason)
            else:
                found.collect_file(change.new, *_read_file(top, change.new, budget), 'new')
    for path in untracked:
        budget.check()
        if path.endswith('/'):
            found.skip(path, 'nested_repository')
        elif _kind(path) not in CONTRACT_KINDS:
            found.skip(path, 'unsupported_type')
        else:
            found.collect_file(path, *_read_file(top, path, budget), 'new')
    for path, (reason, data) in sorted(_base_blobs(top, sha, sorted(set(old_paths)), budget).items()):
        found.collect_file(path, reason, data, 'old')
    _confirm_filters(top, drivers, budget)
    return found.result()


def contracts_diff(diff_file):
    """Contracts on the old side of each hunk, context included, absent from every new side.

    A value-only change is only visible when the diff carries the context
    lines around it (`diff -ruN`); with -U0 only the changed lines are known.
    """
    budget = _Budget()
    changes = _read_diff(diff_file)
    budget.file(len(changes))
    found = _Contracts(budget)
    for change in changes:
        budget.check()
        if not change.git_format:
            change.old, change.new = _strip_one(change.old), _strip_one(change.new)
        path = change.new or change.old
        if path is None:
            continue
        if change.only_in:
            found.skip(path, 'only_in_one_tree')
            continue
        if change.binary:
            found.skip(path, 'binary' if _kind(path) in CONTRACT_KINDS else 'unsupported_type')
            continue
        for name, mode, lines, side in ((change.old, change.old_mode, change.old_lines, 'old'),
                                        (change.new, change.new_mode, change.new_lines, 'new')):
            if name is None or not lines:
                continue
            reason = found.side(name, mode)
            if reason:
                found.skip(name, reason)
            else:
                found.collect(name, lines, side)
    return found.result()


# contrast ------------------------------------------------------------------

def _channel(text):
    match = _NUMBER.fullmatch(text)
    if not match:
        raise CheckError('BAD_COLOR')
    value = float(text.rstrip('%')) * (2.55 if match.group(1) else 1.0)
    if not 0 <= value <= 255:
        raise CheckError('BAD_COLOR')
    return value


def _alpha(text):
    match = _NUMBER.fullmatch(text)
    if not match:
        raise CheckError('BAD_COLOR')
    value = float(text.rstrip('%')) / (100.0 if match.group(1) else 1.0)
    if not 0 <= value <= 1:
        raise CheckError('BAD_COLOR')
    return value


def parse_color(text):
    """#rgb, #rgba, #rrggbb, #rrggbbaa, rgb()/rgba() with commas or spaces."""
    if type(text) is not str or len(text) > 128:
        raise CheckError('BAD_COLOR')
    value = text.strip()
    match = _HEX_COLOR.fullmatch(value)
    if match:
        digits = match.group(1)
        if len(digits) in (3, 4):
            digits = ''.join(char * 2 for char in digits)
        channels = [int(digits[index:index + 2], 16) for index in range(0, len(digits), 2)]
        return (*map(float, channels[:3]), channels[3] / 255 if len(channels) == 4 else 1.0)
    match = _RGB.fullmatch(value)
    if not match:
        raise CheckError('BAD_COLOR')
    body = match.group(1).strip()
    alpha = None
    if ',' in body:
        if '/' in body:
            raise CheckError('BAD_COLOR')
        parts = [part.strip() for part in body.split(',')]
        if len(parts) == 4:
            alpha = parts.pop()
    else:
        if body.count('/') > 1:
            raise CheckError('BAD_COLOR')
        if '/' in body:
            body, alpha = (part.strip() for part in body.split('/'))
        parts = body.split()
    if len(parts) != 3:
        raise CheckError('BAD_COLOR')
    return (*(_channel(part) for part in parts), 1.0 if alpha is None else _alpha(alpha))


def _luminance(rgb):
    def linear(channel):
        channel /= 255
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
    red, green, blue = (linear(channel) for channel in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(pairs, kind='text'):
    """WCAG 2.x ratio per pair; translucent foregrounds are composited over bg."""
    if kind not in KINDS:
        raise CheckError('ARGUMENTS_INVALID')
    pairs = list(pairs)
    if not pairs:
        raise CheckError('ARGUMENTS_INVALID')
    if len(pairs) > MAX_ARGUMENTS:
        raise CheckError('LIMIT_EXCEEDED')
    required = KINDS[kind]
    result = []
    for foreground, background in pairs:
        *fg, fg_alpha = parse_color(foreground)
        *bg, bg_alpha = parse_color(background)
        if bg_alpha < 1:
            raise CheckError('TRANSLUCENT_BACKGROUND')
        composite = [f * fg_alpha + b * (1 - fg_alpha) for f, b in zip(fg, bg)]
        lighter, darker = sorted((_luminance(composite), _luminance(bg)), reverse=True)
        ratio = (lighter + 0.05) / (darker + 0.05)
        result.append({'fg': foreground.strip(), 'bg': background.strip(), 'ratio': round(ratio, 2),
                       'kind': kind, 'required': required, 'passes': ratio >= required})
    return {'pairs': result}


# CLI -----------------------------------------------------------------------

class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise CheckError('ARGUMENTS_INVALID')


def _parser():
    parser = _Parser(prog='ui_checks.py', description='Design-system checks for ui-design.',
                     allow_abbrev=False)
    commands = parser.add_subparsers(dest='action', required=True)
    for name in ('literals', 'contracts'):
        command = commands.add_parser(name, allow_abbrev=False)
        command.add_argument('--repo')
        command.add_argument('--base')
        command.add_argument('--diff')
        if name == 'literals':
            command.add_argument('--root')
            command.add_argument('--tokens', action='append', default=[])
            command.add_argument('--wrappers', action='append', default=[])
    command = commands.add_parser('contrast', allow_abbrev=False)
    command.add_argument('--pair', nargs=2, action='append', required=True, metavar=('FG', 'BG'))
    command.add_argument('--kind', choices=tuple(KINDS), default='text')
    return parser


def _run(argv):
    pathspecs = None
    if '--' in argv:
        index = argv.index('--')
        argv, pathspecs = argv[:index], argv[index + 1:]
    args = _parser().parse_args(argv)
    if args.action == 'contrast':
        if pathspecs is not None:
            raise CheckError('ARGUMENTS_INVALID')
        output = contrast(args.pair, args.kind)
        return output, int(not all(item['passes'] for item in output['pairs']))
    literals = args.action == 'literals'
    if args.diff is not None:
        if args.repo is not None or args.base is not None or pathspecs is not None:
            raise CheckError('ARGUMENTS_INVALID')
        if literals:
            if args.root is None:
                raise CheckError('ARGUMENTS_INVALID')
            output = literals_diff(args.diff, args.root, args.tokens, args.wrappers)
        else:
            output = contracts_diff(args.diff)
    else:
        if args.repo is None or args.base is None or (literals and args.root is not None):
            raise CheckError('ARGUMENTS_INVALID')
        if literals:
            output = literals_git(args.repo, args.base, pathspecs or (), args.tokens, args.wrappers)
        else:
            output = contracts_git(args.repo, args.base, pathspecs or ())
    return output, int(bool(output['findings' if literals else 'missing']))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        output, code = _run(argv)
    except CheckError as exc:
        output, code = {'error': str(exc)}, 2
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        output, code = {'error': 'INPUT_INVALID'}, 2
    except Exception:
        # Exit 1 means findings, so unexpected failures must not fall through to it.
        output, code = {'error': 'INTERNAL_ERROR'}, 2
    print(json.dumps(output, ensure_ascii=True, sort_keys=True))
    return code


if __name__ == '__main__':
    sys.exit(main())
