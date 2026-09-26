#!/usr/bin/env python3
"""Foundry workflow CLI (v1 slice)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from foundry_cli.catalog import build_catalog, cmd_catalog_build
from foundry_cli.commands import (
    cmd_artifact_publish,
    cmd_cli_resolve,
    cmd_ledger_show,
    cmd_receipt_seal,
    cmd_run_create,
    cmd_visit_state_patch,
    cmd_visit_transition,
)
from foundry_cli.context import assemble_context
from foundry_cli.dev import cmd_dev_acceptance, cmd_dev_all, cmd_dev_docs, cmd_dev_unit
from foundry_cli.docgen import write_generated_docs
from foundry_cli.errors import error as cli_error
from foundry_cli.parser import build_parser
from foundry_cli.paths import foundry_root
from foundry_cli.registry import get_node, load_registry
from foundry_cli.render import render_context_markdown
from foundry_cli.run_store import RunStoreError, load_snapshot, resolve_run_dir, select_visit
from foundry_cli.validate import validate_payload


def _error(code: str, message: str) -> dict[str, Any]:
    return cli_error(code, message)


def cmd_run_context(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(args.workspace).resolve()
    try:
        bundle = Path(args.registry).resolve() if args.registry else foundry_root(workspace)
    except FileNotFoundError as exc:
        return _error("REGISTRY_NOT_FOUND", str(exc))

    try:
        run_dir = resolve_run_dir(
            run_id=args.run,
            run_dir=Path(args.run_dir).resolve() if args.run_dir else None,
            workspace=workspace,
        )
        snapshot = load_snapshot(run_dir)
        visit = select_visit(snapshot, args.visit)
        flow_id = args.flow or str(snapshot.get("flow_id") or "implementation")
        _, flow = load_registry(bundle, flow_id=flow_id)
        get_node(flow, str(visit["node_id"]))
    except RunStoreError as exc:
        return _error(exc.code, exc.message)
    except KeyError as exc:
        return _error("NODE_NOT_FOUND", f"Node not found in flow registry: {exc.args[0]}")
    except ValueError as exc:
        return _error("INVALID_NODE", str(exc))

    try:
        context = assemble_context(
            snapshot=snapshot,
            visit=visit,
            flow=flow,
            foundry_bundle=bundle,
            run_dir=run_dir,
        )
    except ValueError as exc:
        return _error("INVALID_NODE", str(exc))

    schema_errors = validate_payload(context, "context-packet.schema.json", bundle)
    if schema_errors:
        return _error("SCHEMA_VALIDATION_FAILED", "; ".join(schema_errors))

    return {"ok": True, "context": context}


def cmd_doc_build(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(args.workspace).resolve()
    try:
        bundle = Path(args.registry).resolve() if args.registry else foundry_root(workspace)
    except FileNotFoundError as exc:
        return _error("REGISTRY_NOT_FOUND", str(exc))

    flow_id = args.flow or "implementation"
    try:
        _, flow = load_registry(bundle, flow_id=flow_id)
    except ValueError as exc:
        return _error("INVALID_FLOW", str(exc))

    all_flow_nodes = [
        str(node["id"])
        for node in (flow.get("nodes") or [])
        if isinstance(node, dict) and node.get("id")
    ]

    if args.node:
        node_ids = [args.node]
        catalog_node_id = args.node
        write_index = False
        try:
            get_node(flow, args.node)
        except KeyError:
            return _error("NODE_NOT_FOUND", f"Node not found in flow registry: {args.node!r}")
    else:
        node_ids = all_flow_nodes
        catalog_node_id = None
        write_index = True

    catalog_result = build_catalog(
        foundry_bundle=bundle,
        flow_id=flow_id,
        node_id=catalog_node_id,
        json_mode=False,
    )
    if not catalog_result.get("ok"):
        return catalog_result

    output_dir = Path(args.output).resolve() if args.output else workspace / "docs"
    parser = build_parser()
    written = write_generated_docs(
        flow=flow,
        foundry_bundle=bundle,
        repo_root=workspace,
        node_ids=node_ids,
        output_dir=output_dir,
        write_index=write_index,
        cli_parser=parser,
    )
    return {
        "ok": True,
        "flow_id": flow_id,
        "output_dir": str(output_dir),
        "generated": [str(path) for path in written],
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "cli" and args.cli_command == "resolve":
        result = cmd_cli_resolve(args)
    elif args.command == "run" and args.run_command == "create":
        result = cmd_run_create(args)
    elif args.command == "visit" and args.visit_command == "state" and args.visit_state_command == "patch":
        result = cmd_visit_state_patch(args)
    elif args.command == "visit" and args.visit_command == "transition":
        result = cmd_visit_transition(args)
    elif args.command == "ledger" and args.ledger_command == "show":
        result = cmd_ledger_show(args)
    elif args.command == "artifact" and args.artifact_command == "publish":
        result = cmd_artifact_publish(args)
    elif args.command == "receipt" and args.receipt_command == "seal":
        result = cmd_receipt_seal(args)
    elif args.command == "run" and args.run_command == "context":
        if args.json and getattr(args, "markdown", False):
            result = _error(
                "INVALID_FLAGS",
                "--json and --markdown are mutually exclusive for run context",
            )
        else:
            result = cmd_run_context(args)
    elif args.command == "catalog" and args.catalog_command == "build":
        result = cmd_catalog_build(args)
    elif args.command == "doc" and args.doc_command == "build":
        result = cmd_doc_build(args)
    elif args.command == "dev" and args.dev_command == "docs":
        result = cmd_dev_docs(args)
    elif args.command == "dev" and args.dev_command == "unit":
        result = cmd_dev_unit(args)
    elif args.command == "dev" and args.dev_command == "acceptance":
        result = cmd_dev_acceptance(args)
    elif args.command == "dev" and args.dev_command == "all":
        result = cmd_dev_all(args)
    else:
        result = _error("UNKNOWN_COMMAND", "Command not implemented")

    if (
        result.get("ok")
        and args.command == "run"
        and args.run_command == "context"
        and getattr(args, "markdown", False)
    ):
        context = result.get("context", {})
        instructions_path = str(context.get("instructions_path") or "")
        instructions_text = ""
        if instructions_path:
            try:
                instructions_text = Path(instructions_path).read_text(encoding="utf-8")
            except OSError as exc:
                result = _error(
                    "INSTRUCTIONS_READ_FAILED",
                    f"Could not read instructions at {instructions_path!r}: {exc}",
                )
        if result.get("ok"):
            print(render_context_markdown(context, instructions_text), end="")
    elif args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result.get("ok") and args.command == "run" and args.run_command == "context":
        context = result.get("context", {})
        print(f"run={context.get('run_id')} visit={context.get('visit_id')} node={context.get('node_id')}")
        print(f"lifecycle={context.get('lifecycle')}")
        print(f"instructions={context.get('instructions')}")
    elif result.get("ok") and args.command == "catalog" and args.catalog_command == "build":
        print(f"flow={result.get('flow_id')} nodes={result.get('node_count')}")
        print(f"output={result.get('output_dir')}")
    elif result.get("ok") and args.command == "doc" and args.doc_command == "build":
        generated = result.get("generated", [])
        print(f"Generated {len(generated)} file(s) in {result.get('output_dir')}")
        for path in generated:
            print(path)
    elif result.get("ok") and args.command == "dev" and args.dev_command == "docs":
        print(f"Generated {result.get('generated_count')} file(s) in {result.get('output_dir')}")
    elif result.get("ok") and args.command == "dev" and args.dev_command in {"unit", "acceptance", "all"}:
        suite = result.get("suite", args.dev_command)
        print(f"suite={suite} ok=true")
        if args.dev_command == "all":
            print(f"suites_passed={','.join(result.get('suites_passed') or [])}")
    else:
        error = result.get("error", {})
        print(f"error [{error.get('code')}]: {error.get('message')}", file=sys.stderr)

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
