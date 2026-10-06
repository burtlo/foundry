"""Acceptance test helpers (subprocess runner, JSON path assertions)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from tests.conftest import CLI_DIR, FOUNDRY_ROOT, REPO_ROOT

CLI_ENTRY = CLI_DIR / "foundry.py"
FIXTURES_ROOT = FOUNDRY_ROOT / "fixtures" / "runs"
DEFAULT_CATALOG_DIR = FOUNDRY_ROOT / "catalog" / "nodes"

FILE_EXISTS = "(file exists)"


def run_dir(acceptance: dict[str, Any]) -> Path:
    """Resolve the run directory from acceptance state."""
    if acceptance.get("fixture_name"):
        return FIXTURES_ROOT / str(acceptance["fixture_name"])
    workspace = Path(acceptance["workspace"])
    run_id = acceptance.get("run_id")
    assert run_id, "run_id not set in acceptance state"
    return workspace / ".foundry" / "runs" / str(run_id)


def snapshot_path(acceptance: dict[str, Any]) -> Path:
    """Resolve snapshot.json for the current acceptance run."""
    return run_dir(acceptance) / "snapshot.json"


def load_snapshot(acceptance: dict[str, Any]) -> dict[str, Any]:
    """Load snapshot.json for the current acceptance run."""
    return json.loads(snapshot_path(acceptance).read_text(encoding="utf-8"))


def active_visit_id(run_dir_path: Path, default: str | None = None) -> str:
    """Return active visit id from a run directory snapshot."""
    snapshot = json.loads((run_dir_path / "snapshot.json").read_text(encoding="utf-8"))
    active = snapshot.get("active_visit") or {}
    visit_id = active.get("id")
    if visit_id is not None:
        return str(visit_id)
    if default is not None:
        return default
    raise AssertionError("active visit id not found in snapshot")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def resolve_json_path(data: Any, path: str) -> Any:
    """Resolve dotted paths with optional [index] segments."""
    current = data
    for segment in path.split("."):
        if not segment:
            raise KeyError(path)
        while segment:
            if segment.endswith("]"):
                name, index_part = segment.split("[", 1)
                index = int(index_part[:-1])
                if name:
                    current = current[name]
                if not isinstance(current, list):
                    raise KeyError(path)
                current = current[index]
                segment = ""
            else:
                if segment not in current:
                    raise KeyError(path)
                current = current[segment]
                segment = ""
    return current


def collect_context_field_failures(context: dict[str, Any], rows: list[list[str]]) -> list[str]:
    """Evaluate all field expectations; return every failure message."""
    failures: list[str] = []
    for row in rows[1:]:
        field_path = row[0].strip()
        expected = row[1].strip()
        try:
            if expected == FILE_EXISTS:
                path_value = resolve_json_path(context, field_path)
                if not Path(str(path_value)).is_file():
                    failures.append(f"{field_path}: expected file to exist at {path_value!r}")
                continue
            actual = resolve_json_path(context, field_path)
            if isinstance(actual, bool):
                normalized = str(actual).lower()
            else:
                normalized = str(actual)
            if normalized != expected:
                failures.append(f"{field_path}: expected {expected!r}, got {actual!r}")
        except KeyError:
            failures.append(f"{field_path}: path not found in context")
        except (TypeError, ValueError, IndexError) as exc:
            failures.append(f"{field_path}: {exc}")
    return failures


def collect_index_field_failures(index: dict[str, Any], rows: list[list[str]]) -> list[str]:
    return collect_context_field_failures(index, rows)


def default_catalog_index_path(node_id: str) -> Path:
    return DEFAULT_CATALOG_DIR / f"{node_id}.index.yaml"


def invoke_foundry(acceptance: dict[str, Any]) -> None:
    argv = [
        sys.executable,
        str(CLI_ENTRY),
        "--workspace",
        str(acceptance["workspace"]),
    ]
    if not acceptance.get("omit_registry"):
        argv.extend(["--registry", str(acceptance["registry"])])
    if acceptance.get("markdown_output"):
        acceptance["json_output"] = False
    if acceptance.get("json_output", True):
        argv.append("--json")
    if acceptance.get("command") == "run context":
        argv.extend(["run", "context"])
        if acceptance.get("markdown_output"):
            argv.append("--markdown")
    elif acceptance.get("command") == "catalog build":
        argv.extend(["catalog", "build"])
        if acceptance.get("flow_id"):
            argv.extend(["--flow", str(acceptance["flow_id"])])
        if acceptance.get("node_id"):
            argv.extend(["--node", str(acceptance["node_id"])])
        if acceptance.get("output_dir"):
            argv.extend(["--output", str(acceptance["output_dir"])])
    elif acceptance.get("command") == "doc build":
        argv.extend(["doc", "build"])
        if acceptance.get("flow_id"):
            argv.extend(["--flow", str(acceptance["flow_id"])])
        if acceptance.get("node_id"):
            argv.extend(["--node", str(acceptance["node_id"])])
        if acceptance.get("output_dir"):
            argv.extend(["--output", str(acceptance["output_dir"])])
    elif acceptance.get("command") == "dev docs":
        argv.extend(["dev", "docs"])
        if acceptance.get("flow_id"):
            argv.extend(["--flow", str(acceptance["flow_id"])])
        if acceptance.get("output_dir"):
            argv.extend(["--output", str(acceptance["output_dir"])])
    elif acceptance.get("command") == "dev unit":
        argv.extend(["dev", "unit"])
    elif acceptance.get("command") == "dev acceptance":
        argv.extend(["dev", "acceptance"])
    elif acceptance.get("command") == "dev all":
        argv.extend(["dev", "all"])
    elif acceptance.get("command") == "cli resolve":
        argv.extend(["cli", "resolve"])
    elif acceptance.get("command") == "run create":
        argv.extend(["run", "create"])
        if acceptance.get("flow_id"):
            argv.extend(["--flow", str(acceptance["flow_id"])])
    elif acceptance.get("command") == "shape":
        argv.append("shape")
    elif acceptance.get("command") == "runs":
        argv.append("runs")
    elif acceptance.get("command") == "status":
        argv.append("status")
    elif acceptance.get("command") == "attach":
        argv.extend(["attach"])
    elif acceptance.get("command") == "answer":
        argv.extend(["answer"])
    elif acceptance.get("command") == "decide":
        argv.extend(["decide"])
    elif acceptance.get("command") == "start":
        argv.append("start")
    elif acceptance.get("command") == "retry":
        argv.append("retry")
    elif acceptance.get("command") == "cancel":
        argv.append("cancel")
    elif acceptance.get("command") == "host status":
        argv.extend(["host", "status"])
    elif acceptance.get("command") == "host start":
        argv.extend(["host", "start"])
    elif acceptance.get("command") == "host stop":
        argv.extend(["host", "stop"])
    elif acceptance.get("command") == "run get":
        argv.extend(["run", "get"])
    elif acceptance.get("command") == "run list":
        argv.extend(["run", "list"])
    elif acceptance.get("command") == "run events":
        argv.extend(["run", "events"])
    elif acceptance.get("command") == "run advance":
        argv.extend(["run", "advance"])
    elif acceptance.get("command") == "run recover":
        argv.extend(["run", "recover"])
    elif acceptance.get("command") == "run agent submit":
        argv.extend(["run", "agent", "submit"])
    elif acceptance.get("command") == "run archive":
        argv.extend(["run", "archive"])
    elif acceptance.get("command") == "visit state patch":
        argv.extend(["visit", "state", "patch"])
    elif acceptance.get("command") == "visit transition":
        argv.extend(["visit", "transition"])
    elif acceptance.get("command") == "visit intake complete":
        argv.extend(["visit", "intake", "complete"])
    elif acceptance.get("command") == "ledger show":
        argv.extend(["ledger", "show"])
    elif acceptance.get("command") == "artifact publish":
        argv.extend(["artifact", "publish"])
    elif acceptance.get("command") == "receipt seal":
        argv.extend(["receipt", "seal"])
    elif acceptance.get("command") == "gate decide":
        argv.extend(["gate", "decide"])
    elif acceptance.get("command") == "app discover":
        argv.extend(["app", "discover"])
    elif acceptance.get("command") == "app init":
        argv.extend(["app", "init"])
        manifest_input = acceptance.get("manifest_input")
        if manifest_input:
            argv.extend(["--manifest-file", str(manifest_input)])
    elif acceptance.get("command") == "app validate":
        argv.extend(["app", "validate"])
    elif acceptance.get("command") == "config validate":
        argv.extend(["config", "validate"])
    elif acceptance.get("command") == "config init":
        argv.extend(["config", "init"])
        config_registry = acceptance.get("config_init_registry")
        if config_registry:
            argv.extend(["--registry", str(config_registry)])
    else:
        raise AssertionError(f"Unsupported command: {acceptance.get('command')!r}")

    for flag in acceptance.get("extra_flags") or []:
        argv.append(str(flag))

    run_commands_needing_run = {
        "run context",
        "run archive",
        "visit state patch",
        "visit transition",
        "visit intake complete",
        "gate decide",
        "ledger show",
        "artifact publish",
        "receipt seal",
        "run get",
        "run events",
        "run advance",
        "run recover",
        "run agent submit",
    }
    positional_run_commands = {"attach", "answer", "decide", "start", "retry", "cancel", "status"}
    if acceptance.get("command") in positional_run_commands and acceptance.get("run_id"):
        if acceptance.get("command") != "status" or not acceptance.get("extra_argv"):
            argv.append(str(acceptance["run_id"]))
    if acceptance.get("command") in run_commands_needing_run:
        if acceptance.get("fixture_name"):
            fixture_dir = FIXTURES_ROOT / str(acceptance["fixture_name"])
            argv.extend(["--run-dir", str(fixture_dir)])
        elif acceptance.get("run_id"):
            argv.extend(["--run", str(acceptance["run_id"])])

    argv.extend(acceptance.get("extra_argv") or [])

    run_dir = None
    if acceptance.get("fixture_name"):
        run_dir = FIXTURES_ROOT / str(acceptance["fixture_name"])
    elif acceptance.get("run_id"):
        run_dir = Path(acceptance["workspace"]) / ".foundry" / "runs" / str(acceptance["run_id"])
    if run_dir is not None:
        snapshot_path = run_dir / "snapshot.json"
        ledger = None
        if snapshot_path.is_file():
            try:
                ledger = json.loads(snapshot_path.read_text(encoding="utf-8")).get("ledger")
            except json.JSONDecodeError:
                ledger = None
        acceptance["ledger_before"] = len(ledger) if isinstance(ledger, list) else None

    completed = subprocess.run(
        argv,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    acceptance["exit_code"] = completed.returncode
    acceptance["stdout"] = completed.stdout
    acceptance["stderr"] = completed.stderr
    if acceptance.get("markdown_output"):
        acceptance["markdown"] = completed.stdout
        acceptance["payload"] = None
    elif acceptance.get("json_output", True) and completed.stdout.strip():
        acceptance["payload"] = json.loads(completed.stdout)
    else:
        acceptance["payload"] = None

    if run_dir is not None:
        snapshot_path = run_dir / "snapshot.json"
        ledger = None
        if snapshot_path.is_file():
            try:
                ledger = json.loads(snapshot_path.read_text(encoding="utf-8")).get("ledger")
            except json.JSONDecodeError:
                ledger = None
        acceptance["ledger_after"] = len(ledger) if isinstance(ledger, list) else None
