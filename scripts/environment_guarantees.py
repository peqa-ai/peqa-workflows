#!/usr/bin/env python3
"""Read-only check of what holds irreversible actions outside the prompt.

Reports, as JSON, whether the checkout's secret files are covered by client
rules, and, on request, whether the default branch, a pull request and the
deployment environments have server-side guarantees. It lists secret files by
name and never opens them, changes no setting and runs no project command.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

LIMIT = 1048576
MAX_ENTRIES = 5000
MAX_SECRETS = 20
DEPTH = 2
TIMEOUT = 15
SKIP_DIRS = {'.git', 'node_modules', '.venv', 'venv', 'dist', 'build', 'vendor', 'target', '__pycache__'}
SAMPLE_SUFFIXES = ('.example', '.sample', '.template', '.dist', '.defaults')
PR_URL = re.compile(r'https://[A-Za-z0-9.-]{1,253}/[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}/pull/[0-9]{1,9}')
NAME = re.compile(r'[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}')
BRANCH = re.compile(r'[A-Za-z0-9_./-]{1,255}')
PASSED = {'SUCCESS', 'NEUTRAL', 'SKIPPED'}
FAILED = {'FAILURE', 'ERROR', 'CANCELLED', 'TIMED_OUT', 'ACTION_REQUIRED', 'STARTUP_FAILURE', 'STALE'}


class CheckError(Exception):
    pass


def secret_files(root):
    """Names only: these files are never opened."""
    found, seen, pending = [], 0, [(root, 0)]
    while pending:
        folder, depth = pending.pop()
        try:
            entries = sorted(os.scandir(folder), key=lambda entry: entry.name)
        except OSError:
            continue
        for entry in entries:
            seen += 1
            if seen > MAX_ENTRIES or len(found) >= MAX_SECRETS:
                return sorted(found), True
            name = entry.name
            if entry.is_dir(follow_symlinks=False):
                if depth < DEPTH and name not in SKIP_DIRS:
                    pending.append((Path(entry.path), depth + 1))
            elif (name == '.env' or name.startswith('.env.')) and not name.endswith(SAMPLE_SUFFIXES):
                found.append(Path(entry.path).relative_to(root).as_posix())
    return sorted(found), False


def read_settings(path):
    """Return (state, data) without following a symlink at the final component."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return 'absent', {}
    except OSError:
        return 'unreadable', {}
    try:
        with os.fdopen(fd, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                return 'unreadable', {}
            raw = stream.read(LIMIT + 1)
        data = json.loads(raw) if len(raw) <= LIMIT else None
    except (OSError, ValueError):
        return 'unreadable', {}
    return ('read', data) if isinstance(data, dict) else ('unreadable', {})


def glob_regex(pattern):
    out, index = [], 0
    while index < len(pattern):
        if pattern.startswith('**/', index):
            out.append('(?:.*/)?')
            index += 3
        elif pattern.startswith('**', index):
            out.append('.*')
            index += 2
        elif pattern[index] == '*':
            out.append('[^/]*')
            index += 1
        elif pattern[index] == '?':
            out.append('[^/]')
            index += 1
        else:
            out.append(re.escape(pattern[index]))
            index += 1
    return re.compile(''.join(out) + r'(?:/.*)?\Z')


def denies(rule, relative, root):
    """Approximate Claude Code's Read(path) matching for one repo-relative file."""
    if not isinstance(rule, str) or not rule.startswith('Read(') or not rule.endswith(')') or len(rule) > 1024:
        return False
    pattern = rule[5:-1]
    if pattern.startswith('//'):
        target, pattern = (root / relative).as_posix(), pattern[1:]
    elif pattern.startswith('~/'):
        target, pattern = (root / relative).as_posix(), Path.home().as_posix() + pattern[1:]
    else:
        anchored = pattern.startswith(('./', '/'))
        pattern = pattern[2:] if pattern.startswith('./') else pattern.lstrip('/')
        # Like gitignore: a bare name matches at any depth, an anchored one from the root.
        target = relative if anchored or '/' in pattern else relative.rsplit('/', 1)[-1]
    return bool(pattern) and glob_regex(pattern).match(target) is not None


def proposed_denies(files):
    rules = []
    for relative in files:
        folder, _, name = relative.rpartition('/')
        prefix = './' + (folder + '/' if folder else '')
        rule = 'Read(' + prefix + ('.env' if name == '.env' else '.env.*') + ')'
        if rule not in rules:
            rules.append(rule)
    return rules


def secrets_check(root, runtime):
    files, truncated = secret_files(root)
    check = {'id': 'secrets', 'files': files, 'truncated': truncated}
    if not files:
        return dict(check, status='not_applicable')
    if runtime != 'claude':
        return dict(check, status='not_verified', reason='CLIENT_SETTINGS_NOT_INSPECTABLE')
    sources = (('local', root / '.claude/settings.local.json'), ('project', root / '.claude/settings.json'),
               ('user', Path.home() / '.claude/settings.json'))
    states, rules, sandbox = {}, [], None
    for scope, path in sources:  # Highest precedence first.
        states[scope], data = read_settings(path)
        permissions = data.get('permissions')
        deny = permissions.get('deny') if isinstance(permissions, dict) else None
        if isinstance(deny, list):
            rules.extend(rule for rule in deny if isinstance(rule, str))
        box = data.get('sandbox')
        if sandbox is None and isinstance(box, dict) and isinstance(box.get('enabled'), bool):
            sandbox = box['enabled']
    uncovered = [name for name in files if not any(denies(rule, name, root) for rule in rules)]
    check.update(settings=states, sandbox_enabled=bool(sandbox), unprotected_files=uncovered)
    if not uncovered and sandbox:
        return dict(check, status='ok')
    add = {}
    if uncovered:
        add['permissions'] = {'deny': proposed_denies(uncovered)}
    if not sandbox:
        add['sandbox'] = {'enabled': True}
    return dict(check, status='missing', proposal={'kind': 'claude_settings', 'file': '.claude/settings.json', 'add': add})


class GitHub:
    def __init__(self, root):
        self.root = root
        self.binary = shutil.which('gh')
        self.repo = self.branch = None
        self.reason = None
        if self.binary is None:
            self.reason = 'GH_NOT_FOUND'
            return
        code, data, _ = self.json('repo', 'view', '--json', 'nameWithOwner,defaultBranchRef')
        name = data.get('nameWithOwner') if isinstance(data, dict) else None
        ref = data.get('defaultBranchRef') if isinstance(data, dict) else None
        branch = ref.get('name') if isinstance(ref, dict) else None
        if code or not isinstance(name, str) or not NAME.fullmatch(name) \
                or not isinstance(branch, str) or not BRANCH.fullmatch(branch) or '..' in branch:
            self.reason = 'GH_REPOSITORY_UNAVAILABLE'
            return
        self.repo, self.branch = name, branch

    def json(self, *args):
        environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        environment.update(GH_PROMPT_DISABLED='1', GH_NO_UPDATE_NOTIFIER='1', NO_COLOR='1')
        try:
            proc = subprocess.run([self.binary, *args], cwd=self.root, capture_output=True, text=True,
                                  timeout=TIMEOUT, env=environment, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            return 1, None, ''
        if len(proc.stdout) > LIMIT:
            return 1, None, ''
        try:
            data = json.loads(proc.stdout) if proc.stdout.strip() else None
        except ValueError:
            data = None
        if proc.returncode == 0 and data is None:
            return 1, None, ''
        return proc.returncode, data, proc.stderr[-400:]

    def api(self, path):
        return self.json('api', f'repos/{self.repo}/{path}')


def workflows(root):
    folder = root / '.github/workflows'
    try:
        return sorted(entry.name for entry in os.scandir(folder) if entry.name.endswith(('.yml', '.yaml')))[:50]
    except OSError:
        return []


def branch_check(github):
    check = {'id': 'branch_protection', 'branch': github.branch}
    code, branch, _ = github.api(f'branches/{github.branch}')
    code_rules, rules, _ = github.api(f'rules/branches/{github.branch}')
    if code or not isinstance(branch, dict) or code_rules or not isinstance(rules, list):
        return dict(check, status='not_verified', reason='GH_REQUEST_FAILED')
    protection = branch.get('protection') if isinstance(branch.get('protection'), dict) else {}
    required = protection.get('required_status_checks') if isinstance(protection.get('required_status_checks'), dict) else {}
    contexts = [item for item in required.get('contexts') or [] if isinstance(item, str)]
    types = sorted({rule.get('type') for rule in rules if isinstance(rule, dict) and isinstance(rule.get('type'), str)})
    for rule in rules:
        parameters = rule.get('parameters') if isinstance(rule, dict) and rule.get('type') == 'required_status_checks' else None
        for item in (parameters or {}).get('required_status_checks') or []:
            if isinstance(item, dict) and isinstance(item.get('context'), str):
                contexts.append(item['context'])
    checks = sorted(set(contexts))[:50]
    check.update(protected=branch.get('protected') is True, ruleset_rules=types, required_checks=checks)
    if checks:
        return dict(check, status='ok')
    need = ['status_checks'] if check['protected'] or 'pull_request' in types else ['pull_request', 'status_checks']
    return dict(check, status='missing', proposal={'kind': 'branch_protection', 'branch': github.branch, 'require': need})


def pr_check(github, url, root):
    check = {'id': 'pr_checks', 'pr': url}
    code, data, _ = github.json('pr', 'view', url, '--json', 'statusCheckRollup,headRefOid,state')
    rollup = data.get('statusCheckRollup') if isinstance(data, dict) else None
    if code or not isinstance(rollup, list):
        return dict(check, status='not_verified', reason='GH_REQUEST_FAILED')
    passed = failed = pending = 0
    for item in rollup:
        result = (item.get('conclusion') or item.get('state') or '') if isinstance(item, dict) else ''
        result = result.upper() if isinstance(result, str) else ''
        passed, failed = passed + (result in PASSED), failed + (result in FAILED)
        pending += result not in PASSED and result not in FAILED
    found = workflows(root)
    check.update(head=data.get('headRefOid'), ran=len(rollup), passed=passed, failed=failed, pending=pending,
                 workflow_files=found)
    if rollup:
        return dict(check, status='ok')
    return dict(check, status='missing', proposal={'kind': 'ci_workflow', 'on': 'pull_request',
                                                   'run': 'existing project test command',
                                                   'workflow_files_present': bool(found)})


def deploy_check(github):
    check = {'id': 'deployment'}
    code, data, _ = github.api('environments')
    items = data.get('environments') if isinstance(data, dict) else None
    if code or not isinstance(items, list):
        return dict(check, status='not_verified', reason='GH_REQUEST_FAILED')
    names = [item.get('name') for item in items if isinstance(item, dict) and isinstance(item.get('name'), str)]
    guarded = [item.get('name') for item in items if isinstance(item, dict) and item.get('protection_rules')
               and isinstance(item.get('name'), str)]
    check.update(environments=names[:50], protected_environments=guarded[:50])
    if guarded:
        return dict(check, status='ok')
    return dict(check, status='missing', proposal={'kind': 'deployment_environment', 'require': ['required_reviewers']})


def run(args):
    root = Path(args.repo).resolve()
    if not root.is_dir():
        raise CheckError('REPOSITORY_DIRECTORY_REQUIRED')
    if args.pr and not PR_URL.fullmatch(args.pr):
        raise CheckError('PULL_REQUEST_URL_REQUIRED')
    checks = [secrets_check(root, args.runtime)]
    wanted = [name for name, on in (('branch_protection', args.merge or args.pr), ('pr_checks', args.pr),
                                    ('deployment', args.deploy)) if on]
    if wanted:
        github = GitHub(root)
        for name in wanted:
            if github.reason:
                checks.append({'id': name, 'status': 'not_verified', 'reason': github.reason})
            elif name == 'branch_protection':
                checks.append(branch_check(github))
            elif name == 'pr_checks':
                checks.append(pr_check(github, args.pr, root))
            else:
                checks.append(deploy_check(github))
    return {
        'schema_version': 1,
        'runtime': args.runtime,
        'checks': checks,
        'missing': [check['id'] for check in checks if check['status'] == 'missing'],
        'not_verified': [check['id'] for check in checks if check['status'] == 'not_verified'],
        'limits': ['MANAGED_AND_COMMAND_LINE_SETTINGS_NOT_READ', 'READ_RULE_MATCHING_IS_APPROXIMATE',
                   'SECRET_FILES_DETECTED_BY_NAME_ONLY'],
        'notice': 'Read-only. Nothing was changed; proposals are for the user to review and apply.',
    }


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise CheckError('INVALID_ARGUMENTS')


def main(argv=None):
    parser = Parser(description=__doc__)
    parser.add_argument('action', choices=['check'])
    parser.add_argument('--repo', required=True)
    parser.add_argument('--runtime', choices=['claude', 'codex'], default='claude')
    parser.add_argument('--merge', action='store_true', help='the task asks to merge')
    parser.add_argument('--deploy', action='store_true', help='the task asks to deploy or publish')
    parser.add_argument('--pr', help='pull request URL, once it exists')
    try:
        print(json.dumps(run(parser.parse_args(argv)), indent=2))
        return 0
    except CheckError as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
