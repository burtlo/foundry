"""Assemble steward context packet from registry + run snapshot."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from foundry_cli.artifact_reads import resolve_reads_artifacts
from foundry_cli.constants import (
    CAP_TRANSITION,
    ENGINE_OWNED_STEP_NODE_IDS,
    KIND_GATE,
    KIND_STEP,
    LIFECYCLE_OPENED,
)
from foundry_cli.paths import (
    resolve_registry_path,
    resolve_run_uri,
    resolve_workspace_uri,
    substitute_visit_id,
    workspace_from_run_dir,
)
from foundry_cli.registry import get_node, normalize_receipts
from foundry_cli.state_paths import effective_state_grants
from foundry_cli.util import list_or_empty


DEFAULT_STEP_CLI = [CAP_TRANSITION]


def _reads_block(node: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    reads = node.get("reads") or {}
    config_keys = list_or_empty(reads.get("config"))
    state_keys = list_or_empty(reads.get("state"))
    snapshot_config = snapshot.get("config") if isinstance(snapshot.get("config"), dict) else {}
    snapshot_state = snapshot.get("state") if isinstance(snapshot.get("state"), dict) else {}
    return {
        "config": {key: snapshot_config.get(key) for key in config_keys},
        "state": {key: snapshot_state.get(key) for key in state_keys},
        "artifacts": deepcopy(reads.get("artifacts") or []),
        "files": list_or_empty(reads.get("files")),
    }


def _effective_allow(node: dict[str, Any], node_id: str) -> dict[str, Any]:
    allow = deepcopy(node.get("allow") or {})
    kind = node.get("kind", KIND_STEP)
    cli = list_or_empty(allow.get("cli"))
    if not cli:
        cli = [] if kind == KIND_GATE else list(DEFAULT_STEP_CLI)
    elif (
        kind == KIND_STEP
        and CAP_TRANSITION not in cli
        and node_id not in ENGINE_OWNED_STEP_NODE_IDS
    ):
        cli = [*cli, CAP_TRANSITION]

    state = effective_state_grants(allow, node_id)

    files_write = list_or_empty((allow.get("files") or {}).get("write"))
    agents = list_or_empty(allow.get("agents"))
    user = allow.get("user") if isinstance(allow.get("user"), dict) else {}
    return {
        "cli": cli,
        "state": state,
        "files": {"write": files_write},
        "agents": agents,
        "user": {
            "ask": bool(user.get("ask", False)),
            "decide": bool(user.get("decide", False)),
        },
    }


def _resolve_file_grants(
    uris: list[str],
    *,
    run_dir: Path,
    workspace: Path,
    visit_id: str,
) -> list[dict[str, str]]:
    grants: list[dict[str, str]] = []
    for uri in uris:
        logical = substitute_visit_id(uri, visit_id)
        if logical.startswith("workspace:"):
            resolved_path = str(resolve_workspace_uri(logical, workspace))
        else:
            resolved_path = str(resolve_run_uri(logical, run_dir, visit_id))
        grants.append(
            {
                "uri": logical,
                "resolved_path": resolved_path,
            }
        )
    return grants


def _produces_block(
    node: dict[str, Any],
    *,
    run_dir: Path,
    visit_id: str,
) -> dict[str, Any]:
    produces = node.get("produces") or {}
    artifacts_in = produces.get("artifacts") or []
    artifacts_out: list[dict[str, Any]] = []
    for artifact in artifacts_in:
        if not isinstance(artifact, dict):
            continue
        item = deepcopy(artifact)
        uri = item.get("uri")
        if isinstance(uri, str):
            resolved_uri = substitute_visit_id(uri, visit_id)
            item["resolved_uri"] = resolved_uri
            if resolved_uri.startswith("run:"):
                item["resolved_path"] = str(resolve_run_uri(resolved_uri, run_dir, visit_id))
        artifacts_out.append(item)
    options = list_or_empty(produces.get("options"))
    return {"artifacts": artifacts_out, "options": options}


def _worker_block(node: dict[str, Any], foundry_bundle: Path) -> dict[str, Any] | None:
    worker = node.get("worker")
    if not isinstance(worker, dict):
        return None
    prompt = str(worker["prompt"])
    contract = str(worker["contract"])
    mode = str(worker["mode"])
    return {
        "prompt": prompt,
        "contract": contract,
        "mode": mode,
        "prompt_path": str(resolve_registry_path(prompt, foundry_bundle)),
        "contract_path": str(resolve_registry_path(contract, foundry_bundle)),
    }


def assemble_context(
    *,
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    foundry_bundle: Path,
    run_dir: Path,
    workspace: Path | None = None,
) -> dict[str, Any]:
    node_id = str(visit["node_id"])
    visit_id = str(visit["id"])
    node = get_node(flow, node_id)
    kind = str(node.get("kind", visit.get("kind", KIND_STEP)))
    lifecycle = str(visit.get("lifecycle", LIFECYCLE_OPENED))

    instructions = node.get("instructions")
    operations = node.get("operations")
    if (
        kind == KIND_STEP
        and node_id not in ENGINE_OWNED_STEP_NODE_IDS
        and not isinstance(instructions, str)
    ):
        raise ValueError(f"Step node {node_id!r} missing instructions")

    allow = _effective_allow(node, node_id)
    file_uris = allow["files"]["write"]
    resolved_workspace = workspace if workspace is not None else workspace_from_run_dir(run_dir)
    allow["files"]["write"] = _resolve_file_grants(
        file_uris,
        run_dir=run_dir,
        workspace=resolved_workspace,
        visit_id=visit_id,
    )

    warnings: list[str] = []
    if lifecycle != LIFECYCLE_OPENED:
        warnings.append(
            f"Visit lifecycle is {lifecycle!r}; steward work should proceed only when lifecycle is {LIFECYCLE_OPENED!r}."
        )

    reads = _reads_block(node, snapshot)
    snapshot_state = snapshot.get("state") if isinstance(snapshot.get("state"), dict) else {}
    reads["artifacts"] = resolve_reads_artifacts(
        list(reads.get("artifacts") or []),
        snapshot=snapshot,
        visit_id=visit_id,
        run_dir=run_dir,
        state=snapshot_state,
    )
    if node_id == "execute.intake.gate":
        from foundry_cli.engine.gates import intake_receipt_summary_for_sealed_step

        summary = intake_receipt_summary_for_sealed_step(
            snapshot, run_dir=run_dir, step_node_id="execute.intake"
        )
        if summary is not None:
            reads["intake_receipt"] = summary
    if node_id == "execute.test.gate":
        from foundry_cli.engine.gates import test_receipt_summary_for_sealed_step

        summary = test_receipt_summary_for_sealed_step(snapshot, run_dir=run_dir)
        if summary is not None:
            reads["test_receipt"] = summary
    if node_id == "execute.repair.limit.gate":
        from foundry_cli.engine.gates import repair_loop_summary_for_snapshot

        reads["repair_loop"] = repair_loop_summary_for_snapshot(snapshot)
    if node_id == "execute.commit.gate":
        from foundry_cli.engine.gates import commit_receipt_summary_for_sealed_step

        summary = commit_receipt_summary_for_sealed_step(snapshot, run_dir=run_dir)
        if summary is not None:
            reads["commit_receipt"] = summary
        gate_state = reads.get("state") if isinstance(reads.get("state"), dict) else {}
        merged_state = dict(gate_state)
        if isinstance(snapshot_state, dict):
            if snapshot_state.get("final_commit_sha") is not None:
                merged_state["final_commit_sha"] = str(snapshot_state["final_commit_sha"])
            if snapshot_state.get("execute_commit_message") is not None:
                merged_state["execute_commit_message"] = str(
                    snapshot_state["execute_commit_message"]
                )
        if merged_state:
            reads["state"] = merged_state

    context: dict[str, Any] = {
        "run_id": str(snapshot.get("run_id", "")),
        "visit_id": visit_id,
        "node_id": node_id,
        "kind": kind,
        "lifecycle": lifecycle,
        "title": str(node.get("title", node_id)),
        "reads": reads,
        "allow": allow,
        "produces": _produces_block(node, run_dir=run_dir, visit_id=visit_id),
        "receipts": normalize_receipts(node),
    }
    if isinstance(instructions, str):
        context["instructions"] = instructions
        context["instructions_path"] = str(
            resolve_registry_path(instructions, foundry_bundle)
        )
    if isinstance(operations, str):
        context["operations"] = operations
        context["operations_path"] = str(resolve_registry_path(operations, foundry_bundle))

    worker = _worker_block(node, foundry_bundle)
    if worker is not None:
        context["worker"] = worker

    if kind == KIND_GATE:
        gate_prompt = node.get("prompt")
        if isinstance(gate_prompt, str) and gate_prompt.strip():
            context["prompt"] = gate_prompt.strip()
        decider = node.get("decider")
        if isinstance(decider, str) and decider.strip():
            context["decider"] = decider.strip()

    if warnings:
        context["warnings"] = warnings

    return context
