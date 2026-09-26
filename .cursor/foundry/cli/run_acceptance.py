#!/usr/bin/env python3
"""Run Foundry CLI acceptance tests via the dev shortcut."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python run_acceptance.py` without installing the package.
CLI_DIR = Path(__file__).resolve().parent
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

from foundry_cli.dev import run_acceptance_tests  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Foundry acceptance tests (alias for foundry dev acceptance)",
    )
    parser.add_argument(
        "pytest_args",
        nargs="*",
        help="Additional arguments passed to pytest",
    )
    parser.add_argument("--quiet", action="store_true", help="Reduce pytest verbosity")
    args = parser.parse_args(argv)

    result = run_acceptance_tests(quiet=args.quiet, extra_argv=list(args.pytest_args))
    if not result.get("ok"):
        if result.get("stdout"):
            print(result["stdout"], end="")
        if result.get("stderr"):
            print(result["stderr"], end="", file=sys.stderr)
    return int(result.get("exit_code", 1))


if __name__ == "__main__":
    sys.exit(main())
