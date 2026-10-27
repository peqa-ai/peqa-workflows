#!/usr/bin/env python3
"""Opt-in local PEQA events. Python 3.10+, macOS/Linux, standard library only.

Only ``enable`` creates storage or grants consent. A Git repository and its
linked worktrees share ``<git-common-dir>/peqa/usage``. Records contain no host
session identifiers, prompts, file paths, source code, or token estimates.
The caller must generate a fresh UUIDv4 for each skill invocation and reuse it
for that invocation's phases. Events report observations, not verified work.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date, datetime, timezone
import errno
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import uuid

if __package__:
    from .git_paths import GitPathError, check_git_marker
else:
    from git_paths import GitPathError, check_git_marker


SKILLS = ("peqa-dirige", "peqa-idea", "peqa-revisa", "peqa-memoria-recuerda",
          "peqa-memoria-extraer")
RUNTIMES = ("t3-codex", "t3-claude", "codex", "claude")
PHASES = ("started", "completed", "failed")
SCOPE = "observed_events_only"
MAX_EVENTS = 50_000
MAX_STATE_BYTES = 16 * 1024 * 1024
LOCK_TIMEOUT_SECONDS = 5
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
FILE_FLAGS = os.O_NOFOLLOW | os.O_NONBLOCK
DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
TIMESTAMP_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z\Z")


class UsageError(Exception):
    """A fixed error code safe to emit without private input or OS messages."""


def random_id(value):
    if not isinstance(value, str) or len(value) != 36:
        raise ValueError("UUIDv4 required")
    parsed = uuid.UUID(value)
    if str(parsed) != value or parsed.version != 4 or parsed.variant != uuid.RFC_4122:
        raise ValueError("UUIDv4 required")
    return value


def validate_arguments(action, repo, skill, runtime, phase, invocation_id, since):
    if action not in ("enable", "disable", "status", "record", "summary"):
        raise UsageError("INVALID_ARGUMENTS")
    if not isinstance(repo, (str, os.PathLike)) or not 0 < len(os.fspath(repo)) <= 4096:
        raise UsageError("INVALID_ARGUMENTS")
    if "\x00" in os.fspath(repo):
        raise UsageError("INVALID_ARGUMENTS")
    try:
        if action == "record":
            if skill not in SKILLS or runtime not in RUNTIMES or phase not in PHASES:
                raise ValueError("Invalid event")
            random_id(invocation_id)
        elif any(value is not None for value in (skill, runtime, phase, invocation_id)):
            raise ValueError("Unexpected event")
        if since is not None:
            if action != "summary" or not isinstance(since, str) or not DATE_PATTERN.fullmatch(since):
                raise ValueError("Invalid date")
            date.fromisoformat(since)
    except (ValueError, TypeError, AttributeError):
        raise UsageError("INVALID_ARGUMENTS") from None


def common_directory(repo):
    # GIT_DIR, GIT_WORK_TREE, and config overrides must not redirect --repo.
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(GIT_OPTIONAL_LOCKS="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    try:
        root = Path(repo).resolve(strict=True)
        check_git_marker(root)
        result = subprocess.run(["git", "-C", str(root), "rev-parse", "--git-common-dir"], capture_output=True, text=True,
                                env=environment, timeout=10)
    except GitPathError as error:
        raise UsageError(str(error)) from None
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError):
        raise UsageError("GIT_REPOSITORY_REQUIRED") from None
    output = result.stdout.rstrip("\n")
    if result.returncode or not output or len(output) > 4096 or "\n" in output or "\x00" in output:
        raise UsageError("GIT_REPOSITORY_REQUIRED")
    # Git's absolute-path option canonicalizes symlinks before we can reject
    # them. Keep its relative form and let descriptor traversal check it.
    return Path(os.path.abspath(output if os.path.isabs(output) else root / output))


def directory_owner(fd, private=False):
    info = os.fstat(fd)
    if info.st_uid != os.geteuid() or info.st_mode & 0o022:
        raise UsageError("UNSAFE_STORAGE")
    if private and stat.S_IMODE(info.st_mode) != 0o700:
        raise UsageError("UNSAFE_STORAGE")


def open_child(parent, name, create=False, private=False):
    if create:
        try:
            os.mkdir(name, mode=0o700, dir_fd=parent)
        except FileExistsError:
            pass
    child = os.open(name, DIR_FLAGS, dir_fd=parent)
    try:
        directory_owner(child, private=private)
        return child
    except BaseException:
        os.close(child)
        raise


@contextmanager
def storage(repo, create=False):
    """Pin every directory with a descriptor; never follow storage symlinks."""
    descriptors = []
    try:
        common = common_directory(repo)
        fd = os.open(common.anchor, DIR_FLAGS)
        descriptors.append(fd)
        for part in common.parts[1:]:
            fd = os.open(part, DIR_FLAGS, dir_fd=fd)
            descriptors.append(fd)
        directory_owner(fd)
        for part in ("peqa", "usage"):
            try:
                fd = open_child(fd, part, create=create, private=part == "usage")
            except FileNotFoundError:
                if create:
                    raise
                yield None
                return
            descriptors.append(fd)
        yield fd
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def check_file(fd, max_size):
    info = os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o600):
        raise UsageError("UNSAFE_STORAGE")
    if info.st_size > max_size:
        raise UsageError("STATE_TOO_LARGE")
    return info


@contextmanager
def locked(directory, create=False):
    if directory is None:
        yield False
        return
    fd = None
    try:
        if create:
            try:
                fd = os.open("usage.lock", os.O_RDWR | os.O_CREAT | os.O_EXCL | FILE_FLAGS,
                             0o600, dir_fd=directory)
            except FileExistsError:
                pass
        if fd is None:
            try:
                fd = os.open("usage.lock", os.O_RDONLY | FILE_FLAGS, dir_fd=directory)
            except FileNotFoundError:
                try:
                    os.stat("state.json", dir_fd=directory, follow_symlinks=False)
                except FileNotFoundError:
                    yield False
                    return
                raise UsageError("STATE_INVALID") from None
        info = check_file(fd, 0)
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise UsageError("STORAGE_BUSY") from None
                time.sleep(0.02)
        current = os.stat("usage.lock", dir_fd=directory, follow_symlinks=False)
        if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
            raise UsageError("UNSAFE_STORAGE")
        yield True
    finally:
        if fd is not None:
            os.close(fd)  # Closing also releases flock, even when validation failed.


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate key")
        result[key] = value
    return result


def validate_state(data):
    if (not isinstance(data, dict) or set(data) != {"schema", "enabled", "project_id", "events"}
            or type(data["schema"]) is not int or data["schema"] != 1
            or type(data["enabled"]) is not bool or not isinstance(data["events"], list)
            or len(data["events"]) > MAX_EVENTS):
        raise ValueError("Invalid state")
    random_id(data["project_id"])
    identities = {}
    seen = set()
    for event in data["events"]:
        if (not isinstance(event, dict)
                or set(event) != {"timestamp", "invocation_id", "skill", "runtime", "phase"}
                or event["skill"] not in SKILLS or event["runtime"] not in RUNTIMES
                or event["phase"] not in PHASES or not isinstance(event["timestamp"], str)
                or not TIMESTAMP_PATTERN.fullmatch(event["timestamp"])):
            raise ValueError("Invalid event")
        datetime.strptime(event["timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ")
        invocation = random_id(event["invocation_id"])
        identity = (event["skill"], event["runtime"])
        if identities.setdefault(invocation, identity) != identity:
            raise ValueError("Inconsistent identity")
        key = (invocation, event["phase"])
        if key in seen:
            raise ValueError("Duplicate event")
        seen.add(key)
    return data


def read_state(directory):
    try:
        fd = os.open("state.json", os.O_RDONLY | FILE_FLAGS, dir_fd=directory)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "rb") as stream:
        check_file(stream.fileno(), MAX_STATE_BYTES)
        raw = stream.read(MAX_STATE_BYTES + 1)
        if len(raw) > MAX_STATE_BYTES:
            raise UsageError("STATE_TOO_LARGE")
    try:
        return validate_state(json.loads(raw, object_pairs_hook=unique_keys))
    except (ValueError, TypeError, KeyError, RecursionError):
        raise UsageError("STATE_INVALID") from None


def save_state(directory, data):
    payload = (json.dumps(data, ensure_ascii=True, separators=(",", ":")) + "\n").encode("utf-8")
    if len(payload) > MAX_STATE_BYTES:
        raise UsageError("STATE_TOO_LARGE")
    temporary = ".state-" + uuid.uuid4().hex + ".tmp"
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | FILE_FLAGS,
                 0o600, dir_fd=directory)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, "state.json", src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
    finally:
        try:
            os.unlink(temporary, dir_fd=directory)
        except FileNotFoundError:
            pass


def summarize(data, since):
    totals = {phase: 0 for phase in PHASES}
    groups = {}
    for event in data["events"] if data else ():
        if since is not None and event["timestamp"][:10] < since:
            continue
        key = (event["skill"], event["runtime"])
        group = groups.setdefault(key, {"skill": key[0], "runtime": key[1],
                                         **{phase: 0 for phase in PHASES}})
        group[event["phase"]] += 1
        totals[event["phase"]] += 1
    return {"enabled": bool(data and data["enabled"]), "scope": SCOPE, "since": since,
            "totals": totals, "groups": [groups[key] for key in sorted(groups)]}


def execute(action, repo, *, skill=None, runtime=None, phase=None, invocation_id=None, since=None):
    """Execute a CLI operation and return its JSON-ready result without printing."""
    validate_arguments(action, repo, skill, runtime, phase, invocation_id, since)
    try:
        with storage(repo, create=action == "enable") as directory:
            with locked(directory, create=action == "enable") as acquired:
                data = read_state(directory) if acquired else None
                if action == "enable":
                    if data is None:
                        data = {"schema": 1, "enabled": True, "project_id": str(uuid.uuid4()), "events": []}
                        save_state(directory, data)
                    elif not data["enabled"]:
                        data["enabled"] = True
                        save_state(directory, data)
                    return {"enabled": True, "status": "enabled"}
                if action == "disable":
                    if data and data["enabled"]:
                        data["enabled"] = False
                        save_state(directory, data)
                    return {"enabled": False, "status": "disabled"}
                if action == "status":
                    return {"enabled": bool(data and data["enabled"]), "scope": SCOPE,
                            "event_count": len(data["events"]) if data else 0}
                if action == "summary":
                    return summarize(data, since)
                if data is None or not data["enabled"]:
                    return {"status": "skipped", "reason": "disabled"}
                for event in data["events"]:
                    if event["invocation_id"] != invocation_id:
                        continue
                    if (event["skill"], event["runtime"]) != (skill, runtime):
                        raise UsageError("INVOCATION_MISMATCH")
                    if event["phase"] == phase:
                        return {"status": "duplicate"}
                if len(data["events"]) >= MAX_EVENTS:
                    raise UsageError("EVENT_LIMIT_REACHED")
                data["events"].append({"timestamp": datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z"),
                                       "invocation_id": invocation_id, "skill": skill,
                                       "runtime": runtime, "phase": phase})
                save_state(directory, data)
                return {"status": "recorded"}
    except OSError as error:
        unsafe = (errno.ELOOP, errno.ENOTDIR, errno.EACCES, errno.EPERM)
        raise UsageError("UNSAFE_STORAGE" if error.errno in unsafe else "STORAGE_UNAVAILABLE") from None


class PrivateParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse normally echoes invalid argument values, which may be private.
        raise UsageError("INVALID_ARGUMENTS")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if sum(len(value) for value in argv) > 32768 or any(len(value) > 4096 for value in argv):
            raise UsageError("INVALID_ARGUMENTS")
        parser = PrivateParser(description=__doc__, allow_abbrev=False)
        commands = parser.add_subparsers(dest="action", required=True)
        for action in ("enable", "disable", "status", "record", "summary"):
            command = commands.add_parser(action, allow_abbrev=False)
            command.add_argument("--repo", required=True, help="Git repository or linked worktree")
            if action == "record":
                command.add_argument("--skill", required=True, choices=SKILLS)
                command.add_argument("--runtime", required=True, choices=RUNTIMES)
                command.add_argument("--phase", required=True, choices=PHASES)
                command.add_argument("--invocation-id", required=True, help="Fresh random UUIDv4, reused only across this invocation's phases")
            if action == "summary":
                command.add_argument("--since", help="Inclusive UTC date, YYYY-MM-DD")
        result = execute(**vars(parser.parse_args(argv)))
    except UsageError as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
