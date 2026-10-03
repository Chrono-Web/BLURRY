"""Private temporary folders and their cleanup.

Blurry processes images in memory and writes videos straight to the
destination, so it normally needs no temporary folder. When one is needed it is
created with mode 0700, removed at exit, and leftovers of a crash are removed
on the next start.
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
import time
from pathlib import Path

PREFIX = "blurry-"
_PID_FILE = ".pid"
# Where liveness cannot be checked safely (Windows), only old leftovers go.
_STALE_AGE_S = 24 * 3600


def make_private_dir() -> Path:
    path = Path(tempfile.mkdtemp(prefix=PREFIX))
    (path / _PID_FILE).write_text(str(os.getpid()))
    atexit.register(shutil.rmtree, path, ignore_errors=True)
    return path


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _is_stale(path: Path) -> bool:
    if os.name == "posix":
        try:
            pid = int((path / _PID_FILE).read_text().strip())
        except (OSError, ValueError):
            pid = 0
        if pid > 0:
            return pid != os.getpid() and not _pid_alive(pid)
    # No pid file, or Windows (where os.kill would terminate the process): age only.
    try:
        return time.time() - path.stat().st_mtime > _STALE_AGE_S
    except OSError:
        return False


def cleanup_stale() -> int:
    """Remove `blurry-*` folders left in the temp dir by a crashed run."""
    removed = 0
    root = Path(tempfile.gettempdir())
    try:
        entries = list(root.iterdir())
    except OSError:
        return 0
    for entry in entries:
        if not entry.name.startswith(PREFIX) or entry.is_symlink() or not entry.is_dir():
            continue
        if hasattr(os, "getuid") and entry.stat().st_uid != os.getuid():
            continue
        if _is_stale(entry):
            shutil.rmtree(entry, ignore_errors=True)
            removed += 1
    return removed
