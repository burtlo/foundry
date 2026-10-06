"""Phase 4 agent connection: validation, submit, advance integration."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from foundry_cli.engine.advance import advance_run
from foundry_cli.engine.agent.adapter import StubAgentAdapter, default_stub_examination_result
from foundry_cli.engine.agent.submit import submit_agent_result
from foundry_cli.engine.lifecycle import admit_visit
from foundry_cli.ledger import filter_events
from foundry_cli.registry import load_registry
from foundry_cli.run_service import advance_run_durable, submit_agent_result_durable
from foundry_cli.run_store import get_revision, load_snapshot, save_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import NODE_SHAPE_EXAMINE, NODE_SHAPE_INTAKE
from tests.unit.test_advance import _intake_open_run, _workspace

BUNDLE = FOUNDRY_ROOT


def _valid_result(**overrides: object) -> dict:
    body = default_stub_examination_result()
    body.update(overrides)
    return body


def test_submit_rejects_invalid_schema(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    run_dir, snapshot, flow = _intake_open_run(workspace, work_prompt="Examine me")
    advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    wait = snapshot["wait"]
    request_id = str(wait["request_ref"])
    outcome = submit_agent_result(
        snapshot,
        request_id=request_id,
        result={"summary": "too small"},
        foundry_bundle=BUNDLE,
    )
    assert outcome["ok"] is False
    assert outcome["code"] == "RESULT_VALIDATION_FAILED"


def test_submit_accepts_result_and_clears_agent_wait(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    run_dir, snapshot, flow = _intake_open_run(workspace, work_prompt="Examine me")
    advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    request_id = str(snapshot["wait"]["request_ref"])
    outcome = submit_agent_result(
        snapshot,
        request_id=request_id,
        result=_valid_result(),
        foundry_bundle=BUNDLE,
    )
    assert outcome["ok"] is True
    assert snapshot["wait"] is None
    assert snapshot["state"]["draft_ac"]
    accepted = filter_events(snapshot, types=["agent.result.accepted"])
    assert len(accepted) == 1


def test_submit_idempotent_second_call(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    run_dir, snapshot, flow = _intake_open_run(workspace, work_prompt="Examine me")
    advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    request_id = str(snapshot["wait"]["request_ref"])
    result = _valid_result()
    first = submit_agent_result(
        snapshot,
        request_id=request_id,
        result=result,
        foundry_bundle=BUNDLE,
    )
    second = submit_agent_result(
        snapshot,
        request_id=request_id,
        result=result,
        foundry_bundle=BUNDLE,
    )
    assert first["ok"] is True
    assert second.get("idempotent") is True


def test_submit_with_questions_sets_user_input_wait(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    run_dir, snapshot, flow = _intake_open_run(workspace, work_prompt="Examine me")
    advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    request_id = str(snapshot["wait"]["request_ref"])
    outcome = submit_agent_result(
        snapshot,
        request_id=request_id,
        result=_valid_result(
            questions=[
                {"id": "q1", "text": "Which API?", "why_needed": "Scope"},
            ]
        ),
        foundry_bundle=BUNDLE,
    )
    assert outcome["ok"] is True
    wait = snapshot["wait"]
    assert wait["kind"] == "user_input"
    assert snapshot["state"]["open_clarifying_questions_count"] == 1


def test_advance_durable_dispatches_stub_adapter(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    run_dir, snapshot, flow = _intake_open_run(workspace, work_prompt="Host dispatch")
    save_snapshot(run_dir, snapshot)
    stub = StubAgentAdapter(default_result=_valid_result(summary="Stub dispatched"))
    first = advance_run_durable(
        workspace=workspace,
        bundle=BUNDLE,
        run_dir=run_dir,
        expected_revision=get_revision(snapshot),
        agent_adapter=stub,
    )
    assert first["ok"] is True
    assert first["wait"]["kind"] == "operator"
    reloaded = load_snapshot(run_dir)
    accepted = filter_events(reloaded, types=["agent.result.accepted"])
    assert len(accepted) == 1
    request_id = str(accepted[0]["payload"]["request_id"])
    record = reloaded["agent_requests"][request_id]
    assert record["status"] == "accepted"
    assert reloaded["state"]["draft_ac"]
    dispatched = filter_events(reloaded, types=["agent.dispatched"])
    assert len(dispatched) == 1


def test_integration_advance_auto_accepts_stub(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    run_dir, snapshot, flow = _intake_open_run(workspace, work_prompt="Full path")
    save_snapshot(run_dir, snapshot)
    rev = get_revision(snapshot)
    continued = advance_run_durable(
        workspace=workspace,
        bundle=BUNDLE,
        run_dir=run_dir,
        expected_revision=rev,
    )
    assert continued["ok"] is True
    assert continued["wait"]["kind"] == "operator"
    final = load_snapshot(run_dir)
    assert final["active_visit"]["node_id"] == NODE_SHAPE_EXAMINE
    assert final["state"]["draft_ac"]
    accepted = filter_events(final, types=["agent.result.accepted"])
    assert len(accepted) == 1


def test_advance_durable_user_input_wait_after_questions(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    run_dir, snapshot, flow = _intake_open_run(workspace, work_prompt="Questions path")
    save_snapshot(run_dir, snapshot)
    stub = StubAgentAdapter(
        default_result=_valid_result(
            questions=[{"id": "q1", "text": "Which API?", "why_needed": "Scope"}],
        )
    )
    outcome = advance_run_durable(
        workspace=workspace,
        bundle=BUNDLE,
        run_dir=run_dir,
        expected_revision=get_revision(snapshot),
        agent_adapter=stub,
    )
    assert outcome["ok"] is True
    assert outcome["wait"]["kind"] == "user_input"
    reloaded = load_snapshot(run_dir)
    assert reloaded["state"]["open_clarifying_questions_count"] == 1


def test_advance_creates_agent_requested_event(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    run_dir, snapshot, flow = _intake_open_run(workspace, work_prompt="Ledger proof")
    advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    wait = snapshot["wait"]
    assert wait["kind"] == "agent"
    assert str(wait["request_ref"]).startswith("ar_")
    requested = filter_events(snapshot, types=["agent.requested"])
    assert len(requested) == 1
