"""Render steward context packets as markdown."""

from __future__ import annotations

from typing import Any


def _kv_table(rows: list[tuple[str, str]]) -> str:
    if not rows:
        return "_None._\n"
    lines = ["| Key | Value |", "|---|---|"]
    for key, value in rows:
        lines.append(f"| {key} | {value} |")
    return "\n".join(lines) + "\n"


def _cli_list(items: list[str]) -> str:
    if not items:
        return "_None._\n"
    return "\n".join(f"- `{item}`" for item in items) + "\n"


def _file_grants_table(grants: list[dict[str, str]]) -> str:
    if not grants:
        return "_None._\n"
    lines = ["| URI | Path |", "|---|---|"]
    for grant in grants:
        lines.append(f"| `{grant.get('uri', '')}` | `{grant.get('resolved_path', '')}` |")
    return "\n".join(lines) + "\n"


def _artifacts_table(artifacts: list[dict[str, Any]]) -> str:
    if not artifacts:
        return "_None._\n"
    lines = ["| ID | URI | Resolved URI |", "|---|---|---|"]
    for artifact in artifacts:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(artifact.get("id", "")),
                    f"`{artifact.get('uri', '')}`" if artifact.get("uri") else "—",
                    f"`{artifact.get('resolved_uri', '')}`" if artifact.get("resolved_uri") else "—",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _worker_subagent_type(worker: dict[str, Any]) -> str:
    contract = str(worker.get("contract", ""))
    prefix = "registry:workers/"
    suffix = "/contract.yaml"
    if contract.startswith(prefix) and contract.endswith(suffix):
        return contract[len(prefix) : -len(suffix)]
    return ""


def _worker_table(worker: dict[str, Any]) -> str:
    rows = [
        ("subagent_type", _worker_subagent_type(worker)),
        ("mode", str(worker.get("mode", ""))),
        ("prompt", str(worker.get("prompt", ""))),
        ("contract", str(worker.get("contract", ""))),
        ("prompt_path", str(worker.get("prompt_path", ""))),
        ("contract_path", str(worker.get("contract_path", ""))),
    ]
    return _kv_table(rows)


