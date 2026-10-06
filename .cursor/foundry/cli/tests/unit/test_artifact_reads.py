"""Unit tests for nearest-sealed-ancestor artifact resolution."""

from __future__ import annotations

import json
from pathlib import Path

from foundry_cli.artifact_reads import (
    ancestor_visit_ids_nearest_first,
    parse_qualified_artifact_ref,
    resolve_nearest_sealed_ancestor_artifact,
    resolve_reads_artifacts,
)
from foundry_cli.context import assemble_context
from foundry_cli.registry import load_registry
from tests.unit.constants import IMPLEMENTATION_FLOW


def test_parse_qualified_artifact_ref() -> None:
    assert parse_qualified_artifact_ref("shape.present.presentation") == (
        "shape.present",
        "presentation",
    )
    assert parse_qualified_artifact_ref("shape.intake.ticket") == ("shape.intake", "ticket")


def test_ancestor_visit_ids_nearest_first_present_gate_fixture(bundle: Path) -> None:
    fixture = (
        bundle
        / "fixtures"
        / "runs"
        / "porcelain-0007-v005-present-gate"
        / "snapshot.json"
    )
    snapshot = json.loads(fixture.read_text(encoding="utf-8"))
    assert ancestor_visit_ids_nearest_first(snapshot, "v-005") == [
        "v-004",
        "v-003",
        "v-002",
        "v-001",
    ]


def test_resolve_nearest_sealed_ancestor_presentation(bundle: Path, tmp_path: Path) -> None:
    fixture_dir = bundle / "fixtures" / "runs" / "porcelain-0007-v005-present-gate"
    run_dir = tmp_path / "run"
    for rel in ("snapshot.json", "artifacts/v-004/presentation.md"):
        src = fixture_dir / rel
        dest = run_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())

    snapshot = json.loads((run_dir / "snapshot.json").read_text(encoding="utf-8"))
    resolved = resolve_nearest_sealed_ancestor_artifact(
        snapshot,
        qualified_ref="shape.present.presentation",
        from_visit_id="v-005",
        run_dir=run_dir,
    )
    assert resolved is not None
    assert resolved["resolved_uri"] == "run:artifacts/v-004/presentation.md"
    assert resolved["resolved_path"].endswith("artifacts/v-004/presentation.md")


def test_assemble_context_resolves_present_gate_artifact_reads(
    bundle: Path, tmp_path: Path
) -> None:
    fixture_dir = bundle / "fixtures" / "runs" / "porcelain-0007-v005-present-gate"
    run_dir = tmp_path / "run"
    for rel in ("snapshot.json", "artifacts/v-004/presentation.md"):
        src = fixture_dir / rel
        dest = run_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())

    snapshot = json.loads((run_dir / "snapshot.json").read_text(encoding="utf-8"))
    _, flow = load_registry(bundle, flow_id=IMPLEMENTATION_FLOW)
    visit = snapshot["active_visit"]
    context = assemble_context(
        snapshot=snapshot,
        visit=visit,
        flow=flow,
        foundry_bundle=bundle,
        run_dir=run_dir,
        workspace=tmp_path,
    )
    artifacts = context["reads"]["artifacts"]
    assert artifacts[0]["artifact"] == "shape.present.presentation"
    assert artifacts[0]["resolved_uri"] == "run:artifacts/v-004/presentation.md"
    assert "presentation.md" in artifacts[0]["resolved_path"]


def test_resolve_reads_artifacts_state_fallback_when_no_ledger_match(
    tmp_path: Path,
) -> None:
    snapshot: dict = {
        "ledger": [],
        "visits": [],
        "state": {"presentation_artifact_path": "run:artifacts/v-004/presentation.md"},
    }
    run_dir = tmp_path / "run"
    (run_dir / "artifacts" / "v-004").mkdir(parents=True)
    (run_dir / "artifacts" / "v-004" / "presentation.md").write_text("# fallback", encoding="utf-8")

    artifacts = resolve_reads_artifacts(
        [{"artifact": "shape.present.presentation", "from": "nearest_sealed_ancestor"}],
        snapshot=snapshot,
        visit_id="v-005",
        run_dir=run_dir,
        state=snapshot["state"],
    )
    assert artifacts[0]["resolved_uri"] == "run:artifacts/v-004/presentation.md"


def test_resolve_reads_artifacts_plan_path_fallback_when_no_ledger_match(
    tmp_path: Path,
) -> None:
    snapshot: dict = {
        "ledger": [],
        "visits": [],
        "state": {"plan_path": "run:artifacts/v-006/plan.md"},
    }
    run_dir = tmp_path / "run"
    (run_dir / "artifacts" / "v-006").mkdir(parents=True)
    (run_dir / "artifacts" / "v-006" / "plan.md").write_text("# plan fallback", encoding="utf-8")

    artifacts = resolve_reads_artifacts(
        [{"artifact": "shape.record.plan", "from": "nearest_sealed_ancestor"}],
        snapshot=snapshot,
        visit_id="v-007",
        run_dir=run_dir,
        state=snapshot["state"],
    )
    assert artifacts[0]["resolved_uri"] == "run:artifacts/v-006/plan.md"
    assert "plan.md" in artifacts[0]["resolved_path"]


def test_assemble_context_resolves_record_gate_artifact_reads(
    bundle: Path, tmp_path: Path
) -> None:
    fixture_dir = bundle / "fixtures" / "runs" / "porcelain-0007-v007-record-gate"
    run_dir = tmp_path / "run"
    for rel in ("snapshot.json", "artifacts/v-006/plan.md"):
        src = fixture_dir / rel
        dest = run_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())

    snapshot = json.loads((run_dir / "snapshot.json").read_text(encoding="utf-8"))
    _, flow = load_registry(bundle, flow_id=IMPLEMENTATION_FLOW)
    visit = snapshot["active_visit"]
    context = assemble_context(
        snapshot=snapshot,
        visit=visit,
        flow=flow,
        foundry_bundle=bundle,
        run_dir=run_dir,
        workspace=tmp_path,
    )
    artifacts = context["reads"]["artifacts"]
    assert artifacts[0]["artifact"] == "shape.record.plan"
    assert artifacts[0]["resolved_uri"] == "run:artifacts/v-006/plan.md"
    assert "plan.md" in artifacts[0]["resolved_path"]
