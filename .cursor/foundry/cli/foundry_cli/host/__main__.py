"""Background entry: python -m foundry_cli.host"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from foundry_cli.host.server import run_host_process


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="foundry-host")
    parser.add_argument("--workspace", default=".", help="Application workspace root")
    parser.add_argument("--registry", help="Foundry bundle root override")
    args = parser.parse_args(argv)
    registry = Path(args.registry).resolve() if args.registry else None
    return run_host_process(Path(args.workspace).resolve(), registry)


if __name__ == "__main__":
    sys.exit(main())
