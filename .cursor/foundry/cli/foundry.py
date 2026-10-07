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
    cmd_run_advance,
    cmd_run_archive,
    cmd_run_context,
    cmd_run_create,
    cmd_run_events,
    cmd_run_get,
    cmd_run_list,
    cmd_run_agent_submit,
    cmd_run_recover,
    cmd_visit_examine_complete,
    cmd_visit_intake_complete,
    cmd_visit_present_complete,
    cmd_visit_plan_complete,
    cmd_visit_record_complete,
    cmd_visit_state_patch,
    cmd_visit_transition,
)
from foundry_cli.user_cli import (
    cmd_answer,
    cmd_attach,
    cmd_cancel,
    cmd_decide,
    cmd_retry,
    cmd_runs,
    cmd_shape,
    cmd_start,
    cmd_status,
)
from foundry_cli.dev import (
    cmd_dev_acceptance,
    cmd_dev_all,
    cmd_dev_docs,
    cmd_dev_engine_matrix,
    cmd_dev_unit,
)
from foundry_cli.bridge_commands import cmd_bridge_start
from foundry_cli.tui_commands import cmd_tui
from foundry_cli.host_commands import (
    cmd_host_logs,
    cmd_host_run,
    cmd_host_start,
    cmd_host_status,
    cmd_host_stop,
)
from foundry_cli.errors import error
from foundry_cli.parser import parse_args
from foundry_cli.render import render_context_markdown

CommandHandler = Callable[[argparse.Namespace], dict[str, Any]]
ResultFormatter = Callable[[argparse.Namespace, dict[str, Any]], None]

COMMAND_REGISTRY: dict[tuple[str, ...], CommandHandler] = {
    ("cli", "resolve"): cmd_cli_resolve,
    ("run", "create"): cmd_run_create,
    ("run", "get"): cmd_run_get,
    ("run", "list"): cmd_run_list,
    ("run", "events"): cmd_run_events,
    ("run", "advance"): cmd_run_advance,
    ("run", "recover"): cmd_run_recover,
    ("run", "agent", "submit"): cmd_run_agent_submit,
    ("run", "context"): cmd_run_context,
    ("run", "archive"): cmd_run_archive,
    ("visit", "state", "patch"): cmd_visit_state_patch,
    ("visit", "intake", "complete"): cmd_visit_intake_complete,
    ("visit", "examine", "complete"): cmd_visit_examine_complete,
    ("visit", "present", "complete"): cmd_visit_present_complete,
    ("visit", "record", "complete"): cmd_visit_record_complete,
    ("visit", "plan", "complete"): cmd_visit_plan_complete,
    ("visit", "transition"): cmd_visit_transition,
    ("gate", "decide"): cmd_gate_decide,
    ("ledger", "show"): cmd_ledger_show,
    ("artifact", "publish"): cmd_artifact_publish,
    ("receipt", "seal"): cmd_receipt_seal,
    ("catalog", "build"): cmd_catalog_build,
    ("doc", "build"): cmd_doc_build,
    ("dev", "docs"): cmd_dev_docs,
    ("dev", "engine-matrix"): cmd_dev_engine_matrix,
    ("dev", "unit"): cmd_dev_unit,
    ("dev", "acceptance"): cmd_dev_acceptance,
    ("dev", "all"): cmd_dev_all,
    ("app", "discover"): cmd_app_discover,
    ("app", "init"): cmd_app_init,
    ("app", "validate"): cmd_app_validate,
    ("config", "validate"): cmd_config_validate,
    ("config", "init"): cmd_config_init,
    ("shape",): cmd_shape,
    ("runs",): cmd_runs,
    ("status",): cmd_status,
    ("attach",): cmd_attach,
    ("answer",): cmd_answer,
    ("decide",): cmd_decide,
    ("start",): cmd_start,
    ("retry",): cmd_retry,
    ("cancel",): cmd_cancel,
    ("host", "start"): cmd_host_start,
    ("host", "status"): cmd_host_status,
    ("host", "logs"): cmd_host_logs,
    ("host", "stop"): cmd_host_stop,
    ("host", "run"): cmd_host_run,
    ("bridge", "start"): cmd_bridge_start,
    ("tui",): cmd_tui,
}


def _command_key(args: argparse.Namespace) -> tuple[str, ...]:
    cmd = args.command
    if cmd == "cli":
        return (cmd, args.cli_command)
    if cmd == "run":
        if args.run_command == "agent":
            return (cmd, args.run_command, args.run_agent_command)
        return (cmd, args.run_command)
    if cmd == "visit":
        if args.visit_command == "state":
            return (cmd, args.visit_command, args.visit_state_command)
        if args.visit_command == "intake":
            return (cmd, args.visit_command, args.visit_intake_command)
        if args.visit_command == "examine":
            return (cmd, args.visit_command, args.visit_examine_command)
        if args.visit_command == "present":
            return (cmd, args.visit_command, args.visit_present_command)
        if args.visit_command == "record":
            return (cmd, args.visit_command, args.visit_record_command)
        if args.visit_command == "plan":
            return (cmd, args.visit_command, args.visit_plan_command)
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
    if cmd in {"shape", "runs", "status", "attach", "answer", "decide", "start", "retry", "cancel", "tui"}:
        return (cmd,)
    if cmd == "host":
        return (cmd, args.host_command)
    if cmd == "bridge":
        return (cmd, args.bridge_command)
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
    err = result.get("error")
    if isinstance(err, dict) and (err.get("code") or err.get("message")):
        print(f"error [{err.get('code')}]: {err.get('message')}", file=sys.stderr)
    elif result.get("suite") in {"unit", "acceptance", "all"}:
        exit_code = result.get("exit_code")
        print(f"tests failed (exit_code={exit_code})", file=sys.stderr)
        stdout = result.get("stdout") or ""
        stderr = result.get("stderr") or ""
        if stdout.strip():
            print(stdout, file=sys.stderr, end="" if stdout.endswith("\n") else "\n")
        if stderr.strip():
            print(stderr, file=sys.stderr, end="" if stderr.endswith("\n") else "\n")
        if isinstance(err, dict) and err:
            print(f"error [{err.get('code')}]: {err.get('message')}", file=sys.stderr)
    else:
        err_dict = err if isinstance(err, dict) else {}
        print(f"error [{err_dict.get('code')}]: {err_dict.get('message')}", file=sys.stderr)


