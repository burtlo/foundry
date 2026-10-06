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

STEP_STUB_FILES = (
    "execute-intake.md",
    "execute-branch.md",
    "execute-plan.md",
    "execute-build.md",
    "execute-test.md",
    "execute-commit.md",
    "verify-intake.md",
    "verify-acceptance.md",
    "verify-code-quality.md",
    "verify-code-review.md",
    "verify-complete.md",
    "deliver-stub.md",
)


def _bundle_with_step_stubs(tmp_path: Path) -> Path:
    import shutil

    dest = tmp_path / "bundle"
    shutil.copytree(FOUNDRY_ROOT, dest)
    steps = dest / "steps"
    steps.mkdir(exist_ok=True)
    for filename in STEP_STUB_FILES:
        (steps / filename).write_text("# workflow-02 placeholder\n", encoding="utf-8")
    return dest


def test_missing_registry_step_refs_lists_execute_verify_instructions(tmp_path: Path) -> None:
    import shutil

    bundle = tmp_path / "bundle-no-steps"
    shutil.copytree(FOUNDRY_ROOT, bundle)
    steps = bundle / "steps"
    if steps.is_dir():
        shutil.rmtree(steps)
    _, flow = load_registry(bundle, flow_id=IMPLEMENTATION_FLOW)
    missing = missing_registry_instruction_paths(flow, bundle)
    assert len(missing) == len(STEP_STUB_FILES)
    assert "registry:steps/execute-intake.md" in missing


def test_validate_registry_instruction_refs_fails_closed(tmp_path: Path) -> None:
    import shutil

    bundle = tmp_path / "bundle-no-steps"
    shutil.copytree(FOUNDRY_ROOT, bundle)
    steps = bundle / "steps"
    if steps.is_dir():
        shutil.rmtree(steps)
    _, flow = load_registry(bundle, flow_id=IMPLEMENTATION_FLOW)
    result = validate_registry_instruction_refs(flow, bundle)
    assert result["ok"] is False
    assert result["code"] == "REFERENCE_NOT_FOUND"
    assert result["missing"]


def test_validate_registry_instruction_refs_passes_when_steps_present(bundle: Path) -> None:
    _, flow = load_registry(bundle, flow_id=IMPLEMENTATION_FLOW)
    result = validate_registry_instruction_refs(flow, bundle)
    assert result["ok"] is True


def test_build_catalog_succeeds_when_step_files_present(tmp_path: Path) -> None:
    bundle = _bundle_with_step_stubs(tmp_path)
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
