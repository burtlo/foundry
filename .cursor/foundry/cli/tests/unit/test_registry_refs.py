"""Unit tests for registry step instruction validation."""

from __future__ import annotations

import os
from pathlib import Path

from foundry_cli.catalog import build_catalog
from foundry_cli.engine.registry_refs import (
    missing_registry_instruction_paths,
    validate_registry_instruction_refs,
)
from foundry_cli.foundry_config import validate_foundry_config
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import IMPLEMENTATION_FLOW


def _flow_with_step_instruction(path: str) -> dict:
    return {
        "nodes": [
            {
                "id": "demo.step.ref",
                "kind": "step",
                "instructions": path,
            }
        ]
    }


def test_missing_registry_step_refs_lists_unknown_step_instructions(tmp_path: Path) -> None:
    import shutil

    bundle = tmp_path / "bundle-no-steps"
    shutil.copytree(FOUNDRY_ROOT, bundle)
    steps = bundle / "steps"
    if steps.is_dir():
        shutil.rmtree(steps)
    flow = _flow_with_step_instruction("registry:steps/deliver-stub.md")
    missing = missing_registry_instruction_paths(flow, bundle)
    assert missing == ["registry:steps/deliver-stub.md"]


def test_validate_registry_instruction_refs_fails_closed(tmp_path: Path) -> None:
    import shutil

    bundle = tmp_path / "bundle-no-steps"
    shutil.copytree(FOUNDRY_ROOT, bundle)
    steps = bundle / "steps"
    if steps.is_dir():
        shutil.rmtree(steps)
    flow = _flow_with_step_instruction("registry:steps/missing-step.md")
    result = validate_registry_instruction_refs(flow, bundle)
    assert result["ok"] is False
    assert result["code"] == "REFERENCE_NOT_FOUND"
    assert result["missing"]


def test_validate_registry_instruction_refs_passes_implementation_flow(bundle: Path) -> None:
    _, flow = load_registry(bundle, flow_id=IMPLEMENTATION_FLOW)
    result = validate_registry_instruction_refs(flow, bundle)
    assert result["ok"] is True


def test_build_catalog_succeeds_without_registry_step_refs(tmp_path: Path) -> None:
    import shutil

    bundle = tmp_path / "bundle"
    shutil.copytree(FOUNDRY_ROOT, bundle)
    output = tmp_path / "out"
    result = build_catalog(foundry_bundle=bundle, flow_id=IMPLEMENTATION_FLOW, output_dir=output)
    assert result["ok"] is True


def test_validate_foundry_config_reports_missing_step_refs(tmp_path: Path, monkeypatch) -> None:
    import shutil
    import yaml

    monkeypatch.delenv("FOUNDRY_REGISTRY", raising=False)
    workspace = tmp_path / "app"
    workspace.mkdir()
    bundle = tmp_path / "registry"
    shutil.copytree(FOUNDRY_ROOT, bundle)
    steps = bundle / "steps"
    if steps.is_dir():
        shutil.rmtree(steps)
    flow_path = bundle / "flows" / "implementation" / "registry.yaml"
    document = yaml.safe_load(flow_path.read_text(encoding="utf-8"))
    flow = document["flow"]
    flow["nodes"].append(
        {
            "id": "demo.bad.step.ref",
            "kind": "step",
            "title": "Demo",
            "produces": {"artifacts": []},
            "instructions": "registry:steps/missing-step.md",
        }
    )
    flow_path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    config_dir = workspace / ".foundry"
    config_dir.mkdir(parents=True)
    registry_ref = Path(os.path.relpath(bundle, workspace)).as_posix()  # type: ignore[name-defined]
    (config_dir / "foundry.yaml").write_text(
        yaml.safe_dump({"schema_version": 1, "registry": registry_ref}, sort_keys=False),
        encoding="utf-8",
    )

    result = validate_foundry_config(workspace)
    assert result["ok"] is False
    assert any("REFERENCE_NOT_FOUND" in err for err in result["errors"])
