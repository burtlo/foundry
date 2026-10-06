"""Unit tests for verify.code_review steward context."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.context import assemble_context
from foundry_cli.render import render_context_markdown
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT


def test_verify_code_review_context_engine_owned_without_instructions(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    snapshot = {
        "run_id": "00000000-0000-4000-8000-000000000099",
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
    assert "## Verify code review" in markdown
    assert "run advance" in markdown
    assert "verify.code_review.gate" in markdown
    assert "## Instructions" not in markdown
