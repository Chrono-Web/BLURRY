"""Windowed launcher; workers use the separate console engine executable."""

import sys

from blurry_opsec.__main__ import gui_main

if __name__ == "__main__":
    if sys.argv[1:2] == ["__smoke-test"]:
        from blurry_opsec.gui.smoke import main

        sys.exit(main(sys.argv[2]))
    sys.exit(gui_main([]))
