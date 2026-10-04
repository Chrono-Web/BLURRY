"""Development only: open the app and restart it whenever its sources change.

    .venv/bin/python scripts/dev.py          macOS: the SwiftUI app (macos/), rebuilt on change
    .venv/bin/python scripts/dev.py --qt     the Qt app (Windows and Linux)

The Swift app gets the engine from this interpreter (BLURRY_PYTHON). Standard
library only (polling), so it adds no dependency. Not part of the package.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MACOS = ROOT / "macos"
APP = MACOS / ".build" / "dev" / "Blurry.app"
POLL = 0.4
SETTLE = 0.3  # editors often write a file in more than one step


def watched(mac: bool) -> list[Path]:
    roots = [ROOT / "src"]
    if mac:
        roots += [MACOS / "Sources", MACOS / "Package.swift", MACOS / "Info.plist"]
    return roots


def snapshot(roots: list[Path]) -> dict[Path, float]:
    files: list[Path] = []
    for r in roots:
        files += [r] if r.is_file() else list(r.rglob("*"))
    return {
        p: p.stat().st_mtime
        for p in files
        if p.is_file() and "__pycache__" not in p.parts and p.suffix not in {".pyc", ""}
    }


def build_mac() -> bool:
    print("[dev] compilo l'app Swift…", flush=True)
    if subprocess.run(["swift", "build", "--package-path", str(MACOS)]).returncode != 0:  # noqa: S603, S607
        return False
    binary = subprocess.run(  # noqa: S603
        ["swift", "build", "--package-path", str(MACOS), "--show-bin-path"],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    # A minimal bundle, so the app has its identity (com.chronocol.blurry) and a Dock icon.
    contents = APP / "Contents"
    (contents / "MacOS").mkdir(parents=True, exist_ok=True)
    shutil.copy2(MACOS / "Info.plist", contents / "Info.plist")
    (contents / "Resources").mkdir(exist_ok=True)
    shutil.copy2(MACOS / "Blurry.icns", contents / "Resources" / "Blurry.icns")
    shutil.copy2(Path(binary) / "Blurry", contents / "MacOS" / "Blurry")
    return True


def start(mac: bool) -> subprocess.Popen | None:
    if mac:
        if not build_mac():
            return None
        print("[dev] avvio dell'app", flush=True)
        env = {**os.environ, "BLURRY_PYTHON": sys.executable}
        return subprocess.Popen([str(APP / "Contents" / "MacOS" / "Blurry")], env=env)  # noqa: S603
    print("[dev] avvio dell'app", flush=True)
    code = "from blurry_opsec.__main__ import gui_main; gui_main()"
    return subprocess.Popen([sys.executable, "-c", code], cwd=ROOT)  # noqa: S603


def stop(proc: subprocess.Popen | None) -> None:
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def main() -> int:
    mac = sys.platform == "darwin" and "--qt" not in sys.argv[1:]
    roots = watched(mac)
    state = snapshot(roots)
    proc = start(mac)
    reported = False
    try:
        while True:
            time.sleep(POLL)
            current = snapshot(roots)
            if current != state:
                time.sleep(SETTLE)
                current = snapshot(roots)
                changed = sorted(
                    str(p.relative_to(ROOT))
                    for p in current.keys() | state.keys()
                    if current.get(p) != state.get(p)
                )
                state = current
                print(f"[dev] modificato: {', '.join(changed)} -> riavvio", flush=True)
                stop(proc)
                proc = start(mac)
                reported = False
            elif proc is None and not reported:
                print("[dev] compilazione fallita; attendo la prossima modifica", flush=True)
                reported = True
            elif proc is not None and proc.poll() not in (None, 0) and not reported:
                # Crashed: wait for the next save instead of looping.
                print(
                    f"[dev] l'app è uscita con codice {proc.returncode}; "
                    "attendo la prossima modifica",
                    flush=True,
                )
                reported = True
    except KeyboardInterrupt:
        pass
    finally:
        stop(proc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
