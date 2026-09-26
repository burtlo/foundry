"""Developer workflow shortcuts (docs, unit tests, acceptance tests)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from foundry_cli.catalog import build_catalog
from foundry_cli.docgen import write_generated_docs
from foundry_cli.paths import foundry_root, repo_root_from_bundle
from foundry_cli.registry import load_registry

CLI_DIR = Path(__file__).resolve().parents[1]
UNIT_TESTS = CLI_DIR / "tests" / "unit"
ACCEPTANCE_TESTS = CLI_DIR / "tests" / "acceptance"
_DEV_PYTEST_GUARD = "FOUNDRY_DEV_PYTEST_ACTIVE"


def _error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message}}


def run_pytest(
    target: Path,
    *,
    quiet: bool = False,
    extra_argv: list[str] | None = None,
) -> dict[str, Any]:
    """Run pytest against a test directory; return a structured result."""
    if os.environ.get(_DEV_PYTEST_GUARD):
        return _error(
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


def run_unit_tests(*, quiet: bool = False, extra_argv: list[str] | None = None) -> dict[str, Any]:
    result = run_pytest(UNIT_TESTS, quiet=quiet, extra_argv=extra_argv)
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
    extra_argv: list[str] | None = None,
    exclude_dev_scenarios: bool = True,
) -> dict[str, Any]:
    unit = run_unit_tests(quiet=quiet, extra_argv=extra_argv)
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
    flow_id: str = "implementation",
    output_dir: Path | None = None,
    smoke: bool = False,
) -> dict[str, Any]:
    """Build catalog indexes and generate node documentation."""
    try:
        _, flow = load_registry(foundry_bundle, flow_id=flow_id)
    except ValueError as exc:
        return _error("INVALID_FLOW", str(exc))

    if smoke:
        node_ids = ["shape.intake"]
        catalog_node_id = "shape.intake"
    else:
        node_ids = [
            str(node["id"])
            for node in (flow.get("nodes") or [])
            if isinstance(node, dict) and node.get("id")
        ]
        catalog_node_id = None

    catalog_result = build_catalog(
        foundry_bundle=foundry_bundle,
        flow_id=flow_id,
        node_id=catalog_node_id,
        json_mode=False,
    )
    if not catalog_result.get("ok"):
        return catalog_result

    out = output_dir or (repo_root_from_bundle(foundry_bundle) / "docs")
    from foundry_cli.parser import build_parser

    written = write_generated_docs(
        flow=flow,
        foundry_bundle=foundry_bundle,
        repo_root=repo_root_from_bundle(foundry_bundle),
        node_ids=node_ids,
        output_dir=out,
        write_index=not smoke,
        cli_parser=build_parser(),
    )
    return {
        "ok": True,
        "flow_id": flow_id,
        "output_dir": str(out.resolve()),
        "generated_count": len(written),
        "generated": [str(path) for path in written],
    }


def cmd_dev_docs(args) -> dict[str, Any]:
    workspace = Path(args.workspace).resolve()
    try:
        bundle = Path(args.registry).resolve() if args.registry else foundry_root(workspace)
    except FileNotFoundError as exc:
        return _error("REGISTRY_NOT_FOUND", str(exc))

    flow_id = args.flow or "implementation"
    output_dir = Path(args.output).resolve() if args.output else None
    return run_dev_docs(
        workspace=workspace,
        foundry_bundle=bundle,
        flow_id=flow_id,
        output_dir=output_dir,
        smoke=bool(getattr(args, "smoke", False)),
    )


def cmd_dev_unit(args) -> dict[str, Any]:
    return run_unit_tests(quiet=bool(args.quiet), extra_argv=list(args.pytest_args or []))


def cmd_dev_acceptance(args) -> dict[str, Any]:
    return run_acceptance_tests(
        quiet=bool(args.quiet),
        extra_argv=list(args.pytest_args or []),
        exclude_dev_scenarios=not bool(getattr(args, "include_dev_scenarios", False)),
    )


def cmd_dev_all(args) -> dict[str, Any]:
    return run_all_tests(
        quiet=bool(args.quiet),
        extra_argv=list(args.pytest_args or []),
        exclude_dev_scenarios=not bool(getattr(args, "include_dev_scenarios", False)),
    )
