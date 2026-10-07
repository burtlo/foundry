"""Unit tests for verify.acceptance steward context."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.render import render_context_markdown
from tests.unit.constants import TEST_RUN_UUID
from tests.unit.context_test_helpers import assemble_step_context


def test_verify_acceptance_context_engine_owned_without_instructions(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    snapshot = {
        "run_id": TEST_RUN_UUID,
        "state": {
            "approved_ac": "- User can log in",
            "final_commit_sha": "abc123",
            "last_test_exit_code": 0,
        },
    }
    visit = {
        "id": "v-acc-ctx",
        "node_id": "verify.acceptance",
        "kind": "step",
        "lifecycle": "opened",
    }
    context = assemble_step_context(run_dir, snapshot, visit)
    assert "instructions" not in context
    assert "worker" not in context
    allow_cli = (context.get("allow") or {}).get("cli") or []
    assert allow_cli == ["transition"]
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Verify acceptance" in markdown
    assert "run advance" in markdown
    assert "implementation-validator" in markdown
    assert "## Instructions" not in markdown
