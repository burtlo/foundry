"""Node runtime matrix inventory for the implementation flow (engine DSL Step 0)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from foundry_cli.constants import DEFAULT_FLOW_ID
from foundry_cli.engine.advance_classifier import (
    _GIT_MECHANICAL_ADVANCE,
    _HOST_ADVANCE,
    _HOST_BOUNDARY_WAIT,
    _TASK_BOUND_ADVANCE,
    _TASK_BOUND_BOUNDARY_WAIT,
    classify_advance_node,
)
from foundry_cli.engine.gate_rules import gate_rules_ref, has_gate_rules
from foundry_cli.engine.node_capability import boundary_status
from foundry_cli.flow_registry import collect_node_registry_refs, load_flow_document, materialize_flow
from foundry_cli.node_view import check_ids_for_hooks, lifecycle_hooks
from foundry_cli.paths import repo_root_from_bundle
from foundry_cli.registry import get_node

_MATRIX_DOC_REL = "docs/generated/engine-node-runtime-matrix.md"

# Node id → Python complete function name (host/task/git mechanical steps).
_NODE_COMPLETE_FN: dict[str, str] = {
    "shape.intake": "run_shape_intake_complete",
    "shape.examine": "run_shape_examine_complete",
    "shape.present": "run_shape_present_complete",
    "shape.record": "run_shape_record_complete",
    "execute.intake": "run_execute_intake_complete",
    "execute.branch": "run_execute_branch_complete",
    "execute.plan": "run_execute_plan_complete",
    "execute.build": "run_execute_build_complete",
    "execute.test": "run_execute_test_complete",
    "execute.commit": "run_execute_commit_complete",
    "verify.intake": "run_verify_intake_complete",
    "verify.acceptance": "run_verify_acceptance_complete",
    "verify.code_quality": "run_verify_code_quality_complete",
    "verify.code_review": "run_verify_code_review_complete",
    "verify.complete": "run_verify_complete_complete",
    "deliver.stub": "run_deliver_stub_complete",
}


@dataclass(frozen=True)
class NodeRuntimeRow:
    node_id: str
    kind: str
    decider: str
    hooks_used: str
    allow_cli: str
    task_file: bool
    operations_yaml: bool
    operations_bound: bool
    python_complete_fn: str
    advance_classifier: str
    gate_resolver: str
    boundary_status: str


def implementation_flow_node_ids(foundry_bundle: Path, flow_id: str = DEFAULT_FLOW_ID) -> list[str]:
    document = load_flow_document(foundry_bundle, flow_id)
    flow = document.get("flow")
    if not isinstance(flow, dict):
        raise ValueError("flow registry missing flow")
    raw_nodes = flow.get("nodes") or []
    if not isinstance(raw_nodes, list):
        raise ValueError("flow.nodes must be a list")
    ids: list[str] = []
    for ref in collect_node_registry_refs(raw_nodes):
        # registry:nodes/<id>/node.yaml
        segment = ref.removeprefix("registry:nodes/").removesuffix("/node.yaml")
        ids.append(segment)
    return ids


def _allow_cli_list(node: dict[str, Any]) -> list[str]:
    allow = node.get("allow")
    if not isinstance(allow, dict):
        return []
    cli = allow.get("cli")
    if not isinstance(cli, list):
        return []
    return [str(item) for item in cli]


def _operations_bound(node: dict[str, Any]) -> bool:
    operations = node.get("operations")
    if operations is None:
        return False
    if isinstance(operations, str) and operations.strip():
        return True
    return False


def _advance_classifier_labels(node_id: str, flow: dict[str, Any], foundry_bundle: Path) -> str:
    labels: list[str] = []
    node_class = classify_advance_node(node_id, flow, foundry_bundle=foundry_bundle)
    labels.append(f"classify:{node_class.value}")
    if node_id in _HOST_ADVANCE:
        labels.append("host_advance")
    if node_id in _HOST_BOUNDARY_WAIT:
        labels.append("host_boundary_wait")
    if node_id in _TASK_BOUND_ADVANCE:
        labels.append("task_bound_advance")
    if node_id in _TASK_BOUND_BOUNDARY_WAIT:
        labels.append("task_bound_boundary_wait")
    if node_id in _GIT_MECHANICAL_ADVANCE:
        labels.append("git_mechanical_advance")
    return ", ".join(labels)


def _gate_resolver_label(node_id: str, node: dict[str, Any], foundry_bundle: Path) -> str:
    if str(node.get("kind")) != "gate":
        return ""
    if str(node.get("decider")) != "engine":
        return ""
    if has_gate_rules(node_id, foundry_bundle):
        return f"`{gate_rules_ref(node_id)}`"
    return "(missing)"


def matrix_warnings(rows: list[NodeRuntimeRow]) -> list[str]:
    warnings: list[str] = []
    for row in rows:
        if row.python_complete_fn == "—":
            continue
        if row.operations_bound:
            continue
        warnings.append(
            f"python-only node without bound operations: {row.node_id} ({row.python_complete_fn})"
        )
    return warnings


def build_node_runtime_row(
    node_id: str,
    flow: dict[str, Any],
    *,
    foundry_bundle: Path,
) -> NodeRuntimeRow:
    node = get_node(flow, node_id)
    hooks = lifecycle_hooks(node)
    hook_ids = check_ids_for_hooks(hooks)
    hooks_summary = ", ".join(hook_ids) if hook_ids else "—"
    cli_cmds = _allow_cli_list(node)
    ops_path = foundry_bundle / "nodes" / node_id / "operations.yaml"
    task_path = foundry_bundle / "tasks" / f"{node_id}.yaml"
    return NodeRuntimeRow(
        node_id=node_id,
        kind=str(node.get("kind") or ""),
        decider=str(node.get("decider") or "—"),
        hooks_used=hooks_summary,
        allow_cli=", ".join(cli_cmds) if cli_cmds else "—",
        task_file=task_path.is_file(),
        operations_yaml=ops_path.is_file(),
        operations_bound=_operations_bound(node),
        python_complete_fn=_NODE_COMPLETE_FN.get(node_id, "—"),
        advance_classifier=_advance_classifier_labels(node_id, flow, foundry_bundle),
        gate_resolver=_gate_resolver_label(node_id, node, foundry_bundle),
        boundary_status=boundary_status(node_id, flow, foundry_bundle=foundry_bundle),
    )


def build_node_runtime_matrix(
    foundry_bundle: Path,
    flow_id: str = DEFAULT_FLOW_ID,
) -> list[NodeRuntimeRow]:
    document = load_flow_document(foundry_bundle, flow_id)
    flow_raw = document.get("flow")
    if not isinstance(flow_raw, dict):
        raise ValueError("flow registry missing flow")
    flow = materialize_flow(flow_raw, foundry_bundle)
    node_ids = implementation_flow_node_ids(foundry_bundle, flow_id)
    return [
        build_node_runtime_row(node_id, flow, foundry_bundle=foundry_bundle) for node_id in node_ids
    ]


def render_node_runtime_matrix_markdown(
    rows: list[NodeRuntimeRow],
    *,
    flow_id: str,
) -> str:
    warnings = matrix_warnings(rows)
    lines = [
        "# Engine node runtime matrix",
        "",
        f"Flow: `{flow_id}`. Generated inventory for [implementation-flow-runtime.md](../features/implementation-flow-runtime.md) (see archived [engine DSL plan](../plans/archive/engine-dsl-orchestration-plan.md)).",
        "",
        "Regenerate: `just engine-matrix` (or `foundry dev engine-matrix`).",
        "",
        "| node_id | kind | decider | hooks (checks) | allow.cli | task.yaml | operations.yaml | ops in node.yaml | python complete | advance_classifier | gate resolver | boundary_status |",
        "|---|---|---|---|---|:---:|:---:|:---:|:---:|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {node_id} | {kind} | {decider} | {hooks} | {cli} | {task} | {ops} | {bound} | {complete} | {advance} | {resolver} | {status} |".format(
                node_id=row.node_id,
                kind=row.kind,
                decider=row.decider,
                hooks=row.hooks_used.replace("|", "\\|"),
                cli=row.allow_cli.replace("|", "\\|"),
                task="yes" if row.task_file else "no",
                ops="yes" if row.operations_yaml else "no",
                bound="yes" if row.operations_bound else "no",
                complete=row.python_complete_fn,
                advance=row.advance_classifier.replace("|", "\\|"),
                resolver=row.gate_resolver or "—",
                status=row.boundary_status,
            )
        )
    if warnings:
        lines.extend(["", "Warnings:", ""])
        for warning in warnings:
            lines.append(f"- {warning}")
    lines.append("")
    return "\n".join(lines)


def default_matrix_output_path(repo_root: Path) -> Path:
    return (repo_root / _MATRIX_DOC_REL).resolve()


def write_node_runtime_matrix(
    foundry_bundle: Path,
    *,
    flow_id: str = DEFAULT_FLOW_ID,
    output_path: Path | None = None,
) -> dict[str, Any]:
    repo_root = repo_root_from_bundle(foundry_bundle)
    dest = output_path or default_matrix_output_path(repo_root)
    rows = build_node_runtime_matrix(foundry_bundle, flow_id)
    markdown = render_node_runtime_matrix_markdown(rows, flow_id=flow_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(markdown, encoding="utf-8")
    return {
        "ok": True,
        "flow_id": flow_id,
        "node_count": len(rows),
        "output_path": str(dest),
        "warnings": matrix_warnings(rows),
    }