def render_context_markdown(
    context: dict[str, Any],
    instructions_text: str,
    *,
    operations_text: str = "",
) -> str:
    """Build steward markdown packet (judgment + optional operations manifest)."""
    node_id = str(context.get("node_id", ""))
    visit_id = str(context.get("visit_id", ""))
    title = str(context.get("title", node_id))
    instructions_ref = str(context.get("instructions", ""))

    lines: list[str] = [
        f"# Steward context — {node_id} ({visit_id})",
        "",
        f"_{title}_",
        "",
    ]

    warnings = context.get("warnings") or []
    if warnings:
        lines.extend(["## Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")

    lines.extend(
        [
            "## Position",
            "",
            f"- run_id: `{context.get('run_id', '')}`",
            f"- visit_id: `{visit_id}`",
            f"- node_id: `{node_id}`",
            f"- kind: `{context.get('kind', '')}`",
            f"- lifecycle: `{context.get('lifecycle', '')}`",
            "",
        ]
    )

    reads = context.get("reads") or {}
    config = reads.get("config") if isinstance(reads.get("config"), dict) else {}
    state = reads.get("state") if isinstance(reads.get("state"), dict) else {}
    read_files = reads.get("files") if isinstance(reads.get("files"), list) else []

    lines.extend(["## Reads", "", "### Config", "", _kv_table([(k, str(v)) for k, v in config.items()])])
    lines.extend(["### State", "", _kv_table([(k, str(v)) for k, v in state.items()])])

    artifacts = reads.get("artifacts") if isinstance(reads.get("artifacts"), list) else []
    if artifacts:
        lines.extend(["### Artifacts", "", _artifacts_table(artifacts)])

    if read_files:
        lines.extend(["### Files", ""])
        for path in read_files:
            lines.append(f"- `{path}`")
        lines.append("")

    allow = context.get("allow") or {}
    lines.extend(["## Allow", "", "### CLI", "", _cli_list(list(allow.get("cli") or []))])

    state_grants = allow.get("state") if isinstance(allow.get("state"), list) else []
    if state_grants:
        lines.extend(["### State", ""])
        for path in state_grants:
            lines.append(f"- `{path}`")
        lines.append("")

    file_grants = (allow.get("files") or {}).get("write") if isinstance(allow.get("files"), dict) else []
    lines.extend(["### Files (write)", "", _file_grants_table(list(file_grants or []))])

    agents = allow.get("agents") if isinstance(allow.get("agents"), list) else []
    if agents:
        lines.extend(["### Agents", ""])
        for agent in agents:
            lines.append(f"- `{agent}`")
        lines.append("")

    user = allow.get("user") if isinstance(allow.get("user"), dict) else {}
    if user.get("ask") or user.get("decide"):
        lines.extend(
            [
                "### User",
                "",
                _kv_table(
                    [
                        ("ask", str(bool(user.get("ask", False))).lower()),
                        ("decide", str(bool(user.get("decide", False))).lower()),
                    ]
                ),
            ]
        )

    produces = context.get("produces") or {}
    produce_artifacts = produces.get("artifacts") if isinstance(produces.get("artifacts"), list) else []
    produce_options = produces.get("options") if isinstance(produces.get("options"), list) else []
    if produce_artifacts or produce_options:
        lines.extend(["## Produces", ""])
        if produce_artifacts:
            lines.extend(["### Artifacts", "", _artifacts_table(produce_artifacts)])
        if produce_options:
            lines.extend(["### Options", ""])
            for option in produce_options:
                lines.append(f"- `{option}`")
            lines.append("")

    receipts = context.get("receipts") if isinstance(context.get("receipts"), list) else []
    if receipts:
        lines.extend(["## Receipts", ""])
        for receipt in receipts:
            lines.append(f"- `{receipt}`")
        lines.append("")

    worker = context.get("worker")
    if isinstance(worker, dict):
        lines.extend(["## Worker", "", _worker_table(worker)])

    gate_prompt = context.get("prompt")
    if isinstance(gate_prompt, str) and gate_prompt.strip():
        lines.extend(["## Gate prompt", "", gate_prompt.strip(), ""])

    operations_ref = str(context.get("operations", ""))
    if operations_ref or operations_text.strip():
        lines.extend(["---", "", "## Operations", ""])
        lines.append(
            "_Deterministic workflow steps for the runtime executor. "
            "Do not reinterpret policy checks the engine already enforces._"
        )
        lines.append("")
        if operations_ref:
            lines.append(f"<!-- inlined from {operations_ref} -->")
            lines.append("")
        if operations_text.strip():
            lines.append("```yaml")
            lines.append(operations_text.rstrip())
            lines.append("```")
            lines.append("")

    if context.get("node_id") == "shape.examine":
        lines.extend(
            [
                "---",
                "",
                "## Examination",
                "",
                "Judgment step: run the `shape.examine` task, then `run agent submit` with the "
                "structured result. Answer clarifying questions with `answer` when the wait is "
                "`user_input`. Complete with `visit examine complete` (or `run advance` when no "
                "open questions remain). Use `--with-open-questions` only to proceed to the "
                "examination gate without answering.",
                "",
            ]
        )

    if context.get("node_id") == "shape.present":
        lines.extend(
            [
                "---",
                "",
                "## Presentation",
                "",
                "Judgment step: run the `shape.present` task, then `run agent submit` with the "
                "structured result. Complete with `visit present complete` (or `run advance` after "
                "a PROCEED verdict). A BLOCKED verdict seals the agent receipt only — resolve "
                "blockers and submit again before completing.",
                "",
            ]
        )

    if instructions_ref or instructions_text.strip():
        instructions_heading = "## Instructions" if context.get("kind") == "gate" else "## Judgment"
        lines.extend(["---", "", instructions_heading, ""])
        if instructions_ref:
            lines.append(f"<!-- inlined from {instructions_ref} -->")
            lines.append("")
        if instructions_text:
            lines.append(instructions_text.rstrip())
            lines.append("")
    elif context.get("node_id") == "shape.intake":
        lines.extend(
            [
                "---",
                "",
                "## Intake",
                "",
                "Engine-owned step: use `visit intake complete` (or `run advance` when "
                "`config.shape.work_prompt` is set). Step instructions resume at `shape.examine`.",
                "",
            ]
        )
    return "\n".join(lines)
