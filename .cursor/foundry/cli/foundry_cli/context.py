"""Assemble steward context packet from registry + run snapshot."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from foundry_cli.paths import resolve_registry_path, resolve_run_uri, substitute_visit_id
from foundry_cli.registry import get_node, normalize_receipts


DEFAULT_STEP_CLI = ["transition"]


def _list_or_empty(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    raise ValueError("Expected list")


def _reads_block(node: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    reads = node.get("reads") or {}
    config_keys = _list_or_empty(reads.get("config"))
    state_keys = _list_or_empty(reads.get("state"))
    snapshot_config = snapshot.get("config") if isinstance(snapshot.get("config"), dict) else {}
    snapshot_state = snapshot.get("state") if isinstance(snapshot.get("state"), dict) else {}
    return {
        "config": {key: snapshot_config.get(key) for key in config_keys},
        "state": {key: snapshot_state.get(key) for key in state_keys},
        "artifacts": deepcopy(reads.get("artifacts") or []),
        "files": _list_or_empty(reads.get("files")),
    }


def _effective_allow(node: dict[str, Any], node_id: str) -> dict[str, Any]:
    allow = deepcopy(node.get("allow") or {})
    kind = node.get("kind", "step")
    cli = _list_or_empty(allow.get("cli"))
    if not cli:
        cli = [] if kind == "gate" else list(DEFAULT_STEP_CLI)
    elif kind == "step" and "transition" not in cli:
        cli = [*cli, "transition"]

    state = _list_or_empty(allow.get("state"))
    implicit = f"state.nodes.{node_id}.*"
    if implicit not in state:
        state = [*state, implicit]

    files_write = _list_or_empty((allow.get("files") or {}).get("write"))
    agents = _list_or_empty(allow.get("agents"))
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
    visit_id: str,
) -> list[dict[str, str]]:
    grants: list[dict[str, str]] = []
    for uri in uris:
        logical = substitute_visit_id(uri, visit_id)
        grants.append(
            {
                "uri": logical,
                "resolved_path": str(resolve_run_uri(logical, run_dir, visit_id)),
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
    options = _list_or_empty(produces.get("options"))
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
) -> dict[str, Any]:
    node_id = str(visit["node_id"])
    visit_id = str(visit["id"])
    node = get_node(flow, node_id)
    kind = str(node.get("kind", visit.get("kind", "step")))
    lifecycle = str(visit.get("lifecycle", "opened"))

    instructions = node.get("instructions")
    if kind == "step" and not isinstance(instructions, str):
        raise ValueError(f"Step node {node_id!r} missing instructions")

    allow = _effective_allow(node, node_id)
    file_uris = allow["files"]["write"]
    allow["files"]["write"] = _resolve_file_grants(file_uris, run_dir=run_dir, visit_id=visit_id)

    warnings: list[str] = []
    if lifecycle != "opened":
        warnings.append(
            f"Visit lifecycle is {lifecycle!r}; steward work should proceed only when lifecycle is 'opened'."
        )

    context: dict[str, Any] = {
        "run_id": str(snapshot.get("run_id", "")),
        "visit_id": visit_id,
        "node_id": node_id,
        "kind": kind,
        "lifecycle": lifecycle,
        "title": str(node.get("title", node_id)),
        "reads": _reads_block(node, snapshot),
        "allow": allow,
        "produces": _produces_block(node, run_dir=run_dir, visit_id=visit_id),
        "receipts": normalize_receipts(node),
        "instructions": instructions if isinstance(instructions, str) else "",
        "instructions_path": str(resolve_registry_path(str(instructions), foundry_bundle))
        if isinstance(instructions, str)
        else "",
    }

    worker = _worker_block(node, foundry_bundle)
    if worker is not None:
        context["worker"] = worker

    if warnings:
        context["warnings"] = warnings

    return context
