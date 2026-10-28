#!/usr/bin/env python3
"""Optional session-scoped hooks. Direct validators remain authoritative."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import uuid

from git_paths import GitPathError, check_git_marker

LIMIT = 1048576
BUDGET = Path(__file__).resolve().parents[1] / 'skills/revisa/scripts/review_budget.py'
CHECKS = Path(__file__).with_name('review_checks.py')


class HookError(Exception):
    pass


def git_path(repo, flag):
    check_git_marker(repo)
    environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    environment.update(GIT_OPTIONAL_LOCKS='0', GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
    proc = subprocess.run(['git', '-C', str(repo), 'rev-parse', flag],
                          capture_output=True, text=True, timeout=5, env=environment)
    if proc.returncode:
        raise HookError('GIT_REPOSITORY_REQUIRED')
    path = Path(proc.stdout.strip())
    return Path(os.path.abspath(path if path.is_absolute() else repo / path))


def open_directory(path):
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except Exception:
        os.close(fd)
        raise


def read_fd(fd):
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise HookError('REGULAR_FILE_REQUIRED')
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise HookError('INPUT_TOO_LARGE')
    return json.loads(raw)


def read_json(path):
    # Walk each component without following links, including parent directories.
    path = Path(os.path.abspath(path))
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return read_fd(os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd))
    finally:
        os.close(fd)


class State:
    def __init__(self, repo, session, create=False):
        if not isinstance(session, str) or not 1 <= len(session) <= 256:
            raise HookError('SESSION_ID_REQUIRED')
        self.repo = git_path(Path(repo).resolve(), '--show-toplevel')
        self.common = git_path(self.repo, '--git-common-dir')
        self.key = hashlib.sha256((str(self.repo) + '\0' + session).encode()).hexdigest()
        self.fd = open_directory(self.common)
        try:
            for part in ('peqa', 'hooks'):
                if create:
                    try:
                        os.mkdir(part, 0o700, dir_fd=self.fd)
                    except FileExistsError:
                        pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.fd)
                os.close(self.fd)
                self.fd = child
        except FileNotFoundError:
            self.close()
        except Exception:
            self.close()
            raise

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    @contextmanager
    def locked(self):
        fd = os.open(self.key + '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK,
                     0o600, dir_fd=self.fd)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise HookError('INVALID_LOCK')
            # Never hang the host on a stale/concurrent hook lock.
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            os.close(fd)

    def read(self):
        if self.fd is None:
            return None
        try:
            data = read_fd(os.open(self.key + '.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.fd))
        except FileNotFoundError:
            return None
        if not isinstance(data, dict) or data.get('schema_version') != 1:
            raise HookError('INVALID_STATE')
        return data

    def write(self, data):
        name = self.key + '.' + uuid.uuid4().hex + '.tmp'
        fd = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600, dir_fd=self.fd)
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(data, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.key + '.json', src_dir_fd=self.fd, dst_dir_fd=self.fd)
        finally:
            try:
                os.unlink(name, dir_fd=self.fd)
            except FileNotFoundError:
                pass


def bounded_script(script, args):
    proc = subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, timeout=8)
    if len(proc.stdout) > LIMIT:
        raise HookError('VALIDATOR_OUTPUT_TOO_LARGE')
    return proc.returncode, json.loads(proc.stdout)


def artifact_dir(repo):
    state = State(repo, 'artifact-directory', create=True)
    try:
        # Create via a directory descriptor; reject a symlink in either component.
        parent = os.open('..', os.O_RDONLY | os.O_DIRECTORY, dir_fd=state.fd)
        try:
            try:
                os.mkdir('checks', 0o700, dir_fd=parent)
            except FileExistsError:
                pass
            child = os.open('checks', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            os.close(child)
        finally:
            os.close(parent)
        return state.common / 'peqa/checks'
    finally:
        state.close()


def reservations_check(items, repo, claim=False):
    if not isinstance(items, list) or not 1 <= len(items) <= 32:
        raise HookError('RESERVATIONS_REQUIRED')
    for item in items:
        if not isinstance(item, dict) or set(item) != {'repo', 'identity', 'token', 'head'}:
            raise HookError('INVALID_RESERVATION')
        if any(not isinstance(value, str) or not value or len(value) > 2048 for value in item.values()):
            raise HookError('INVALID_RESERVATION')
        relative = Path(item['repo'])
        if relative.is_absolute() or '..' in relative.parts:
            raise HookError('INVALID_REPOSITORY_PATH')
        target = (repo / relative).resolve()
        if not target.is_relative_to(repo) or git_path(target, '--show-toplevel') != target:
            raise HookError('REPOSITORY_OUTSIDE_SCOPE')
        flag = '--pr-url' if item['identity'].startswith('https://') else '--id'
        code, receipt = bounded_script(BUDGET, ['claim' if claim else 'verify', '--repo', str(target), flag, item['identity'],
                                               '--token', item['token'], '--head', item['head']])
        if code or receipt.get('valid') is not True:
            raise HookError('BUDGET_VERIFICATION_FAILED')


def handle(args, event):
    if not isinstance(event, dict):
        raise HookError('INVALID_EVENT')
    name = event.get('hook_event_name')
    if name not in ('SessionStart', 'PreToolUse', 'Stop') or event.get('agent_id'):
        return {}
    session = event.get('session_id')
    cwd = event.get('cwd')
    if not isinstance(cwd, str):
        return {}
    state = State(args.repo, session)
    try:
        if git_path(Path(cwd).resolve(), '--show-toplevel') != state.repo:
            return {}
        if name == 'SessionStart':
            # Session IDs are opaque data, not instructions or shell snippets.
            session_json = json.dumps(session, ensure_ascii=True)
            return {'hookSpecificOutput': {'hookEventName': name, 'additionalContext':
                'PEQA hooks optional; direct validators remain required. Session ID JSON: ' + session_json}}
        if state.read() is None:
            return {}
        with state.locked():
            data = state.read()
            enforce = args.runtime == 'claude' and args.mode == 'enforce'
            if name == 'PreToolUse':
                guard = data.get('guard')
                if not guard or event.get('tool_name') != guard['tool']:
                    return {}
                try:
                    if guard.get('attempted'):
                        raise HookError('REVIEW_DISPATCH_ALREADY_CHECKED')
                    reservations_check(guard['reservations'], state.repo, claim=True)
                    guard['attempted'] = True
                    state.write(data)
                    return {}
                except HookError as exc:
                    reason = 'PEQA: ' + str(exc) + '. Verify the existing reservation; do not reserve again for this hook.'
                    if enforce:
                        return {'hookSpecificOutput': {'hookEventName': name, 'permissionDecision': 'deny',
                                                       'permissionDecisionReason': reason}}
                    return {'hookSpecificOutput': {'hookEventName': name, 'additionalContext': reason}}
            report = data.get('report')
            if not report:
                return {}
            try:
                read_json(report)  # Reject symlinked/nonregular artifacts before invoking the validator.
                code, result = bounded_script(CHECKS, ['validate', '--report', report, '--repo', str(state.repo)])
                valid = code == 0 and result.get('valid') is True
            except (OSError, ValueError, HookError, subprocess.TimeoutExpired):
                valid = False
            if valid:
                data.pop('report', None)
                state.write(data)
                return {}
            reason = 'PEQA: report or revision evidence is invalid. Run review_checks.py validate, fix the artifact or report the check as incomplete. Do not launch another reviewer automatically.'
            if enforce and not event.get('stop_hook_active') and not data.get('stop_blocked'):
                data['stop_blocked'] = True
                state.write(data)
                return {'decision': 'block', 'reason': reason}
            # Codex only warns. Claude may request at most one continuation per arm.
            data.pop('report', None)
            state.write(data)
            return {'systemMessage': reason}
    finally:
        state.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['artifact-dir', 'config', 'arm', 'guard', 'clear', 'run'])
    parser.add_argument('--repo', required=True)
    parser.add_argument('--runtime', choices=['claude', 'codex'], default='claude')
    parser.add_argument('--mode', choices=['warn', 'enforce'], default='warn')
    parser.add_argument('--session-id')
    parser.add_argument('--report')
    parser.add_argument('--reservations')
    parser.add_argument('--tool-name')
    args = parser.parse_args()
    state = None
    try:
        if args.action == 'artifact-dir':
            print(json.dumps({'directory': str(artifact_dir(args.repo))}))
            return 0
        if args.action == 'config':
            root = git_path(Path(args.repo).resolve(), '--show-toplevel')
            mode = 'warn' if args.runtime == 'codex' else args.mode
            command = shlex.join([sys.executable, str(Path(__file__).resolve()), 'run', '--repo', str(root),
                                  '--runtime', args.runtime, '--mode', mode])
            hooks = {name: [{'hooks': [{'type': 'command', 'command': command, 'timeout': 20}]}]
                     for name in ('SessionStart', 'PreToolUse', 'Stop')}
            print(json.dumps({'hooks': hooks}, indent=2))
            return 0
        if args.action == 'run':
            raw = sys.stdin.buffer.read(LIMIT + 1)
            if len(raw) > LIMIT:
                raise HookError('INPUT_TOO_LARGE')
            print(json.dumps(handle(args, json.loads(raw))))
            return 0
        state = State(args.repo, args.session_id, create=args.action != 'clear')
        if state.fd is None:
            print(json.dumps({'status': 'unchanged'}))
            return 0
        with state.locked():
            data = state.read() or {'schema_version': 1}
            if args.action == 'arm':
                if not args.report:
                    raise HookError('REPORT_REQUIRED')
                path = Path(os.path.abspath(args.report))
                allowed = state.common / 'peqa/checks'
                if not path.is_relative_to(allowed) or '..' in Path(args.report).parts:
                    raise HookError('REPORT_MUST_BE_IN_PRIVATE_CHECKS_DIRECTORY')
                read_json(path)
                data.update(report=str(path), stop_blocked=False)
            elif args.action == 'guard':
                if not args.reservations or not args.tool_name or len(args.tool_name) > 256:
                    raise HookError('RESERVATIONS_AND_TOOL_REQUIRED')
                items = read_json(args.reservations)
                reservations_check(items, state.repo)
                data['guard'] = {'tool': args.tool_name, 'reservations': items, 'attempted': False}
            else:
                data = {'schema_version': 1}
            state.write(data)
        print(json.dumps({'status': 'ok'}))
        return 0
    except (HookError, GitPathError, OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError, subprocess.TimeoutExpired) as exc:
        code = str(exc) if isinstance(exc, (HookError, GitPathError)) else type(exc).__name__
        if args.action == 'run':
            # Host failures must never trap a session or fabricate a passing check.
            print(json.dumps({'systemMessage': 'PEQA hook unavailable: ' + code + '. Use direct validators.'}))
            return 0
        print(json.dumps({'error': code}), file=sys.stderr)
        return 2
    finally:
        if state is not None:
            state.close()


if __name__ == '__main__':
    sys.exit(main())