def _format_run_context(_args: argparse.Namespace, result: dict[str, Any]) -> None:
    context = result.get("context", {})
    print(f"run={context.get('run_id')} visit={context.get('visit_id')} node={context.get('node_id')}")
    print(f"lifecycle={context.get('lifecycle')}")
    print(f"instructions={context.get('instructions')}")


def _format_run_context_markdown(
    _args: argparse.Namespace, result: dict[str, Any]
) -> dict[str, Any] | None:
    prebuilt = result.get("markdown")
    if isinstance(prebuilt, str):
        print(prebuilt, end="")
        return None
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
    operations_path = str(context.get("operations_path") or "")
    operations_text = ""
    if operations_path:
        try:
            operations_text = Path(operations_path).read_text(encoding="utf-8")
        except OSError as exc:
            return error(
                "OPERATIONS_READ_FAILED",
                f"Could not read operations at {operations_path!r}: {exc}",
            )
    print(
        render_context_markdown(context, instructions_text, operations_text=operations_text),
        end="",
    )
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


def _format_dev_engine_matrix(_args: argparse.Namespace, result: dict[str, Any]) -> None:
    print(f"flow={result.get('flow_id')} nodes={result.get('node_count')}")
    print(f"output={result.get('output_path')}")


def _format_dev_test_suite(args: argparse.Namespace, result: dict[str, Any]) -> None:
    suite = result.get("suite", args.dev_command)
    print(f"suite={suite} ok=true")
    if args.dev_command == "all":
        print(f"suites_passed={','.join(result.get('suites_passed') or [])}")


def _format_runs(_args: argparse.Namespace, result: dict[str, Any]) -> None:
    for row in result.get("runs") or []:
        if not isinstance(row, dict):
            continue
        print(
            f"{row.get('run_id')} status={row.get('status')} "
            f"node={row.get('active_node_id')} wait={row.get('wait_kind')}"
        )


def _format_status(_args: argparse.Namespace, result: dict[str, Any]) -> None:
    print(
        f"run={result.get('run_id')} phase={result.get('phase')} "
        f"status={result.get('status')} node={result.get('active_node_id')} "
        f"revision={result.get('revision')}"
    )
    wait_kind = result.get("wait_kind")
    if wait_kind:
        wait = result.get("wait") if isinstance(result.get("wait"), dict) else {}
        print(f"wait={wait_kind} summary={wait.get('summary')!r}")


def _format_shape(_args: argparse.Namespace, result: dict[str, Any]) -> None:
    print(f"run={result.get('run_id')} node={result.get('active_node_id')} revision={result.get('revision')}")
    wait = result.get("wait")
    if isinstance(wait, dict):
        print(f"wait={wait.get('kind')} summary={wait.get('summary')!r}")


def _format_host_status(_args: argparse.Namespace, result: dict[str, Any]) -> None:
    running = result.get("running")
    print(f"host running={running}")
    logs = result.get("logs")
    if isinstance(logs, dict):
        if logs.get("host"):
            print(f"log_host={logs.get('host')}")
        if logs.get("startup"):
            print(f"log_startup={logs.get('startup')}")
    host = result.get("host")
    if isinstance(host, dict) and host:
        print(
            f"pid={host.get('pid')} transport={host.get('transport')} "
            f"address={host.get('address')} started_at={host.get('started_at')}"
        )
        if host.get("auto_advance"):
            print(
                f"auto_advance=true interval={host.get('auto_advance_interval')} "
                f"status_file={result.get('auto_advance_status_path')}"
            )
        else:
            print("auto_advance=false")
    status = result.get("auto_advance_status")
    if isinstance(status, dict) and status:
        print(
            f"auto_advance_tick last={status.get('last_tick_at')} "
            f"advanced={status.get('runs_advanced')} "
            f"eligible={status.get('runs_eligible')} "
            f"scanned={status.get('runs_scanned')}"
        )
        failures = status.get("recent_failures")
        if isinstance(failures, list) and failures:
            last = failures[-1]
            if isinstance(last, dict):
                print(
                    f"auto_advance_last_failure run={last.get('run_id')} "
                    f"code={last.get('code')} message={last.get('message')}"
                )


FORMATTER_REGISTRY: dict[tuple[str, ...], ResultFormatter] = {
    ("run", "context"): _format_run_context,
    ("runs",): _format_runs,
    ("status",): _format_status,
    ("shape",): _format_shape,
    ("host", "status"): _format_host_status,
    ("catalog", "build"): _format_catalog_build,
    ("doc", "build"): _format_doc_build,
    ("dev", "docs"): _format_dev_docs,
    ("dev", "engine-matrix"): _format_dev_engine_matrix,
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


def _ensure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass


def main(argv: list[str] | None = None) -> int:
    _ensure_utf8_stdio()
    args = parse_args(argv)
    result = _format_result(args, _dispatch(args))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
