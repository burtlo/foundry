"""Unit tests for verify.acceptance steward context."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.context import assemble_context
from foundry_cli.render import render_context_markdown
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT


def test_verify_acceptance_context_engine_owned_without_instructions(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    snapshot = {
        "run_id": "00000000-0000-4000-8000-000000000099",
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
    _, flow = load_registry(FOUNDRY_ROOT)
    context = assemble_context(
        snapshot=snapshot,
        visit=visit,
        flow=flow,
        foundry_bundle=FOUNDRY_ROOT,
        run_dir=run_dir,
    )
    assert "instructions" not in context
    assert "worker" not in context
    allow_cli = (context.get("allow") or {}).get("cli") or []
    assert allow_cli == ["transition"]
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Verify acceptance" in markdown
    assert "run advance" in markdown
    assert "implementation-validator" in markdown
    assert "## Instructions" not in markdown
