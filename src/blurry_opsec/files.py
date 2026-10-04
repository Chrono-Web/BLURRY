"""Input checks and safe output writing.

Outputs are written as `.<name>.blurry-partial` next to their destination and
renamed at the end. No existing file is ever overwritten: if the target name is
taken, a numbered name is used instead.
"""

from __future__ import annotations

import contextlib
import os
import stat
from collections.abc import Iterator
from pathlib import Path

PARTIAL_SUFFIX = ".blurry-partial"


class InputError(ValueError):
    """The input cannot be processed. Messages never contain paths."""


def check_regular_file(path: Path, max_bytes: int) -> os.stat_result:
    text = str(path)
    if "://" in text:
        raise InputError("URLs are not accepted: Blurry only reads local files")
    try:
        st = os.stat(path)
    except FileNotFoundError as exc:
        raise InputError("file not found (check the name and the folder)") from exc
    except PermissionError as exc:
        raise InputError("permission denied: the file cannot be read") from exc
    except OSError as exc:
        raise InputError("the file cannot be read") from exc
    if not stat.S_ISREG(st.st_mode):
        raise InputError("not a regular file")
    if st.st_size == 0:
        raise InputError("empty file")
    if st.st_size > max_bytes:
        raise InputError(f"file too large (limit {max_bytes // (1024 * 1024)} MB)")
    return st


def output_path(src: Path, out_dir: Path | None, ext: str) -> Path:
    """`<name>.blurry.<ext>` in out_dir (default: next to the source), never an
    existing file and never the source itself."""
    directory = out_dir if out_dir is not None else src.parent
    if not directory.is_dir():
        raise InputError("output folder does not exist")
    stem = src.stem
    candidate = directory / f"{stem}.blurry.{ext}"
    n = 2
    while candidate.exists() or candidate.is_symlink():
        candidate = directory / f"{stem}.blurry-{n}.{ext}"
        n += 1
    if _same_file(candidate, src):
        raise InputError("output would overwrite the input")
    return candidate


def chosen_output(src: Path, final: Path) -> Path:
    """An output path the user chose in a save dialog (which has already asked
    before replacing an existing file). Never the source itself."""
    if not final.parent.is_dir():
        raise InputError("output folder does not exist")
    if _same_file(final, src):
        raise InputError("output would overwrite the input")
    return final


def _same_file(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve() or (a.exists() and os.path.samefile(a, b))
    except OSError:
        return False


@contextlib.contextmanager
def partial_output(final: Path, replace: bool = False) -> Iterator[Path]:
    """Yield a private partial path in the destination folder; on success it is
    renamed to `final`, on any failure it is removed. An existing `final` is
    replaced only with `replace` (the user confirmed it in a save dialog)."""
    partial = final.with_name(f".{final.name}{PARTIAL_SUFFIX}")
    with contextlib.suppress(FileNotFoundError):
        partial.unlink()  # stale leftover of a crash with the same name
    fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    os.close(fd)
    try:
        yield partial
        if not replace and (final.exists() or final.is_symlink()):
            raise InputError("output name was taken while processing")
        os.replace(partial, final)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            partial.unlink()
        raise
