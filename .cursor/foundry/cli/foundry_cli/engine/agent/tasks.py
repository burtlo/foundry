"""Registry task definitions for agent judgment work."""

from __future__ import annotations

import hashlib
import json
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from foundry_cli.context import assemble_context
from foundry_cli.engine.receipts import schema_name_from_registry
from foundry_cli.paths import resolve_registry_path
from foundry_cli.registry import get_node

SHAPE_EXAMINE_TASK_ID = "shape.examine"
EXAMINATION_RESULT_SCHEMA = "registry:schemas/shape-examination-result.schema.json"
EXAMINATION_RESULT_SCHEMA_FILE = "shape-examination-result.schema.json"

MANUAL_STEWARD_STEP_NODES = frozenset(
    {
        "shape.present",
        "shape.record",
    }
)


def task_registry_binding_exists(task_id: str, foundry_bundle: Path) -> bool:
    return (foundry_bundle / "tasks" / f"{task_id}.yaml").is_file()


def load_task_definition(task_id: str, foundry_bundle: Path) -> dict[str, Any]:
    path = foundry_bundle / "tasks" / f"{task_id}.yaml"
    if not path.is_file():
        raise KeyError(f"Unknown agent task: {task_id}")
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid task file: {path}")
    return data


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def digest_payload(payload: Any) -> str:
    raw = _canonical_json(payload).encode("utf-8")
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _read_instructions(ref: str, foundry_bundle: Path) -> str:
    path = resolve_registry_path(ref, foundry_bundle)
    return path.read_text(encoding="utf-8")


def build_shape_examine_input(
    snapshot: dict[str, Any],
    *,
    foundry_bundle: Path,
) -> dict[str, Any]:
    state = snapshot.get("state") if isinstance(snapshot.get("state"), dict) else {}
    ticket = state.get("ticket")
    prior = state.get("clarifying_questions")
    if not isinstance(prior, list):
        prior = []
    return {
        "ticket": deepcopy(ticket),
        "prior_answers": deepcopy(prior),
        "project_context": [],
    }


def build_agent_request(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    task_id: str,
    foundry_bundle: Path,
    workspace: Path,
    run_dir: Path,
) -> dict[str, Any]:
    task = load_task_definition(task_id, foundry_bundle)
    node_id = str(task.get("node_id") or task_id)
    node = get_node(flow, node_id)
    instructions_ref = str(task.get("instructions") or node.get("instructions") or "")
    instructions = _read_instructions(instructions_ref, foundry_bundle) if instructions_ref else ""

    context = assemble_context(
        snapshot=snapshot,
        visit=visit,
        flow=flow,
        foundry_bundle=foundry_bundle,
        workspace=workspace,
        run_dir=run_dir,
    )
    input_body = build_shape_examine_input(snapshot, foundry_bundle=foundry_bundle)
    input_body["context_packet_digest"] = digest_payload(
        {k: context.get(k) for k in ("node_id", "lifecycle", "reads", "allow")}
    )

    definition = {
        "task_id": task_id,
        "instructions_ref": instructions_ref,
        "output_schema": task.get("output_schema", EXAMINATION_RESULT_SCHEMA),
        "limits": task.get("limits") or {},
        "capabilities": task.get("capabilities") or {},
    }

    request_id = f"ar_{uuid.uuid4().hex[:16]}"
    return {
        "protocol_version": 1,
        "request_id": request_id,
        "run_id": snapshot.get("run_id"),
        "visit_id": str(visit.get("id")),
        "task_id": task_id,
        "attempt": 1,
        "definition_digest": digest_payload(definition),
        "input_digest": digest_payload(input_body),
        "instructions": instructions,
        "input": input_body,
        "output_schema": str(task.get("output_schema") or EXAMINATION_RESULT_SCHEMA),
        "limits": task.get("limits") or {},
        "capabilities": task.get("capabilities") or {},
        "status": "requested",
    }


def output_schema_file(request: dict[str, Any], foundry_bundle: Path) -> str:
    ref = str(request.get("output_schema") or EXAMINATION_RESULT_SCHEMA)
    return schema_name_from_registry(ref)
