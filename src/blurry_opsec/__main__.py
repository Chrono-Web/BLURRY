"""Entry point. The network guard is installed before anything else is imported."""

import sys

from blurry_opsec import netguard

netguard.install()


def main(argv: list[str] | None = None) -> int:
    from blurry_opsec import tempfiles

    tempfiles.cleanup_stale()
    args = sys.argv[1:] if argv is None else argv
    from blurry_opsec import cli

    return cli.main(args)


if __name__ == "__main__":
    sys.exit(main())
