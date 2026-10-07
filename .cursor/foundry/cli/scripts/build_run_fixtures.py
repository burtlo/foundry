#!/usr/bin/env python3
"""Regenerate committed run fixtures under .cursor/foundry/fixtures/runs/."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[1]
FOUNDRY_ROOT = CLI_DIR.parent
FIXTURES_ROOT = FOUNDRY_ROOT / "fixtures" / "runs"
SOURCE_FIXTURE = "porcelain-0007-v007-record-gate"

sys.path.insert(0, str(CLI_DIR))

from foundry_cli.engine.advance import advance_run  # noqa: E402
from foundry_cli.registry import load_registry  # noqa: E402
from foundry_cli.run_service import execute_start_durable  # noqa: E402
from foundry_cli.run_store import load_snapshot, save_snapshot  # noqa: E402
from tests.unit.execute_advance_helpers import submit_execute_plan_proceed_if_waiting  # noqa: E402
from tests.unit.git_workspace import ensure_clean_git_workspace  # noqa: E402

BUNDLE = FOUNDRY_ROOT
CLI = CLI_DIR / "foundry.py"


def _workspace_with_fixture(workspace_root: Path, fixture_name: str) -> tuple[Path, str]:
    src = FIXTURES_ROOT / fixture_name
    snapshot = json.loads((src / "snapshot.json").read_text(encoding="utf-8"))
    run_id = str(snapshot.get("run_id") or fixture_name)
    workspace = workspace_root / "app"
    dest = workspace / ".foundry" / "runs" / run_id
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    shutil.copytree(
        BUNDLE / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
        dirs_exist_ok=True,
    )
    ensure_clean_git_workspace(workspace)
    return workspace, run_id


def _run_cli(workspace: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--json",
            "--workspace",
            str(workspace),
            "--registry",
            str(BUNDLE),
            *argv,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _authorize_execute(workspace: Path, run_id: str) -> None:
    decide = _run_cli(workspace, "gate", "decide", "--run", run_id, "--decision", "accept")
    if decide.returncode != 0:
        raise RuntimeError(f"gate decide failed: {decide.stderr} {decide.stdout}")
    advance = _run_cli(workspace, "run", "advance", "--run", run_id)
    if advance.returncode != 0:
        raise RuntimeError(f"run advance failed: {advance.stderr} {advance.stdout}")
    ensure_clean_git_workspace(workspace)
    start = execute_start_durable(workspace=workspace, bundle=BUNDLE, run_id=run_id)
    if not start.get("ok"):
        raise RuntimeError(f"execute start failed: {start}")
    if start.get("active_node_id") != "execute.intake":
        raise RuntimeError(f"expected execute.intake, got {start.get('active_node_id')}")


def _advance_until(
    workspace: Path,
    run_id: str,
    *,
    node_id: str,
    lifecycle: str = "opened",
    visit_id: str | None = None,
    max_steps: int = 64,
) -> dict:
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / run_id
    snapshot = load_snapshot(run_dir)
    for _ in range(max_steps):
        active = snapshot.get("active_visit") or {}
        if submit_execute_plan_proceed_if_waiting(
            snapshot,
            visit=active,
            flow=flow,
            workspace=workspace,
            foundry_bundle=BUNDLE,
            run_dir=run_dir,
        ):
            save_snapshot(run_dir, snapshot)
            continue
        if active.get("node_id") == node_id and active.get("lifecycle") == lifecycle:
            if visit_id is None or active.get("id") == visit_id:
                save_snapshot(run_dir, snapshot)
                return snapshot
        outcome = advance_run(
            snapshot,
            flow,
            workspace=workspace,
            foundry_bundle=BUNDLE,
            run_dir=run_dir,
            step_budget=1,
        )
        save_snapshot(run_dir, snapshot)
        if not outcome.get("steps_taken"):
            reason = str(outcome.get("reason") or "")
            if reason in ("execute_build_boundary", "repair_reentry_boundary"):
                continue
    active = snapshot.get("active_visit") or {}
    raise RuntimeError(
        f"did not reach {node_id}/{lifecycle} visit={visit_id!r}; "
        f"active={active.get('node_id')}/{active.get('lifecycle')} id={active.get('id')}"
    )


def _publish_fixture(run_dir: Path, fixture_name: str) -> Path:
    dest = FIXTURES_ROOT / fixture_name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(run_dir, dest)
    return dest


def build_v008(workspace_root: Path) -> Path:
    os.environ.setdefault("FOUNDRY_ALLOW_STUB_ADAPTER", "1")
    os.environ.setdefault("FOUNDRY_EXECUTE_STUB", "1")
    workspace, run_id = _workspace_with_fixture(workspace_root, SOURCE_FIXTURE)
    _authorize_execute(workspace, run_id)
    _advance_until(
        workspace,
        run_id,
        node_id="execute.intake.gate",
        lifecycle="opened",
        visit_id="v-010",
    )
    run_dir = workspace / ".foundry" / "runs" / run_id
    return _publish_fixture(run_dir, "porcelain-0007-v008-execute-intake-gate")


def build_v010(workspace_root: Path) -> Path:
    os.environ.setdefault("FOUNDRY_ALLOW_STUB_ADAPTER", "1")
    os.environ.setdefault("FOUNDRY_EXECUTE_STUB", "1")
    os.environ["FOUNDRY_EXECUTE_TEST_EXIT_CODE"] = "1"
    workspace, run_id = _workspace_with_fixture(workspace_root, SOURCE_FIXTURE)
    _authorize_execute(workspace, run_id)
    _advance_until(
        workspace,
        run_id,
        node_id="execute.repair.limit.gate",
        lifecycle="opened",
    )
    run_dir = workspace / ".foundry" / "runs" / run_id
    return _publish_fixture(run_dir, "porcelain-0007-v010-execute-repair-limit-gate")


def main() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        v008 = build_v008(root)
        print(f"wrote {v008}")
        v010 = build_v010(root)
        print(f"wrote {v010}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
