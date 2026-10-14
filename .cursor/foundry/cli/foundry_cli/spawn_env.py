"""Environment for detached Foundry child processes (host, judgment bridge)."""

from __future__ import annotations

import os
from pathlib import Path


def cli_package_root(bundle: Path) -> Path:
    """Directory that must be on PYTHONPATH for ``python -m foundry_cli.*`` imports."""
    return (bundle / "cli").resolve()


def child_process_env(
    bundle: Path,
    *,
    base: dict[str, str] | None = None,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build a full env dict with PYTHONPATH set for the registry CLI bundle."""
    env = dict(base if base is not None else os.environ)
    root = str(cli_package_root(bundle))
    existing = env.get("PYTHONPATH", "")
    if existing:
        parts = [p for p in existing.split(os.pathsep) if p]
        if root not in parts:
            env["PYTHONPATH"] = os.pathsep.join([root, existing])
    else:
        env["PYTHONPATH"] = root
    if extra:
        env.update(extra)
    return env
