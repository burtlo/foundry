"""Argparse definition for the Foundry CLI."""

from __future__ import annotations

import argparse
import sys
from typing import Any

GLOBAL_FLAGS_WITH_VALUE = frozenset({"--workspace", "--registry"})
GLOBAL_FLAGS_BOOLEAN = frozenset({"--json"})


def _is_config_init_registry_context(cleaned_argv: list[str]) -> bool:
    """Return True when the next --registry belongs to config init, not globals."""
    try:
        config_idx = cleaned_argv.index("config")
    except ValueError:
        return False
    if config_idx + 1 >= len(cleaned_argv):
        return False
    return cleaned_argv[config_idx + 1] == "init"


def extract_global_flags(argv: list[str] | None) -> tuple[dict[str, Any], list[str]]:
    """Pull global flags from any position in argv; return globals and cleaned argv."""
    if argv is None:
        return {"workspace": ".", "registry": None, "json": False}, []

    globals_out: dict[str, Any] = {"workspace": ".", "registry": None, "json": False}
    cleaned: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in GLOBAL_FLAGS_BOOLEAN:
            if token == "--json":
                globals_out["json"] = True
            index += 1
            continue
        if token in GLOBAL_FLAGS_WITH_VALUE:
            if index + 1 >= len(argv):
                raise ValueError(f"option {token} requires a value")
            value = argv[index + 1]
            if token == "--workspace":
                globals_out["workspace"] = value
            elif token == "--registry":
                if _is_config_init_registry_context(cleaned):
                    cleaned.extend([token, value])
                else:
                    globals_out["registry"] = value
            index += 2
            continue
        cleaned.append(token)
        index += 1
    return globals_out, cleaned


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse argv after extracting global flags from any position."""
    if argv is None:
        argv = sys.argv[1:]
    globals_out, cleaned_argv = extract_global_flags(argv)
    parser = build_parser()
    args = parser.parse_args(cleaned_argv)
    args.workspace = globals_out["workspace"]
    args.registry = globals_out["registry"]
    args.json = globals_out["json"]
    return args


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="foundry")
    parser.add_argument("--workspace", default=".", help="Application repository root")
    parser.add_argument("--registry", help="Foundry bundle root (.cursor/foundry)")
    parser.add_argument("--json", action="store_true", help="Emit JSON response envelope")

    sub = parser.add_subparsers(dest="command", required=True)

    cli = sub.add_parser("cli", help="CLI introspection commands")
    cli_sub = cli.add_subparsers(dest="cli_command", required=True)
    cli_sub.add_parser("resolve", help="Resolve foundry bundle paths")

    run = sub.add_parser("run", help="Run lifecycle commands")
    run_sub = run.add_subparsers(dest="run_command", required=True)

    run_create = run_sub.add_parser("create", help="Create a new run and admit the entry visit")
    run_create.add_argument("--flow", help="Flow id (default: implementation)")
    run_create.add_argument("--run-id", help="Explicit run id slug")
    run_create.add_argument(
        "--work-prompt",
        help="Verbatim shape request stored on run config for engine advance",
    )

    run_advance = run_sub.add_parser("advance", help="Advance run until wait, halt, or step budget")
    run_advance.add_argument("--run", help="Run id")
    run_advance.add_argument("--run-dir", help="Run directory containing snapshot.json")
    run_advance.add_argument("--flow", help="Flow id override")
    run_advance.add_argument(
        "--revision",
        type=int,
        help="Expected snapshot revision; returns STALE_REVISION on conflict",
    )
    run_advance.add_argument(
        "--step-budget",
        type=int,
        default=8,
        help="Maximum automatic steps per invocation (default: 8)",
    )
    run_advance.add_argument(
        "--local",
        action="store_true",
        help="Advance on disk even when the job host is running",
    )

    run_agent = run_sub.add_parser("agent", help="Agent judgment result commands")
    run_agent_sub = run_agent.add_subparsers(dest="run_agent_command", required=True)
    run_agent_submit = run_agent_sub.add_parser(
        "submit",
        help="Submit a validated agent result for the active agent wait",
    )
    run_agent_submit.add_argument("--run", help="Run id")
    run_agent_submit.add_argument("--run-dir", help="Run directory containing snapshot.json")
    run_agent_submit.add_argument("--request-id", required=True, help="Agent request id (ar_…)")
    run_agent_submit.add_argument("--result-json", help="Inline JSON result object")
    run_agent_submit.add_argument("--result-file", help="Path to JSON result file")
    run_agent_submit.add_argument(
        "--revision",
        type=int,
        help="Expected snapshot revision; returns STALE_REVISION on conflict",
    )
    run_agent_submit.add_argument(
        "--local",
        action="store_true",
        help="Submit on disk even when the job host is running",
    )

    run_recover = run_sub.add_parser(
        "recover",
        help="Reload durable snapshot and advance (crash-safe resume)",
    )
    run_recover.add_argument("--run", help="Run id")
    run_recover.add_argument("--run-dir", help="Run directory containing snapshot.json")
    run_recover.add_argument("--flow", help="Flow id override")
    run_recover.add_argument("--step-budget", type=int, default=8)

    run_get = run_sub.add_parser("get", help="Inspect run snapshot summary (via host when running)")
    run_get.add_argument("--run", help="Run id")
    run_get.add_argument("--run-dir", help="Run directory containing snapshot.json")
    run_get.add_argument(
        "--local",
        action="store_true",
        help="Read snapshot from disk even when the job host is running",
    )

    run_list = run_sub.add_parser("list", help="List workspace runs (via host when running)")
    run_list.add_argument(
        "--local",
        action="store_true",
        help="Read runs from disk even when the job host is running",
    )

    run_events_cmd = run_sub.add_parser("events", help="Ledger events after a sequence (via host when running)")
    run_events_cmd.add_argument("--run", help="Run id")
    run_events_cmd.add_argument("--run-dir", help="Run directory containing snapshot.json")
    run_events_cmd.add_argument("--after-seq", type=int, default=0, help="Return events with seq > after_seq")
    run_events_cmd.add_argument("--local", action="store_true", help="Read from disk when host is running")

    context = run_sub.add_parser("context", help="Assemble steward context for a visit")
    context.add_argument("--run", help="Run id")
    context.add_argument("--visit", help="Visit id (default: active visit)")
    context.add_argument("--run-dir", help="Run directory containing snapshot.json")
    context.add_argument("--flow", help="Flow id override")
    context.add_argument(
        "--markdown",
        action="store_true",
        help="Emit steward context as a single markdown packet (mutually exclusive with --json)",
    )

    run_archive = run_sub.add_parser(
        "archive",
        help="Move a workspace run into the Foundry repo runs/ store with sequential archive slug",
    )
    run_archive.add_argument("--run", help="Run id slug under workspace .foundry/runs/")
    run_archive.add_argument("--run-dir", help="Run directory containing snapshot.json")
    run_archive.add_argument(
        "--archive-root",
        help="Override archive directory (default: {foundry_repo}/runs)",
    )
    run_archive.add_argument(
        "--archive-slug",
        help="Explicit archive folder name (default: next {app_id}-NNNN under archive root)",
    )
    run_archive.add_argument("--transcript", help="Path to steward chat transcript (.jsonl) to copy")
    run_archive.add_argument("--review-file", help="Path to evaluation review markdown to copy")
    run_archive.add_argument("--dry-run", action="store_true", help="Preview archive slug and manifest without moving")
    run_archive.add_argument(
        "--copy",
        action="store_true",
        help="Copy the run instead of moving it from the workspace",
    )

    catalog = sub.add_parser("catalog", help="Catalog index commands")
    catalog_sub = catalog.add_subparsers(dest="catalog_command", required=True)

    build = catalog_sub.add_parser("build", help="Generate node index YAML files")
    build.add_argument("--flow", help="Flow id (default: implementation)")
    build.add_argument("--node", help="Build index for a single node id")
    build.add_argument("--output", help="Output directory for index files")

    doc = sub.add_parser("doc", help="Documentation generation")
    doc_sub = doc.add_subparsers(dest="doc_command", required=True)

    doc_build = doc_sub.add_parser(
        "build",
        help="Generate documentation from factory-flow.yaml (default: entire flow)",
    )
    doc_build.add_argument("--flow", default="implementation", help="Flow id (default: implementation)")
    doc_build.add_argument("--node", help="Generate documentation for a single node only")
    doc_build.add_argument("--output", help="Output directory (default: docs)")

    dev = sub.add_parser("dev", help="Developer workflow shortcuts")
    dev_sub = dev.add_subparsers(dest="dev_command", required=True)

    dev_docs = dev_sub.add_parser("docs", help="Build catalog indexes and generate all node docs")
    dev_docs.add_argument("--flow", default="implementation", help="Flow id (default: implementation)")
    dev_docs.add_argument("--output", help="Output directory (default: docs)")
    dev_docs.add_argument(
        "--smoke",
        action="store_true",
        help="Generate shape.intake only (fast check; skips index.md)",
    )

    dev_unit = dev_sub.add_parser("unit", help="Run unit tests (pytest tests/unit)")
    dev_unit.add_argument("--quiet", action="store_true", help="Reduce pytest verbosity")
    dev_unit.add_argument("pytest_args", nargs="*", help="Extra arguments passed to pytest")

    dev_acceptance = dev_sub.add_parser(
        "acceptance",
        help="Run acceptance tests (pytest tests/acceptance; dev_commands excluded by default)",
    )
    dev_acceptance.add_argument("--quiet", action="store_true", help="Reduce pytest verbosity")
    dev_acceptance.add_argument(
        "--include-dev-scenarios",
        action="store_true",
        help="Also run dev_commands.feature (meta-testing only; may recurse if misused)",
    )
    dev_acceptance.add_argument("pytest_args", nargs="*", help="Extra arguments passed to pytest")

    dev_all = dev_sub.add_parser("all", help="Run unit tests then acceptance tests")
    dev_all.add_argument("--quiet", action="store_true", help="Reduce pytest verbosity")
    dev_all.add_argument(
        "--include-dev-scenarios",
        action="store_true",
        help="Also run dev_commands.feature in the acceptance leg",
    )
    dev_all.add_argument("pytest_args", nargs="*", help="Extra arguments passed to pytest")

    visit = sub.add_parser("visit", help="Visit lifecycle commands")
    visit_sub = visit.add_subparsers(dest="visit_command", required=True)

    visit_state = visit_sub.add_parser("state", help="Visit state commands")
    visit_state_sub = visit_state.add_subparsers(dest="visit_state_command", required=True)

    visit_state_patch = visit_state_sub.add_parser("patch", help="Patch allowed run state fields")
    visit_state_patch.add_argument("--run", help="Run id")
    visit_state_patch.add_argument("--visit", help="Visit id (default: active visit)")
    visit_state_patch.add_argument("--run-dir", help="Run directory containing snapshot.json")
    visit_state_patch.add_argument("--set", help="JSON object of state paths and values")
    visit_state_patch.add_argument("--file", help="run: or workspace: path to JSON patch document")
    visit_state_patch.add_argument(
        "--revision",
        type=int,
        help="Expected snapshot revision before commit",
    )

    visit_transition = visit_sub.add_parser("transition", help="Request close and seal on an opened visit")
    visit_transition.add_argument("--run", help="Run id")
    visit_transition.add_argument("--visit", help="Visit id (default: active visit)")
    visit_transition.add_argument("--run-dir", help="Run directory containing snapshot.json")
    visit_transition.add_argument("--summary", help="Short steward summary")
    visit_transition.add_argument("--revision", type=int, help="Expected snapshot revision before commit")

    visit_intake = visit_sub.add_parser("intake", help="Shape intake deterministic commands")
    visit_intake_sub = visit_intake.add_subparsers(dest="visit_intake_command", required=True)

    visit_intake_complete = visit_intake_sub.add_parser(
        "complete",
        help="Capture work request, publish ticket, seal receipts, and transition (no worker)",
    )
    visit_intake_complete.add_argument("--run", help="Run id")
    visit_intake_complete.add_argument("--visit", help="Visit id (default: active visit)")
    visit_intake_complete.add_argument("--run-dir", help="Run directory containing snapshot.json")
    visit_intake_complete.add_argument(
        "--work-prompt",
        help="Verbatim work request; omit to record blocked intake without transition",
    )
    visit_intake_complete.add_argument(
        "--source-type",
        default="chat",
        choices=["chat", "paste", "file", "url", "repo_inference"],
        help="How the work request was supplied",
    )
    visit_intake_complete.add_argument("--source-ref", help="Optional file path or URL reference")
    visit_intake_complete.add_argument("--summary", help="Short summary for visit transition on success")
    visit_intake_complete.add_argument("--revision", type=int, help="Expected snapshot revision before commit")

    visit_examine = visit_sub.add_parser("examine", help="Shape examination deterministic commands")
    visit_examine_sub = visit_examine.add_subparsers(dest="visit_examine_command", required=True)

    visit_examine_complete = visit_examine_sub.add_parser(
        "complete",
        help="Seal agent receipt and transition after accepted examination judgment",
    )
    visit_examine_complete.add_argument("--run", help="Run id")
    visit_examine_complete.add_argument("--visit", help="Visit id (default: active visit)")
    visit_examine_complete.add_argument("--run-dir", help="Run directory containing snapshot.json")
    visit_examine_complete.add_argument("--summary", help="Short summary for visit transition on success")
    visit_examine_complete.add_argument(
        "--with-open-questions",
        action="store_true",
        help="Allow transition to shape.examine.gate while clarifying questions remain open",
    )
    visit_examine_complete.add_argument("--revision", type=int, help="Expected snapshot revision before commit")

    visit_present = visit_sub.add_parser("present", help="Shape presentation deterministic commands")
    visit_present_sub = visit_present.add_subparsers(dest="visit_present_command", required=True)

    visit_present_complete = visit_present_sub.add_parser(
        "complete",
        help="Publish presentation artifact and transition after accepted presentation judgment",
    )
    visit_present_complete.add_argument("--run", help="Run id")
    visit_present_complete.add_argument("--visit", help="Visit id (default: active visit)")
    visit_present_complete.add_argument("--run-dir", help="Run directory containing snapshot.json")
    visit_present_complete.add_argument("--summary", help="Short summary for visit transition on success")
    visit_present_complete.add_argument("--revision", type=int, help="Expected snapshot revision before commit")

    visit_record = visit_sub.add_parser("record", help="Shape record deterministic commands")
    visit_record_sub = visit_record.add_subparsers(dest="visit_record_command", required=True)

    visit_record_complete = visit_record_sub.add_parser(
        "complete",
        help="Publish plan artifact and transition after accepted record judgment",
    )
    visit_record_complete.add_argument("--run", help="Run id")
    visit_record_complete.add_argument("--visit", help="Visit id (default: active visit)")
    visit_record_complete.add_argument("--run-dir", help="Run directory containing snapshot.json")
    visit_record_complete.add_argument("--summary", help="Short summary for visit transition on success")
    visit_record_complete.add_argument("--revision", type=int, help="Expected snapshot revision before commit")

    visit_plan = visit_sub.add_parser("plan", help="Execute plan deterministic commands")
    visit_plan_sub = visit_plan.add_subparsers(dest="visit_plan_command", required=True)

    visit_plan_complete = visit_plan_sub.add_parser(
        "complete",
        help="Publish execution graph and brief after accepted plan judgment",
    )
    visit_plan_complete.add_argument("--run", help="Run id")
    visit_plan_complete.add_argument("--visit", help="Visit id (default: active visit)")
    visit_plan_complete.add_argument("--run-dir", help="Run directory containing snapshot.json")
    visit_plan_complete.add_argument("--summary", help="Short summary for visit transition on success")
    visit_plan_complete.add_argument("--revision", type=int, help="Expected snapshot revision before commit")

    gate = sub.add_parser("gate", help="Gate decision commands")
    gate_sub = gate.add_subparsers(dest="gate_command", required=True)

    gate_decide = gate_sub.add_parser("decide", help="Record a user gate decision and close the visit")
    gate_decide.add_argument("--run", help="Run id")
    gate_decide.add_argument("--visit", help="Visit id (default: active gate visit)")
    gate_decide.add_argument("--run-dir", help="Run directory containing snapshot.json")
    gate_decide.add_argument("--decision", required=True, help="One of the gate produces.options values")
    gate_decide.add_argument("--revision", type=int, help="Expected snapshot revision before commit")

    ledger = sub.add_parser("ledger", help="Ledger inspection commands")
    ledger_sub = ledger.add_subparsers(dest="ledger_command", required=True)

    ledger_show = ledger_sub.add_parser("show", help="Show ledger events for a run")
    ledger_show.add_argument("--run", help="Run id")
    ledger_show.add_argument("--run-dir", help="Run directory containing snapshot.json")
    ledger_show.add_argument("--from-seq", help="First sequence number (inclusive)")
    ledger_show.add_argument("--to-seq", help="Last sequence number (inclusive)")
    ledger_show.add_argument("--types", help="Comma-separated event type filter")

    artifact = sub.add_parser("artifact", help="Artifact publication commands")
    artifact_sub = artifact.add_subparsers(dest="artifact_command", required=True)

    artifact_publish = artifact_sub.add_parser("publish", help="Publish a declared artifact")
    artifact_publish.add_argument("--run", help="Run id")
    artifact_publish.add_argument("--visit", help="Visit id (default: active visit)")
    artifact_publish.add_argument("--run-dir", help="Run directory containing snapshot.json")
    artifact_publish.add_argument("--artifact", required=True, help="Logical artifact id")
    artifact_publish.add_argument("--source", required=True, help="Source run: or workspace: path")
    artifact_publish.add_argument("--revision", type=int, help="Expected snapshot revision before commit")

    receipt = sub.add_parser("receipt", help="Receipt sealing commands")
    receipt_sub = receipt.add_subparsers(dest="receipt_command", required=True)

    receipt_seal = receipt_sub.add_parser("seal", help="Validate and seal a receipt draft")
    receipt_seal.add_argument("--run", help="Run id")
    receipt_seal.add_argument("--visit", help="Visit id (default: active visit)")
    receipt_seal.add_argument("--run-dir", help="Run directory containing snapshot.json")
    receipt_seal.add_argument("--schema", help="Receipt schema registry path")
    receipt_seal.add_argument("--file", required=True, help="run: or workspace: path to receipt JSON draft")
    receipt_seal.add_argument("--revision", type=int, help="Expected snapshot revision before commit")

    app = sub.add_parser("app", help="Application manifest bootstrap commands")
    app_sub = app.add_subparsers(dest="app_command", required=True)

    app_sub.add_parser("discover", help="Propose a .foundry/app.yaml manifest without writing files")

    app_init = app_sub.add_parser("init", help="Write .foundry/app.yaml from a validated manifest input")
    app_init.add_argument("--manifest-file", required=True, help="Path to manifest YAML or JSON input")
    app_init.add_argument("--dry-run", action="store_true", help="Validate and preview without writing")
    app_init.add_argument("--force", action="store_true", help="Overwrite an existing manifest")

    app_validate = app_sub.add_parser("validate", help="Validate workspace .foundry/app.yaml")
    app_validate.add_argument(
        "--manifest",
        help="Explicit manifest path (default: workspace .foundry/app.yaml)",
    )

    config = sub.add_parser("config", help="Foundry registry config commands")
    config_sub = config.add_subparsers(dest="config_command", required=True)

    config_sub.add_parser("validate", help="Validate workspace .foundry/foundry.yaml")

    config_init = config_sub.add_parser("init", help="Write .foundry/foundry.yaml registry pointer")
    config_init.add_argument(
        "--registry",
        dest="registry_path",
        help="Registry path relative to workspace (default: probe ../foundry/.cursor/foundry)",
    )
    config_init.add_argument(
        "--flow",
        help="Default flow id (default: implementation)",
    )
    config_init.add_argument("--dry-run", action="store_true", help="Validate and preview without writing")
    config_init.add_argument("--force", action="store_true", help="Overwrite an existing foundry.yaml")

    shape = sub.add_parser("shape", help="Create a run from a shape request and advance into Shape")
    shape_group = shape.add_mutually_exclusive_group(required=True)
    shape_group.add_argument("--input", help="Verbatim shape request text")
    shape_group.add_argument("--input-file", help="Path to a file containing the shape request")
    shape.add_argument("--flow", help="Flow id (default: implementation)")
    shape.add_argument("--run-id", help="Explicit run id slug")
    shape.add_argument(
        "--no-host",
        action="store_true",
        help="Do not auto-start the job host; advance on disk when host is not running",
    )
    shape.add_argument(
        "--local",
        action="store_true",
        help="Use disk/engine directly even when the job host is running",
    )

    runs = sub.add_parser("runs", help="List workspace runs (phase, node, status, wait)")
    runs.add_argument(
        "--local",
        action="store_true",
        help="Read from disk even when the job host is running",
    )

    status = sub.add_parser("status", help="Show run status (default: sole active run)")
    status.add_argument("run", nargs="?", help="Run id (optional when unambiguous)")
    status.add_argument(
        "--local",
        action="store_true",
        help="Read from disk even when the job host is running",
    )

    attach = sub.add_parser("attach", help="Show run snapshot and stream ledger events")
    attach.add_argument("run", help="Run id")
    attach.add_argument("--after-seq", type=int, default=0, help="Stream events with seq > after-seq")
    attach.add_argument(
        "--no-follow",
        action="store_true",
        help="Print snapshot (and events with --json) without streaming",
    )
    attach.add_argument(
        "--local",
        action="store_true",
        help="Use disk reads even when the job host is running",
    )

    answer = sub.add_parser("answer", help="Submit clarifying answers when wait.kind is user_input")
    answer.add_argument("run", help="Run id")
    answer.add_argument(
        "--answers",
        required=True,
        help='JSON object mapping question id to answer text, e.g. \'{"q1": "Use REST"}\'',
    )
    answer.add_argument(
        "--revision",
        type=int,
        help="Expected snapshot revision; returns STALE_REVISION on conflict",
    )
    answer.add_argument(
        "--local",
        action="store_true",
        help="Answer on disk even when the job host is running",
    )

    decide = sub.add_parser("decide", help="Submit a decision at the active user gate")
    decide.add_argument("run", help="Run id")
    decide.add_argument("option", help="One of the gate option values")
    decide.add_argument(
        "--revision",
        type=int,
        help="Expected snapshot revision; returns STALE_REVISION on conflict",
    )
    decide.add_argument(
        "--local",
        action="store_true",
        help="Decide on disk even when the job host is running",
    )

    start = sub.add_parser("start", help="Explicit Shape → Execute authorization at execute.start")
    start.add_argument("run", nargs="?", help="Run id (optional when unambiguous)")
    start.add_argument(
        "--revision",
        type=int,
        help="Expected snapshot revision; returns STALE_REVISION on conflict",
    )
    start.add_argument(
        "--no-host",
        action="store_true",
        help="Do not auto-start the job host",
    )
    start.add_argument(
        "--local",
        action="store_true",
        help="Authorize and advance on disk even when the job host is running",
    )

    retry = sub.add_parser("retry", help="Retry a recoverable halted or errored run")
    retry.add_argument("run", help="Run id")
    retry.add_argument("--reason", help="Optional reason recorded in the ledger")
    retry.add_argument("--revision", type=int, help="Expected snapshot revision")
    retry.add_argument(
        "--local",
        action="store_true",
        help="Retry on disk even when the job host is running",
    )

    cancel = sub.add_parser("cancel", help="Stop a run with a recorded reason")
    cancel.add_argument("run", help="Run id")
    cancel.add_argument("--reason", required=True, help="Why the run is being cancelled")
    cancel.add_argument("--revision", type=int, help="Expected snapshot revision")
    cancel.add_argument(
        "--local",
        action="store_true",
        help="Cancel on disk even when the job host is running",
    )

    host = sub.add_parser("host", help="Local job host control")
    host_sub = host.add_subparsers(dest="host_command", required=True)
    host_sub.add_parser("start", help="Start the background job host for this workspace")
    host_sub.add_parser("status", help="Report whether the job host is running")
    host_stop = host_sub.add_parser("stop", help="Stop the background job host")
    host_stop.add_argument("--idempotency-key", help="Client idempotency key for host.stop")
    host_sub.add_parser("run", help="Run the job host in the foreground (tests)")

    return parser
