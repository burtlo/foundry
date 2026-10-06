"""Unit tests for verify.complete.gate steward context."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.context import assemble_context
from foundry_cli.render import render_context_markdown
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT


def test_verify_complete_gate_context_minimal_state_reads(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    snapshot = {
        "run_id": "00000000-0000-4000-8000-0000000000aa",
        "config": {},
        "state": {
            "verified_at": "2026-10-06T18:00:00Z",
            "feature_branch": "foundry/demo",
            "final_commit_sha": "abc123def",
            "approved_ac": "should-not-appear-in-reads",
        },
    }
    visit = {
        "id": "v-vcg-ctx",
        "node_id": "verify.complete.gate",
        "kind": "gate",
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
    state = (context.get("reads") or {}).get("state") or {}
    assert set(state.keys()) == {"verified_at", "feature_branch", "final_commit_sha"}
    assert state["verified_at"] == "2026-10-06T18:00:00Z"
    assert "approved_ac" not in state
    artifacts = (context.get("reads") or {}).get("artifacts") or []
    assert artifacts == []
    allow_user = (context.get("allow") or {}).get("user") or {}
    assert allow_user.get("decide") is True
    assert (context.get("produces") or {}).get("options") == ["accept"]

    markdown = render_context_markdown(
        context,
        "# Verify complete gate\n\nTwo-turn minimum.\n",
    )
    assert "## Instructions" in markdown
    assert "Two-turn minimum" in markdown
    assert "abc123def" in markdown
    assert "### Artifacts" not in markdown
