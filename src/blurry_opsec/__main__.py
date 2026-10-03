"""Entry point. Phase 0 skeleton: only --version for now."""

import sys

from blurry_opsec import __version__


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args in (["--version"], ["-V"]):
        print(f"blurry {__version__}")
        return 0
    print("blurry: not implemented yet (phase 0 skeleton)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
