"""Argparse definition for the Foundry CLI."""

from __future__ import annotations

import argparse


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

    visit_transition = visit_sub.add_parser("transition", help="Request close and seal on an opened visit")
    visit_transition.add_argument("--run", help="Run id")
    visit_transition.add_argument("--visit", help="Visit id (default: active visit)")
    visit_transition.add_argument("--run-dir", help="Run directory containing snapshot.json")
    visit_transition.add_argument("--summary", help="Short steward summary")

    gate = sub.add_parser("gate", help="Gate decision commands")
    gate_sub = gate.add_subparsers(dest="gate_command", required=True)

    gate_decide = gate_sub.add_parser("decide", help="Record a user gate decision and close the visit")
    gate_decide.add_argument("--run", help="Run id")
    gate_decide.add_argument("--visit", help="Visit id (default: active gate visit)")
    gate_decide.add_argument("--run-dir", help="Run directory containing snapshot.json")
    gate_decide.add_argument("--decision", required=True, help="One of the gate produces.options values")

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

    receipt = sub.add_parser("receipt", help="Receipt sealing commands")
    receipt_sub = receipt.add_subparsers(dest="receipt_command", required=True)

    receipt_seal = receipt_sub.add_parser("seal", help="Validate and seal a receipt draft")
    receipt_seal.add_argument("--run", help="Run id")
    receipt_seal.add_argument("--visit", help="Visit id (default: active visit)")
    receipt_seal.add_argument("--run-dir", help="Run directory containing snapshot.json")
    receipt_seal.add_argument("--schema", help="Receipt schema registry path")
    receipt_seal.add_argument("--file", required=True, help="run: or workspace: path to receipt JSON draft")

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

    return parser
