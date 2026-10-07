"""View-model builders for node documentation and related CLI surfaces."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from foundry_cli.flow_helpers import node_connections
from foundry_cli.registry import get_node, normalize_receipts
from foundry_cli.util import list_or_empty

LIFECYCLE_HOOKS = ("on_examine", "on_open", "on_close", "on_seal")


def lifecycle_hooks(node: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    lifecycle = node.get("lifecycle") or {}
    hooks: dict[str, list[dict[str, Any]]] = {}
    for hook in LIFECYCLE_HOOKS:
        entries = lifecycle.get(hook)
        if entries is None:
            hooks[hook] = []
        elif isinstance(entries, list):
            hooks[hook] = [entry for entry in entries if isinstance(entry, dict)]
        else:
            hooks[hook] = []
    return hooks


def check_ids_for_hooks(hooks: dict[str, list[dict[str, Any]]]) -> list[str]:
    ids: list[str] = []
    for entries in hooks.values():
        for entry in entries:
            check_id = entry.get("check")
            if isinstance(check_id, str) and check_id not in ids:
                ids.append(check_id)
    return ids


def check_definition(flow: dict[str, Any], check_id: str) -> dict[str, Any] | None:
    checks = flow.get("checks") or {}
    if not isinstance(checks, dict):
        return None
    body = checks.get(check_id)
    if not isinstance(body, dict):
        return None
    return body


def outgoing_target_names(outgoing: list[dict[str, Any]]) -> list[str]:
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
    route_targets = outgoing_target_names(outgoing)
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


def hooks_table(hooks: dict[str, list[dict[str, Any]]]) -> str:
    rows = [
        "| Hook | Authored checks | Engine-implicit |",
        "|---|---|---|",
    ]
    for hook in LIFECYCLE_HOOKS:
        entries = hooks.get(hook, [])
        check_names = ", ".join(f"`{e.get('check')}`" for e in entries if e.get("check"))
        if not check_names:
            check_names = "*(empty)*"
        implicit = "—"
        if hook == "on_close":
            implicit = "Declared artifact completeness"
        rows.append(f"| `{hook}` | {check_names} | {implicit} |")
    return "\n".join(rows)


def reads_table(node: dict[str, Any]) -> str:
    reads = node.get("reads") or {}
    rows = [
        "| Namespace | Paths |",
        "|---|---|",
    ]
    for namespace in ("config", "state", "files"):
        keys = list_or_empty(reads.get(namespace))
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


def allow_table(node: dict[str, Any], node_id: str) -> str:
    allow = node.get("allow") or {}
    rows = [
        "| Namespace | Grant | Purpose |",
        "|---|---|---|",
    ]
    state_keys = list_or_empty(allow.get("state"))
    if state_keys:
        implicit = f"state.nodes.{node_id}.*"
        if implicit not in state_keys:
            state_keys = [*state_keys, implicit]
        rows.append(
            f"| `state` | {', '.join(f'`{k}`' for k in state_keys)} | Domain fields |"
        )
    files_write = list_or_empty((allow.get("files") or {}).get("write"))
    if files_write:
        rows.append(
            f"| `files.write` | {', '.join(f'`{u}`' for u in files_write)} | Writable run paths |"
        )
    cli_caps = list_or_empty(allow.get("cli"))
    if cli_caps:
        cap_links = ", ".join(f"`{cap}`" for cap in cli_caps)
        rows.append(f"| `cli` | {cap_links} | Steward CLI capabilities |")
    if len(rows) == 2:
        rows.append("| — | *(none declared)* | — |")
    return "\n".join(rows)


def qualified_artifact_refs(node_id: str, node: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for artifact in (node.get("produces") or {}).get("artifacts") or []:
        if isinstance(artifact, dict) and artifact.get("id"):
            refs.append(f"{node_id}.{artifact['id']}")
    return refs


def ledger_excerpt_config(annotations: dict[str, Any] | None) -> dict[str, str] | None:
    if not annotations:
        return None
    config = annotations.get("ledger_excerpt")
    if not isinstance(config, dict):
        return None
    fixture_run = config.get("fixture_run") or config.get("fixture")
    visit_id = config.get("visit_id") or config.get("visit")
    if not isinstance(fixture_run, str) or not isinstance(visit_id, str):
        return None
    return {"fixture_run": fixture_run, "visit_id": visit_id}


def ledger_event_summary(event: dict[str, Any]) -> str:
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


def load_fixture_ledger(foundry_bundle: Path, fixture_run: str) -> list[dict[str, Any]] | None:
    snapshot_path = foundry_bundle / "fixtures" / "runs" / fixture_run / "snapshot.json"
    if not snapshot_path.is_file():
        return None
    with snapshot_path.open(encoding="utf-8") as handle:
        snapshot = json.load(handle)
    ledger = snapshot.get("ledger")
    if not isinstance(ledger, list):
        return None
    return [event for event in ledger if isinstance(event, dict)]


def ledger_events_for_visit(
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


def ledger_excerpt_section(
    node_id: str,
    foundry_bundle: Path,
    annotations: dict[str, Any] | None,
) -> str:
    config = ledger_excerpt_config(annotations)
    if not config:
        return ""

    ledger = load_fixture_ledger(foundry_bundle, config["fixture_run"])
    if not ledger:
        return ""

    events = ledger_events_for_visit(
        ledger,
        visit_id=config["visit_id"],
        node_id=node_id,
    )
    if not events:
        return ""

    fixture_run = config["fixture_run"]
    visit_id = config["visit_id"]
    lines = [
        f"Fixture `{fixture_run}` visit `{visit_id}` (compact).",
        "",
        "| seq | type | summary |",
        "|---:|---|---|",
    ]
    for event in events:
        seq = event.get("seq", "—")
        event_type = event.get("type", "—")
        summary = ledger_event_summary(event).replace("|", "\\|")
        lines.append(f"| {seq} | `{event_type}` | {summary} |")
    lines.append("")
    return "\n".join(lines)


def engine_only_surfaces_rows(
    flow: dict[str, Any],
    node: dict[str, Any],
    hooks: dict[str, list[dict[str, Any]]],
    outgoing: list[dict[str, Any]],
) -> list[str]:
    cli_caps = set(list_or_empty((node.get("allow") or {}).get("cli")))
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

    route_targets = outgoing_target_names(outgoing)
    if route_targets:
        route_label = ", ".join(f"`{target}`" for target in route_targets)
        rows.append(
            f"| Connection selection | After `visit.sealed` | Routes to {route_label} |"
        )

    return rows


def node_concepts_links(
    node: dict[str, Any],
    kind: str,
    check_ids: list[str],
    concept_link: Any,
) -> str:
    links: list[str] = []
    links.append(f"- **Lifecycle:** {concept_link('visits-lifecycle.md', 'Visit lifecycle')}")
    links.append(f"- **Connections:** {concept_link('graph.md', 'Graph and routing')}")
    reads = node.get("reads")
    allow = node.get("allow")
    if reads or allow:
        links.append(f"- **Permissions:** {concept_link('capabilities.md', 'Reads and allow')}")
    artifacts = (node.get("produces") or {}).get("artifacts") or []
    if artifacts:
        links.append(f"- **Artifacts:** {concept_link('artifacts.md', 'Artifact publication')}")
    if normalize_receipts(node):
        links.append(f"- **Receipts:** {concept_link('artifacts.md', 'Receipts vs artifacts')}")
    if check_ids:
        links.append(f"- **Checks:** {concept_link('control-plane.md', 'Control plane')}")
    if kind == "gate":
        links.append(f"- **Gate decisions:** {concept_link('graph.md', 'Gate nodes')}")
    return "\n".join(links)


@dataclass(frozen=True)
class NodeDocView:
    """Assembled node data for documentation generation."""

    node_id: str
    node: dict[str, Any]
    kind: str
    title: str
    annotations: dict[str, Any] | None
    hooks: dict[str, list[dict[str, Any]]]
    check_ids: list[str]
    incoming: list[dict[str, Any]]
    outgoing: list[dict[str, Any]]

    @property
    def is_full_doc(self) -> bool:
        return self.annotations is not None

    @property
    def status(self) -> str:
        return str((self.annotations or {}).get("status", "generated"))

    @property
    def summary(self) -> str:
        return str((self.annotations or {}).get("summary") or self.title)

    @classmethod
    def build(
        cls,
        node_id: str,
        flow: dict[str, Any],
        annotations: dict[str, Any] | None,
    ) -> NodeDocView:
        node = get_node(flow, node_id)
        hooks = lifecycle_hooks(node)
        connections = node_connections(flow, node_id)
        return cls(
            node_id=node_id,
            node=node,
            kind=str(node.get("kind", "step")),
            title=str(node.get("title", node_id)),
            annotations=annotations,
            hooks=hooks,
            check_ids=check_ids_for_hooks(hooks),
            incoming=connections["in"],
            outgoing=connections["out"],
        )
