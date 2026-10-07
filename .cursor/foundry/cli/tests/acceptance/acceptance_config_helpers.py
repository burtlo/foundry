"""Temporary registry bundle trees for config and archive acceptance scenarios."""

from __future__ import annotations

import shutil
from pathlib import Path

from tests.conftest import FOUNDRY_ROOT


def prepare_bundle_target(bundle_target: Path) -> None:
    bundle_target.mkdir(parents=True, exist_ok=True)
    flows_dest = bundle_target / "flows"
    flows_dest.mkdir(parents=True, exist_ok=True)
    implementation_src = FOUNDRY_ROOT / "flows" / "implementation"
    if implementation_src.is_dir():
        shutil.copytree(implementation_src, flows_dest / "implementation", dirs_exist_ok=True)
    else:
        (flows_dest / "implementation" / "registry.yaml").parent.mkdir(parents=True, exist_ok=True)
        (flows_dest / "implementation" / "registry.yaml").write_text("flow: test\n", encoding="utf-8")
    nodes_src = FOUNDRY_ROOT / "nodes"
    if nodes_src.is_dir():
        shutil.copytree(nodes_src, bundle_target / "nodes", dirs_exist_ok=True)
    schemas_dest = bundle_target / "schemas"
    if schemas_dest.exists():
        shutil.rmtree(schemas_dest)
    shutil.copytree(FOUNDRY_ROOT / "schemas", schemas_dest)
    cli_dir = bundle_target / "cli"
    cli_dir.mkdir(parents=True, exist_ok=True)
    foundry_sh = FOUNDRY_ROOT / "cli" / "foundry.sh"
    if foundry_sh.is_file():
        shutil.copy2(foundry_sh, cli_dir / "foundry.sh")
    else:
        (cli_dir / "foundry.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    steps_src = FOUNDRY_ROOT / "steps"
    if steps_src.is_dir():
        steps_dest = bundle_target / "steps"
        if steps_dest.exists():
            shutil.rmtree(steps_dest)
        shutil.copytree(steps_src, steps_dest)
