"""Build machine-readable node index files from the flow registry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from foundry_cli.paths import foundry_root
from foundry_cli.registry import get_node, load_registry, normalize_receipts

LIFECYCLE_HOOKS = ("on_examine", "on_open", "on_close", "on_seal")
DEFAULT_FEATURE_DIR = Path(".cursor/foundry/cli/tests/acceptance/features")


def extract_checks_used(node: dict[str, Any]) -> dict[str, list[str]]:
    lifecycle = node.get("lifecycle") or {}
    checks_used: dict[str, list[str]] = {}
    for hook in LIFECYCLE_HOOKS:
        items = lifecycle.get(hook) or []
        hook_checks: list[str] = []
        for item in items:
            if isinstance(item, dict) and item.get("check"):
                hook_checks.append(str(item["check"]))
        checks_used[hook] = hook_checks
    return checks_used


def normalize_connection(connection: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {
        "id": str(connection["id"]),
        "from": str(connection["from"]),
        "to": str(connection["to"]),
    }
    if "on" in connection:
        normalized["on"] = connection["on"]
    if "when" in connection:
        normalized["when"] = connection["when"]
    if "loop" in connection:
        normalized["loop"] = connection["loop"]
    return normalized


def _node_connections(flow: dict[str, Any], node_id: str) -> dict[str, list[dict[str, Any]]]:
    connections = flow.get("connections") or []
    incoming: list[dict[str, Any]] = []
    outgoing: list[dict[str, Any]] = []
    for connection in connections:
        if not isinstance(connection, dict):
            continue
        if connection.get("from") == node_id:
            outgoing.append(normalize_connection(connection))
        if connection.get("to") == node_id:
            incoming.append(normalize_connection(connection))
    return {"in": incoming, "out": outgoing}


def _assets_block(node: dict[str, Any]) -> dict[str, Any]:
    assets: dict[str, Any] = {}
    instructions = node.get("instructions")
    if isinstance(instructions, str):
        assets["instructions"] = instructions

    worker = node.get("worker")
    if isinstance(worker, dict):
        assets["worker"] = {
            "prompt": str(worker["prompt"]),
            "contract": str(worker["contract"]),
            "mode": str(worker["mode"]),
        }

    assets["receipts"] = normalize_receipts(node)

    produces = node.get("produces") or {}
    artifacts = produces.get("artifacts") or []
    assets["artifacts"] = [artifact for artifact in artifacts if isinstance(artifact, dict)]

    return assets


def collect_node_tests(node_id: str, *, feature_dir: Path, repo_root: Path) -> list[str]:
    if not feature_dir.is_dir():
        return []

    matches: list[str] = []
    for feature_path in sorted(feature_dir.glob("*.feature")):
        text = feature_path.read_text(encoding="utf-8")
        tag = f"@node.{node_id}"
        if tag in text or node_id in text:
            matches.append(str(feature_path.relative_to(repo_root)))
    return sorted(matches)


def build_node_index(
    flow: dict[str, Any],
    *,
    node_id: str,
    flow_id: str,
    foundry_bundle: Path,
    feature_dir: Path | None = None,
) -> dict[str, Any]:
    node = get_node(flow, node_id)
    repo_root = foundry_bundle.parent.parent
    features = feature_dir or (repo_root / DEFAULT_FEATURE_DIR)

    index: dict[str, Any] = {
        "node_id": node_id,
        "flow_id": flow_id,
        "kind": str(node.get("kind", "step")),
        "title": str(node.get("title", node_id)),
        "entry": flow.get("entry") == node_id,
        "terminal": bool(node.get("terminal", False)),
        "assets": _assets_block(node),
        "connections": _node_connections(flow, node_id),
        "checks_used": extract_checks_used(node),
        "tests": collect_node_tests(node_id, feature_dir=features, repo_root=repo_root),
    }

    doc_path = foundry_bundle / "nodes" / node_id / "doc.yaml"
    if doc_path.is_file():
        index["authoring"] = f"registry:nodes/{node_id}/doc.yaml"

    return index


def _default_output_dir(foundry_bundle: Path) -> Path:
    return foundry_bundle / "catalog" / "nodes"


def _write_indexes(indexes: dict[str, dict[str, Any]], output_dir: Path) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for node_id, index in sorted(indexes.items()):
        path = output_dir / f"{node_id}.index.yaml"
        with path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(index, handle, sort_keys=False, allow_unicode=True)
        written.append(str(path))
    return written


def build_catalog(
    *,
    foundry_bundle: Path,
    flow_id: str = "implementation",
    output_dir: Path | None = None,
    node_id: str | None = None,
    json_mode: bool = False,
    feature_dir: Path | None = None,
) -> dict[str, Any]:
    try:
        _, flow = load_registry(foundry_bundle, flow_id=flow_id)
    except (FileNotFoundError, ValueError) as exc:
        return {"ok": False, "error": {"code": "REGISTRY_ERROR", "message": str(exc)}}

    nodes = flow.get("nodes") or []
    node_ids = [str(node["id"]) for node in nodes if isinstance(node, dict) and node.get("id")]

    if node_id:
        if node_id not in node_ids:
            return {
                "ok": False,
                "error": {"code": "NODE_NOT_FOUND", "message": f"Node not found in flow registry: {node_id!r}"},
            }
        target_ids = [node_id]
    else:
        target_ids = node_ids

    repo_root = foundry_bundle.parent.parent
    features = feature_dir or (repo_root / DEFAULT_FEATURE_DIR)
    indexes = {
        target: build_node_index(
            flow,
            node_id=target,
            flow_id=flow_id,
            foundry_bundle=foundry_bundle,
            feature_dir=features,
        )
        for target in target_ids
    }

    destination = output_dir or _default_output_dir(foundry_bundle)
    written: list[str] = []
    if not json_mode:
        written = _write_indexes(indexes, destination)

    result: dict[str, Any] = {
        "ok": True,
        "flow_id": flow_id,
        "node_count": len(indexes),
        "nodes": sorted(indexes.keys()),
    }
    if json_mode:
        result["indexes"] = indexes
    else:
        result["output_dir"] = str(destination)
        result["written"] = written
    return result


def cmd_catalog_build(args) -> dict[str, Any]:
    workspace = Path(args.workspace).resolve()
    try:
        bundle = Path(args.registry).resolve() if args.registry else foundry_root(workspace)
    except FileNotFoundError as exc:
        return {"ok": False, "error": {"code": "REGISTRY_NOT_FOUND", "message": str(exc)}}

    output_dir = Path(args.output).resolve() if args.output else None
    return build_catalog(
        foundry_bundle=bundle,
        flow_id=args.flow or "implementation",
        output_dir=output_dir,
        node_id=args.node,
        json_mode=bool(args.json),
    )
