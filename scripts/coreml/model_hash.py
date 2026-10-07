"""SHA-256 of a compiled Core ML model folder, as BlurryKit's Model.swift computes it.

For every file, in order of relative path (as a POSIX string): the path, a zero
byte, the size as 8 bytes little-endian, the contents.
"""

import hashlib
import sys
from pathlib import Path


def model_hash(folder: Path) -> str:
    h = hashlib.sha256()
    files = [p for p in folder.rglob("*") if p.is_file()]
    for path in sorted(files, key=lambda p: p.relative_to(folder).as_posix()):
        data = path.read_bytes()
        h.update(path.relative_to(folder).as_posix().encode() + b"\0")
        h.update(len(data).to_bytes(8, "little"))
        h.update(data)
    return h.hexdigest()


if __name__ == "__main__":
    print(model_hash(Path(sys.argv[1])))
