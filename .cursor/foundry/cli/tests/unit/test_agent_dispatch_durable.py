"""Crash-boundary tests for durable agent dispatch."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.engine.advance import advance_run
from foundry_cli.engine.agent.adapter import StubAgentAdapter, default_stub_examination_result
from foundry_cli.engine.agent.dispatch import dispatch_for_agent_wait
from foundry_cli.run_store import commit_snapshot, get_revision, load_snapshot, save_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.shape_flow_helpers import intake_open_run, shape_test_workspace

BUNDLE = FOUNDRY_ROOT


def _valid_result(**overrides: object) -> dict:
    body = default_stub_examination_result()
    body.update(overrides)
    return body


def test_dispatch_after_outbox_commit_skips_second_network_call(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    run_dir, snapshot, flow = intake_open_run(workspace, work_prompt="Outbox durability")
    advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    assert snapshot["wait"]["kind"] == "agent"
    from foundry_cli.engine.agent.dispatch import stage_agent_dispatch_outbox

    request_id = str(snapshot["wait"]["request_ref"])
    stage_agent_dispatch_outbox(snapshot, request_id)
    commit_snapshot(run_dir, snapshot, expected_revision=get_revision(snapshot), bump=True)

    stub = StubAgentAdapter(default_result=_valid_result(summary="Once"))
    first = dispatch_for_agent_wait(snapshot, adapter=stub)
    assert first is not None
    commit_snapshot(run_dir, snapshot, expected_revision=get_revision(load_snapshot(run_dir)), bump=True)

    reloaded = load_snapshot(run_dir)
    record = reloaded["agent_requests"][request_id]
    assert record.get("pending_envelope")
    assert record.get("status") == "dispatched"

    stub_after_reload = StubAgentAdapter(default_result=_valid_result(summary="Twice"))
    dispatch_for_agent_wait(reloaded, adapter=stub_after_reload)
    assert stub_after_reload.invoke_count == 0
