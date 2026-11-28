#!/usr/bin/env python3
"""Bounded, read-only review evidence checks. Python 3.10+, Git, macOS/Linux.

Public API:
    snapshot(repo) -> scope dict; raises CheckError with a safe code on failure.
    validate_report(report, repo) -> {"valid": bool, "errors": [safe codes]}.
    load_report(path) -> dict; rejects duplicate keys, symlinks and >1 MiB input.

Report schema 1 has exactly: schema_version, language, depth, recommendation,
minimums, requester, reason, criteria, findings, tests, security, impact, scope,
trace. depth is 'lite' or 'deep'. criteria has requirements/tests/security/
compatibility, each {status, evidence}. findings contains {id, material: bool,
status, evidence} plus optional structured keys (severity, path, line,
conditions, impact, minimal_fix, visible_flow, adjudication); tests contains
{command, cwd: relative path, status, evidence}. security has string lists
standards/controls/limitations. trace has models: string list, route: string,
cr: string list, plus optional metadata keys (pr_url, base, head,
requested_model, effective_model, requested_effort, effective_effort,
session_model, fallback). requester is a caller-confirmed name or null, never
inferred. Use `template` to obtain a complete incomplete-review document with
live scope.

No commands from reports are executed. No remote services, Git writes, hooks,
filters or submodule initialization are used. Git metadata may live outside the
worktree, as it does for linked worktrees and submodules. Working-tree reads use
no-follow directory descriptors. Symlinks, special files, nested standalone Git
repositories, unreadable files, and absent submodules make coverage incomplete.
Ignored files and repositories outside the chosen root are explicitly excluded.
Fingerprints are evidence of state, not proof of test execution or review quality.
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import html
import json
import os
from pathlib import Path
import re
import selectors
import stat
import subprocess
import sys
import time


MAX_REPORT_BYTES = 1024 * 1024
MAX_GIT_BYTES = 8 * 1024 * 1024
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_FILES = 50000
MAX_REPOSITORIES = 128
MAX_DEPTH = 16
MAX_SECONDS = 45
GIT_SECONDS = 8
CRITERIA = ('requirements', 'tests', 'security', 'compatibility')
DEPTHS = ('lite', 'deep')
SEVERITIES = ('critical', 'high', 'medium', 'low')
STATUSES = ('met', 'not_met', 'not_verified', 'not_applicable')
RECOMMENDATIONS = ('approval_recommended', 'changes_required', 'review_incomplete')
TEST_STATUSES = ('passed', 'failed', 'not_run', 'partial', 'no_tests')
ROOT_FIELDS = {'schema_version', 'language', 'depth', 'recommendation', 'minimums',
               'requester', 'reason', 'criteria', 'findings', 'tests',
               'security', 'impact', 'scope', 'trace'}
FINDING_REQUIRED = {'id', 'material', 'status', 'evidence'}
FINDING_OPTIONAL = {'severity', 'path', 'line', 'conditions', 'impact',
                    'minimal_fix', 'visible_flow', 'adjudication'}
TRACE_REQUIRED = {'models', 'route', 'cr'}
TRACE_OPTIONAL = {'pr_url', 'base', 'head', 'requested_model', 'effective_model',
                  'requested_effort', 'effective_effort', 'session_model', 'fallback'}
EXCLUSIONS = ['ignored_files', 'external_repositories']
SHA = re.compile(r'(?:[a-f0-9]{40}|[a-f0-9]{64})\Z')
NOFOLLOW = os.O_NOFOLLOW
DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW


class CheckError(Exception):
    """Only fixed codes cross the CLI boundary; raw paths/errors never do."""


class _Budget:
    def __init__(self):
        self.deadline = time.monotonic() + MAX_SECONDS
        self.bytes = 0
        self.files = 0
        self.repositories = 0
        self.observed_paths = {}
        self.observed_repositories = []

    def check(self):
        if time.monotonic() > self.deadline:
            raise CheckError('SNAPSHOT_TIMEOUT')


def _git(root, args, budget, optional=False):
    """No shell, bounded output/time; disable config features that run helpers."""
    budget.check()
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0',
               GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               GIT_NO_REPLACE_OBJECTS='1', GIT_NO_LAZY_FETCH='1', LC_ALL='C')
    command = ['git', '--no-optional-locks', '--literal-pathspecs',
               '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=' + os.devnull,
               '-c', 'protocol.allow=never',
               '-C', str(root), *args]
    try:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL, env=env)
    except OSError as exc:
        raise CheckError('GIT_UNAVAILABLE') from exc
    output = bytearray()
    deadline = min(budget.deadline, time.monotonic() + GIT_SECONDS)
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout, selectors.EVENT_READ)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise CheckError('GIT_TIMEOUT')
                for key, _ in selector.select(min(remaining, 0.2)):
                    block = os.read(key.fileobj.fileno(), 65536)
                    if not block:
                        selector.unregister(key.fileobj)
                    else:
                        output.extend(block)
                        if len(output) > MAX_GIT_BYTES:
                            raise CheckError('GIT_OUTPUT_LIMIT')
            try:
                status = proc.wait(timeout=max(0.01, deadline - time.monotonic()))
            except subprocess.TimeoutExpired as exc:
                raise CheckError('GIT_TIMEOUT') from exc
        if status:
            if optional:
                return None
            raise CheckError('GIT_COMMAND_FAILED')
        return bytes(output)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        proc.stdout.close()


def _relative(value, dot=False):
    if type(value) is not str or not value or len(value) > 4096:
        return False
    if dot and value == '.':
        return True
    if any(ord(char) < 32 or ord(char) == 127 for char in value) or '\\' in value:
        return False
    parts = value.split('/')
    return not (value.startswith('/') or any(part in ('', '.', '..', '.git') for part in parts))


def _dir_fd(root, relative='.'):
    """Traverse relative paths without resolving symlinks, including ancestors."""
    descriptor = os.open(root, DIRECTORY)
    try:
        if relative != '.':
            for part in relative.split('/'):
                next_fd = os.open(part, DIRECTORY, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = next_fd
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _stable_stat(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _path_state(root, relative):
    """Read identity without following a file or directory replacement."""
    directory = None
    try:
        path = root if relative == '.' else root / relative
        directory = _open_absolute_directory(path.parent)
        return _stable_stat(os.stat(path.name, dir_fd=directory, follow_symlinks=False))
    except OSError as exc:
        return ('unavailable', exc.errno)
    finally:
        if directory is not None:
            os.close(directory)


def _observe_path(root, relative, budget):
    key = (root, relative)
    if key not in budget.observed_paths:
        budget.observed_paths[key] = _path_state(root, relative)


def _verify_stability(budget):
    """Recheck the entire traversal, including children already visited."""
    for root, head, index, flags, others in budget.observed_repositories:
        if (not _repository_root(root, budget) or _head(root, budget) != head or
                _git(root, ['ls-files', '--stage', '-z'], budget) != index or
                _git(root, ['ls-files', '-v', '-z'], budget) != flags or
                _git(root, ['ls-files', '--others', '--exclude-standard', '-z'], budget) != others):
            raise CheckError('SNAPSHOT_CHANGED_DURING_READ')
    for (root, relative), before in budget.observed_paths.items():
        budget.check()
        if _path_state(root, relative) != before:
            raise CheckError('SNAPSHOT_CHANGED_DURING_READ')


def _record_file(root, relative, budget, object_format):
    """Return state and a Git blob id only for a regular file, never a target."""
    budget.check()
    budget.files += 1
    if budget.files > MAX_FILES:
        raise CheckError('FILE_COUNT_LIMIT')
    if not _relative(relative):
        return {'path': relative, 'kind': 'unsafe'}, None
    _observe_path(root, relative, budget)
    parts = relative.split('/')
    parent = '/'.join(parts[:-1]) or '.'
    directory = None
    descriptor = None
    try:
        directory = _dir_fd(root, parent)
        info = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode):
            kind = 'symlink' if stat.S_ISLNK(info.st_mode) else 'special'
            return {'path': relative, 'kind': kind, 'metadata': _stable_stat(info)}, None
        if info.st_size > MAX_FILE_BYTES:
            return {'path': relative, 'kind': 'oversized'}, None
        descriptor = os.open(parts[-1], os.O_RDONLY | NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or _stable_stat(opened) != _stable_stat(info):
            raise CheckError('SNAPSHOT_CHANGED_DURING_READ')
        digest = hashlib.sha256()
        git_digest = hashlib.new(object_format)
        git_digest.update(('blob ' + str(info.st_size) + '\0').encode())
        size = 0
        while True:
            budget.check()
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            size += len(block)
            budget.bytes += len(block)
            if size > MAX_FILE_BYTES or budget.bytes > MAX_TOTAL_BYTES:
                raise CheckError('CONTENT_LIMIT')
            digest.update(block)
            git_digest.update(block)
        if size != info.st_size or _stable_stat(os.fstat(descriptor)) != _stable_stat(info):
            raise CheckError('SNAPSHOT_CHANGED_DURING_READ')
        mode = '100755' if info.st_mode & stat.S_IXUSR else '100644'
        return {'path': relative, 'kind': 'regular', 'mode': mode,
                'sha256': digest.hexdigest()}, git_digest.hexdigest()
    except FileNotFoundError:
        return {'path': relative, 'kind': 'missing'}, None
    except OSError as exc:
        kind = 'unsafe' if exc.errno in (errno.ELOOP, errno.ENOTDIR) else 'unreadable'
        return {'path': relative, 'kind': kind}, None
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if directory is not None:
            os.close(directory)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                     separators=(',', ':')).encode()).hexdigest()


def _entries(raw, tree=False):
    result = []
    for record in raw.split(b'\0'):
        if not record:
            continue
        try:
            prefix, path = record.split(b'\t', 1)
            mode, oid, stage = prefix.split() if not tree else (prefix.split()[0], prefix.split()[2], b'0')
            item = {'path': os.fsdecode(path), 'mode': mode.decode('ascii'),
                    'oid': oid.decode('ascii'), 'stage': int(stage)}
            if not SHA.fullmatch(item['oid']) or item['stage'] not in (0, 1, 2, 3):
                raise ValueError
            result.append(item)
            if len(result) > MAX_FILES:
                raise CheckError('FILE_COUNT_LIMIT')
        except (ValueError, UnicodeError, IndexError) as exc:
            raise CheckError('GIT_OUTPUT_INVALID') from exc
    return sorted(result, key=lambda item: (item['path'], item['stage']))


def _head(root, budget):
    value = _git(root, ['rev-parse', '--verify', 'HEAD'], budget, optional=True)
    if value is None:
        return None
    result = value.decode('ascii', errors='replace').strip()
    if not SHA.fullmatch(result):
        raise CheckError('GIT_OUTPUT_INVALID')
    return result


def _repository_root(root, budget):
    """Require the explicit root, so missing children cannot resolve to parent."""
    if not _check_git_metadata(root):
        return False
    value = _git(root, ['rev-parse', '--show-toplevel'], budget, optional=True)
    return value is not None and os.path.realpath(os.fsdecode(value).rstrip('\n')) == str(root)


def _read_git_pointer(directory, name):
    descriptor = os.open(name, os.O_RDONLY | NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 4096:
            raise CheckError('REPOSITORY_PATH_UNSAFE')
        data = stream.read(4097)
    value = os.fsdecode(data).rstrip('\n')
    if not value or len(data) > 4096 or '\n' in value or '\0' in value:
        raise CheckError('REPOSITORY_PATH_UNSAFE')
    return value


def _open_absolute_directory(path):
    return _dir_fd(path.anchor, '/'.join(path.parts[1:]) or '.')


def _check_git_metadata(root):
    """Permit real external worktree metadata, but reject symlink redirects."""
    descriptors = []
    try:
        directory = _dir_fd(root)
        descriptors.append(directory)
        try:
            info = os.stat('.git', dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            return False
        if stat.S_ISDIR(info.st_mode):
            gitdir = root / '.git'
        elif stat.S_ISREG(info.st_mode):
            pointer = _read_git_pointer(directory, '.git')
            if not pointer.startswith('gitdir: '):
                raise CheckError('REPOSITORY_PATH_UNSAFE')
            gitdir = Path(pointer[8:])
            if not gitdir.is_absolute():
                gitdir = root / gitdir
        else:
            raise CheckError('REPOSITORY_PATH_UNSAFE')
        metadata = _open_absolute_directory(gitdir)
        descriptors.append(metadata)
        try:
            os.stat('commondir', dir_fd=metadata, follow_symlinks=False)
        except FileNotFoundError:
            return True
        common = Path(_read_git_pointer(metadata, 'commondir'))
        if not common.is_absolute():
            common = gitdir / common
        descriptors.append(_open_absolute_directory(common))
        return True
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.ENOTDIR):
            raise CheckError('REPOSITORY_PATH_UNSAFE') from exc
        raise
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _capture_repository(root, relative, budget, result, depth=0):
    budget.repositories += 1
    if depth > MAX_DEPTH or budget.repositories > MAX_REPOSITORIES:
        raise CheckError('REPOSITORY_LIMIT')
    _observe_path(root, '.', budget)
    _observe_path(root, '.git', budget)
    head = _head(root, budget)
    index_raw = _git(root, ['ls-files', '--stage', '-z'], budget)
    index = _entries(index_raw)
    flags_raw = _git(root, ['ls-files', '-v', '-z'], budget)
    flags = sorted(os.fsdecode(item) for item in flags_raw.split(b'\0') if item)
    skipped = {item[2:] for item in flags if item[0].upper() == 'S'}
    tree = _entries(_git(root, ['ls-tree', '-r', '-z', '--full-tree', 'HEAD'], budget), tree=True) if head else []
    other_raw = _git(root, ['ls-files', '--others', '--exclude-standard', '-z'], budget)
    budget.observed_repositories.append((root, head, index_raw, flags_raw, other_raw))
    others = sorted(set(os.fsdecode(path) for path in other_raw.split(b'\0') if path))
    tracked = {item['path']: item for item in index if item['mode'] != '160000'}
    issues = []
    records = []
    dirty = index != tree or bool(others)
    object_format = 'sha256' if head and len(head) == 64 else 'sha1'
    for path in sorted(set(tracked) | set(others)):
        # Git reports a standalone nested repo as a directory ending in '/'.
        if path.endswith('/'):
            record, oid = {'path': path, 'kind': 'external_repository'}, None
        else:
            record, oid = _record_file(root, path, budget, object_format)
        if record['kind'] == 'missing' and path in skipped:
            record['kind'] = 'sparse_missing'
        records.append(record)
        if record['kind'] not in ('regular', 'missing'):
            issues.append({'path': path, 'code': record['kind'].upper()})
        if path in tracked:
            expected = tracked[path]
            dirty = dirty or oid != expected['oid'] or record.get('mode') != expected['mode']
    if any(item['stage'] for item in index):
        issues.append({'path': '.', 'code': 'UNMERGED_INDEX'})
    repo = {'path': relative, 'head': head, 'index_sha256': _digest({'entries': index, 'flags': flags}),
            'worktree_sha256': _digest(records), 'tracked_files': len(tracked),
            'untracked_files': len(others), 'dirty': dirty, 'issues': issues}
    if head is None:
        issues.append({'path': '.', 'code': 'HEAD_UNAVAILABLE'})
    result['repositories'].append(repo)
    if issues:
        result['coverage']['complete'] = False
    head_links = {item['path']: item['oid'] for item in tree if item['mode'] == '160000'}
    index_links = {item['path']: item['oid'] for item in index if item['mode'] == '160000' and item['stage'] == 0}
    for path in sorted(set(head_links) | set(index_links)):
        full_relative = path if relative == '.' else relative + '/' + path
        sub = {'path': full_relative, 'pinned_head': index_links.get(path),
               'head_pinned': head_links.get(path), 'current_head': None, 'state': 'missing'}
        result['submodules'].append(sub)
        if path not in index_links:
            # A removed gitlink is recorded; any leftover content remains untracked.
            sub['state'] = 'removed'
            continue
        if not _relative(path):
            sub['state'] = 'unsafe'
            result['coverage']['complete'] = False
            continue
        _observe_path(root, path, budget)
        _observe_path(root, path + '/.git', budget)
        try:
            directory = _dir_fd(root, path)
            os.close(directory)
            child = root.joinpath(*path.split('/'))
            if not _repository_root(child, budget):
                result['coverage']['complete'] = False
                continue
            sub['current_head'] = _head(child, budget)
            sub['state'] = 'initialized' if sub['current_head'] == sub['pinned_head'] else 'changed'
            dirty = dirty or sub['state'] == 'changed'
            _capture_repository(child, full_relative, budget, result, depth + 1)
            if _head(child, budget) != sub['current_head']:
                raise CheckError('SNAPSHOT_CHANGED_DURING_READ')
        except OSError:
            sub['state'] = 'unsafe' if child_path_is_symlink(root, path) else 'missing'
            result['coverage']['complete'] = False
        except CheckError as exc:
            if str(exc) == 'REPOSITORY_PATH_UNSAFE':
                sub['state'] = 'unsafe'
                result['coverage']['complete'] = False
            else:
                raise
    repo['dirty'] = dirty or any(item['dirty'] for item in result['repositories']
                                 if item['path'].startswith(relative + '/') and relative != '.')


def child_path_is_symlink(root, relative):
    # This only examines components and never opens a target.
    current = root
    for part in relative.split('/'):
        current = current / part
        if current.is_symlink():
            return True
    return False


def snapshot(repo):
    """Capture exact current content, staged state, and recursive gitlink state."""
    budget = _Budget()
    try:
        root = Path(repo).expanduser().resolve(strict=True)
        if not root.is_dir() or not _repository_root(root, budget):
            raise CheckError('REPOSITORY_ROOT_REQUIRED')
        result = {'schema_version': 1, 'root': str(root), 'repositories': [],
                  'submodules': [], 'coverage': {'complete': True},
                  'exclusions': list(EXCLUSIONS)}
        _capture_repository(root, '.', budget, result)
        _verify_stability(budget)
        if result['repositories']:
            result['repositories'][0]['dirty'] = any(item['dirty'] for item in result['repositories'])
        return result
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        raise CheckError('REPOSITORY_UNAVAILABLE') from exc


def _text(value):
    return type(value) is str and bool(value.strip()) and len(value) <= 16384 and not any(
        ord(char) < 32 and char not in '\n\t\r' for char in value)


def _strings(value, nonempty=False):
    return type(value) is list and len(value) <= 1000 and (bool(value) or not nonempty) and all(_text(item) for item in value)


def _shape(value, fields, optional=()):
    if type(value) is not dict:
        return False
    keys = set(value)
    required = set(fields)
    return required <= keys <= (required | set(optional))


def _bounded_json(value):
    """Reject pathological API inputs before serialization or recursive equality."""
    nodes = 0
    characters = 0
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if depth > 24 or nodes > 100000:
            return False
        if type(item) is dict:
            if len(item) > 100000 or any(type(key) is not str for key in item):
                return False
            characters += sum(len(key) for key in item)
            stack.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            if len(item) > 100000:
                return False
            stack.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            characters += len(item)
        elif type(item) is int and item.bit_length() > 64:
            return False
        elif item is not None and type(item) not in (str, bool, int):
            return False
        if characters > MAX_REPORT_BYTES:
            return False
    try:
        return len(json.dumps(value, ensure_ascii=True).encode()) <= MAX_REPORT_BYTES
    except (ValueError, TypeError, RecursionError):
        return False


def validate_report(report, repo):
    """Validate data and fresh scope only, never attest to supplied evidence."""
    errors = []
    def error(code):
        if code not in errors:
            errors.append(code)
    if not _bounded_json(report) or not _shape(report, ROOT_FIELDS):
        return {'valid': False, 'errors': ['REPORT_SCHEMA_INVALID']}
    if type(report['schema_version']) is not int or report['schema_version'] != 1:
        error('REPORT_SCHEMA_INVALID')
    if report['language'] not in ('es', 'en'):
        error('REPORT_SCHEMA_INVALID')
    if report['depth'] not in DEPTHS:
        error('DEPTH_INVALID')
    if report['recommendation'] not in RECOMMENDATIONS or report['minimums'] not in STATUSES[:3]:
        error('REPORT_SCHEMA_INVALID')
    if report['requester'] is not None and not _text(report['requester']):
        error('REPORT_SCHEMA_INVALID')
    if not _text(report['reason']) or not _text(report['impact']):
        error('EVIDENCE_REQUIRED')
    criteria = report['criteria']
    if not _shape(criteria, CRITERIA):
        error('CRITERIA_INVALID')
    else:
        for item in criteria.values():
            if not _shape(item, ('status', 'evidence')) or item['status'] not in STATUSES:
                error('CRITERIA_INVALID')
            elif not _text(item['evidence']):
                error('EVIDENCE_REQUIRED')
    findings = report['findings']
    if type(findings) is not list or len(findings) > 1000:
        error('FINDINGS_INVALID')
    else:
        identifiers = set()
        for item in findings:
            if (not _shape(item, FINDING_REQUIRED, FINDING_OPTIONAL) or
                    not _text(item['id']) or type(item['material']) is not bool or
                    item['status'] not in ('open', 'resolved', 'dismissed')):
                error('FINDINGS_INVALID')
            elif not _text(item['evidence']):
                error('EVIDENCE_REQUIRED')
            elif item['id'] in identifiers:
                error('FINDINGS_INVALID')
            elif ('severity' in item and item['severity'] not in SEVERITIES) or (
                    'path' in item and not _relative(item['path'])) or (
                    'line' in item and (type(item['line']) is not int or item['line'] < 1)) or any(
                    key in item and not _text(item[key])
                    for key in ('conditions', 'impact', 'minimal_fix', 'visible_flow', 'adjudication')):
                error('FINDINGS_INVALID')
            else:
                identifiers.add(item['id'])
    tests = report['tests']
    if type(tests) is not list or not tests or len(tests) > 1000:
        error('TESTS_INVALID')
    else:
        for item in tests:
            if (not _shape(item, ('command', 'cwd', 'status', 'evidence')) or
                    not _text(item['command']) or not _relative(item['cwd'], dot=True) or
                    item['status'] not in TEST_STATUSES):
                error('TESTS_INVALID')
            elif not _text(item['evidence']):
                error('EVIDENCE_REQUIRED')
    security = report['security']
    if not _shape(security, ('standards', 'controls', 'limitations')) or not all(_strings(value) for value in security.values()):
        error('SECURITY_INVALID')
    elif (type(criteria) is dict and type(criteria.get('security')) is dict and
          criteria['security'].get('status') == 'met' and
          (not security['standards'] or not security['controls'])):
        error('SECURITY_EVIDENCE_REQUIRED')
    trace = report['trace']
    if (not _shape(trace, TRACE_REQUIRED, TRACE_OPTIONAL) or
            not _strings(trace['models'], nonempty=True) or not _text(trace['route']) or not _strings(trace['cr']) or
            any(key in trace and trace[key] is not None and not _text(trace[key]) for key in TRACE_OPTIONAL)):
        error('TRACE_INVALID')
    # Fresh state is always derived from the explicit argument, never report paths.
    try:
        current = snapshot(repo)
        if _digest(report['scope']) != _digest(current):
            error('SCOPE_STALE')
    except CheckError as exc:
        error(str(exc))
        current = None
    structural = any(code not in ('SCOPE_STALE',) for code in errors)
    if not structural:
        states = [criteria[key]['status'] for key in CRITERIA]
        failure = ('not_met' in states or any(item['material'] and item['status'] == 'open' for item in findings)
                   or any(item['status'] == 'failed' for item in tests))
        no_functional_tests = criteria['tests']['status'] == 'not_applicable'
        pending_tests = any(item['status'] != 'passed' and
                            not (no_functional_tests and item['status'] == 'no_tests') for item in tests)
        pending = ('not_verified' in states or pending_tests
                   or not current['coverage']['complete'])
        expected = 'not_met' if failure else 'not_verified' if pending else 'met'
        recommendation = {'met': 'approval_recommended', 'not_met': 'changes_required',
                          'not_verified': 'review_incomplete'}[expected]
        if report['minimums'] != expected:
            error('MINIMUMS_CONTRADICTION')
        if (report['recommendation'] != recommendation or
                (report['recommendation'] == 'approval_recommended' and report['minimums'] != 'met')):
            error('RECOMMENDATION_CONTRADICTION')
        if report['recommendation'] == 'approval_recommended' and not current['coverage']['complete']:
            error('COVERAGE_INCOMPLETE')
    return {'valid': not errors, 'errors': errors}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CheckError('REPORT_JSON_INVALID')
        result[key] = value
    return result


def _json_integer(value):
    if len(value) > 20:
        raise CheckError('REPORT_JSON_INVALID')
    return int(value)


def _reject_json_number(value):
    raise CheckError('REPORT_JSON_INVALID')


def load_report(path):
    """Explicit local report input, no symlink traversal and a one MiB ceiling."""
    descriptor = directory = None
    try:
        absolute = Path(os.path.abspath(os.fspath(path)))
        directory = _dir_fd(absolute.anchor, '/'.join(absolute.parts[1:-1]) or '.')
        descriptor = os.open(absolute.name, os.O_RDONLY | NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_REPORT_BYTES:
            raise CheckError('REPORT_INPUT_LIMIT')
        with os.fdopen(descriptor, 'rb') as stream:
            descriptor = None
            content = stream.read(MAX_REPORT_BYTES + 1)
        if len(content) > MAX_REPORT_BYTES:
            raise CheckError('REPORT_INPUT_LIMIT')
        return json.loads(content, object_pairs_hook=_unique_object,
                          parse_int=_json_integer, parse_float=_reject_json_number,
                          parse_constant=_reject_json_number)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise CheckError('REPORT_JSON_INVALID') from exc
    except OSError as exc:
        raise CheckError('REPORT_UNREADABLE') from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if directory is not None:
            os.close(directory)


def template(repo, language='es', depth='deep'):
    """A truthful starting point: all checks pending, no claim of execution."""
    if depth not in DEPTHS:
        raise CheckError('DEPTH_INVALID')
    pending = 'Pendiente de aportar evidencia.' if language == 'es' else 'Evidence has not been supplied.'
    return {'schema_version': 1, 'language': language, 'depth': depth, 'recommendation': 'review_incomplete',
            'minimums': 'not_verified', 'requester': None, 'reason': pending,
            'criteria': {key: {'status': 'not_verified', 'evidence': pending} for key in CRITERIA},
            'findings': [], 'tests': [{'command': 'Not selected', 'cwd': '.', 'status': 'not_run', 'evidence': pending}],
            'security': {'standards': [], 'controls': [], 'limitations': [pending]},
            'impact': pending, 'scope': snapshot(repo),
            'trace': {'models': ['Not recorded'], 'route': 'Not recorded', 'cr': []}}


def _escape(value):
    text = html.escape(str(value), quote=False)
    text = re.sub(r'([\\`*_{}\[\]()#+.!|>-])', r'\\\1', text)
    return text.replace('\r', '').replace('\n', '<br>')


def _code(value):
    text = str(value).replace('\r', '').replace('\n', ' ')
    fence = '``' if '`' in text else '`'
    if text.startswith('`') or text.endswith('`'):
        text = ' ' + text + ' '
    return fence + text + fence


SAFE_PR_URL = re.compile(r'^https://[a-zA-Z0-9.-]+(?::[0-9]{1,5})?/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/[1-9][0-9]*/?$')


def _header_model_summary(trace, es):
    req_m = trace.get('requested_model')
    eff_m = trace.get('effective_model')
    req_e = trace.get('requested_effort')
    eff_e = trace.get('effective_effort')
    if any((req_m, eff_m, req_e, eff_e)):
        req_parts = [part for part in (req_m, req_e) if part]
        eff_parts = [part for part in (eff_m, eff_e) if part]
        req_text = ' / '.join(req_parts) if req_parts else ('no declarado' if es else 'not declared')
        eff_text = ' / '.join(eff_parts) if eff_parts else ('desconocido' if es else 'unknown')
        if es:
            return f'solicitado {_escape(req_text)}; efectivo {_escape(eff_text)}'
        return f'requested {_escape(req_text)}; effective {_escape(eff_text)}'
    return '; '.join(_escape(item) for item in trace['models'])


def render_report(report, repo, language=None):
    """Produce Markdown only after validation; never execute reported commands."""
    validation = validate_report(report, repo)
    if not validation['valid']:
        raise CheckError(','.join(validation['errors']))
    language = language or report['language']
    if language not in ('es', 'en'):
        raise CheckError('LANGUAGE_INVALID')
    es = language == 'es'
    names = {'approval_recommended': 'Aprobación sugerida' if es else 'Approval recommended',
             'changes_required': 'Cambios requeridos' if es else 'Changes required',
             'review_incomplete': 'Revisión incompleta' if es else 'Review incomplete'}
    states = dict(zip(STATUSES, ('Cumple', 'No cumple', 'No verificado', 'No aplica') if es else
                      ('Met', 'Not met', 'Not verified', 'Not applicable')))
    labels = dict(zip(CRITERIA, ('Requisitos acordados', 'Validación funcional', 'Seguridad aplicable', 'Compatibilidad e impacto') if es else
                     ('Agreed requirements', 'Functional validation', 'Applicable security', 'Compatibility and impact')))
    requester = report['requester']
    attribution = (('Generado por IA en nombre de ' if es else 'AI-generated on behalf of ') + _escape(requester) + '.') if requester else (
        'Generado por IA. Persona solicitante no identificada.' if es else 'AI-generated. Requester not identified.')
    trace = report['trace']
    depth = report['depth']
    pr_url = trace.get('pr_url')
    if pr_url and SAFE_PR_URL.fullmatch(pr_url):
        scope_display = pr_url
    else:
        scope_display = _escape(pr_url or report['scope']['root'])
    base_ref = trace.get('base')
    head_ref = trace.get('head') or (report['scope']['repositories'][0]['head'] if report['scope']['repositories'] else None)
    rev_text = ''
    if base_ref and head_ref:
        rev_text = ' (' + _code(base_ref + '..' + head_ref) + ')'
    elif head_ref:
        rev_text = ' (HEAD ' + _code(head_ref) + ')'
    cr_text = ', '.join(_escape(value) for value in trace['cr']) if trace['cr'] else ('No registrado' if es else 'Not recorded')
    lines = ['# ' + ('Review consolidado: ' if es else 'Consolidated review: ') + names[report['recommendation']],
             '', attribution, '',
             '**' + ('Mínimos del cambio' if es else 'Change minimums') + ':** ' + states[report['minimums']],
             '**' + ('Profundidad' if es else 'Depth') + ':** `' + depth + '`',
             '**' + ('Alcance' if es else 'Scope') + ':** ' + scope_display + rev_text,
             '**' + ('Modelo y esfuerzo' if es else 'Model and effort') + ':** ' + _header_model_summary(trace, es),
             '**' + ('Presupuesto' if es else 'Budget') + ':** ' + cr_text,
             '**' + ('Motivo' if es else 'Reason') + ':** ' + _escape(report['reason']), '',
             '| ' + ('Criterio | Evaluación | Evidencia o pendiente' if es else 'Criterion | Evaluation | Evidence or pending work') + ' |',
             '| --- | --- | --- |']
    for key in CRITERIA:
        item = report['criteria'][key]
        lines.append('| ' + labels[key] + ' | ' + states[item['status']] + ' | ' + _escape(item['evidence']) + ' |')
    lines.extend(['', '## ' + ('Alcance capturado' if es else 'Captured scope'), ''])
    complete = report['scope']['coverage']['complete']
    coverage = ('completa' if complete else 'incompleta') if es else ('complete' if complete else 'incomplete')
    lines.extend([('Cobertura de captura: ' if es else 'Snapshot coverage: ') + coverage + '.', ''])
    for item in report['scope']['repositories']:
        lines.append('- ' + _escape(item['path']) + ': HEAD `' + (item['head'] or 'unavailable') +
                     '`, index `' + item['index_sha256'] + '`, worktree `' + item['worktree_sha256'] + '`.')
        lines.append('- ' + _escape(item['path']) + ': ' +
                     ('cambios locales' if es else 'local changes') + ' = ' + str(item['dirty']).lower() +
                     ', ' + ('archivos nuevos' if es else 'untracked files') + ' = ' + str(item['untracked_files']) + '.')
        for issue in item['issues']:
            lines.append('- ' + _escape(item['path'] + '/' + issue['path']) + ': ' + issue['code'] + '.')
    for item in report['scope']['submodules']:
        lines.append('- ' + _escape(item['path']) + ': ' + item['state'] + ', pinned `' +
                     (item['pinned_head'] or 'none') + '`, current `' + (item['current_head'] or 'unavailable') + '`.')
    lines.extend(['', '## ' + ('Hallazgos materiales y adjudicaciones' if es else 'Material findings and adjudications'), ''])
    for item in report['findings']:
        tags = []
        if item['material']:
            tags.append('material')
        if item.get('severity'):
            tags.append(item['severity'])
        tag_text = (' [' + ', '.join(tags) + ']') if tags else ''
        loc = ''
        if item.get('path'):
            loc = ' ' + _code(item['path'] + (':' + str(item['line']) if item.get('line') else ''))
        lines.append('- ' + _escape(item['id']) + ': ' + item['status'] + tag_text + loc + '. ' + _escape(item['evidence']))
        detail_labels = (
            ('conditions', 'Condiciones', 'Conditions'),
            ('impact', 'Impacto', 'Impact'),
            ('minimal_fix', 'Corrección mínima', 'Minimal fix'),
            ('visible_flow', 'Flujo / pantalla visible', 'Visible flow / screen'),
            ('adjudication', 'Adjudicación del padre', 'Parent adjudication'),
        )
        for field_key, label_es, label_en in detail_labels:
            if item.get(field_key):
                lines.append('  - ' + (label_es if es else label_en) + ': ' + _escape(item[field_key]))
    if not report['findings']:
        lines.append('Sin hallazgos declarados dentro del alcance.' if es else 'No findings declared within the scope.')
    lines.extend(['', '## ' + ('Evidencia de pruebas' if es else 'Test evidence'), ''])
    for item in report['tests']:
        lines.append('- ' + _escape(item['command']) + ' (cwd: ' + _escape(item['cwd']) + '): ' + item['status'] + '. ' + _escape(item['evidence']))
    lines.extend(['', '## ' + ('Alcance del impacto (blast radius)' if es else 'Blast radius'), '', _escape(report['impact'])])
    lines.extend(['', '## ' + ('Evidencia de seguridad' if es else 'Security evidence'), ''])
    has_security_entries = any(report['security'][k] for k in ('standards', 'controls', 'limitations'))
    if depth == 'lite' and not has_security_entries:
        lines.append(
            'Profundidad `lite`: se omitió la auditoría completa OWASP Top 10 / NIST SSDF al no observarse defectos de seguridad obvios en el cambio.'
            if es else
            'Depth `lite`: skipped full OWASP Top 10 / NIST SSDF compliance audit with no obvious security defects spotted in the change.'
        )
    else:
        if depth == 'lite':
            lines.append(
                'Profundidad `lite` (sin auditoría completa OWASP/NIST SSDF salvo hallazgos o límites declarados):'
                if es else
                'Depth `lite` (no full OWASP/NIST SSDF audit beyond declared findings or limitations):'
            )
        for idx, (key, title_es, title_en) in enumerate((('standards', 'Referencias', 'Standards'), ('controls', 'Controles', 'Controls'), ('limitations', 'Límites', 'Limitations'))):
            if idx > 0 or depth == 'lite':
                lines.append('')
            lines.append('**' + (title_es if es else title_en) + '**')
            lines.append('')
            lines.extend('- ' + _escape(value) for value in report['security'][key])
            if not report['security'][key]:
                lines.append('Sin entradas declaradas.' if es else 'No entries declared.')
    lines.extend(['', '## ' + ('Trazabilidad' if es else 'Traceability'), ''])
    lines.append('- ' + ('Profundidad: `' if es else 'Depth: `') + depth + '`')
    lines.extend('- ' + _escape(value) for value in trace['models'])
    if trace.get('session_model'):
        lines.append('- ' + ('Modelo de sesión: ' if es else 'Session model: ') + _escape(trace['session_model']))
    lines.append('- ' + ('Ruta: ' if es else 'Route: ') + _escape(trace['route']))
    if trace.get('fallback'):
        lines.append('- ' + ('Fallback: ' if es else 'Fallback: ') + _escape(trace['fallback']))
    lines.extend('- ' + _escape(value) for value in trace['cr'])
    lines.extend(['', ('La captura excluye archivos ignorados por Git y repositorios externos. ' if es else
                       'The snapshot excludes Git-ignored files and external repositories. ') +
                      ('El validador comprueba estructura, coherencia y vigencia del alcance; no ejecuta las pruebas declaradas ni certifica su calidad, seguridad o una aprobación humana.' if es else
                       'The validator checks structure, consistency and current scope; it does not execute declared tests or certify their quality, security or human approval.'), ''])
    return '\n'.join(lines)


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise CheckError('ARGUMENTS_INVALID')


def main(argv=None):
    try:
        parser = _Parser(description=__doc__)
        parser.add_argument('action', choices=('snapshot', 'validate', 'render', 'template'))
        parser.add_argument('--repo', required=True)
        parser.add_argument('--report')
        parser.add_argument('--language', choices=('es', 'en'))
        parser.add_argument('--depth', choices=DEPTHS, default='deep')
        args = parser.parse_args(argv)
        if args.action in ('validate', 'render') and not args.report:
            raise CheckError('REPORT_REQUIRED')
        if args.action == 'snapshot':
            output = snapshot(args.repo)
        elif args.action == 'template':
            output = template(args.repo, args.language or 'es', args.depth)
        else:
            report = load_report(args.report)
            if args.action == 'render':
                print(render_report(report, args.repo, args.language), end='')
                return 0
            output = validate_report(report, args.repo)
        print(json.dumps(output, ensure_ascii=True, sort_keys=True))
        return 2 if type(output) is dict and output.get('valid') is False else 0
    except CheckError as exc:
        print(json.dumps({'valid': False, 'errors': str(exc).split(',')}))
        return 2
    except (OSError, ValueError, TypeError, RecursionError):
        print(json.dumps({'valid': False, 'errors': ['INPUT_INVALID']}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
