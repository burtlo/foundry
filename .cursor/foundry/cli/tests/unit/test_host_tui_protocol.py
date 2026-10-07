"""Phase 4 host TUI protocol: run.context, run.get enrichments, run.events long-poll."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from foundry_cli.ledger import append_event, filter_events

from foundry_cli.engine.advance import advance_run
from foundry_cli.host.handlers import HostHandlers
from foundry_cli.host.protocol import parse_request_line
from foundry_cli.run_store import commit_snapshot, get_revision, load_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.shape_flow_helpers import intake_open_run, shape_test_workspace

BUNDLE = FOUNDRY_ROOT


def test_parse_request_accepts_run_context() -> None:
    payload = {
        "protocol_version": 1,
        "id": "ctx-1",
        "method": "run.context",
        "params": {"run_id": "adv-0001", "format": "json"},
    }
    parsed = parse_request_line(json.dumps(payload))
    assert parsed["method"] == "run.context"


def test_handler_run_context_json(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    run_dir, snapshot, flow = intake_open_run(workspace, work_prompt="Host context RPC")
    advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    commit_snapshot(run_dir, snapshot, expected_revision=get_revision(snapshot), bump=True)
    run_id = str(snapshot.get("run_id"))

    handlers = HostHandlers(workspace, BUNDLE)
    result = handlers.run_context({"run_id": run_id, "format": "json"})
    assert result.get("ok") is True
    context = result.get("context")
    assert isinstance(context, dict)
    assert context.get("run_id") == run_id
    assert context.get("node_id") == "shape.examine"


def test_handler_run_context_markdown(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    run_dir, snapshot, flow = intake_open_run(workspace, work_prompt="Host context markdown")
    run_id = str(snapshot.get("run_id"))
    handlers = HostHandlers(workspace, BUNDLE)
    result = handlers.run_context({"run_id": run_id, "format": "markdown"})
    assert result.get("ok") is True
    markdown = result.get("markdown")
    assert isinstance(markdown, str) and "# Steward context" in markdown


def test_handler_run_get_includes_phase_and_wait_kind(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    run_dir, snapshot, flow = intake_open_run(workspace, work_prompt="Enriched get")
    advance_run(
        snapshot,
        flow,
        workspace=workspace,
        foundry_bundle=BUNDLE,
        run_dir=run_dir,
    )
    commit_snapshot(run_dir, snapshot, expected_revision=get_revision(snapshot), bump=True)
    run_id = str(snapshot.get("run_id"))

    handlers = HostHandlers(workspace, BUNDLE)
    result = handlers.run_get({"run_id": run_id})
    assert result.get("ok") is True
    assert result.get("phase") == "shape"
    assert result.get("wait_kind") == "agent"
    assert result.get("status_reason") is None or isinstance(result.get("status_reason"), dict)


def test_run_events_rejects_invalid_block_ms(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    _run_dir, snapshot, _flow = intake_open_run(workspace, work_prompt="Bad block_ms")
    run_id = str(snapshot.get("run_id"))
    handlers = HostHandlers(workspace, BUNDLE)
    result = handlers.run_events({"run_id": run_id, "block_ms": "nope"})
    assert result.get("ok") is False
    assert result.get("error", {}).get("code") == "INVALID_REQUEST"


def test_run_events_block_ms_returns_when_ledger_appends(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    run_dir, snapshot, _flow = intake_open_run(workspace, work_prompt="Long poll events")
    run_id = str(snapshot.get("run_id"))
    handlers = HostHandlers(workspace, BUNDLE)
    existing = filter_events(snapshot)
    tail_seq = max(int(e.get("seq", 0)) for e in existing) if existing else 0

    def append_later() -> None:
        time.sleep(0.05)
        snap = load_snapshot(run_dir)
        append_event(snap, event_type="acceptance.test.poll", payload={"probe": True})
        commit_snapshot(run_dir, snap, expected_revision=get_revision(snap), bump=True)

    thread = threading.Thread(target=append_later, daemon=True)
    thread.start()
    polled = handlers.run_events(
        {"run_id": run_id, "after_seq": tail_seq, "block_ms": 3000},
    )
    thread.join(timeout=5.0)
    assert polled.get("ok") is True
    assert polled.get("timed_out") is False
    assert len(polled.get("events") or []) >= 1


def test_run_events_block_ms_times_out_when_no_new_events(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    _run_dir, snapshot, _flow = intake_open_run(workspace, work_prompt="Long poll")
    run_id = str(snapshot.get("run_id"))
    handlers = HostHandlers(workspace, BUNDLE)

    polled = handlers.run_events({"run_id": run_id, "after_seq": 10_000, "block_ms": 80})
    assert polled.get("ok") is True
    assert polled.get("events") == []
    assert polled.get("timed_out") is True
