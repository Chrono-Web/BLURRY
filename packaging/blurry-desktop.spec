# ruff: noqa
# Native builds only: Windows x64 or Linux x86-64.
import sys
from PyInstaller.utils.hooks import collect_data_files, copy_metadata
ROOT = SPECPATH + "/.."
datas = collect_data_files("blurry_opsec")
datas += collect_data_files("PySide6", includes=["Qt/translations/qtbase_it.qm"])
for package in ("av", "numpy", "pillow", "pi-heif", "opencv-python-headless",
                "PySide6-Essentials", "shiboken6", "pyinstaller"):
    datas += copy_metadata(package)
datas += [(ROOT + "/licenses", "licenses"),
          (ROOT + "/LICENSE", "."), (ROOT + "/THIRD_PARTY_LICENSES.md", ".")]
# Both analyses include Qt: the single onedir tree shares compatible binaries.
a = Analysis([SPECPATH + "/desktop.py"], pathex=[ROOT + "/src"], datas=datas,
             excludes=["tkinter"], noarchive=False)
b = Analysis([SPECPATH + "/engine.py"], pathex=[ROOT + "/src"],
             datas=collect_data_files("blurry_opsec"), excludes=["tkinter"], noarchive=False)
gui = EXE(PYZ(a.pure), a.scripts, [], exclude_binaries=True,
          name="Blurry", console=False, icon=ROOT + "/docs/icona.png")
engine = EXE(PYZ(b.pure), b.scripts, [], exclude_binaries=True,
             name="blurry-engine", console=True)
coll = COLLECT(gui, engine, a.binaries, a.datas, b.binaries, b.datas, name="Blurry")
