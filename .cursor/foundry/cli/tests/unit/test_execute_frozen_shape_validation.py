"""Unit tests for execute intake frozen shape validation."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.engine.execute_step_executor import _validate_frozen_shape

AC_MISMATCH = "plan.md does not contain approved acceptance criteria text"


def _minimal_snapshot(plan_uri: str, approved_ac: str) -> dict:
    return {
        "run_id": "test-run",
        "state": {
            "approved_ac": approved_ac,
            "approved_ac_version": 1,
            "approved_ac_digest": "deadbeef",
            "plan_path": plan_uri,
        },
    }


def test_validate_frozen_shape_ignores_extra_blank_lines_in_plan(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "test-run"
    artifacts = run_dir / "artifacts" / "v-001"
    artifacts.mkdir(parents=True)
    approved_ac = "First criterion.\nSecond criterion."
    plan_body = "## Acceptance criteria\n\nFirst criterion.\n\nSecond criterion.\n"
    (artifacts / "plan.md").write_text(plan_body, encoding="utf-8")
    snapshot = _minimal_snapshot("run:artifacts/v-001/plan.md", approved_ac)

    findings = _validate_frozen_shape(snapshot, run_dir)

    assert AC_MISMATCH not in findings


def test_validate_frozen_shape_rejects_missing_ac_content(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "test-run"
    artifacts = run_dir / "artifacts" / "v-001"
    artifacts.mkdir(parents=True)
    (artifacts / "plan.md").write_text("## Plan\n\nDifferent scope entirely.\n", encoding="utf-8")
    snapshot = _minimal_snapshot("run:artifacts/v-001/plan.md", "Required criterion one.\nTwo.")

    findings = _validate_frozen_shape(snapshot, run_dir)

    assert AC_MISMATCH in findings
