"""Append-only ledger file and commit ordering."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.ledger import append_event
from foundry_cli.ledger_store import (
    LEDGER_FILE_NAME,
    STORAGE_VERSION_V2,
    migrate_run_storage,
    read_ledger_file,
)
from foundry_cli.run_store import (
    commit_snapshot,
    get_revision,
    load_snapshot,
    save_snapshot,
)


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
    assert len(events) == 1
    assert events[0]["type"] == "run.created"
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
    assert len(events) == 1
    assert events[0]["type"] == "visit.opened"
    on_disk = load_snapshot(run_dir)
    assert on_disk["ledger"][-1]["seq"] == 1
    assert on_disk.get("storage_version") == STORAGE_VERSION_V2


def test_missing_snapshot_recoverable_from_ledger(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    save_snapshot(run_dir, {"run_id": "r1", "revision": 0, "ledger": []})
    snapshot = {"run_id": "r1", "revision": 0, "ledger": []}
    append_event(snapshot, event_type="only.on.file", visit_id="v1")
    commit_snapshot(run_dir, snapshot, expected_revision=0)
    (run_dir / "snapshot.json").unlink()
    recovered = load_snapshot(run_dir)
    assert len(recovered["ledger"]) == 1
    assert recovered["ledger"][0]["type"] == "only.on.file"
    assert recovered.get("storage_version") == STORAGE_VERSION_V2


def test_corrupt_snapshot_recoverable_from_ledger(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    save_snapshot(run_dir, {"run_id": "r1", "revision": 0, "ledger": []})
    snapshot = {"run_id": "r1", "revision": 0, "ledger": []}
    append_event(snapshot, event_type="a", visit_id="v1")
    append_event(snapshot, event_type="b", visit_id="v1")
    commit_snapshot(run_dir, snapshot, expected_revision=0)
    (run_dir / "snapshot.json").write_text(
        '{"run_id": "r1", "revision": 1, "ledger": [',
        encoding="utf-8",
    )
    recovered = load_snapshot(run_dir)
    assert len(recovered["ledger"]) == 2
    assert recovered["ledger"][1]["type"] == "b"
    assert get_revision(recovered) == 1


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
    assert len(fixed["ledger"]) == 2
    assert fixed["ledger"][1]["type"] == "two"


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
