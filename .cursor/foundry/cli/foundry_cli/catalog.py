"""Build machine-readable node index files from the flow registry."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

from foundry_cli.command_context import CommandContext
from foundry_cli.constants import DEFAULT_FLOW_ID, KIND_STEP
from foundry_cli.errors import error, ok
from foundry_cli.engine.registry_refs import validate_registry_instruction_refs
from foundry_cli.flow_helpers import node_connections, normalize_connection
from foundry_cli.flow_registry import docs_catalog_nodes_dir
from foundry_cli.paths import repo_root_from_bundle
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


def _assets_block(node: dict[str, Any]) -> dict[str, Any]:
    assets: dict[str, Any] = {}
    instructions = node.get("instructions")
    if isinstance(instructions, str):
        assets["instructions"] = instructions
    operations = node.get("operations")
    if isinstance(operations, str):
        assets["operations"] = operations

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


def load_feature_texts(feature_dir: Path, repo_root: Path) -> list[tuple[str, str]]:
    """Read each feature file once; return (repo-relative path, text) pairs."""
    if not feature_dir.is_dir():
        return []
    loaded: list[tuple[str, str]] = []
    for feature_path in sorted(feature_dir.glob("*.feature")):
        rel = str(feature_path.relative_to(repo_root)).replace("\\", "/")
        loaded.append((rel, feature_path.read_text(encoding="utf-8")))
    return loaded


def collect_node_tests(
    node_id: str,
    *,
    feature_dir: Path,
    repo_root: Path,
    feature_texts: list[tuple[str, str]] | None = None,
) -> list[str]:
    texts = feature_texts if feature_texts is not None else load_feature_texts(feature_dir, repo_root)
    if not texts:
        return []

    tag = f"@node.{node_id}"
    matches: list[str] = []
    for rel_path, text in texts:
        if tag in text or node_id in text:
            matches.append(rel_path)
    return sorted(matches)


def build_node_index(
    flow: dict[str, Any],
    *,
    node_id: str,
    flow_id: str,
    foundry_bundle: Path,
    feature_dir: Path | None = None,
    feature_texts: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    node = get_node(flow, node_id)
    repo_root = foundry_bundle.parent.parent
    features = feature_dir or (repo_root / DEFAULT_FEATURE_DIR)
    texts = feature_texts
    if texts is None and features.is_dir():
        texts = load_feature_texts(features, repo_root)

    index: dict[str, Any] = {
        "node_id": node_id,
        "flow_id": flow_id,
        "kind": str(node.get("kind", KIND_STEP)),
        "title": str(node.get("title", node_id)),
        "entry": flow.get("entry") == node_id,
        "terminal": bool(node.get("terminal", False)),
        "assets": _assets_block(node),
        "connections": node_connections(flow, node_id),
        "checks_used": extract_checks_used(node),
        "tests": collect_node_tests(
            node_id,
            feature_dir=features,
            repo_root=repo_root,
            feature_texts=texts,
        ),
    }

    doc_path = foundry_bundle / "nodes" / node_id / "doc.yaml"
    if doc_path.is_file():
        index["authoring"] = f"registry:nodes/{node_id}/doc.yaml"

    return index


def default_catalog_output_dir(foundry_bundle: Path, flow_id: str) -> Path:
    repo_root = repo_root_from_bundle(foundry_bundle)
    return docs_catalog_nodes_dir(repo_root, flow_id)


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
        document, flow = load_registry(foundry_bundle, flow_id=flow_id)
    except (FileNotFoundError, ValueError) as exc:
        return error("REGISTRY_ERROR", str(exc))

    raw_flow = document.get("flow")
    ref_result = validate_registry_instruction_refs(
        flow,
        foundry_bundle,
        raw_flow=raw_flow if isinstance(raw_flow, dict) else None,
    )
    if not ref_result.get("ok"):
        return error(
            str(ref_result.get("code", "REFERENCE_NOT_FOUND")),
            str(ref_result.get("message", "Unresolved registry instruction references")),
            missing=ref_result.get("missing") or [],
        )

    nodes = flow.get("nodes") or []
    node_ids = [str(node["id"]) for node in nodes if isinstance(node, dict) and node.get("id")]

    if node_id:
        if node_id not in node_ids:
            return error("NODE_NOT_FOUND", f"Node not found in flow registry: {node_id!r}")
        target_ids = [node_id]
    else:
        target_ids = node_ids

    repo_root = foundry_bundle.parent.parent
    features = feature_dir or (repo_root / DEFAULT_FEATURE_DIR)
    feature_texts = load_feature_texts(features, repo_root) if features.is_dir() else []
    indexes = {
        target: build_node_index(
            flow,
            node_id=target,
            flow_id=flow_id,
            foundry_bundle=foundry_bundle,
            feature_dir=features,
            feature_texts=feature_texts,
        )
        for target in target_ids
    }

    written: list[str] = []
    output_dirs: list[Path] = []
    if not json_mode:
        if output_dir is not None:
            output_dirs = [output_dir]
        else:
            output_dirs = [default_catalog_output_dir(foundry_bundle, flow_id)]
        for destination in output_dirs:
            written.extend(_write_indexes(indexes, destination))

    fields: dict[str, Any] = {
        "flow_id": flow_id,
        "node_count": len(indexes),
        "nodes": sorted(indexes.keys()),
    }
    if json_mode:
        fields["indexes"] = indexes
    else:
        fields["output_dirs"] = [str(path) for path in output_dirs]
        if len(output_dirs) == 1:
            fields["output_dir"] = str(output_dirs[0])
        fields["written"] = written
    return ok(**fields)


def cmd_catalog_build(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    output_dir = Path(args.output).resolve() if args.output else None
    return build_catalog(
        foundry_bundle=ctx.bundle,
        flow_id=args.flow or DEFAULT_FLOW_ID,
        output_dir=output_dir,
        node_id=args.node,
        json_mode=bool(args.json),
    )
