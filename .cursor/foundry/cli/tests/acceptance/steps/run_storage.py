"""Step definitions for run_storage.feature."""

from __future__ import annotations

import json

from pytest_bdd import given, then

from foundry_cli.host.idempotency_store import IDEMPOTENCY_FILE_NAME
from foundry_cli.host.paths import host_dir
from foundry_cli.ledger_store import LEDGER_FILE_NAME, read_ledger_file
from foundry_cli.run_store import load_snapshot as load_durable_snapshot
from tests.acceptance.helpers import run_dir


@given("a legacy inline-only run in the workspace")
def legacy_inline_only_run(acceptance) -> None:
    run_id = "legacy-inline-run"
    run_path = run_dir_from_workspace(acceptance, run_id)
    run_path.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "run_id": run_id,
        "revision": 1,
        "status": "running",
        "ledger": [
            {
                "seq": 1,
                "type": "run.created",
                "visit_id": "v1",
                "payload": {},
            }
        ],
        "visits": [],
    }
    (run_path / "snapshot.json").write_text(
        json.dumps(snapshot, indent=2) + "\n",
        encoding="utf-8",
    )
    acceptance["run_id"] = run_id


def run_dir_from_workspace(acceptance, run_id: str):
    from pathlib import Path

    workspace = Path(acceptance["workspace"])
    return workspace / ".foundry" / "runs" / run_id


@then("the current run has a ledger.jsonl file")
def assert_ledger_jsonl(acceptance) -> None:
    path = run_dir(acceptance) / LEDGER_FILE_NAME
    assert path.is_file(), f"expected {path} to exist"


@then("the run snapshot has storage version 2")
def assert_storage_version_two(acceptance) -> None:
    snapshot = load_durable_snapshot(run_dir(acceptance))
    assert snapshot.get("storage_version") == 2


@then("inline ledger matches ledger.jsonl event count")
def assert_inline_matches_file(acceptance) -> None:
    snapshot = load_durable_snapshot(run_dir(acceptance))
    inline = snapshot.get("ledger")
    assert isinstance(inline, list), "snapshot ledger must be a list"
    file_events = read_ledger_file(run_dir(acceptance))
    assert len(inline) == len(file_events), (
        f"inline ledger has {len(inline)} events, ledger.jsonl has {len(file_events)}"
    )


@then("workspace host idempotency store file exists")
def assert_host_idempotency_store(acceptance) -> None:
    from pathlib import Path

    workspace = Path(acceptance["workspace"])
    path = host_dir(workspace) / IDEMPOTENCY_FILE_NAME
    assert path.is_file(), f"expected durable idempotency store at {path}"
