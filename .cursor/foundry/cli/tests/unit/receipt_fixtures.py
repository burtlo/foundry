"""Disk receipts and ledger rows for gate resolution and context tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from foundry_cli.engine.receipts import seal_receipt_path
from foundry_cli.paths import resolve_run_uri
from tests.unit.constants import (
    EVENT_RECEIPT_LINKED,
    EVENT_VISIT_SEALED,
    REGISTRY_AGENT_RECEIPT_SCHEMA,
    TEST_RECEIPT_TIMESTAMP,
    TEST_RUN_UUID,
)


def prepare_run_dir(tmp_path: Path, name: str = "run") -> Path:
    run_dir = tmp_path / name
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def ledger_visit_sealed(
    visit_id: str,
    node_id: str,
    *,
    outcome: str = "completed",
    seq: int = 1,
) -> dict[str, Any]:
    return {
        "seq": seq,
        "type": EVENT_VISIT_SEALED,
        "visit_id": visit_id,
        "node_id": node_id,
        "payload": {"outcome": outcome},
    }


def ledger_receipt_linked(
    visit_id: str,
    *,
    schema: str,
    path: str,
    receipt_id: str,
    seq: int = 2,
) -> dict[str, Any]:
    return {
        "seq": seq,
        "type": EVENT_RECEIPT_LINKED,
        "visit_id": visit_id,
        "payload": {"schema": schema, "path": path, "receipt_id": receipt_id},
    }


def ledger_artifact_linked(
    visit_id: str,
    *,
    artifact_id: str,
    uri: str,
    seq: int = 2,
) -> dict[str, Any]:
    return {
        "seq": seq,
        "type": "artifact.linked",
        "visit_id": visit_id,
        "payload": {"artifact_id": artifact_id, "uri": uri},
    }


def write_receipt_to_run(run_dir: Path, visit_id: str, schema: str, receipt: dict[str, Any]) -> str:
    uri = seal_receipt_path(schema, visit_id)
    path = resolve_run_uri(uri, run_dir, visit_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt), encoding="utf-8")
    return uri


def intake_receipt_body(
    step_id: str,
    *,
    status: str = "passed",
    receipt_id: str,
    **extra: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": "2.2.0",
        "receipt_id": receipt_id,
        "run_id": TEST_RUN_UUID,
        "timestamp": TEST_RECEIPT_TIMESTAMP,
        "step_id": step_id,
        "status": status,
    }
    body.update(extra)
    return body


def agent_receipt_body(
    *,
    receipt_id: str,
    status: str = "completed",
    agent: dict[str, str] | None = None,
    recommended_next_state: str | None = None,
    commands: list[dict[str, Any]] | None = None,
    step_id: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": "2.2.0",
        "receipt_id": receipt_id,
        "run_id": TEST_RUN_UUID,
        "timestamp": TEST_RECEIPT_TIMESTAMP,
        "status": status,
        "provenance": {"source": "test", "run_id": TEST_RUN_UUID},
    }
    if agent is not None:
        body["agent"] = agent
    if recommended_next_state is not None:
        body["recommended_next_state"] = recommended_next_state
    if commands is not None:
        body["commands"] = commands
    if step_id is not None:
        body["step_id"] = step_id
    body.update(extra)
    return body


def snapshot_with_sealed_receipt(
    run_dir: Path,
    *,
    visit_id: str,
    step_node_id: str,
    schema: str,
    receipt: dict[str, Any],
    state: dict[str, Any] | None = None,
    run_id: str = TEST_RUN_UUID,
    linked_artifacts: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    uri = write_receipt_to_run(run_dir, visit_id, schema, receipt)
    ledger: list[dict[str, Any]] = [ledger_visit_sealed(visit_id, step_node_id, seq=1)]
    seq = 2
    if linked_artifacts:
        for artifact_id, artifact_uri in linked_artifacts:
            ledger.append(
                ledger_artifact_linked(visit_id, artifact_id=artifact_id, uri=artifact_uri, seq=seq)
            )
            seq += 1
    ledger.append(
        ledger_receipt_linked(
            visit_id,
            schema=schema,
            path=uri,
            receipt_id=str(receipt["receipt_id"]),
            seq=seq,
        )
    )
    snapshot: dict[str, Any] = {"run_id": run_id, "ledger": ledger}
    if state is not None:
        snapshot["state"] = state
    return snapshot


def opened_gate_visit(visit_id: str, node_id: str) -> dict[str, Any]:
    return {"id": visit_id, "node_id": node_id, "kind": "gate", "lifecycle": "opened"}


def minimal_engine_gate_flow(node_id: str, options: list[str]) -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": node_id,
                "kind": "gate",
                "decider": "engine",
                "produces": {"options": options},
            }
        ]
    }


def gate_context_arrange(
    tmp_path: Path,
    *,
    step_visit_id: str,
    step_node_id: str,
    gate_visit_id: str,
    gate_node_id: str,
    schema: str,
    receipt: dict[str, Any],
    state: dict[str, Any] | None = None,
    linked_artifacts: list[tuple[str, str]] | None = None,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    """Return run_dir, snapshot, gate visit for assemble_context tests."""
    run_dir = prepare_run_dir(tmp_path)
    snapshot = snapshot_with_sealed_receipt(
        run_dir,
        visit_id=step_visit_id,
        step_node_id=step_node_id,
        schema=schema,
        receipt=receipt,
        state=state,
        linked_artifacts=linked_artifacts,
    )
    visit = opened_gate_visit(gate_visit_id, gate_node_id)
    return run_dir, snapshot, visit


# Re-export for tests that only need the agent schema constant.
AGENT_RECEIPT_SCHEMA = REGISTRY_AGENT_RECEIPT_SCHEMA
