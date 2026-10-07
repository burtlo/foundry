"""Unit tests for verify.code_review steward context."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.render import render_context_markdown
from tests.unit.constants import TEST_RUN_UUID
from tests.unit.context_test_helpers import assemble_step_context


def test_verify_code_review_context_engine_owned_without_instructions(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    snapshot = {
        "run_id": TEST_RUN_UUID,
        "config": {"review": {"enabled": True}},
        "state": {
            "feature_branch": "feature/demo",
            "verify_findings": {"gate_decision": "pass"},
            "approved_ac": "User can log in",
        },
    }
    visit = {
        "id": "v-cr-ctx",
        "node_id": "verify.code_review",
        "kind": "step",
        "lifecycle": "opened",
    }
    context = assemble_step_context(run_dir, snapshot, visit)
    assert "instructions" not in context
    assert "worker" not in context
    allow_cli = (context.get("allow") or {}).get("cli") or []
    assert allow_cli == ["transition"]
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Verify code review" in markdown
    assert "run advance" in markdown
    assert "verify.code_review.gate" in markdown
    assert "## Instructions" not in markdown
