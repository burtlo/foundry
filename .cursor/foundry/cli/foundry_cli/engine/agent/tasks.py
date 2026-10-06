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
from foundry_cli.engine.project_context import select_bounded_project_context
from foundry_cli.engine.receipts import schema_name_from_registry
from foundry_cli.paths import resolve_registry_path
from foundry_cli.registry import get_node

SHAPE_EXAMINE_TASK_ID = "shape.examine"
SHAPE_PRESENT_TASK_ID = "shape.present"
SHAPE_RECORD_TASK_ID = "shape.record"
EXECUTE_PLAN_TASK_ID = "execute.plan"
EXAMINATION_RESULT_SCHEMA = "registry:schemas/shape-examination-result.schema.json"
EXAMINATION_RESULT_SCHEMA_FILE = "shape-examination-result.schema.json"
PRESENTATION_RESULT_SCHEMA = "registry:schemas/shape-presentation-result.schema.json"
PRESENTATION_RESULT_SCHEMA_FILE = "shape-presentation-result.schema.json"
RECORD_RESULT_SCHEMA = "registry:schemas/shape-record-result.schema.json"
RECORD_RESULT_SCHEMA_FILE = "shape-record-result.schema.json"
PLAN_RESULT_SCHEMA = "registry:schemas/execute-plan-result.schema.json"
PLAN_RESULT_SCHEMA_FILE = "execute-plan-result.schema.json"


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
    workspace: Path | None = None,
) -> dict[str, Any]:
    state = snapshot.get("state") if isinstance(snapshot.get("state"), dict) else {}
    ticket = state.get("ticket")
    prior = state.get("clarifying_questions")
    if not isinstance(prior, list):
        prior = []
    answers_map = state.get("clarifying_answers")
    if isinstance(answers_map, dict):
        merged_prior: list[Any] = []
        for item in prior:
            if not isinstance(item, dict):
                merged_prior.append(item)
                continue
            qid = item.get("id")
            if isinstance(qid, str) and qid in answers_map and not item.get("answer"):
                merged_prior.append({**item, "answer": answers_map[qid]})
            else:
                merged_prior.append(item)
        prior = merged_prior
    ws = workspace
    if ws is None:
        config = snapshot.get("config")
        if isinstance(config, dict):
            raw = config.get("workspace")
            if isinstance(raw, str) and raw.strip():
                ws = Path(raw)
    project_context: list[dict[str, str]] = []
    if ws is not None and ws.is_dir():
        project_context = select_bounded_project_context(ws)
    return {
        "ticket": deepcopy(ticket),
        "prior_answers": deepcopy(prior),
        "project_context": project_context,
    }


def build_shape_present_input(
    snapshot: dict[str, Any],
    *,
    foundry_bundle: Path,
    workspace: Path | None = None,
) -> dict[str, Any]:
    state = snapshot.get("state") if isinstance(snapshot.get("state"), dict) else {}
    ws = workspace
    if ws is None:
        config = snapshot.get("config")
        if isinstance(config, dict):
            raw = config.get("workspace")
            if isinstance(raw, str) and raw.strip():
                ws = Path(raw)
    project_context: list[dict[str, str]] = []
    if ws is not None and ws.is_dir():
        project_context = select_bounded_project_context(ws)
    body: dict[str, Any] = {
        "draft_ac": state.get("draft_ac"),
        "assumptions": deepcopy(state.get("assumptions") or []),
        "ticket": deepcopy(state.get("ticket")),
        "examination_decisions": deepcopy(state.get("examination_decisions") or []),
        "clarifying_questions": deepcopy(state.get("clarifying_questions") or []),
        "project_context": project_context,
    }
    approved = state.get("approved_ac")
    if isinstance(approved, str) and approved.strip():
        body["approved_ac"] = approved.strip()
    return body


