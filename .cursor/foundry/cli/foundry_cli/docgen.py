"""Generate node, worker, and index documentation from registry artifacts."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import yaml

from foundry_cli.paths import resolve_registry_path
from foundry_cli.registry import get_node, normalize_receipts

LEDGER_FIXTURE_DIR = "porcelain-0007-v001"
LEDGER_FIXTURE_VISIT = "v-001"

CONCEPT_DOCS: list[tuple[str, str]] = [
    ("README.md", "Concepts index"),
    ("graph.md", "Graph invariants, nodes, and connections"),
    ("visits-lifecycle.md", "Visit lifecycle and hooks"),
    ("artifacts.md", "Artifacts, publication, and receipts"),
    ("control-plane.md", "Checks, policies, and actions"),
    ("capabilities.md", "Reads, allow, and paths"),
    ("registry.md", "Integrated registry example"),
    ("run-record.md", "Ledger and run persistence"),
    ("engine.md", "Engine procedure"),
    ("expressions.md", "Expression language"),
    ("validation.md", "Structural and semantic validation"),
]


def rel_link(from_file: Path, target: Path, label: str | None = None) -> str:
    """Markdown link from a generated doc file to a repo path."""
    from_dir = from_file.parent
    try:
        href = os.path.relpath(target.resolve(), from_dir.resolve())
    except ValueError:
        href = str(target)
    text = label if label is not None else str(target.name)
    return f"[{text}]({Path(href).as_posix()})"


def registry_link(ref: str, foundry_bundle: Path, from_file: Path, label: str | None = None) -> str:
    path = resolve_registry_path(ref, foundry_bundle)
    text = label if label is not None else ref
    return rel_link(from_file, path, text)


def concept_link(
    from_file: Path,
    repo_root: Path,
    concept_file: str,
    label: str | None = None,
) -> str:
    target = repo_root / "docs" / "concepts" / concept_file
    text = label if label is not None else concept_file
    return rel_link(from_file, target, text)


def _node_concepts_section(
    node: dict[str, Any],
    kind: str,
    from_file: Path,
    repo_root: Path,
    check_ids: list[str],
) -> str:
    links: list[str] = []
    links.append(
        f"- **Lifecycle:** {concept_link(from_file, repo_root, 'visits-lifecycle.md', 'Visit lifecycle')}"
    )
    links.append(
        f"- **Connections:** {concept_link(from_file, repo_root, 'graph.md', 'Graph and routing')}"
    )
    reads = node.get("reads")
    allow = node.get("allow")
    if reads or allow:
        links.append(
            f"- **Permissions:** {concept_link(from_file, repo_root, 'capabilities.md', 'Reads and allow')}"
        )
    artifacts = (node.get("produces") or {}).get("artifacts") or []
    if artifacts:
        links.append(
            f"- **Artifacts:** {concept_link(from_file, repo_root, 'artifacts.md', 'Artifact publication')}"
        )
    if normalize_receipts(node):
        links.append(
            f"- **Receipts:** {concept_link(from_file, repo_root, 'artifacts.md', 'Receipts vs artifacts')}"
        )
    if check_ids:
        links.append(
            f"- **Checks:** {concept_link(from_file, repo_root, 'control-plane.md', 'Control plane')}"
        )
    if kind == "gate":
        links.append(
            f"- **Gate decisions:** {concept_link(from_file, repo_root, 'graph.md', 'Gate nodes')}"
        )
    return "\n".join(links)


def node_page_href(node_id: str, from_file: Path) -> str:
    target = from_file.parent / f"{node_id}.md"
    return rel_link(from_file, target, node_id)


def cli_capability_link(cap_id: str, from_file: Path) -> str:
    return f"`{cap_id}`"


def load_node_annotations(node_id: str, foundry_bundle: Path) -> dict[str, Any] | None:
    path = foundry_bundle / "nodes" / node_id / "doc.yaml"
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data if isinstance(data, dict) else None


def _list_or_empty(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _node_connections(flow: dict[str, Any], node_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    incoming: list[dict[str, Any]] = []
    outgoing: list[dict[str, Any]] = []
    for conn in flow.get("connections") or []:
        if not isinstance(conn, dict):
            continue
        if conn.get("from") == node_id:
            outgoing.append(conn)
        if conn.get("to") == node_id:
            incoming.append(conn)
    return incoming, outgoing


def _lifecycle_hooks(node: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    lifecycle = node.get("lifecycle") or {}
    hooks: dict[str, list[dict[str, Any]]] = {}
    for hook in ("on_examine", "on_open", "on_close", "on_seal"):
        entries = lifecycle.get(hook)
        if entries is None:
            hooks[hook] = []
        elif isinstance(entries, list):
            hooks[hook] = [entry for entry in entries if isinstance(entry, dict)]
        else:
            hooks[hook] = []
    return hooks


def _check_ids_for_hooks(hooks: dict[str, list[dict[str, Any]]]) -> list[str]:
    ids: list[str] = []
    for entries in hooks.values():
        for entry in entries:
            check_id = entry.get("check")
            if isinstance(check_id, str) and check_id not in ids:
                ids.append(check_id)
    return ids


def _check_definition(flow: dict[str, Any], check_id: str) -> dict[str, Any] | None:
    checks = flow.get("checks") or {}
    if not isinstance(checks, dict):
        return None
    body = checks.get(check_id)
    if not isinstance(body, dict):
        return None
    return body


def _outgoing_target_names(outgoing: list[dict[str, Any]]) -> list[str]:
    targets: list[str] = []
    for conn in outgoing:
        target = conn.get("to")
        if isinstance(target, str) and target not in targets:
            targets.append(target)
    return targets


def build_lifecycle_mermaid(
    node_id: str,
    hooks: dict[str, list[dict[str, Any]]],
    outgoing: list[dict[str, Any]],
) -> str:
    on_open_checks = [e.get("check", "") for e in hooks.get("on_open", []) if e.get("check")]
    on_seal_checks = [e.get("check", "") for e in hooks.get("on_seal", []) if e.get("check")]
    route_targets = _outgoing_target_names(outgoing)
    route_label = ", ".join(route_targets) if route_targets else "next node"

    on_open_label = "\\n".join(on_open_checks) if on_open_checks else "(none)"
    on_seal_label = "\\n".join(on_seal_checks) if on_seal_checks else "(none)"

    lines = [
        "stateDiagram-v2",
        "  direction LR",
        "",
        "  [*] --> examined: visit.admitted",
        "",
        f"  examined --> opened: on_open\\n{on_open_label}",
        "  note right of opened",
        "    pass → continue → opened",
        "    fail → halt (default policy)",
        "  end note",
        "",
        "  opened --> closed: steward transition\\non_close (engine checks)",
        "  note right of closed",
        "    Engine verifies artifact completeness",
        "  end note",
        "",
        f"  closed --> sealed: on_seal\\n{on_seal_label}",
        "  note right of sealed",
        "    checks pass → sealed, outcome completed",
        "    fail → reopen (closed → opened)",
        "  end note",
        "",
        f"  sealed --> [*]: connection.taken\\n→ {route_label}",
        "  sealed --> opened: reopen\\n(same visit_id)",
    ]
    return "\n".join(lines)


def _hooks_table(hooks: dict[str, list[dict[str, Any]]]) -> str:
    rows = [
        "| Hook | Authored checks | Engine-implicit |",
        "|---|---|---|",
    ]
    for hook in ("on_examine", "on_open", "on_close", "on_seal"):
        entries = hooks.get(hook, [])
        check_names = ", ".join(f"`{e.get('check')}`" for e in entries if e.get("check"))
        if not check_names:
            check_names = "*(empty)*"
        implicit = "—"
        if hook == "on_close":
            implicit = "Declared artifact completeness"
        rows.append(f"| `{hook}` | {check_names} | {implicit} |")
    return "\n".join(rows)


def _reads_table(node: dict[str, Any]) -> str:
    reads = node.get("reads") or {}
    rows = [
        "| Namespace | Paths |",
        "|---|---|",
    ]
    for namespace in ("config", "state", "files"):
        keys = _list_or_empty(reads.get(namespace))
        if keys:
            rows.append(f"| `{namespace}` | {', '.join(f'`{k}`' for k in keys)} |")
    artifacts = reads.get("artifacts") or []
    if artifacts:
        artifact_refs = []
        for item in artifacts:
            if isinstance(item, dict) and item.get("artifact"):
                artifact_refs.append(f"`{item['artifact']}`")
        if artifact_refs:
            rows.append(f"| `artifacts` | {', '.join(artifact_refs)} |")
    if len(rows) == 2:
        rows.append("| — | *(none declared)* |")
    return "\n".join(rows)


def _allow_table(node: dict[str, Any], node_id: str, from_file: Path) -> str:
    allow = node.get("allow") or {}
    rows = [
        "| Namespace | Grant | Purpose |",
        "|---|---|---|",
    ]
    state_keys = _list_or_empty(allow.get("state"))
    implicit = f"state.nodes.{node_id}.*"
    if implicit not in state_keys:
        state_keys = [*state_keys, implicit]
    if state_keys:
        rows.append(
            f"| `state` | {', '.join(f'`{k}`' for k in state_keys)} | Domain fields |"
        )
    files_write = _list_or_empty((allow.get("files") or {}).get("write"))
    if files_write:
        rows.append(
            f"| `files.write` | {', '.join(f'`{u}`' for u in files_write)} | Writable run paths |"
        )
    cli_caps = _list_or_empty(allow.get("cli"))
    if cli_caps:
        cap_links = ", ".join(f"`{cap}`" for cap in cli_caps)
        rows.append(f"| `cli` | {cap_links} | Steward CLI capabilities |")
    worker = node.get("worker")
    if isinstance(worker, dict):
        rows.append("| `worker` | bound worker | Authorized without `allow.agents` |")
    if len(rows) == 2:
        rows.append("| — | *(none declared)* | — |")
    return "\n".join(rows)


def _check_catalog_section(
    flow: dict[str, Any],
    check_ids: list[str],
    hooks: dict[str, list[dict[str, Any]]],
    from_file: Path,
    foundry_bundle: Path,
) -> str:
    if not check_ids:
        return "_No authored lifecycle checks._\n"

    hook_for: dict[str, str] = {}
    for hook, entries in hooks.items():
        for entry in entries:
            check_id = entry.get("check")
            if isinstance(check_id, str):
                hook_for[check_id] = hook

    sections: list[str] = []
    for check_id in check_ids:
        body = _check_definition(flow, check_id) or {}
        hook = hook_for.get(check_id, "—")
        sections.append(f"### `{check_id}`\n")
        sections.append("| Property | Value |")
        sections.append("|---|---|")
        if "command" in body:
            sections.append(f"| **Body** | `command: {body['command']}` |")
            if check_id == "validate-manifest":
                manifest_schema = foundry_bundle / "schemas" / "app-manifest.schema.json"
                sections.append(
                    f"| **Probe** | `foundry app validate` "
                    f"({rel_link(from_file, manifest_schema, 'app-manifest.schema.json')}) |"
                )
        elif "when" in body:
            expr = str(body["when"]).replace("\n", " ")
            sections.append(f"| **Body** | `when` |")
            sections.append(f"| **Expression** | `{expr}` |")
        sections.append(f"| **Hook** | `{hook}` |")
        for entry in hooks.get(hook, []):
            if entry.get("check") == check_id:
                on_fail = entry.get("on_fail")
                if isinstance(on_fail, dict):
                    action = on_fail.get("action", "—")
                    reason = on_fail.get("reason", "")
                    sections.append(f"| **on_fail** | `{action}` — {reason} |")
        sections.append("")
    return "\n".join(sections)


def _artifacts_section(
    node: dict[str, Any],
    node_id: str,
    flow: dict[str, Any],
    from_file: Path,
    foundry_bundle: Path,
) -> str:
    produces = node.get("produces") or {}
    artifacts = produces.get("artifacts") or []
    if not artifacts:
        return "_No work artifacts declared._\n"

    lines: list[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        artifact_id = artifact.get("id", "artifact")
        lines.append(f"### Work artifact: `{artifact_id}`\n")
        lines.append("| Field | Value |")
        lines.append("|---|---|")
        lines.append(f"| **Logical id** | `{artifact_id}` |")
        qualified_ref = f"{node_id}.{artifact_id}"
        lines.append(f"| **Qualified ref** | `{qualified_ref}` |")
        if artifact.get("kind"):
            lines.append(f"| **Kind** | `{artifact['kind']}` |")
        if artifact.get("uri"):
            lines.append(f"| **URI** | `{artifact['uri']}` |")
        schema = artifact.get("schema")
        if isinstance(schema, str):
            lines.append(f"| **Schema** | {registry_link(schema, foundry_bundle, from_file, schema)} |")
        if artifact.get("media_type"):
            lines.append(f"| **Media type** | `{artifact['media_type']}` |")
        lines.append("")
        if isinstance(schema, str) and artifact_id == "ticket" and "ticket.schema.json" in schema:
            lines.append(_ticket_fields_table(schema, foundry_bundle))

    lines.append(_downstream_consumption_section(flow, node_id, node, from_file))
    return "\n".join(lines)


def _receipts_section(node: dict[str, Any], from_file: Path, foundry_bundle: Path) -> str:
    receipts = normalize_receipts(node)
    if not receipts:
        return "_No receipts declared._\n"

    lines = [
        "| Schema | Role |",
        "|---|---|",
    ]
    for ref in receipts:
        role = "Evidence receipt"
        if "intake-receipt" in ref:
            role = "Intake evidence (`intake-receipt-sealed` on `on_seal`)"
        elif "agent-receipt" in ref:
            role = "Worker completion evidence (`agent-receipt-sealed` on `on_seal`)"
        lines.append(f"| {registry_link(ref, foundry_bundle, from_file, ref)} | {role} |")
    lines.append("")
    return "\n".join(lines)


def _worker_section(
    node: dict[str, Any],
    from_file: Path,
    foundry_bundle: Path,
    output_nodes_dir: Path,
    annotations: dict[str, Any] | None,
) -> str:
    worker = node.get("worker")
    if not isinstance(worker, dict):
        return "_No worker bound._\n"

    prompt = str(worker.get("prompt", ""))
    contract = str(worker.get("contract", ""))
    mode = str(worker.get("mode", ""))
    worker_id = _worker_id_from_contract(contract)

    lines = [
        "| Field | Value |",
        "|---|---|",
        f"| **Worker id** | `{worker_id}` |",
        f"| **Mode** | `{mode}` |",
        f"| **Prompt** | {registry_link(prompt, foundry_bundle, from_file, prompt)} |",
        f"| **Contract** | {registry_link(contract, foundry_bundle, from_file, contract)} |",
    ]
    worker_doc = output_nodes_dir.parent / "catalog" / "workers" / f"{worker_id}.md"
    if worker_doc.exists() or worker_id:
        lines.append(
            f"| **Generated worker doc** | {rel_link(from_file, worker_doc, worker_id)} |"
        )
    lines.append("")
    concern_table = _worker_concern_table(annotations, node, worker_id)
    if concern_table:
        lines.extend(["#### Worker concern ownership", "", concern_table])
    return "\n".join(lines)


def _connections_section(
    node_id: str,
    incoming: list[dict[str, Any]],
    outgoing: list[dict[str, Any]],
    from_file: Path,
    flow: dict[str, Any],
) -> str:
    lines: list[str] = []

    lines.append("### Incoming\n")
    if node_id == flow.get("entry"):
        lines.append("- Flow entry (`flow.entry`)")
    if not incoming and node_id != flow.get("entry"):
        lines.append("_No incoming connections._")
    else:
        for conn in incoming:
            conn_id = conn.get("id", "—")
            source = conn.get("from", "—")
            loop = conn.get("loop")
            extra = f", loop: `{loop}`" if loop else ""
            lines.append(
                f"- `{conn_id}`: {node_page_href(str(source), from_file)} → **{node_id}**{extra}"
            )
    lines.append("")

    lines.append("### Outgoing\n")
    if not outgoing:
        lines.append("_No outgoing connections._")
    else:
        for conn in outgoing:
            conn_id = conn.get("id", "—")
            target = conn.get("to", "—")
            outcomes = (conn.get("on") or {}).get("outcomes") or []
            outcome_text = f" (`on.outcomes: {outcomes}`)" if outcomes else ""
            lines.append(
                f"- `{conn_id}`: **{node_id}** → {node_page_href(str(target), from_file)}{outcome_text}"
            )
    lines.append("")
    return "\n".join(lines)


def _worker_id_from_contract(contract_ref: str) -> str:
    match = re.search(r"workers/([^/]+)/", contract_ref)
    return match.group(1) if match else contract_ref


def _load_schema_json(schema_ref: str, foundry_bundle: Path) -> dict[str, Any] | None:
    path = resolve_registry_path(schema_ref, foundry_bundle)
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as handle:
        loaded = json.load(handle)
    return loaded if isinstance(loaded, dict) else None


def _ticket_fields_table(schema_ref: str, foundry_bundle: Path) -> str:
    schema = _load_schema_json(schema_ref, foundry_bundle)
    if not schema:
        return ""

    required = set(schema.get("required") or [])
    properties = schema.get("properties") or {}
    if not isinstance(properties, dict):
        return ""

    rows = [
        "",
        "#### Ticket fields",
        "",
        "| Field | Required | Description |",
        "|---|---|:---:|",
    ]
    for field_name, field_body in properties.items():
        if not isinstance(field_body, dict):
            continue
        is_required = "yes" if field_name in required else "no"
        description = str(field_body.get("description", "")).replace("|", "\\|")
        const = field_body.get("const")
        if const is not None:
            description = f"{description} (`{const}`)" if description else f"`{const}`"
        rows.append(f"| `{field_name}` | {is_required} | {description or '—'} |")
    rows.append("")
    return "\n".join(rows)


def _qualified_artifact_refs(node_id: str, node: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for artifact in (node.get("produces") or {}).get("artifacts") or []:
        if isinstance(artifact, dict) and artifact.get("id"):
            refs.append(f"{node_id}.{artifact['id']}")
    return refs


def _downstream_consumption_section(
    flow: dict[str, Any],
    node_id: str,
    node: dict[str, Any],
    from_file: Path,
) -> str:
    qualified_refs = _qualified_artifact_refs(node_id, node)
    if not qualified_refs:
        return ""

    consumers: list[tuple[str, str, str]] = []
    for flow_node in flow.get("nodes") or []:
        if not isinstance(flow_node, dict):
            continue
        consumer_id = flow_node.get("id")
        if not isinstance(consumer_id, str) or consumer_id == node_id:
            continue
        for item in (flow_node.get("reads") or {}).get("artifacts") or []:
            if not isinstance(item, dict):
                continue
            artifact_ref = item.get("artifact")
            if isinstance(artifact_ref, str) and artifact_ref in qualified_refs:
                source = str(item.get("from", "—"))
                consumers.append((consumer_id, artifact_ref, source))

    if not consumers:
        return ""

    lines = [
        "#### Downstream consumption",
        "",
    ]
    for consumer_id, artifact_ref, source in sorted(consumers):
        lines.append(
            f"- {node_page_href(consumer_id, from_file)} reads `{artifact_ref}` "
            f"via `{source}`"
        )
    lines.append("")
    return "\n".join(lines)


def _engine_only_surfaces_section(
    flow: dict[str, Any],
    node: dict[str, Any],
    hooks: dict[str, list[dict[str, Any]]],
    outgoing: list[dict[str, Any]],
    from_file: Path,
) -> str:
    cli_caps = set(_list_or_empty((node.get("allow") or {}).get("cli")))
    rows = [
        "| Surface | Trigger | Maps to |",
        "|---|---|---|",
    ]

    if "run.create" not in cli_caps:
        rows.append("| `foundry run create` | New run bootstrap | Admit entry visit, run `on_open` |")

    for hook, entries in hooks.items():
        for entry in entries:
            check_id = entry.get("check")
            if isinstance(check_id, str) and check_id not in cli_caps:
                maps_to = f"`{hook}` check `{check_id}`"
                if check_id == "validate-manifest":
                    maps_to = "`command: validate_manifest` → `foundry app validate`"
                rows.append(f"| `{check_id}` | `{hook}` hook | {maps_to} |")

    if not hooks.get("on_close"):
        rows.append(
            "| Artifact completeness | `close_request` before `closed` | "
            "Every `produces.artifacts` declaration satisfied |"
        )

    route_targets = _outgoing_target_names(outgoing)
    if route_targets:
        route_label = ", ".join(f"`{target}`" for target in route_targets)
        rows.append(
            f"| Connection selection | After `visit.sealed` | Routes to {route_label} |"
        )

    if len(rows) == 2:
        return "_No engine-only surfaces beyond standard lifecycle._\n"

    return "\n".join(rows) + "\n"


def _catalog_index_link(node_id: str, foundry_bundle: Path, from_file: Path) -> str | None:
    index_path = foundry_bundle / "catalog" / "nodes" / f"{node_id}.index.yaml"
    if index_path.is_file():
        return rel_link(from_file, index_path, f"{node_id}.index.yaml")
    return None


def _worker_concern_table(
    annotations: dict[str, Any] | None,
    node: dict[str, Any],
    worker_id: str,
) -> str:
    ownership = (annotations or {}).get("ownership") or {}
    engine_owner = ownership.get("engine", "Engine")
    steward_owner = ownership.get("steward", "Steward")
    worker_owner = ownership.get("worker", worker_id)

    rows = [
        "| Concern | Owner |",
        "|---|---|",
        f"| `on_examine` / `on_open` / `on_seal` checks | {engine_owner} |",
        f"| Intake receipt `checks[]` | {steward_owner} — from ledger when sealing |",
        f"| Work artifact publication | {steward_owner} — `artifact.publish` |",
        f"| Receipts | {steward_owner} — `receipt.link` |",
        f"| Worker assessment and proceed/blocked judgment | {worker_owner} |",
    ]

    if not node.get("worker"):
        return ""

    return "\n".join(rows) + "\n"


def _ledger_event_summary(event: dict[str, Any]) -> str:
    event_type = str(event.get("type", ""))
    payload = event.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}

    if event_type == "run.status_changed":
        prior = payload.get("prior_status", "new")
        new = payload.get("new_status", "running")
        return f"{new} ← ({prior})"
    if event_type == "visit.admitted":
        return f"source: {payload.get('source', 'entry')}"
    if event_type == "lifecycle.changed":
        return f"{payload.get('from')} → {payload.get('to')}"
    if event_type == "check.recorded":
        hook = payload.get("hook", "")
        check_id = payload.get("check_id", payload.get("check", ""))
        result = payload.get("result", "")
        return f"{hook}: {check_id} → {result}"
    if event_type == "policy.applied":
        check_id = payload.get("check_id", payload.get("check", ""))
        action = payload.get("action", "")
        return f"{check_id} → {action}"
    if event_type == "artifact.linked":
        artifact_id = payload.get("artifact_id", payload.get("artifact", ""))
        uri = payload.get("uri", "")
        if uri:
            return f"{artifact_id} → {uri}"
        return str(artifact_id)
    if event_type == "receipt.linked":
        schema = payload.get("schema", payload.get("path", ""))
        return str(schema).split("/")[-1]
    if event_type == "visit.sealed":
        return f"outcome: {payload.get('outcome', 'completed')}"
    if event_type == "connection.taken":
        connection_id = payload.get("connection_id", "")
        target = payload.get("to_node_id", payload.get("target", ""))
        if connection_id and target:
            return f"{connection_id} → {target}"
        return str(connection_id or target)
    return event_type


def _load_fixture_ledger(foundry_bundle: Path) -> list[dict[str, Any]] | None:
    snapshot_path = foundry_bundle / "fixtures" / "runs" / LEDGER_FIXTURE_DIR / "snapshot.json"
    if not snapshot_path.is_file():
        return None
    with snapshot_path.open(encoding="utf-8") as handle:
        snapshot = json.load(handle)
    ledger = snapshot.get("ledger")
    if not isinstance(ledger, list):
        return None
    return [event for event in ledger if isinstance(event, dict)]


def _ledger_events_for_visit(
    ledger: list[dict[str, Any]],
    *,
    visit_id: str,
    node_id: str,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for event in sorted(ledger, key=lambda item: int(item.get("seq", 0))):
        event_visit = event.get("visit_id")
        event_node = event.get("node_id")
        if event.get("type") == "run.status_changed" and event_visit is None:
            events.append(event)
            continue
        if event_visit == visit_id and event_node == node_id:
            events.append(event)
    return events


def _ledger_excerpt_section(node_id: str, foundry_bundle: Path) -> str:
    if node_id != "shape.intake":
        return ""

    ledger = _load_fixture_ledger(foundry_bundle)
    if not ledger:
        return ""

    events = _ledger_events_for_visit(
        ledger,
        visit_id=LEDGER_FIXTURE_VISIT,
        node_id=node_id,
    )
    if not events:
        return ""

    lines = [
        f"Fixture `{LEDGER_FIXTURE_DIR}` visit `{LEDGER_FIXTURE_VISIT}` (compact).",
        "",
        "| seq | type | summary |",
        "|---:|---|---|",
    ]
    for event in events:
        seq = event.get("seq", "—")
        event_type = event.get("type", "—")
        summary = _ledger_event_summary(event).replace("|", "\\|")
        lines.append(f"| {seq} | `{event_type}` | {summary} |")
    lines.append("")
    return "\n".join(lines)


def build_node_doc(
    node_id: str,
    flow: dict[str, Any],
    foundry_bundle: Path,
    repo_root: Path,
    *,
    output_nodes_dir: Path | None = None,
) -> str:
    """Build markdown documentation for a single flow node."""
    node = get_node(flow, node_id)
    annotations = load_node_annotations(node_id, foundry_bundle)
    nodes_dir = output_nodes_dir or (repo_root / "docs" / "nodes")
    from_file = nodes_dir / f"{node_id}.md"

    kind = str(node.get("kind", "step"))
    title = str(node.get("title", node_id))
    status = (annotations or {}).get("status", "generated")
    summary = (annotations or {}).get("summary") or title

    hooks = _lifecycle_hooks(node)
    check_ids = _check_ids_for_hooks(hooks)
    incoming, outgoing = _node_connections(flow, node_id)

    flow_link = rel_link(from_file, foundry_bundle / "flows" / "factory-flow.yaml", "factory-flow.yaml")

    lines: list[str] = [
        f"# Node: `{node_id}`",
        "",
        f"Status: **{status}**",
        "",
        f"Flow: `{flow.get('id', 'implementation')}` in {flow_link}.",
        "",
        f"{summary}",
        "",
    ]

    # Table of contents for full docs (shape.intake and annotated nodes)
    is_full = annotations is not None or node_id == "shape.intake"
    if is_full:
        lines.extend(
            [
                "## Contents",
                "",
                "- [Lifecycle](#lifecycle)",
                "- [Sequence](#sequence)",
                "- [Ledger excerpt](#ledger-excerpt)",
                "- [References](#references)",
                "- [Permissions](#permissions)",
                "- [Artifacts](#artifacts)",
                "- [Receipts](#receipts)",
                "- [Worker](#worker)",
                "- [Connections](#connections)",
                "- [Check catalog](#check-catalog)",
                "- [Gaps](#gaps)",
                "",
                "---",
                "",
            ]
        )

    lines.extend(["## Lifecycle", ""])
    lines.append(
        f"Admission is an event (`visit.admitted`), not a lifecycle state. "
        f"See {concept_link(from_file, repo_root, 'visits-lifecycle.md', 'visit lifecycle')}."
    )
    lines.append("")
    lines.append("```mermaid")
    lines.append(build_lifecycle_mermaid(node_id, hooks, outgoing))
    lines.append("```")
    lines.append("")
    lines.append(_hooks_table(hooks))
    lines.append("")

    if is_full:
        lines.extend(["## Sequence", ""])
        sequence = (annotations or {}).get("sequence")
        if sequence:
            lines.append(str(sequence).strip())
            lines.append("")
        else:
            lines.append("_Sequence diagram not authored in `doc.yaml`._")
            lines.append("")

        ledger_excerpt = _ledger_excerpt_section(node_id, foundry_bundle)
        if ledger_excerpt:
            lines.extend(["## Ledger excerpt", "", ledger_excerpt])

    lines.extend(["## References", ""])
    instructions = node.get("instructions")
    if isinstance(instructions, str):
        lines.append(
            f"- **Instructions:** {registry_link(instructions, foundry_bundle, from_file, instructions)}"
        )
    prompt = node.get("prompt")
    if isinstance(prompt, str):
        lines.append(f"- **Gate prompt:** `{prompt}`")

    schemas: set[str] = set()
    for artifact in (node.get("produces") or {}).get("artifacts") or []:
        if isinstance(artifact, dict) and isinstance(artifact.get("schema"), str):
            schemas.add(artifact["schema"])
    for receipt in normalize_receipts(node):
        schemas.add(receipt)

    if schemas:
        lines.append("- **Schemas:**")
        for schema in sorted(schemas):
            lines.append(f"  - {registry_link(schema, foundry_bundle, from_file, schema)}")
    catalog_link = _catalog_index_link(node_id, foundry_bundle, from_file)
    if catalog_link:
        lines.append(f"- **Catalog index:** {catalog_link}")
    lines.append("")

    ownership = (annotations or {}).get("ownership")
    if isinstance(ownership, dict) and ownership:
        lines.extend(["## Ownership", "", "| Role | Owner |", "|---|---|"])
        for role, owner in ownership.items():
            lines.append(f"| **{role}** | {owner} |")
        lines.append("")

    if is_full:
        lines.extend(["## Permissions", "", "### `reads`", "", _reads_table(node), ""])
        lines.extend(["### `allow`", "", _allow_table(node, node_id, from_file), ""])
        cli_caps = _list_or_empty((node.get("allow") or {}).get("cli"))
        if cli_caps:
            lines.extend(["### Steward CLI capabilities", ""])
            lines.append("| Capability |")
            lines.append("|---|")
            for cap in cli_caps:
                lines.append(f"| `{cap}` |")
            lines.append("")
        lines.extend(["### Engine-only surfaces", ""])
        lines.append(_engine_only_surfaces_section(flow, node, hooks, outgoing, from_file))

    lines.extend(
        ["## Artifacts", "", _artifacts_section(node, node_id, flow, from_file, foundry_bundle)]
    )
    lines.extend(["## Receipts", "", _receipts_section(node, from_file, foundry_bundle)])

    if kind == "step":
        lines.extend(
            [
                "## Worker",
                "",
                _worker_section(node, from_file, foundry_bundle, nodes_dir, annotations),
            ]
        )

    lines.extend(
        [
            "## Connections",
            "",
            _connections_section(node_id, incoming, outgoing, from_file, flow),
        ]
    )

    if is_full and check_ids:
        lines.extend(
            [
                "## Check catalog",
                "",
                _check_catalog_section(flow, check_ids, hooks, from_file, foundry_bundle),
            ]
        )

    gaps = (annotations or {}).get("gaps")
    if gaps:
        lines.extend(["## Gaps", ""])
        for gap in gaps:
            lines.append(f"- {gap}")
        lines.append("")

    lines.extend(
        [
            "## Concepts",
            "",
            _node_concepts_section(node, kind, from_file, repo_root, check_ids),
            "",
        ]
    )

    # Node summary table
    lines.extend(["## Node summary", ""])
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append(f"| **id** | `{node_id}` |")
    lines.append(f"| **kind** | `{kind}` |")
    lines.append(f"| **title** | {title} |")
    if node_id == flow.get("entry"):
        lines.append(f"| **entry point** | Yes — `flow.entry` |")
    if node.get("terminal"):
        lines.append(f"| **terminal** | Yes |")
    lines.append("")

    return "\n".join(lines)


def build_worker_doc(
    worker_id: str,
    *,
    contract_ref: str,
    prompt_ref: str,
    foundry_bundle: Path,
    repo_root: Path,
    nodes_using: list[str],
    output_workers_dir: Path,
) -> str:
    from_file = output_workers_dir / f"{worker_id}.md"
    contract_path = resolve_registry_path(contract_ref, foundry_bundle)
    contract_data: dict[str, Any] = {}
    if contract_path.is_file():
        with contract_path.open(encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
            if isinstance(loaded, dict):
                contract_data = loaded

    lines = [
        f"# Worker: `{worker_id}`",
        "",
        f"**Prompt:** {registry_link(prompt_ref, foundry_bundle, from_file, prompt_ref)}",
        "",
        f"**Contract:** {registry_link(contract_ref, foundry_bundle, from_file, contract_ref)}",
        "",
    ]

    capabilities = _list_or_empty(contract_data.get("capabilities"))
    if capabilities:
        lines.extend(["## Capabilities", ""])
        for cap in capabilities:
            lines.append(f"- `{cap}`")
        lines.append("")

    required = _list_or_empty(contract_data.get("required_output_fields"))
    if required:
        lines.extend(["## Required output fields", ""])
        for field in required:
            lines.append(f"- `{field}`")
        lines.append("")

    modes = contract_data.get("modes")
    if isinstance(modes, dict) and modes:
        lines.extend(["## Modes", ""])
        for mode_name, mode_body in modes.items():
            lines.append(f"### `{mode_name}`")
            if isinstance(mode_body, dict):
                next_states = _list_or_empty(mode_body.get("valid_next_states"))
                if next_states:
                    lines.append(f"- **valid_next_states:** {', '.join(f'`{s}`' for s in next_states)}")
            lines.append("")

    if nodes_using:
        lines.extend(["## Used by nodes", ""])
        nodes_dir = output_workers_dir.parent.parent / "nodes"
        for node_id in nodes_using:
            lines.append(f"- {rel_link(from_file, nodes_dir / f'{node_id}.md', node_id)}")
        lines.append("")

    return "\n".join(lines)


def _mermaid_node_id(node_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", node_id)


def build_flow_connections_mermaid(flow: dict[str, Any]) -> str:
    connections = flow.get("connections") or []
    node_ids: set[str] = set()
    for conn in connections:
        if not isinstance(conn, dict):
            continue
        source = conn.get("from")
        target = conn.get("to")
        if isinstance(source, str):
            node_ids.add(source)
        if isinstance(target, str):
            node_ids.add(target)

    lines = ["flowchart TD", ""]
    for node_id in sorted(node_ids):
        lines.append(f'  {_mermaid_node_id(node_id)}["{node_id}"]')
    lines.append("")

    for conn in connections:
        if not isinstance(conn, dict):
            continue
        source = conn.get("from")
        target = conn.get("to")
        if not isinstance(source, str) or not isinstance(target, str):
            continue
        label_parts: list[str] = []
        on_block = conn.get("on")
        if isinstance(on_block, dict):
            decisions = on_block.get("decisions")
            if isinstance(decisions, list) and decisions:
                label_parts.append("/".join(str(item) for item in decisions))
        loop = conn.get("loop")
        if isinstance(loop, str) and loop:
            label_parts.append(f"loop:{loop}")
        edge = f"  {_mermaid_node_id(source)} --> {_mermaid_node_id(target)}"
        if label_parts:
            edge += f":|{' '.join(label_parts)}|"
        lines.append(edge)

    return "\n".join(lines)


def _flow_registry_version(foundry_bundle: Path) -> str | int:
    flow_path = foundry_bundle / "flows" / "factory-flow.yaml"
    with flow_path.open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    if isinstance(document, dict) and "version" in document:
        return document["version"]
    return "?"


def _connection_summary(conn: dict[str, Any]) -> str:
    parts: list[str] = []
    on_block = conn.get("on")
    if isinstance(on_block, dict):
        outcomes = on_block.get("outcomes")
        if isinstance(outcomes, list) and outcomes:
            parts.append(f"outcomes={outcomes}")
        decisions = on_block.get("decisions")
        if isinstance(decisions, list) and decisions:
            parts.append(f"decisions={decisions}")
    when_expr = conn.get("when")
    if isinstance(when_expr, str) and when_expr.strip():
        parts.append(f"when={when_expr.strip()}")
    loop = conn.get("loop")
    if isinstance(loop, str) and loop:
        parts.append(f"loop={loop}")
    return "; ".join(parts) if parts else "—"


def build_flow_doc(
    flow: dict[str, Any],
    foundry_bundle: Path,
    repo_root: Path,
    *,
    output_dir: Path,
) -> str:
    from_file = output_dir / "flow.md"
    flow_id = str(flow.get("id", "implementation"))
    entry = str(flow.get("entry", ""))
    version = _flow_registry_version(foundry_bundle)
    flow_yaml = rel_link(
        from_file,
        foundry_bundle / "flows" / "factory-flow.yaml",
        "factory-flow.yaml",
    )
    nodes = [n for n in (flow.get("nodes") or []) if isinstance(n, dict) and n.get("id")]
    nodes_dir = output_dir / "nodes"

    lines = [
        f"# Flow: `{flow_id}`",
        "",
        "Generated from `.cursor/foundry/flows/factory-flow.yaml`. "
        "Regenerate with `foundry doc build` or `foundry dev docs`.",
        "",
        f"Registry version: `{version}`",
        f"Entry node: `{entry}`",
        f"Source: {flow_yaml}",
        "",
        "## Graph",
        "",
        "```mermaid",
        build_flow_connections_mermaid(flow),
        "```",
        "",
        "## Concepts",
        "",
        f"Graph routing rules: {concept_link(from_file, repo_root, 'graph.md', 'graph.md')}. "
        f"Check catalog semantics: {concept_link(from_file, repo_root, 'control-plane.md', 'control-plane.md')}.",
        "",
        "## Nodes",
        "",
        "| Node | Kind | Title | Doc |",
        "|---|---|---|---|",
    ]
    for node in sorted(nodes, key=lambda item: str(item.get("id"))):
        node_id = str(node["id"])
        node_doc = nodes_dir / f"{node_id}.md"
        lines.append(
            f"| `{node_id}` | `{node.get('kind', 'step')}` | {node.get('title', '')} | "
            f"{rel_link(from_file, node_doc, 'doc')} |"
        )

    lines.extend(["", "## Connections", "", "| Id | From | To | Routing |", "|---|---|---|---|"])
    for conn in flow.get("connections") or []:
        if not isinstance(conn, dict):
            continue
        conn_id = str(conn.get("id", "—"))
        source = str(conn.get("from", "—"))
        target = str(conn.get("to", "—"))
        summary = _connection_summary(conn).replace("|", "\\|")
        lines.append(f"| `{conn_id}` | `{source}` | `{target}` | {summary} |")

    checks = flow.get("checks") or {}
    if isinstance(checks, dict) and checks:
        lines.extend(["", "## Check catalog", "", "| Check id | Definition |", "|---|---|"])
        for check_id, body in sorted(checks.items()):
            if not isinstance(body, dict):
                lines.append(f"| `{check_id}` | — |")
                continue
            command = body.get("command")
            when_expr = body.get("when")
            detail_parts: list[str] = []
            if isinstance(command, str):
                detail_parts.append(f"command: `{command}`")
            if isinstance(when_expr, str) and when_expr.strip():
                detail_parts.append(f"when: `{when_expr.strip()}`")
            detail = "; ".join(detail_parts) if detail_parts else "—"
            lines.append(f"| `{check_id}` | {detail} |")

    lines.append("")
    return "\n".join(lines)


def build_index(
    flow: dict[str, Any],
    repo_root: Path,
    *,
    output_dir: Path,
    node_ids: list[str] | None = None,
) -> str:
    from_file = output_dir / "index.md"
    nodes = [n for n in (flow.get("nodes") or []) if isinstance(n, dict) and n.get("id")]
    cli_index = output_dir / "cli" / "index.md"
    flow_doc = output_dir / "flow.md"
    concepts_index = repo_root / "docs" / "concepts" / "README.md"
    v1_spec = repo_root / "docs" / "v1-spec.md"
    lines = [
        "# Foundry documentation",
        "",
        f"Flow: `{flow.get('id', 'implementation')}` — "
        f"{rel_link(from_file, repo_root / '.cursor/foundry/flows/factory-flow.yaml', 'factory-flow.yaml')}",
        "",
        "Node, worker, flow, and CLI pages below are generated by `foundry dev docs`. "
        "Workflow concepts and the product spec are maintained separately.",
        "",
        "## Product",
        "",
        f"- {rel_link(from_file, v1_spec, 'v1 product spec')}",
        "",
        "## Concepts",
        "",
        f"- {rel_link(from_file, concepts_index, 'Workflow concepts index')}",
    ]
    for concept_file, concept_label in CONCEPT_DOCS:
        if concept_file == "README.md":
            continue
        concept_path = repo_root / "docs" / "concepts" / concept_file
        lines.append(f"- {rel_link(from_file, concept_path, concept_label)}")
    lines.extend(
        [
            "",
            "## Flow",
            "",
            f"- {rel_link(from_file, flow_doc, 'Flow graph and connections')}",
            "",
            "## CLI",
            "",
            f"- {rel_link(from_file, cli_index, 'CLI reference (implemented commands)')}",
            "",
            "## Nodes",
            "",
            "| Node | Kind | Title |",
            "|---|---|---|",
        ]
    )
    for node in sorted(nodes, key=lambda n: str(n.get("id"))):
        node_id = str(node["id"])
        node_doc = output_dir / "nodes" / f"{node_id}.md"
        lines.append(
            f"| {rel_link(from_file, node_doc, node_id)} | `{node.get('kind', 'step')}` | {node.get('title', '')} |"
        )

    target_ids = node_ids or [str(node["id"]) for node in nodes]
    workers = collect_workers_for_nodes(flow, target_ids)
    lines.extend(["", "## Workers", ""])
    if workers:
        workers_dir = output_dir / "catalog" / "workers"
        for worker_id in sorted(workers):
            worker_doc = workers_dir / f"{worker_id}.md"
            lines.append(f"- {rel_link(from_file, worker_doc, worker_id)}")
    else:
        lines.append("_No workers for generated nodes._")
    lines.append("")
    return "\n".join(lines)


def collect_workers_for_nodes(flow: dict[str, Any], node_ids: list[str]) -> dict[str, dict[str, Any]]:
    workers: dict[str, dict[str, Any]] = {}
    for node_id in node_ids:
        node = get_node(flow, node_id)
        worker = node.get("worker")
        if not isinstance(worker, dict):
            continue
        contract = str(worker.get("contract", ""))
        worker_id = _worker_id_from_contract(contract)
        entry = workers.setdefault(
            worker_id,
            {
                "contract_ref": contract,
                "prompt_ref": str(worker.get("prompt", "")),
                "nodes": [],
            },
        )
        entry["nodes"].append(node_id)
    return workers


def write_generated_docs(
    *,
    flow: dict[str, Any],
    foundry_bundle: Path,
    repo_root: Path,
    node_ids: list[str],
    output_dir: Path,
    write_index: bool,
    write_flow: bool | None = None,
    cli_parser: Any | None = None,
) -> list[Path]:
    output_dir = output_dir.resolve()
    nodes_dir = output_dir / "nodes"
    workers_dir = output_dir / "catalog" / "workers"
    nodes_dir.mkdir(parents=True, exist_ok=True)
    workers_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for node_id in node_ids:
        doc = build_node_doc(
            node_id,
            flow,
            foundry_bundle,
            repo_root,
            output_nodes_dir=nodes_dir,
        )
        path = nodes_dir / f"{node_id}.md"
        path.write_text(doc, encoding="utf-8")
        written.append(path)

    workers = collect_workers_for_nodes(flow, node_ids)
    for worker_id, info in workers.items():
        worker_doc = build_worker_doc(
            worker_id,
            contract_ref=info["contract_ref"],
            prompt_ref=info["prompt_ref"],
            foundry_bundle=foundry_bundle,
            repo_root=repo_root,
            nodes_using=info["nodes"],
            output_workers_dir=workers_dir,
        )
        path = workers_dir / f"{worker_id}.md"
        path.write_text(worker_doc, encoding="utf-8")
        written.append(path)

    if cli_parser is not None:
        from foundry_cli.cli_docgen import write_cli_docs

        written.extend(
            write_cli_docs(parser=cli_parser, repo_root=repo_root, output_dir=output_dir)
        )

    should_write_flow = write_flow if write_flow is not None else write_index
    if should_write_flow:
        flow_doc = build_flow_doc(
            flow,
            foundry_bundle,
            repo_root,
            output_dir=output_dir,
        )
        flow_path = output_dir / "flow.md"
        flow_path.write_text(flow_doc, encoding="utf-8")
        written.append(flow_path)

    if write_index:
        index_doc = build_index(flow, repo_root, output_dir=output_dir, node_ids=node_ids)
        index_path = output_dir / "index.md"
        index_path.write_text(index_doc, encoding="utf-8")
        written.append(index_path)

    return written
