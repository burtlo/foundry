"""Unit tests for verify.acceptance steward context."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.render import render_context_markdown
from tests.unit.constants import TEST_RUN_UUID
from tests.unit.context_test_helpers import assemble_step_context


def test_verify_acceptance_context_agent_judgment_with_instructions(tmp_path: Path) -> None:
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
    assert isinstance(context.get("instructions"), str)
    assert "judgment" in str(context.get("instructions_path") or "")
    allow_cli = (context.get("allow") or {}).get("cli") or []
    assert "run.agent.submit" in allow_cli
    instructions_text = Path(str(context.get("instructions_path"))).read_text(encoding="utf-8")
    assert "gate_decision" in instructions_text
    markdown = render_context_markdown(context, instructions_text, operations_text="")
    assert "## Judgment" in markdown
    assert "verify.acceptance.gate" in instructions_text
