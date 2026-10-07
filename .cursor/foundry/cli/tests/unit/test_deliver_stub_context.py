"""Unit tests for deliver.stub steward context."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.render import render_context_markdown
from tests.unit.constants import TEST_RUN_UUID
from tests.unit.context_test_helpers import assemble_step_context


def test_deliver_stub_context_engine_owned_without_instructions(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    snapshot = {
        "run_id": TEST_RUN_UUID,
        "config": {},
        "state": {
            "verified_at": "2026-01-01T00:00:00Z",
            "feature_branch": "feature/demo",
            "final_commit_sha": "abc123",
        },
    }
    visit = {
        "id": "v-ds-ctx",
        "node_id": "deliver.stub",
        "kind": "step",
        "lifecycle": "opened",
    }
    context = assemble_step_context(run_dir, snapshot, visit)
    assert "instructions" not in context
    assert "worker" not in context
    allow_cli = (context.get("allow") or {}).get("cli") or []
    assert allow_cli == ["transition"]
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Deliver (terminal)" in markdown
    assert "run advance" in markdown
    assert "deliver_handoff_message" in markdown
    assert "## Instructions" not in markdown
