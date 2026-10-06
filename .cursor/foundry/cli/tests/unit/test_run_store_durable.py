"""Durability helpers on run_store."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from foundry_cli.run_store import (
    RunStoreError,
    commit_snapshot,
    get_revision,
    load_snapshot,
    save_snapshot,
)


def test_save_snapshot_is_atomic_replace(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    snapshot = {"run_id": "r1", "revision": 1, "ledger": [{"seq": 1, "type": "t"}]}
    save_snapshot(run_dir, snapshot)
    path = run_dir / "snapshot.json"
    assert path.is_file()
    assert not (run_dir / "snapshot.json.tmp").exists()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["ledger"][0]["type"] == "t"


def test_commit_snapshot_stale_revision(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    save_snapshot(run_dir, {"run_id": "r1", "revision": 3, "ledger": []})
    snapshot = {"run_id": "r1", "revision": 3, "ledger": [{"seq": 1, "type": "mut"}]}
    with pytest.raises(RunStoreError) as exc:
        commit_snapshot(run_dir, snapshot, expected_revision=2)
    assert exc.value.code == "STALE_REVISION"
    assert get_revision(load_snapshot(run_dir)) == 3


def test_commit_snapshot_bumps_from_disk_revision(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    save_snapshot(run_dir, {"run_id": "r1", "revision": 4, "ledger": []})
    snapshot = {"run_id": "r1", "revision": 0, "ledger": [{"seq": 1, "type": "x"}]}
    new_revision = commit_snapshot(run_dir, snapshot, expected_revision=4)
    assert new_revision == 5
    assert get_revision(load_snapshot(run_dir)) == 5
