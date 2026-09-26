#!/usr/bin/env python3
"""Foundry workflow CLI (v1 slice)."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from foundry_cli.catalog import cmd_catalog_build
from foundry_cli.commands import (
    cmd_app_discover,
    cmd_app_init,
    cmd_app_validate,
    cmd_artifact_publish,
    cmd_cli_resolve,
    cmd_config_init,
    cmd_config_validate,
    cmd_doc_build,
    cmd_gate_decide,
    cmd_ledger_show,
    cmd_receipt_seal,
    cmd_run_context,
    cmd_run_create,
    cmd_visit_state_patch,
    cmd_visit_transition,
)
from foundry_cli.dev import cmd_dev_acceptance, cmd_dev_all, cmd_dev_docs, cmd_dev_unit
from foundry_cli.errors import error
from foundry_cli.parser import build_parser
from foundry_cli.render import render_context_markdown

CommandHandler = Callable[[argparse.Namespace], dict[str, Any]]
ResultFormatter = Callable[[argparse.Namespace, dict[str, Any]], None]

COMMAND_REGISTRY: dict[tuple[str, ...], CommandHandler] = {
    ("cli", "resolve"): cmd_cli_resolve,
    ("run", "create"): cmd_run_create,
    ("run", "context"): cmd_run_context,
    ("visit", "state", "patch"): cmd_visit_state_patch,
    ("visit", "transition"): cmd_visit_transition,
    ("gate", "decide"): cmd_gate_decide,
    ("ledger", "show"): cmd_ledger_show,
    ("artifact", "publish"): cmd_artifact_publish,
    ("receipt", "seal"): cmd_receipt_seal,
    ("catalog", "build"): cmd_catalog_build,
    ("doc", "build"): cmd_doc_build,
    ("dev", "docs"): cmd_dev_docs,
    ("dev", "unit"): cmd_dev_unit,
    ("dev", "acceptance"): cmd_dev_acceptance,
    ("dev", "all"): cmd_dev_all,
    ("app", "discover"): cmd_app_discover,
    ("app", "init"): cmd_app_init,
    ("app", "validate"): cmd_app_validate,
    ("config", "validate"): cmd_config_validate,
    ("config", "init"): cmd_config_init,
}


def _command_key(args: argparse.Namespace) -> tuple[str, ...]:
    cmd = args.command
    if cmd == "cli":
        return (cmd, args.cli_command)
    if cmd == "run":
        return (cmd, args.run_command)
    if cmd == "visit":
        if args.visit_command == "state":
            return (cmd, args.visit_command, args.visit_state_command)
        return (cmd, args.visit_command)
    if cmd == "gate":
        return (cmd, args.gate_command)
    if cmd == "ledger":
        return (cmd, args.ledger_command)
    if cmd == "artifact":
        return (cmd, args.artifact_command)
    if cmd == "receipt":
        return (cmd, args.receipt_command)
    if cmd == "catalog":
        return (cmd, args.catalog_command)
    if cmd == "doc":
        return (cmd, args.doc_command)
    if cmd == "dev":
        return (cmd, args.dev_command)
    if cmd == "app":
        return (cmd, args.app_command)
    if cmd == "config":
        return (cmd, args.config_command)
    return (cmd,)


def _dispatch(args: argparse.Namespace) -> dict[str, Any]:
    key = _command_key(args)
    if key == ("run", "context") and args.json and getattr(args, "markdown", False):
        return error(
            "INVALID_FLAGS",
            "--json and --markdown are mutually exclusive for run context",
        )

    handler = COMMAND_REGISTRY.get(key)
    if handler is None:
        return error("UNKNOWN_COMMAND", "Command not implemented")
    return handler(args)


def _format_json(_args: argparse.Namespace, result: dict[str, Any]) -> None:
    print(json.dumps(result, indent=2, sort_keys=True))


def _format_error(_args: argparse.Namespace, result: dict[str, Any]) -> None:
    err = result.get("error", {})
    print(f"error [{err.get('code')}]: {err.get('message')}", file=sys.stderr)


def _format_run_context(_args: argparse.Namespace, result: dict[str, Any]) -> None:
    context = result.get("context", {})
    print(f"run={context.get('run_id')} visit={context.get('visit_id')} node={context.get('node_id')}")
    print(f"lifecycle={context.get('lifecycle')}")
    print(f"instructions={context.get('instructions')}")


def _format_run_context_markdown(
    _args: argparse.Namespace, result: dict[str, Any]
) -> dict[str, Any] | None:
    context = result.get("context", {})
    instructions_path = str(context.get("instructions_path") or "")
    instructions_text = ""
    if instructions_path:
        try:
            instructions_text = Path(instructions_path).read_text(encoding="utf-8")
        except OSError as exc:
            return error(
                "INSTRUCTIONS_READ_FAILED",
                f"Could not read instructions at {instructions_path!r}: {exc}",
            )
    print(render_context_markdown(context, instructions_text), end="")
    return None


def _format_catalog_build(_args: argparse.Namespace, result: dict[str, Any]) -> None:
    print(f"flow={result.get('flow_id')} nodes={result.get('node_count')}")
    print(f"output={result.get('output_dir')}")


def _format_doc_build(_args: argparse.Namespace, result: dict[str, Any]) -> None:
    generated = result.get("generated", [])
    print(f"Generated {len(generated)} file(s) in {result.get('output_dir')}")
    for path in generated:
        print(path)


def _format_dev_docs(_args: argparse.Namespace, result: dict[str, Any]) -> None:
    print(f"Generated {result.get('generated_count')} file(s) in {result.get('output_dir')}")


def _format_dev_test_suite(args: argparse.Namespace, result: dict[str, Any]) -> None:
    suite = result.get("suite", args.dev_command)
    print(f"suite={suite} ok=true")
    if args.dev_command == "all":
        print(f"suites_passed={','.join(result.get('suites_passed') or [])}")


FORMATTER_REGISTRY: dict[tuple[str, ...], ResultFormatter] = {
    ("run", "context"): _format_run_context,
    ("catalog", "build"): _format_catalog_build,
    ("doc", "build"): _format_doc_build,
    ("dev", "docs"): _format_dev_docs,
    ("dev", "unit"): _format_dev_test_suite,
    ("dev", "acceptance"): _format_dev_test_suite,
    ("dev", "all"): _format_dev_test_suite,
}


def _format_result(args: argparse.Namespace, result: dict[str, Any]) -> dict[str, Any]:
    """Print CLI output for a command result; may replace result on read errors."""
    key = _command_key(args)

    if result.get("ok") and key == ("run", "context") and getattr(args, "markdown", False):
        replacement = _format_run_context_markdown(args, result)
        if replacement is not None:
            return replacement
        return result

    if args.json:
        _format_json(args, result)
        return result

    if result.get("ok"):
        formatter = FORMATTER_REGISTRY.get(key)
        if formatter is not None:
            formatter(args, result)
            return result

    _format_error(args, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = _format_result(args, _dispatch(args))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
