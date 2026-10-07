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
    parser.add_argument(
        "--auto-advance",
        action="store_true",
        help="Background loop: advance runs without human waits",
    )
    parser.add_argument(
        "--auto-advance-interval",
        type=float,
        default=2.0,
        help="Seconds between auto-advance scans (default: 2)",
    )
    args = parser.parse_args(argv)
    registry = Path(args.registry).resolve() if args.registry else None
    return run_host_process(
        Path(args.workspace).resolve(),
        registry,
        auto_advance=bool(args.auto_advance),
        auto_advance_interval=float(args.auto_advance_interval),
    )


if __name__ == "__main__":
    sys.exit(main())
