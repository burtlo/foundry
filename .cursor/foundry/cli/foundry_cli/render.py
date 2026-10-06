"""Render steward context packets as markdown."""

from __future__ import annotations

from pathlib import Path
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
        ref = artifact.get("id") or artifact.get("artifact") or ""
        uri = artifact.get("uri") or artifact.get("from") or ""
        lines.append(
            "| "
            + " | ".join(
                [
                    str(ref),
                    f"`{uri}`" if uri else "—",
                    f"`{artifact.get('resolved_uri', '')}`" if artifact.get("resolved_uri") else "—",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _artifact_markdown_body(context: dict[str, Any], *, qualified_ref: str) -> str | None:
    reads = context.get("reads") if isinstance(context.get("reads"), dict) else {}
    artifacts = reads.get("artifacts") if isinstance(reads.get("artifacts"), list) else []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        if artifact.get("artifact") != qualified_ref:
            continue
        resolved_path = artifact.get("resolved_path")
        if isinstance(resolved_path, str) and resolved_path:
            path = Path(resolved_path)
            if path.is_file():
                return path.read_text(encoding="utf-8")
    return None


def _plan_presentation_markdown_body(context: dict[str, Any]) -> str | None:
    return _artifact_markdown_body(context, qualified_ref="shape.present.presentation")


def _living_plan_markdown_body(context: dict[str, Any]) -> str | None:
    return _artifact_markdown_body(context, qualified_ref="shape.record.plan")


def _verify_notes_markdown_body(context: dict[str, Any]) -> str | None:
    return _artifact_markdown_body(context, qualified_ref="verify.code_review.verify-notes")


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

    if context.get("node_id") == "shape.record":
        lines.extend(
            [
                "---",
                "",
                "## Record",
                "",
                "Judgment step: run the `shape.record` task, then `run agent submit` with the "
                "structured result. Complete with `visit record complete` (or `run advance` after "
                "a PROCEED verdict). A BLOCKED verdict seals the agent receipt only — resolve "
                "blockers and submit again before completing.",
                "",
            ]
        )

    if context.get("node_id") == "execute.plan":
        lines.extend(
            [
                "---",
                "",
                "## Execute plan",
                "",
                "Judgment step: run the `execute.plan` task, then `run agent submit` with the "
                "structured result. Complete with `visit plan complete` (or `run advance` after "
                "a PROCEED verdict). A BLOCKED verdict seals the agent receipt only — resolve "
                "blockers and submit again before completing.",
                "",
            ]
        )

    if context.get("node_id") == "shape.present.gate":
        presentation_body = _plan_presentation_markdown_body(context)
        lines.extend(["---", "", "## Plan presentation", ""])
        if presentation_body is not None:
            lines.append(presentation_body.rstrip())
            lines.append("")
        else:
            lines.append(
                "_Presentation markdown could not be loaded from resolved artifact paths in this packet._"
            )
            lines.append("")

    if context.get("node_id") in ("shape.record.gate", "execute.start"):
        plan_body = _living_plan_markdown_body(context)
        lines.extend(["---", "", "## Living plan", ""])
        if plan_body is not None:
            lines.append(plan_body.rstrip())
            lines.append("")
        else:
            lines.append(
                "_Plan markdown could not be loaded from resolved artifact paths in this packet._"
            )
            lines.append("")

    if context.get("node_id") == "verify.code_review.gate":
        notes_body = _verify_notes_markdown_body(context)
        lines.extend(["---", "", "## Verify notes", ""])
        if notes_body is not None:
            lines.append(notes_body.rstrip())
            lines.append("")
        else:
            lines.append(
                "_Verify notes could not be loaded from resolved artifact paths in this packet._"
            )
            lines.append("")

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
    elif context.get("node_id") == "execute.intake":
        lines.extend(
            [
                "---",
                "",
                "## Execute intake",
                "",
                "Engine-owned step: the host validates frozen shape artifacts and git cleanliness, "
                "then seals intake receipts via `run advance`. Do not invoke `intake-checker.execute` "
                "for receipt mechanics on the default path.",
                "",
            ]
        )
    elif context.get("node_id") == "execute.branch":
        lines.extend(
            [
                "---",
                "",
                "## Feature branch",
                "",
                "Engine-owned step: the host resolves the `foundry/…` feature branch name, checks out "
                "or creates the branch, and records branch state via `run advance`. Do not run "
                "`git checkout -b` manually on the default path.",
                "",
            ]
        )
    elif context.get("node_id") == "execute.build":
        lines.extend(
            [
                "---",
                "",
                "## Execute build",
                "",
                "Engine-owned step: the host runs manifest (or stub) build commands, seals a "
                "`feature-builder` agent receipt with command exit codes, and advances via "
                "`run advance`. The first advance after plan or repair re-entry may park once "
                "(`execute_build_boundary`); call `run advance` again to record build evidence. "
                "Task-registry builder agents are out of scope for the default host slice.",
                "",
            ]
        )
    elif context.get("node_id") == "execute.test":
        lines.extend(
            [
                "---",
                "",
                "## Execute test",
                "",
                "Engine-owned step: the host runs manifest (or stub) verification commands, "
                "seals a `repairer`-labeled agent receipt with command exit codes and "
                "verification policy, and advances via `run advance`. Pass vs repair routing "
                "happens at `execute.test.gate`; do not bind the repairer worker on the "
                "default host slice.",
                "",
            ]
        )
    elif context.get("node_id") == "execute.commit":
        lines.extend(
            [
                "---",
                "",
                "## Execute commit",
                "",
                "Engine-owned step: the host checks out the feature branch, records a final "
                "git commit (empty allowed when stubbing), publishes `final-commit`, seals a "
                "`commit-agent` receipt, and advances via `run advance`. Do not bind the "
                "commit-agent worker on the default host slice.",
                "",
            ]
        )
    elif context.get("node_id") == "verify.intake":
        lines.extend(
            [
                "---",
                "",
                "## Verify intake",
                "",
                "Engine-owned step: the host captures the feature-branch diff, validates "
                "execute context (`final_commit_sha`, `feature_branch`, usable diff), then "
                "seals intake receipts via `run advance`. Do not invoke `intake-checker.verify` "
                "for receipt mechanics on the default path.",
                "",
            ]
        )
    elif context.get("node_id") == "verify.acceptance":
        lines.extend(
            [
                "---",
                "",
                "## Verify acceptance",
                "",
                "Engine-owned step: the host assesses sealed execute context and branch diff "
                "(`_assess_acceptance`), publishes `verify-findings.json` with a deterministic "
                "`gate_decision`, seals an `implementation-validator`-labeled agent receipt, and "
                "advances via `run advance`. Routing (pass, replan, reshape, rework_execute) is "
                "at `verify.acceptance.gate`; do not bind the implementation-validator worker on "
                "the default host slice.",
                "",
            ]
        )
    elif context.get("node_id") == "verify.code_quality":
        lines.extend(
            [
                "---",
                "",
                "## Verify code quality",
                "",
                "Engine-owned step: when review is enabled, the host runs manifest `code_quality` "
                "or `lint` commands (stub env under `FOUNDRY_EXECUTE_STUB`), publishes "
                "`code-quality-report.md`, seals an `implementation-validator`-labeled agent receipt, "
                "and advances via `run advance`. When review is disabled, the host seals "
                "`not_applicable` and routes to `verify.code_review`. Pass vs repair is at "
                "`verify.code_quality.gate`; do not bind workers for command evidence on the "
                "default host slice.",
                "",
            ]
        )
    elif context.get("node_id") == "verify.code_review":
        lines.extend(
            [
                "---",
                "",
                "## Verify code review",
                "",
                "Engine-owned step: the host publishes `verify-notes.md` (review packet for the "
                "user gate), patches `verify_notes` in run state, and advances via `run advance`. "
                "Accept, reject, and reshape decisions are at `verify.code_review.gate` only; do "
                "not manually publish verify-notes on the default host slice.",
                "",
            ]
        )

    intake_gate = context.get("node_id")
    if intake_gate in ("execute.intake.gate", "verify.intake.gate"):
        reads = context.get("reads") if isinstance(context.get("reads"), dict) else {}
        receipt = reads.get("intake_receipt") if isinstance(reads.get("intake_receipt"), dict) else {}
        status = receipt.get("status") or "—"
        visit_id = receipt.get("visit_id") or "—"
        if intake_gate == "verify.intake.gate":
            step_label = "verify.intake"
            heading = "## Verify intake evidence"
        else:
            step_label = "execute.intake"
            heading = "## Intake evidence"
        lines.extend(
            [
                "---",
                "",
                heading,
                "",
                f"Sealed **{step_label}** visit `{visit_id}` — intake receipt status: **`{status}`**.",
                "",
                "Engine gate: use `run advance` to resolve **pass** when status is `passed`. "
                "Do not use `gate decide` on this node.",
                "",
            ]
        )
    if context.get("node_id") == "execute.test.gate":
        reads = context.get("reads") if isinstance(context.get("reads"), dict) else {}
        receipt = reads.get("test_receipt") if isinstance(reads.get("test_receipt"), dict) else {}
        visit_id = receipt.get("visit_id") or "—"
        commands = receipt.get("commands") if isinstance(receipt.get("commands"), list) else []
        if commands:
            summary_parts = [
                f"`{item.get('command', '?')}` exit {item.get('exit_code', '?')}"
                for item in commands
                if isinstance(item, dict)
            ]
            cmd_line = ", ".join(summary_parts) if summary_parts else "—"
        else:
            cmd_line = "—"
        lines.extend(
            [
                "---",
                "",
                "## Test evidence",
                "",
                f"Sealed **execute.test** visit `{visit_id}` — verification commands: {cmd_line}.",
                "",
                "Engine gate: use `run advance` to resolve **pass** (all exit codes 0) or **repair** "
                "(any non-zero). Do not use `gate decide` on this node.",
                "",
            ]
        )
    if context.get("node_id") == "execute.repair.limit.gate":
        reads = context.get("reads") if isinstance(context.get("reads"), dict) else {}
        loop = reads.get("repair_loop") if isinstance(reads.get("repair_loop"), dict) else {}
        repair_count = loop.get("repair_count", "—")
        limit = loop.get("limit", "—")
        within = loop.get("within_limit")
        if within is True:
            limit_line = "within configured limit"
        elif within is False:
            limit_line = "exceeds configured limit (examine escalates until operator resumes)"
        else:
            limit_line = "—"
        lines.extend(
            [
                "---",
                "",
                "## Repair loop",
                "",
                f"Prior repair cycles: **{repair_count}** of limit **{limit}** — {limit_line}.",
                "",
                "Engine gate: use `run advance` to resolve **proceed** when the count is within "
                "`config.limits.repair`. Do not use `gate decide` on this node.",
                "",
            ]
        )
    if context.get("node_id") == "verify.code_quality.gate":
        reads = context.get("reads") if isinstance(context.get("reads"), dict) else {}
        receipt = (
            reads.get("code_quality_receipt")
            if isinstance(reads.get("code_quality_receipt"), dict)
            else {}
        )
        visit_id = receipt.get("visit_id") or "—"
        commands = receipt.get("commands") if isinstance(receipt.get("commands"), list) else []
        if commands:
            summary_parts = [
                f"`{item.get('command', '?')}` exit {item.get('exit_code', '?')}"
                for item in commands
                if isinstance(item, dict)
            ]
            cmd_line = ", ".join(summary_parts) if summary_parts else "—"
        else:
            cmd_line = "—"
        receipt_status = receipt.get("status") or "—"
        lines.extend(
            [
                "---",
                "",
                "## Code quality evidence",
                "",
                f"Sealed **verify.code_quality** visit `{visit_id}` — verification commands: "
                f"{cmd_line}; implementation-validator receipt status: **`{receipt_status}`**.",
                "",
                "Engine gate: use `run advance` to resolve **pass** (all exit codes 0, receipt not "
                "failed/partial) or **repair** (non-zero exit or failed receipt). "
                "Do not use `gate decide` on this node.",
                "",
            ]
        )
    if context.get("node_id") == "verify.acceptance.gate":
        reads = context.get("reads") if isinstance(context.get("reads"), dict) else {}
        findings = reads.get("verify_findings") if isinstance(reads.get("verify_findings"), dict) else {}
        receipt = reads.get("acceptance_receipt") if isinstance(reads.get("acceptance_receipt"), dict) else {}
        visit_id = findings.get("visit_id") or receipt.get("visit_id") or "—"
        gate_decision = findings.get("gate_decision") or "—"
        evidence_ok = findings.get("evidence_ok")
        if evidence_ok is True:
            evidence_line = "evidence_ok: **true**"
        elif evidence_ok is False:
            evidence_line = "evidence_ok: **false**"
        else:
            evidence_line = "evidence_ok: —"
        receipt_status = receipt.get("status") or "—"
        lines.extend(
            [
                "---",
                "",
                "## Acceptance evidence",
                "",
                f"Sealed **verify.acceptance** visit `{visit_id}` — verify-findings "
                f"`gate_decision`: **`{gate_decision}`** ({evidence_line}); "
                f"implementation-validator receipt status: **`{receipt_status}`**.",
                "",
                "Engine gate: use `run advance` to resolve **pass** (requires `evidence_ok: true`), "
                "**replan**, **reshape**, or **rework_execute** from sealed verify-findings. "
                "Do not use `gate decide` on this node.",
                "",
            ]
        )
    if context.get("node_id") == "execute.commit.gate":
        reads = context.get("reads") if isinstance(context.get("reads"), dict) else {}
        receipt = reads.get("commit_receipt") if isinstance(reads.get("commit_receipt"), dict) else {}
        state = reads.get("state") if isinstance(reads.get("state"), dict) else {}
        visit_id = receipt.get("visit_id") or "—"
        status = receipt.get("status") or "—"
        sha = state.get("final_commit_sha") or "—"
        message = state.get("execute_commit_message")
        msg_line = f" Commit message: {message!r}." if message else ""
        lines.extend(
            [
                "---",
                "",
                "## Commit evidence",
                "",
                f"Sealed **execute.commit** visit `{visit_id}` — final commit SHA: **`{sha}`**; "
                f"commit-agent receipt status: **`{status}`**.{msg_line}",
                "",
                "Engine gate: use `run advance` to resolve **pass** when `final_commit_sha` is "
                "recorded. Do not use `gate decide` on this node.",
                "",
            ]
        )
    return "\n".join(lines)
