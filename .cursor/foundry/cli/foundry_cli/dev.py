"""Developer workflow shortcuts (docs, unit tests, acceptance tests)."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from foundry_cli.command_context import CommandContext
from foundry_cli.constants import DEFAULT_FLOW_ID
from foundry_cli.docs import build_docs
from foundry_cli.engine.node_runtime_matrix import write_node_runtime_matrix
from foundry_cli.errors import error
from foundry_cli.paths import repo_root_from_bundle

CLI_DIR = Path(__file__).resolve().parents[1]
UNIT_TESTS = CLI_DIR / "tests" / "unit"
ACCEPTANCE_TESTS = CLI_DIR / "tests" / "acceptance"
_DEV_PYTEST_GUARD = "FOUNDRY_DEV_PYTEST_ACTIVE"


def run_pytest(
    target: Path,
    *,
    quiet: bool = False,
    extra_argv: list[str] | None = None,
) -> dict[str, Any]:
    """Run pytest against a test directory; return a structured result."""
    if os.environ.get(_DEV_PYTEST_GUARD):
        return error(
            "NESTED_DEV_PYTEST",
            "Refusing nested dev pytest invocation (dev acceptance/all must exclude dev_commands scenarios)",
        )

    argv = [sys.executable, "-m", "pytest", str(target)]
    if quiet:
        argv.append("-q")
    else:
        argv.extend(["-v", "--tb=short"])
    argv.extend(extra_argv or [])

    env = os.environ.copy()
    env[_DEV_PYTEST_GUARD] = "1"
    completed = subprocess.run(argv, cwd=CLI_DIR, capture_output=True, text=True, env=env)
    return {
        "ok": completed.returncode == 0,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "command": " ".join(argv),
    }


def run_unit_tests(
    *,
    quiet: bool = False,
    parallel: bool = False,
    extra_argv: list[str] | None = None,
) -> dict[str, Any]:
    argv = list(extra_argv or [])
    if parallel and not any(arg == "-n" or arg.startswith("-n") for arg in argv):
        argv = ["-n", "auto", *argv]
    result = run_pytest(UNIT_TESTS, quiet=quiet, extra_argv=argv)
    result["suite"] = "unit"
    return result


def run_acceptance_tests(
    *,
    quiet: bool = False,
    extra_argv: list[str] | None = None,
    exclude_dev_scenarios: bool = True,
) -> dict[str, Any]:
    """Run acceptance tests. Dev scenarios are excluded by default to prevent recursion."""
    argv = list(extra_argv or [])
    if exclude_dev_scenarios:
        argv = ["-k", "not dev_commands", *argv]
    result = run_pytest(ACCEPTANCE_TESTS, quiet=quiet, extra_argv=argv)
    result["suite"] = "acceptance"
    return result


def run_all_tests(
    *,
    quiet: bool = False,
    parallel: bool = False,
    extra_argv: list[str] | None = None,
    exclude_dev_scenarios: bool = True,
) -> dict[str, Any]:
    unit = run_unit_tests(quiet=quiet, parallel=parallel, extra_argv=extra_argv)
    acceptance = run_acceptance_tests(
        quiet=quiet,
        extra_argv=extra_argv,
        exclude_dev_scenarios=exclude_dev_scenarios,
    )
    suites_passed = [
        name
        for name, result in (("unit", unit), ("acceptance", acceptance))
        if result.get("ok")
    ]
    return {
        "ok": unit.get("ok") and acceptance.get("ok"),
        "suite": "all",
        "suites_passed": suites_passed,
        "unit": unit,
        "acceptance": acceptance,
    }


def run_dev_docs(
    *,
    workspace: Path,
    foundry_bundle: Path,
    flow_id: str = DEFAULT_FLOW_ID,
    output_dir: Path | None = None,
    smoke: bool = False,
) -> dict[str, Any]:
    """Build catalog indexes and generate node documentation."""
    return build_docs(
        workspace=workspace,
        bundle=foundry_bundle,
        flow_id=flow_id,
        output_dir=output_dir,
        smoke=smoke,
        repo_root=repo_root_from_bundle(foundry_bundle),
    )


def cmd_dev_engine_matrix(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    flow_id = args.flow or DEFAULT_FLOW_ID
    output = Path(args.output).resolve() if getattr(args, "output", None) else None
    return write_node_runtime_matrix(
        ctx.bundle,
        flow_id=flow_id,
        output_path=output,
    )


def cmd_dev_docs(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    flow_id = args.flow or DEFAULT_FLOW_ID
    output_dir = Path(args.output).resolve() if args.output else None
    return run_dev_docs(
        workspace=ctx.workspace,
        foundry_bundle=ctx.bundle,
        flow_id=flow_id,
        output_dir=output_dir,
        smoke=bool(getattr(args, "smoke", False)),
    )


def cmd_dev_unit(args: argparse.Namespace) -> dict[str, Any]:
    return run_unit_tests(
        quiet=bool(args.quiet),
        parallel=bool(getattr(args, "parallel", False)),
        extra_argv=list(args.pytest_args or []),
    )


def cmd_dev_acceptance(args: argparse.Namespace) -> dict[str, Any]:
    return run_acceptance_tests(
        quiet=bool(args.quiet),
        extra_argv=list(args.pytest_args or []),
        exclude_dev_scenarios=not bool(getattr(args, "include_dev_scenarios", False)),
    )


def cmd_dev_all(args: argparse.Namespace) -> dict[str, Any]:
    return run_all_tests(
        quiet=bool(args.quiet),
        parallel=bool(getattr(args, "parallel", False)),
        extra_argv=list(args.pytest_args or []),
        exclude_dev_scenarios=not bool(getattr(args, "include_dev_scenarios", False)),
    )
