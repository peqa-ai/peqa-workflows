#!/usr/bin/env python3
"""Atomically reserve at most three review dispatches per PR in a shared Git repo."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid
from urllib.parse import urlsplit

LIMIT = 3
CHANGE_ID = re.compile(r'^change-[a-z0-9][a-z0-9-]{0,79}$')
LEGACY_ID = re.compile(r'^pr-([1-9][0-9]*)$')
IDENTITY = re.compile(r'^(?:pr-[1-9][0-9]*|pr-url-[0-9a-f]{64}|change-[a-z0-9][a-z0-9-]{0,79})$')


class BudgetError(Exception):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def pr_identity(value):
    """Normalize a GitHub-style web PR URL, including enterprise hosts."""
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise BudgetError('HTTPS_PR_URL_REQUIRED')
    host = parsed.hostname.lower().rstrip('.')
    if not re.fullmatch(r'[a-z0-9.-]+', host):
        raise BudgetError('INVALID_PR_HOST')
    port = parsed.port
    if port is not None and not 1 <= port <= 65535:
        raise BudgetError('INVALID_PR_PORT')
    if port not in (None, 443):
        host += ':' + str(port)
    match = re.fullmatch(r'/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/pull/([1-9][0-9]*)/?', parsed.path)
    if not match or any(part in ('.', '..') for part in match.groups()[:2]):
        raise BudgetError('PR_WEB_URL_REQUIRED')
    owner, repo, number = match.groups()
    canonical = f'https://{host}/{owner.lower()}/{repo.lower()}/pull/{number}'
    return 'pr-url-' + hashlib.sha256(canonical.encode('utf-8')).hexdigest(), canonical, number


def directory(repo):
    root = Path(repo).resolve()
    result = subprocess.run(['git', '-C', str(root), 'rev-parse', '--git-common-dir'], capture_output=True, text=True)
    if result.returncode:
        raise BudgetError('GIT_REPOSITORY_REQUIRED')
    common = Path(result.stdout.strip())
    if not common.is_absolute():
        common = root / common
    location = common.resolve() / 'peqa' / 'reviews'
    location.mkdir(parents=True, exist_ok=True)
    return location


@contextmanager
def locked(location):
    with (location / 'budget.lock').open('a+b') as stream:
        if os.name == 'nt':
            import msvcrt
            if stream.seek(0, 2) == 0:
                stream.write(b'\0')
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == 'nt':
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def resolve(entries, identity):
    seen = set()
    while identity not in seen:
        seen.add(identity)
        data = entries.get(identity)
        if data is None:
            return identity, None
        if 'redirect' not in data:
            if not isinstance(data.get('passes'), list):
                raise BudgetError('LEDGER_INVALID')
            return identity, data
        identity = data['redirect']
        if not isinstance(identity, str) or not IDENTITY.fullmatch(identity):
            raise BudgetError('LEDGER_INVALID')
    raise BudgetError('LEDGER_REDIRECT_CYCLE')


def save(path, data):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('w') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def result(path, data):
    used = len(data['passes']) if data else 0
    return {'ledger': str(path), 'identity': data.get('identity') if data else None, 'pr_url': data.get('pr_url') if data else None, 'initialized': data is not None, 'used': used, 'remaining': max(0, LIMIT - used), 'limit': LIMIT, 'over_budget': used > LIMIT, 'passes': data['passes'] if data else []}


def run(args):
    if args.pr_url:
        requested, pr_url, number = pr_identity(args.pr_url)
    else:
        if not CHANGE_ID.fullmatch(args.id):
            raise BudgetError('PR_URL_REQUIRED_OR_CHANGE_ID')
        requested, pr_url, number = args.id, None, None
    if args.action in ('attach', 'migrate') and not pr_url:
        raise BudgetError('PR_URL_REQUIRED')
    location = directory(args.repo)
    with locked(location):
        path = location / 'budget.json'
        database = json.loads(path.read_text()) if path.exists() else {'schema': 1, 'entries': {}}
        if database.get('schema') != 1 or not isinstance(database.get('entries'), dict):
            raise BudgetError('LEDGER_INVALID')
        entries = database['entries']
        identity, data = resolve(entries, requested)
        if args.action == 'migrate':
            legacy = LEGACY_ID.fullmatch(args.from_id or '')
            if not legacy or legacy.group(1) != number:
                raise BudgetError('MATCHING_LEGACY_PR_ID_REQUIRED')
            source_identity, source = resolve(entries, args.from_id)
            if source is None:
                raise BudgetError('SOURCE_LEDGER_UNINITIALIZED')
            if source_identity.startswith('pr-url-'):
                if source_identity != identity:
                    raise BudgetError('LEGACY_ALREADY_BOUND_TO_ANOTHER_PR')
                return result(path, data)
            if data is None:
                data = {'identity': identity, 'pr_url': pr_url, 'created_at': source['created_at'], 'passes': []}
                entries[identity] = data
            tokens = {p['token'] for p in data['passes']}
            data['passes'].extend(p for p in source['passes'] if p['token'] not in tokens)
            entries[source_identity] = {'redirect': identity}
            save(path, database)
            return result(path, data)
        if number and ('pr-' + number) in entries:
            legacy_identity, _ = resolve(entries, 'pr-' + number)
            if not legacy_identity.startswith('pr-url-'):
                raise BudgetError('LEGACY_PR_ASSOCIATION_REQUIRED')
        if args.action == 'inspect':
            return result(path, data)
        if args.action == 'init':
            if data is not None:
                raise BudgetError('LEDGER_ALREADY_EXISTS')
            if args.prior_used is None or not 0 <= args.prior_used <= LIMIT:
                raise BudgetError('VERIFIED_PRIOR_COUNT_REQUIRED')
            data = {'identity': identity, 'pr_url': pr_url, 'created_at': now(), 'passes': [{'token': uuid.uuid4().hex, 'status': 'imported', 'head': None, 'reserved_at': now()} for _ in range(args.prior_used)]}
            entries[identity] = data
            save(path, database)
            return result(path, data)
        if data is None:
            raise BudgetError('LEDGER_UNINITIALIZED')
        if args.action == 'reserve':
            if len(data['passes']) >= LIMIT:
                raise BudgetError('BUDGET_EXHAUSTED')
            if not args.head or not re.fullmatch(r'[a-fA-F0-9]{7,64}', args.head):
                raise BudgetError('REVIEWED_REVISION_REQUIRED')
            token = uuid.uuid4().hex
            data['passes'].append({'token': token, 'status': 'reserved', 'head': args.head, 'reserved_at': now()})
            save(path, database)
            return {**result(path, data), 'token': token}
        if args.action == 'finish':
            review = next((p for p in data['passes'] if p['token'] == args.token), None)
            if review is None:
                raise BudgetError('UNKNOWN_RESERVATION')
            if review['status'] not in ['reserved', args.status]:
                raise BudgetError('RESERVATION_ALREADY_FINISHED')
            review.update(status=args.status, finished_at=now())
            save(path, database)
            return result(path, data)
        if not args.from_id or not CHANGE_ID.fullmatch(args.from_id):
            raise BudgetError('SOURCE_IDENTITY_REQUIRED')
        source_identity, source = resolve(entries, args.from_id)
        if source is None:
            raise BudgetError('SOURCE_LEDGER_UNINITIALIZED')
        if source_identity == identity:
            return result(path, data)
        if not CHANGE_ID.fullmatch(source_identity):
            raise BudgetError('LEGACY_PR_ASSOCIATION_REQUIRED' if LEGACY_ID.fullmatch(source_identity)
                              else 'SOURCE_CHANGE_ALREADY_BOUND_TO_ANOTHER_PR')
        tokens = {p['token'] for p in data['passes']}
        data['passes'].extend(p for p in source['passes'] if p['token'] not in tokens)
        # Counter and alias are committed together, including across process interruption.
        entries[source_identity] = {'redirect': identity}
        save(path, database)
        return result(path, data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['inspect', 'init', 'reserve', 'finish', 'attach', 'migrate'])
    parser.add_argument('--repo', required=True)
    identity = parser.add_mutually_exclusive_group(required=True)
    identity.add_argument('--id', help='Stable local change label: change-feature')
    identity.add_argument('--pr-url', help='Full HTTPS PR web URL, including host, owner/repository and /pull/number')
    parser.add_argument('--prior-used', type=int, help='Verified earlier review dispatch count; required for init')
    parser.add_argument('--head')
    parser.add_argument('--token')
    parser.add_argument('--status', choices=['completed', 'failed', 'cancelled'])
    parser.add_argument('--from-id', help='Source change label for attach, or verified legacy pr-N for migrate')
    args = parser.parse_args()
    if args.action == 'finish' and (not args.token or not args.status):
        parser.error('finish requires --token and --status')
    try:
        print(json.dumps(run(args), ensure_ascii=False))
    except (BudgetError, OSError, ValueError) as exc:
        error = str(exc) if isinstance(exc, BudgetError) else type(exc).__name__
        print(json.dumps({'error': error, 'limit': LIMIT}))
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