def build_shape_record_input(
    snapshot: dict[str, Any],
    *,
    visit_id: str,
    run_dir: Path,
) -> dict[str, Any]:
    from foundry_cli.artifact_reads import resolve_nearest_sealed_ancestor_artifact
    from foundry_cli.paths import resolve_run_uri

    state = snapshot.get("state") if isinstance(snapshot.get("state"), dict) else {}
    presented_ac = state.get("presented_ac")
    presentation_path = state.get("presentation_artifact_path")
    body: dict[str, Any] = {
        "presented_ac": presented_ac,
        "presentation_artifact_path": presentation_path,
    }
    approved = state.get("approved_ac")
    if isinstance(approved, str) and approved.strip():
        body["approved_ac"] = approved.strip()
    presentation_md: str | None = None
    match = resolve_nearest_sealed_ancestor_artifact(
        snapshot,
        qualified_ref="shape.present.presentation",
        from_visit_id=visit_id,
        run_dir=run_dir,
    )
    if match:
        path = Path(match["resolved_path"])
        if path.is_file():
            presentation_md = path.read_text(encoding="utf-8")
    elif isinstance(presentation_path, str) and presentation_path.startswith("run:"):
        path = resolve_run_uri(presentation_path, run_dir, visit_id)
        if path.is_file():
            presentation_md = path.read_text(encoding="utf-8")
    if presentation_md is not None:
        body["presentation"] = presentation_md
    return body


def build_execute_plan_input(
    snapshot: dict[str, Any],
    *,
    visit_id: str,
    run_dir: Path,
) -> dict[str, Any]:
    from foundry_cli.artifact_reads import resolve_nearest_sealed_ancestor_artifact
    from foundry_cli.paths import resolve_run_uri

    state = snapshot.get("state") if isinstance(snapshot.get("state"), dict) else {}
    body: dict[str, Any] = {
        "approved_ac": state.get("approved_ac"),
        "approved_ac_digest": state.get("approved_ac_digest"),
        "feature_branch": state.get("feature_branch"),
        "execution_graph_id": state.get("execution_graph_id"),
        "run_id": snapshot.get("run_id"),
    }
    plan_md: str | None = None
    match = resolve_nearest_sealed_ancestor_artifact(
        snapshot,
        qualified_ref="shape.record.plan",
        from_visit_id=visit_id,
        run_dir=run_dir,
    )
    if match:
        path = Path(match["resolved_path"])
        if path.is_file():
            plan_md = path.read_text(encoding="utf-8")
    plan_uri = state.get("plan_path")
    if plan_md is None and isinstance(plan_uri, str) and plan_uri.startswith("run:"):
        path = resolve_run_uri(plan_uri, run_dir, visit_id)
        if path.is_file():
            plan_md = path.read_text(encoding="utf-8")
    if plan_md is not None:
        body["shape_plan_markdown"] = plan_md
    return body


def _task_input_body(
    task_id: str,
    snapshot: dict[str, Any],
    *,
    foundry_bundle: Path,
    workspace: Path,
    visit_id: str,
    run_dir: Path,
) -> dict[str, Any]:
    if task_id == SHAPE_EXAMINE_TASK_ID:
        return build_shape_examine_input(
            snapshot,
            foundry_bundle=foundry_bundle,
            workspace=workspace,
        )
    if task_id == SHAPE_PRESENT_TASK_ID:
        return build_shape_present_input(
            snapshot,
            foundry_bundle=foundry_bundle,
            workspace=workspace,
        )
    if task_id == SHAPE_RECORD_TASK_ID:
        return build_shape_record_input(snapshot, visit_id=visit_id, run_dir=run_dir)
    if task_id == EXECUTE_PLAN_TASK_ID:
        return build_execute_plan_input(snapshot, visit_id=visit_id, run_dir=run_dir)
    return {}


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
    input_body = _task_input_body(
        task_id,
        snapshot,
        foundry_bundle=foundry_bundle,
        workspace=workspace,
        visit_id=str(visit.get("id")),
        run_dir=run_dir,
    )
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
