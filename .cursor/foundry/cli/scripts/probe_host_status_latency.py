#!/usr/bin/env python3
"""Measure wall time for ``foundry host status`` (D11 latency probe).

Run from an application workspace (or pass --workspace). Three scenarios from
docs/plans/foundry-up/probes/host-status-latency.md:

  1. bridge absent / host down — default when nothing is running
  2. bridge + host ready — after ``foundry up`` in the same workspace
  3. stale discovery — corrupt or truncate host state while PID is dead

This script only times the CLI call in the *current* environment; prepare
each scenario manually, then run with --scenario <name> to label output.

Provisional caps: <=3s (absent), <=5s (ready), <=8s (stale).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[1]
FOUNDRY_CLI = CLI_DIR / "foundry.py"

CAPS_SECONDS = {
    "absent": 3.0,
    "ready": 5.0,
    "stale": 8.0,
}


def _run_status(workspace: Path, registry: Path | None) -> tuple[float, int]:
    argv = [
        sys.executable,
        str(FOUNDRY_CLI),
        "--json",
        "--workspace",
        str(workspace.resolve()),
    ]
    if registry is not None:
        argv.extend(["--registry", str(registry.resolve())])
    argv.extend(["host", "status"])

    start = time.perf_counter()
    proc = subprocess.run(argv, capture_output=True, text=True, check=False)
    elapsed = time.perf_counter() - start
    return elapsed, proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Application workspace (default: cwd)",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=None,
        help="Foundry registry bundle (optional if .foundry/foundry.yaml exists)",
    )
    parser.add_argument(
        "--scenario",
        choices=sorted(CAPS_SECONDS),
        default="absent",
        help="Label for the prepared environment (default: absent)",
    )
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        print(f"workspace not found: {workspace}", file=sys.stderr)
        return 2

    elapsed, code = _run_status(workspace, args.registry)
    cap = CAPS_SECONDS[args.scenario]
    status = "ok" if elapsed <= cap else "SLOW"
    print(
        f"scenario={args.scenario} elapsed_s={elapsed:.3f} cap_s={cap} "
        f"exit_code={code} {status}"
    )
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
