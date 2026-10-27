"""Read-only validation of Git markers before Git canonicalizes their targets.

Call ``check_git_marker`` with the resolved repository/worktree path before
asking Git for its common directory. Consumers must still open that directory
and storage children without following symlinks. No files are created here.
"""
import os
from pathlib import Path
import stat


__all__ = ["GitPathError", "check_git_marker"]
FILE_FLAGS = os.O_NOFOLLOW | os.O_NONBLOCK


class GitPathError(Exception):
    """Fixed UNSAFE_STORAGE or GIT_REPOSITORY_REQUIRED code, without paths."""


def check_git_marker(root):
    """Reject symlink markers, gitfile targets, and worktree common-dir links.

    Return None if no unsafe marker is found. Absence of a marker is allowed
    for bare repositories; the caller's Git query must establish repository
    validity. Invalid/unreadable pointers raise only ``GitPathError``.
    """
    try:
        _check_git_marker(Path(root))
    except (OSError, RuntimeError, ValueError, TypeError):
        raise GitPathError("GIT_REPOSITORY_REQUIRED") from None


def _check_git_marker(root):
    for parent in (root, *root.parents):
        marker = parent / ".git"
        try:
            info = marker.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode):
            raise GitPathError("UNSAFE_STORAGE")
        if stat.S_ISDIR(info.st_mode):
            gitdir = marker
        elif stat.S_ISREG(info.st_mode):
            raw = read_git_pointer(marker)
            if not raw.startswith("gitdir: "):
                raise GitPathError("GIT_REPOSITORY_REQUIRED")
            gitdir = Path(raw[8:])
            if not gitdir.is_absolute():
                gitdir = parent / gitdir
            reject_path_alias(gitdir)
        else:
            raise GitPathError("UNSAFE_STORAGE")
        pointer = gitdir / "commondir"
        if os.path.lexists(pointer):
            raw = read_git_pointer(pointer)
            target = Path(raw)
            reject_path_alias(target if target.is_absolute() else gitdir / target)
        return


def reject_path_alias(path):
    if path.resolve(strict=True) != Path(os.path.abspath(path)):
        raise GitPathError("UNSAFE_STORAGE")


def read_git_pointer(path):
    fd = os.open(path, os.O_RDONLY | FILE_FLAGS)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 4096:
            raise GitPathError("UNSAFE_STORAGE")
        raw = stream.read(4097)
    try:
        result = raw.decode("utf-8").rstrip("\n")
    except UnicodeError:
        raise GitPathError("GIT_REPOSITORY_REQUIRED") from None
    if not result or len(raw) > 4096 or "\n" in result or "\x00" in result:
        raise GitPathError("GIT_REPOSITORY_REQUIRED")
    return result
