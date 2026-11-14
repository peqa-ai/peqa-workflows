#!/usr/bin/env python3
"""Read-only starting map of what a change may reach; the reviewer judges it.

Reports, as JSON: the files changed between the merge base and the reviewed
state, the tracked files outside the diff that mention each one, the top-level
definitions the diff removes that are still mentioned elsewhere, and the
submodule pointers that moved. A renamed file is searched by its previous path.

It is a declared heuristic, not a dependency analyzer. Mentions are whole-word
fixed strings found by `git grep`: the path, the parent/name pair in slash and
dotted form, and the bare name. Definitions are unindented lines that start
with a common keyword; one that moves to another file counts as removed. The
output carries paths and names, never file content: `truncated` names each
limit that cut this map and `limits` what no run sees. Nothing is changed, no
filter or hook runs and no remote is reached.
"""
import argparse
import json
import os
import posixpath
import re
import subprocess
import sys
import time

MAX_CHANGED = 200  # changed files listed and searched
PER_FILE = 20  # references kept for one changed file or definition
MAX_REFERENCES = 400  # references kept in the whole map
MAX_DEFINITIONS = 100  # removed definitions searched
MIN_NAME = 3  # a shorter bare name matches too much to be a signal
MAX_LINE = 300  # characters of a definition line that are parsed
TIMEOUT = 20  # seconds for one Git call
MAX_SECONDS = 120  # seconds for all the searches
MAX_OUTPUT = 2 * 1024 * 1024  # bytes used from one Git call

GIT = ['git', '--no-pager', '--no-optional-locks', '--literal-pathspecs', '-c', 'core.fsmonitor=',
       '-c', 'core.hooksPath=' + os.devnull, '-c', 'core.quotePath=false', '-c', 'protocol.allow=never',
       '-c', 'grep.lineNumber=false', '-c', 'grep.column=false']
GIT_ERROR = re.compile(rb'^(error|fatal): ', re.M)
FILTER_KEY = re.compile(rb'filter\.([\s\S]*)\.(?:clean|smudge|process|required)')
SHA = re.compile(r'[0-9a-f]{40,64}')
GITLINK = '160000'
STATUS = {'A': 'added', 'D': 'deleted', 'R': 'renamed'}
INDEX_NAMES = {'__init__', 'index'}  # imported by the name of their folder
CODE = {'.py', '.pyi', '.js', '.jsx', '.mjs', '.cjs', '.ts', '.tsx', '.go', '.rs', '.rb', '.php', '.java', '.kt',
        '.kts', '.swift', '.scala', '.cs', '.dart'}
MODIFIERS = r'export|default|declare|public|private|internal|pub|pub\([a-z]+\)|async|abstract|final|static|data|sealed|open'
KEYWORDS = 'def|class|function|func|fun|fn|interface|type|struct|enum|trait|protocol|module|object|const|let|var'
# Valid both as a POSIX extended expression for Git and as a Python one.
DEFINITION_LINE = '^((%s)[ \t]+)*(%s)[ \t]+' % (MODIFIERS, KEYWORDS)
DEFINITION = re.compile(DEFINITION_LINE + r'(?:\([^)]*\)[ \t]*)?(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)')
TEST_FOLDERS = {'test', 'tests', '__tests__', 'spec', 'specs', 'e2e'}
TEST_NAME = re.compile(r'^(test_|conftest\.)|[._-](test|spec|e2e)\.|(Test|Tests|Spec)\.[A-Za-z]+$')
LIMITS = ['DYNAMIC_AND_GENERATED_REFERENCES_NOT_SEEN', 'OTHER_REPOSITORIES_AND_SUBMODULE_CONTENTS_NOT_SEARCHED',
          'IGNORED_FILES_NOT_SEARCHED', 'NAME_MATCHES_CAN_BE_FALSE_POSITIVES',
          'NAMES_UNDER_3_CHARACTERS_NOT_SEARCHED', 'DEFINITIONS_FOUND_BY_KEYWORD_AT_LINE_START_ONLY']


class CheckError(Exception):
    """Only fixed codes cross the CLI boundary."""


