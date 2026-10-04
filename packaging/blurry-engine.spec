# PyInstaller spec: the engine for the macOS app, as a folder (onedir).
#
#   pyinstaller packaging/blurry-engine.spec --distpath build/engine-dist --workpath build/engine-work
#
# Built in an environment without the "gui" extra (scripts/crea-app.sh): the
# Mac interface is SwiftUI, so Qt must not end up here. Data files (YuNet model
# and its licence, fonts for the watermark) come from the package itself.
# ruff: noqa

from PyInstaller.utils.hooks import collect_data_files

ROOT = SPECPATH + "/.."

a = Analysis(
    [SPECPATH + "/engine.py"],
    pathex=[ROOT + "/src"],
    datas=collect_data_files("blurry_opsec"),
    excludes=[
        # The Qt interface and anything that could pull it in.
        "PySide6",
        "shiboken6",
        "blurry_opsec.gui",
        "tkinter",
        # Network servers and clients the engine never uses (R1). The socket
        # module itself stays: the standard library imports it, and netguard
        # blocks it at run time.
        "ssl",
        "ftplib",
        "smtplib",
        "imaplib",
        "poplib",
        "xmlrpc",
        "http.server",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="blurry",
    console=True,
    target_arch="arm64",
    codesign_identity=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="engine")
