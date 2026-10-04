"""Entry point of the frozen engine shipped inside Blurry.app (see blurry-engine.spec).

The same `main` as the `blurry` command: the network guard is installed by
blurry_opsec.__main__ before anything else is imported.
"""

import sys

from blurry_opsec.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
