"""Build native frozen apps, then a per-user installer. Use uv run --group packaging."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tarfile
from importlib.metadata import distributions
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args):
    subprocess.run(args, cwd=ROOT, check=True)  # noqa: S603


def main():
    if sys.platform not in ("win32", "linux") or platform.machine().lower() not in (
        "amd64",
        "x86_64",
    ):
        raise SystemExit("Build on Windows x64 or Linux x86-64; no cross-compilation.")
    import tomllib

    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "packaging/blurry-desktop.spec",
            "--noconfirm",
            "--distpath",
            "build/desktop-dist",
            "--workpath",
            "build/desktop-work",
        ]
    )
    app = ROOT / "build/desktop-dist/Blurry"
    shutil.copy2(ROOT / "docs/icona.png", app / "icon.png")
    # Record resolved native dependency versions, including licence texts from wheel metadata.
    manifest = [{"name": "Python", "version": platform.python_version()}]
    notices = app / "THIRD_PARTY"
    notices.mkdir(exist_ok=True)
    for dist in distributions():
        name = dist.metadata["Name"]
        manifest.append({"name": name, "version": dist.version})
        for file in dist.files or []:
            if ".dist-info/" in str(file) and any(
                word in str(file).lower() for word in ("license", "licence", "copying", "notice")
            ):
                src = Path(dist.locate_file(file))
                if src.is_file():
                    dest = notices / name / Path(*file.parts[1:])
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
    (app / "dependencies.json").write_text(
        json.dumps(sorted(manifest, key=lambda x: x["name"]), indent=2) + "\n"
    )
    out = ROOT / "build/desktop-packages"
    out.mkdir(exist_ok=True)
    if sys.platform == "win32":
        iscc = shutil.which("ISCC") or str(Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"))
        run([iscc, f"/DAppVersion={version}", "packaging/windows.iss"])
        package = out / f"Blurry-{version}-windows-x64-setup.exe"
    else:
        stage = ROOT / "build/linux-stage"
        if stage.exists():
            shutil.rmtree(stage)
        stage.mkdir()
        shutil.copytree(app, stage / "Blurry")
        for name in ("install.sh", "uninstall.sh"):
            shutil.copy2(ROOT / "packaging/linux" / name, stage / name)
            (stage / name).chmod(0o755)
        package = out / f"Blurry-{version}-linux-x86_64.tar.gz"
        with tarfile.open(package, "w:gz") as archive:
            archive.add(stage, arcname="Blurry-linux")
    checksum = hashlib.file_digest(package.open("rb"), "sha256").hexdigest()
    (out / (package.name + ".sha256")).write_text(f"{checksum}  {package.name}\n")
    print(package)


if __name__ == "__main__":
    main()