class Limits:
    """Budgets shared by every search; `hit` names each limit that cut the map."""

    def __init__(self):
        self.left = MAX_REFERENCES
        self.deadline = time.monotonic() + MAX_SECONDS
        self.hit = set()

    def expired(self):
        if time.monotonic() > self.deadline:
            self.hit.add('TIME_BUDGET')
            return True
        return False


def environment():
    """Caller GIT_* variables dropped; no global configuration, prompt or transport.

    An empty GIT_ALLOW_PROTOCOL outranks any protocol.<name>.allow of the
    repository, so a lazy fetch from a promisor remote cannot start, also on
    Git releases that ignore GIT_NO_LAZY_FETCH.
    """
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env.update(GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0', GIT_CONFIG_NOSYSTEM='1',
               GIT_CONFIG_GLOBAL=os.devnull, GIT_ATTR_NOSYSTEM='1', GIT_NO_REPLACE_OBJECTS='1',
               GIT_NO_LAZY_FETCH='1', GIT_ALLOW_PROTOCOL='', LC_ALL='C')
    return env


def run(top, args):
    """(exit code, stdout up to the cap, cut) of one Git call, with no shell and a time limit.

    `git grep` skips an object it cannot read and still exits 0 or 1, so an
    error line from Git turns a quiet exit into a failure.
    """
    try:
        proc = subprocess.run([*GIT, '-C', top, *args], capture_output=True, stdin=subprocess.DEVNULL,
                              env=environment(), timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        raise CheckError('TIMEOUT') from None
    except OSError:
        raise CheckError('GIT_UNAVAILABLE') from None
    failed = proc.returncode in (0, 1) and GIT_ERROR.search(proc.stderr)
    return 128 if failed else proc.returncode, proc.stdout[:MAX_OUTPUT], len(proc.stdout) > MAX_OUTPUT


def git(top, *args, ok=(0,)):
    code, data, cut = run(top, args)
    if cut:
        raise CheckError('GIT_OUTPUT_TOO_LARGE')
    if code not in ok:
        raise CheckError('GIT_COMMAND_FAILED')
    return data


def commit(top, ref, error):
    code, data, _ = run(top, ['rev-parse', '--verify', '--quiet', ref + '^{commit}'])
    sha = data.decode('ascii', 'replace').strip()
    if code or not SHA.fullmatch(sha):
        raise CheckError(error)
    return sha


def raw_diff(top, *args):
    """Entries of a raw NUL-separated diff: status, paths and what identifies a gitlink."""
    fields = git(top, *args, '-z').split(b'\0')[:-1]
    entries, position = [], 0
    while position < len(fields):
        meta = fields[position].decode('ascii', 'replace').split(' ')
        paths = [os.fsdecode(item) for item in fields[position + 1:position + (3 if meta[-1][:1] == 'R' else 2)]]
        if len(meta) != 5 or not meta[4] or not paths:
            raise CheckError('GIT_OUTPUT_INVALID')
        position += 1 + len(paths)
        old, new = (sha if sha.strip('0') else None for sha in meta[2:4])
        entry = {'path': paths[-1], 'status': STATUS.get(meta[4][0], 'modified'),
                 'gitlink': GITLINK in (meta[0][1:], meta[1]), 'old': old, 'new': new}
        if len(paths) == 2:
            entry['previous_path'] = paths[0]
        entries.append(entry)
    return entries


def blank_filters(top):
    """Options that empty every filter driver of the repository, so comparing working files runs none."""
    listed = git(top, 'config', '-z', '--name-only', '--get-regexp', r'^filter\.', ok=(0, 1)).split(b'\0')
    names = {match.group(1) for match in map(FILTER_KEY.fullmatch, (key.rstrip(b'\n') for key in listed)) if match}
    options = []
    for name in sorted(names):
        if b'=' in name or b'\n' in name:  # `-c` splits at the first `=`
            raise CheckError('FILTER_UNSUPPORTED')
        for setting in ('clean=', 'smudge=', 'process=', 'required=false'):
            options += ['-c', 'filter.' + os.fsdecode(name) + '.' + setting]
    return options


def changes_between(top, merge_base, head, uncommitted):
    """{path: change} from the merge base to HEAD or, when asked, to the working tree."""
    if not uncommitted:
        return {entry['path']: entry for entry in raw_diff(top, 'diff-tree', '-r', '-M', merge_base, head)}
    # Plumbing compares the index by object name and working files by their
    # stat data; only a file as recent as the index is read to tell.
    changes = {entry['path']: entry for entry in raw_diff(top, 'diff-index', '--cached', '-M', merge_base)}
    for entry in raw_diff(top, *blank_filters(top), 'diff-files', '--ignore-submodules=dirty'):
        known = changes.pop(entry['path'], None)
        if entry['status'] != 'deleted':
            changes[entry['path']] = dict(known, new=entry['new']) if known else entry
        elif known is None or known['status'] != 'added':
            source = known or entry
            origin = source.get('previous_path', source['path'])
            changes[origin] = {'path': origin, 'status': 'deleted', 'gitlink': source['gitlink'],
                               'old': source['old'], 'new': None}
    for name in git(top, 'ls-files', '-z', '--others', '--exclude-standard').split(b'\0')[:-1]:
        path = os.fsdecode(name)  # a trailing slash is an untracked nested repository
        changes[path] = {'path': path.rstrip('/'), 'status': 'added', 'untracked': True,
                         'gitlink': path.endswith('/'), 'old': None, 'new': None}
    return changes


def grep(top, tree, options, pathspec=()):
    """Bounded `git grep` over the reviewed tree or, without one, the tracked working files."""
    code, data, cut = run(top, ['grep', '-I', '--no-color', '--no-recurse-submodules', *options,
                                *([tree] if tree else []), '--', *pathspec])
    if code not in (0, 1) and not cut:
        raise CheckError('GIT_COMMAND_FAILED')
    return data, cut


def is_test(path):
    *folders, name = path.split('/')
    return bool(TEST_FOLDERS.intersection(folder.lower() for folder in folders) or TEST_NAME.search(name))


def needles(change):
    """Fixed strings a consumer may use for this file, strongest kind first."""
    path = change.get('previous_path', change['path'])
    folder, stem = posixpath.split(posixpath.splitext(path)[0])
    if stem in INDEX_NAMES and folder:
        folder, stem = posixpath.split(folder)
    parent = posixpath.basename(folder)
    groups = [('path', [path])]
    if parent:
        groups.append(('module', [parent + '/' + stem, parent + '.' + stem]))
    if len(stem) >= MIN_NAME and change['status'] != 'added':  # a new name has no earlier consumers
        groups.append(('name', [stem]))
    return groups


def references(top, tree, groups, changed, limits):
    """Files outside the diff that mention any needle: consumers and tests, each grouped by kind of match."""
    result = {'referenced_by': {}, 'tests': {}, 'references_found': None, 'truncated': True}
    if limits.expired():
        return result
    found, cut = {}, False
    for kind, group in groups:
        options = ['-l', '-z', '-F', '-w']
        for needle in group:
            if '\n' not in needle:
                options += ['-e', needle]
        if len(options) == 4:
            continue
        data, part = grep(top, tree, options)
        cut = cut or part
        for name in data.split(b'\0')[:-1]:
            path = os.fsdecode(name[len(tree) + 1 if tree else 0:])
            if path not in changed:
                found.setdefault(path, kind)
    kinds = [kind for kind, _ in groups]
    keep = sorted(found, key=lambda path: (kinds.index(found[path]), path))[:min(PER_FILE, limits.left)]
    if cut:
        limits.hit.add('GIT_OUTPUT')
    if len(found) > PER_FILE:
        limits.hit.add('REFERENCES_PER_FILE')
    if min(len(found), PER_FILE) > limits.left:
        limits.hit.add('REFERENCES_TOTAL')
    limits.left -= len(keep)
    for path in keep:
        result['tests' if is_test(path) else 'referenced_by'].setdefault(found[path], []).append(path)
    result.update(references_found=len(found), truncated=cut or len(keep) < len(found))
    return result


def definitions(top, tree, path):
    """{name: keyword} of the unindented definition lines of one file; Git hands over those lines only."""
    data, _ = grep(top, tree, ['-h', '-E', '-e', DEFINITION_LINE], [path])
    found = {}
    for line in data.decode('utf-8', 'replace').split('\n'):
        match = DEFINITION.match(line[:MAX_LINE])
        if match:
            found.setdefault(match.group('name'), match.group(3))
    return found


def removed_definitions(top, merge_base, tree, files, changed, limits):
    """Definitions gone from their file, by removal or rename, that files outside the diff still mention."""
    found, searched = [], 0
    for change in files:
        before = change.get('previous_path', change['path'])
        if change['status'] == 'added' or posixpath.splitext(before)[1] not in CODE:
            continue
        if limits.expired():
            break
        old = definitions(top, merge_base, before)
        new = {} if change['status'] == 'deleted' else definitions(top, tree, change['path'])
        for name in sorted(set(old) - set(new)):
            if len(name) < MIN_NAME:
                continue
            if searched >= MAX_DEFINITIONS:
                limits.hit.add('REMOVED_DEFINITIONS')
                return found
            searched += 1
            result = references(top, tree, [('name', [name])], changed, limits)
            if result['references_found']:
                found.append({'name': name, 'kind': old[name], 'path': before, **result})
    return found


def build(repo, base, uncommitted=False):
    if not repo or not os.path.isdir(repo):
        raise CheckError('GIT_REPOSITORY_REQUIRED')
    code, data, _ = run(os.path.realpath(repo), ['rev-parse', '--show-toplevel'])
    top = os.fsdecode(data).rstrip('\n')
    if code or not os.path.isabs(top):
        raise CheckError('GIT_REPOSITORY_REQUIRED')
    # An option-looking ref never reaches Git.
    if base.startswith('-') or not 0 < len(base) <= 256 or any(ord(char) < 32 or ord(char) == 127 for char in base):
        raise CheckError('BAD_BASE')
    base_sha, head = commit(top, base, 'BAD_BASE'), commit(top, 'HEAD', 'HEAD_COMMIT_REQUIRED')
    merge_base = git(top, 'merge-base', base_sha, head, ok=(0, 1)).decode('ascii', 'replace').strip()
    if not SHA.fullmatch(merge_base):
        raise CheckError('MERGE_BASE_NOT_FOUND')
    tree = None if uncommitted else head
    changes = changes_between(top, merge_base, head, uncommitted)
    ordered = sorted(changes.values(), key=lambda change: change['path'])
    files = [change for change in ordered if not change['gitlink']]
    limits = Limits()
    if len(files) > MAX_CHANGED:
        limits.hit.add('CHANGED_FILES')
        files = files[:MAX_CHANGED]
    changed = []
    for change in files:
        entry = {key: change[key] for key in ('path', 'status', 'previous_path', 'untracked') if key in change}
        changed.append({**entry, **references(top, tree, needles(change), changes, limits)})
    removed = removed_definitions(top, merge_base, tree, files, changes, limits)
    submodules = [{key: change[key] for key in ('path', 'status', 'old', 'new', 'untracked') if key in change}
                  for change in ordered if change['gitlink']]
    return {
        'schema_version': 1,
        'base': base_sha,
        'merge_base': merge_base,
        'head': head,
        'uncommitted': uncommitted,
        'changed': changed,
        'removed_definitions': removed,
        'submodules': submodules[:MAX_CHANGED],
        'truncated': sorted(limits.hit | ({'SUBMODULES'} if len(submodules) > MAX_CHANGED else set())),
        'limits': LIMITS + (['WORKING_FILES_COMPARED_BY_STAT_NOT_CONTENT'] if uncommitted
                            else ['UNCOMMITTED_AND_UNTRACKED_CHANGES_NOT_INCLUDED']),
        'notice': 'Read-only starting map from fixed-string searches. Follow what it cannot see; '
                  'classifying the impact stays with the reviewer and the parent.',
    }


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise CheckError('INVALID_ARGUMENTS')


def main(argv=None):
    parser = Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', choices=['map'])
    parser.add_argument('--repo', required=True, help='checkout under review')
    parser.add_argument('--base', required=True, help='ref the change will merge into; its merge base with HEAD is used')
    parser.add_argument('--uncommitted', action='store_true',
                        help='review the working tree: staged, unstaged and untracked files too')
    try:
        args = parser.parse_args(argv)
        print(json.dumps(build(args.repo, args.base, args.uncommitted), indent=2))
        return 0
    except CheckError as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
