"""Entry point. The network guard is installed before anything else is imported.

blurry                 opens the desktop app (if installed with the GUI)
blurry INPUT...        the command (see cli.py)
blurry __worker        hidden: the app's worker process (see worker.py)
"""

import sys

from blurry_opsec import netguard

netguard.install()

WORKER_ARG = "__worker"


def gui_available() -> bool:
    try:
        import PySide6.QtWidgets  # noqa: F401
    except ImportError:
        return False
    return True


def gui_main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args:
        return main(args)
    from blurry_opsec import tempfiles

    tempfiles.cleanup_stale()
    from blurry_opsec.gui.app import run

    return run()


def main(argv: list[str] | None = None) -> int:
    from blurry_opsec import tempfiles

    args = sys.argv[1:] if argv is None else argv
    if args[:1] == [WORKER_ARG]:
        from blurry_opsec import worker

        return worker.main()
    tempfiles.cleanup_stale()
    if not args and gui_available():
        from blurry_opsec.gui.app import run

        return run()
    from blurry_opsec import cli

    return cli.main(args)


if __name__ == "__main__":
    sys.exit(main())
