"""Append-only ledger file and commit ordering."""

from __future__ import annotations

from pathlib import Path

import pytest

from foundry_cli.ledger import append_event
from foundry_cli.ledger_replay import CHECKPOINT_EVENT_TYPE, is_runnable_snapshot
from foundry_cli.ledger_store import (
    LEDGER_FILE_NAME,
    LedgerStoreError,
    STORAGE_VERSION_V2,
    migrate_run_storage,
    read_ledger_file,
)
from foundry_cli.run_service import advance_run_durable
from foundry_cli.run_store import (
    RunStoreError,
    commit_snapshot,
    get_revision,
    load_snapshot,
    save_snapshot,
)
from foundry_cli.engine.agent.adapter import StubAgentAdapter
from tests.conftest import FOUNDRY_ROOT
from tests.unit.shape_flow_helpers import intake_open_run, shape_test_workspace, valid_examination_result

BUNDLE = FOUNDRY_ROOT


def test_migrate_inline_ledger_writes_jsonl_once(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    snapshot = {
        "run_id": "r1",
        "revision": 1,
        "ledger": [{"seq": 1, "type": "run.created", "payload": {}}],
    }
    save_snapshot(run_dir, snapshot)
    loaded = load_snapshot(run_dir)
    assert loaded.get("storage_version") == STORAGE_VERSION_V2
    lines = (run_dir / LEDGER_FILE_NAME).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    loaded_again = load_snapshot(run_dir)
    assert len(read_ledger_file(run_dir)) == 1
    assert loaded_again.get("storage_version") == STORAGE_VERSION_V2


def test_commit_snapshot_first_write_without_pre_save(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    snapshot = {"run_id": "r1", "revision": 0, "ledger": []}
    append_event(snapshot, event_type="run.created", visit_id="v1")
    revision = commit_snapshot(run_dir, snapshot, expected_revision=0)
    assert revision == 1
    assert (run_dir / "snapshot.json").is_file()
    events = read_ledger_file(run_dir)
    assert len(events) == 2
    assert events[0]["type"] == "run.created"
    assert events[1]["type"] == CHECKPOINT_EVENT_TYPE
    on_disk = load_snapshot(run_dir)
    assert get_revision(on_disk) == 1


def test_commit_appends_to_ledger_before_snapshot(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    save_snapshot(run_dir, {"run_id": "r1", "revision": 0, "ledger": []})
    snapshot = {"run_id": "r1", "revision": 0, "ledger": []}
    append_event(snapshot, event_type="visit.opened", visit_id="v1")
    commit_snapshot(run_dir, snapshot, expected_revision=0)
    events = read_ledger_file(run_dir)
    assert len(events) == 2
    assert events[0]["type"] == "visit.opened"
    assert events[1]["type"] == CHECKPOINT_EVENT_TYPE
    on_disk = load_snapshot(run_dir)
    assert on_disk["ledger"][-1]["seq"] == 2
    assert on_disk["ledger"][-1]["type"] == CHECKPOINT_EVENT_TYPE
    assert on_disk.get("storage_version") == STORAGE_VERSION_V2


def test_missing_snapshot_recoverable_from_ledger(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    run_dir, snapshot, _flow = intake_open_run(workspace, work_prompt="Recover me")
    commit_snapshot(run_dir, snapshot, expected_revision=get_revision(snapshot), bump=True)
    (run_dir / "snapshot.json").unlink()
    recovered = load_snapshot(run_dir)
    assert is_runnable_snapshot(recovered)
    assert recovered.get("active_visit")
    checkpoints = [e for e in recovered["ledger"] if e.get("type") == CHECKPOINT_EVENT_TYPE]
    assert checkpoints
    assert recovered.get("storage_version") == STORAGE_VERSION_V2


def test_ledger_only_shell_without_checkpoint_not_runnable(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    save_snapshot(run_dir, {"run_id": "r1", "revision": 0, "ledger": []})
    snapshot = {"run_id": "r1", "revision": 0, "ledger": []}
    append_event(snapshot, event_type="only.on.file", visit_id="v1")
    commit_snapshot(run_dir, snapshot, expected_revision=0)
    (run_dir / "snapshot.json").unlink()
    with pytest.raises(RunStoreError) as exc:
        load_snapshot(run_dir)
    assert exc.value.code == "SNAPSHOT_NOT_RUNNABLE"


def test_corrupt_snapshot_recoverable_from_ledger(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    run_dir, snapshot, _flow = intake_open_run(workspace, work_prompt="Corrupt recovery")
    commit_snapshot(run_dir, snapshot, expected_revision=get_revision(snapshot), bump=True)
    append_event(snapshot, event_type="post.checkpoint.note", visit_id=snapshot["active_visit"]["id"])
    commit_snapshot(run_dir, snapshot, expected_revision=get_revision(load_snapshot(run_dir)), bump=True)
    (run_dir / "snapshot.json").write_text(
        '{"run_id": "broken", "revision": 1, "ledger": [',
        encoding="utf-8",
    )
    recovered = load_snapshot(run_dir)
    assert is_runnable_snapshot(recovered)
    assert len(recovered["ledger"]) >= 2
    assert get_revision(recovered) >= 1


def test_repaired_run_can_advance_after_snapshot_loss(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    run_dir, snapshot, _flow = intake_open_run(workspace, work_prompt="Advance after repair")
    commit_snapshot(run_dir, snapshot, expected_revision=get_revision(snapshot), bump=True)
    revision = get_revision(load_snapshot(run_dir))
    (run_dir / "snapshot.json").unlink()
    reloaded = load_snapshot(run_dir)
    assert is_runnable_snapshot(reloaded)
    stub = StubAgentAdapter(default_result=valid_examination_result(summary="After repair"))
    outcome = advance_run_durable(
        workspace=workspace,
        bundle=BUNDLE,
        run_dir=run_dir,
        expected_revision=get_revision(reloaded),
        agent_adapter=stub,
    )
    assert outcome["ok"] is True
    assert stub.invoke_count == 2


def test_truncated_snapshot_ledger_synced_from_file(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    save_snapshot(run_dir, {"run_id": "r1", "revision": 0, "ledger": []})
    snapshot = {"run_id": "r1", "revision": 0, "ledger": []}
    append_event(snapshot, event_type="one")
    commit_snapshot(run_dir, snapshot, expected_revision=0)
    append_event(snapshot, event_type="two")
    commit_snapshot(run_dir, snapshot, expected_revision=1)
    stale = {"run_id": "r1", "revision": 2, "ledger": snapshot["ledger"][:1]}
    save_snapshot(run_dir, stale)
    fixed = load_snapshot(run_dir)
    user_events = [event for event in fixed["ledger"] if event.get("type") != CHECKPOINT_EVENT_TYPE]
    assert len(user_events) == 2
    assert user_events[1]["type"] == "two"


def test_migrate_run_storage_idempotent(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    snapshot = {
        "run_id": "r1",
        "revision": 0,
        "ledger": [{"seq": 1, "type": "t", "payload": {}}],
    }
    first = migrate_run_storage(run_dir, dict(snapshot))
    second = migrate_run_storage(run_dir, dict(first))
    assert first["storage_version"] == STORAGE_VERSION_V2
    assert second["storage_version"] == STORAGE_VERSION_V2
    assert len(read_ledger_file(run_dir)) == 1
