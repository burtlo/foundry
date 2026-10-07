"""Advance implementation-flow runs from execute.start through verify (stub execute)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from foundry_cli.engine.advance import advance_run
from foundry_cli.engine.execute_step_executor import _git_run, _snapshot_state
from foundry_cli.registry import load_registry
from foundry_cli.run_service import execute_start_durable
from foundry_cli.run_store import load_snapshot, save_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import FIXTURE_PORCELAIN_RECORD_GATE
from tests.unit.execute_advance_helpers import (
    submit_execute_plan_proceed_if_waiting,
    submit_verify_acceptance_if_waiting,
)
from tests.unit.git_workspace import ensure_clean_git_workspace
from tests.unit.snapshot_helpers import find_visit

BUNDLE = FOUNDRY_ROOT
CLI = BUNDLE / "cli" / "foundry.py"

_USER_VERIFY_GATES = frozenset({"verify.code_review.gate", "verify.complete.gate"})


@dataclass
class ImplementationRunFixture:
    workspace: Path
    run_id: str
    flow: dict
    snapshot: dict | None = None

    @property
    def run_dir(self) -> Path:
        return self.workspace / ".foundry" / "runs" / self.run_id


def workspace_with_run_fixture(tmp_path: Path, fixture_name: str) -> tuple[Path, str]:
    src = BUNDLE / "fixtures" / "runs" / fixture_name
    snapshot = json.loads((src / "snapshot.json").read_text(encoding="utf-8"))
    run_id = str(snapshot.get("run_id") or fixture_name)
    workspace = tmp_path / "app"
    dest = workspace / ".foundry" / "runs" / run_id
    shutil.copytree(src, dest)
    shutil.copytree(
        BUNDLE / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
        dirs_exist_ok=True,
    )
    ensure_clean_git_workspace(workspace)
    return workspace, run_id


def invoke_foundry_cli(workspace: Path, *argv: str) -> subprocess.CompletedProcess[str]:
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


def stub_record_gate_run(
    tmp_path: Path,
    *,
    fixture: str = FIXTURE_PORCELAIN_RECORD_GATE,
    verify_review: bool = False,
    advance_to: str | None = "execute.commit",
) -> ImplementationRunFixture:
    """Copy record-gate run fixture, authorize execute.start, optionally advance stub execute."""
    workspace, run_id = workspace_with_run_fixture(tmp_path, fixture)
    authorize_execute_start(workspace, run_id)
    if verify_review:
        enable_verify_review(workspace, run_id)
    _, flow = load_registry(BUNDLE)
    snapshot: dict | None = None
    if advance_to == "execute.commit":
        snapshot = advance_snapshot_to_execute_commit(workspace, run_id)
    elif advance_to is not None:
        snapshot = advance_snapshot_through_stub_execute(workspace, run_id, stop_at=advance_to)
    return ImplementationRunFixture(
        workspace=workspace,
        run_id=run_id,
        flow=flow,
        snapshot=snapshot,
    )


def authorize_execute_start(workspace: Path, run_id: str) -> None:
    decide = invoke_foundry_cli(workspace, "gate", "decide", "--run", run_id, "--decision", "accept")
    assert decide.returncode == 0, decide.stderr + decide.stdout
    advance = invoke_foundry_cli(workspace, "run", "advance", "--run", run_id)
    assert advance.returncode == 0, advance.stderr + advance.stdout
    ensure_clean_git_workspace(workspace)
    start = execute_start_durable(workspace=workspace, bundle=BUNDLE, run_id=run_id)
    assert start.get("ok") is True, start


def enable_verify_review(workspace: Path, run_id: str) -> None:
    run_dir = workspace / ".foundry" / "runs" / run_id
    snapshot = load_snapshot(run_dir)
    config = snapshot.setdefault("config", {})
    if isinstance(config, dict):
        config["review"] = {"enabled": True}
        config.setdefault("limits", {"repair": 2, "reverify": 2})
    save_snapshot(run_dir, snapshot)


def ensure_feature_branch_diff(workspace: Path, snapshot: dict) -> None:
    """Stub execute commit uses --allow-empty; verify intake requires a non-empty branch diff."""
    state = _snapshot_state(snapshot)
    feature = state.get("feature_branch")
    default = state.get("default_branch") or "main"
    if not isinstance(feature, str) or not feature.strip():
        return
    diff = _git_run(workspace, "diff", f"{default}...{feature}")
    if diff.returncode in (0, 1) and (diff.stdout or "").strip():
        return
    checkout = _git_run(workspace, "checkout", feature)
    if checkout.returncode != 0:
        return
    marker = workspace / ".foundry" / "execute-stub-diff.txt"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(f"stub diff for {snapshot.get('run_id')}\n", encoding="utf-8")
    _git_run(workspace, "add", ".foundry/execute-stub-diff.txt")
    _git_run(workspace, "commit", "-m", "foundry: stub execute diff for verify")
    ensure_clean_git_workspace(workspace)


def advance_snapshot_through_stub_execute(
    workspace: Path,
    run_id: str,
    *,
    stop_at: str = "execute.commit",
    max_steps: int = 48,
    submit_plan_judgment_if_waiting: bool = True,
) -> dict:
    """Advance a stub-execute run until `stop_at` is opened (or repair gate seen when stopping at build)."""
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / run_id
    snapshot = load_snapshot(run_dir)
    for _ in range(max_steps):
        active = snapshot.get("active_visit") or {}
        if submit_plan_judgment_if_waiting and submit_execute_plan_proceed_if_waiting(
            snapshot,
            visit=active,
            flow=flow,
            workspace=workspace,
            foundry_bundle=BUNDLE,
            run_dir=run_dir,
        ):
            continue
        if submit_verify_acceptance_if_waiting(
            snapshot,
            visit=active,
            flow=flow,
            workspace=workspace,
            foundry_bundle=BUNDLE,
            run_dir=run_dir,
        ):
            continue
        if active.get("node_id") == stop_at and active.get("lifecycle") == "opened":
            if stop_at == "execute.build":
                if find_visit(snapshot, "execute.repair.limit.gate") is not None:
                    break
            else:
                break
        outcome = advance_run(
            snapshot,
            flow,
            workspace=workspace,
            foundry_bundle=BUNDLE,
            run_dir=run_dir,
            step_budget=1,
        )
        if not outcome.get("steps_taken"):
            reason = str(outcome.get("reason") or "")
            if reason in ("execute_build_boundary", "repair_reentry_boundary"):
                continue
            break
    save_snapshot(run_dir, snapshot)
    return snapshot


def advance_snapshot_to_execute_commit(workspace: Path, run_id: str) -> dict:
    """Advance through execute intake..test gates to opened execute.commit."""
    snapshot = advance_snapshot_through_stub_execute(workspace, run_id, stop_at="execute.commit")
    active = snapshot.get("active_visit") or {}
    assert active.get("node_id") == "execute.commit", active.get("node_id")
    ensure_feature_branch_diff(workspace, snapshot)
    return snapshot


def advance_stub_run_to_completion(
    workspace: Path,
    run_id: str,
    *,
    snapshot: dict | None = None,
    max_steps: int = 120,
) -> dict:
    """Advance from post-commit stub execute through verify to completed (user gates via CLI)."""
    _, flow = load_registry(BUNDLE)
    run_dir = workspace / ".foundry" / "runs" / run_id
    if snapshot is None:
        snapshot = load_snapshot(run_dir)
    for _ in range(max_steps):
        active = snapshot.get("active_visit") or {}
        node_id = str(active.get("node_id") or "")
        kind = str(active.get("kind") or "")
        if snapshot.get("status") == "completed":
            break
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
        if submit_verify_acceptance_if_waiting(
            snapshot,
            visit=active,
            flow=flow,
            workspace=workspace,
            foundry_bundle=BUNDLE,
            run_dir=run_dir,
        ):
            save_snapshot(run_dir, snapshot)
            continue
        if kind == "gate" and active.get("decision") is None and node_id in _USER_VERIFY_GATES:
            save_snapshot(run_dir, snapshot)
            decide = invoke_foundry_cli(workspace, "gate", "decide", "--run", run_id, "--decision", "accept")
            assert decide.returncode == 0, decide.stderr + decide.stdout
            advance = invoke_foundry_cli(workspace, "run", "advance", "--run", run_id)
            assert advance.returncode == 0, advance.stderr + advance.stdout
            snapshot = load_snapshot(run_dir)
            if snapshot.get("status") == "completed":
                break
            continue
        outcome = advance_run(
            snapshot,
            flow,
            workspace=workspace,
            foundry_bundle=BUNDLE,
            run_dir=run_dir,
            step_budget=1,
        )
        if not outcome.get("steps_taken"):
            reason = str(outcome.get("reason") or "")
            if reason in ("execute_build_boundary", "repair_reentry_boundary"):
                continue
            if reason == "wait" and kind == "gate":
                continue
            break
        if snapshot.get("status") == "completed":
            break
        save_snapshot(run_dir, snapshot)
    save_snapshot(run_dir, snapshot)
    return snapshot
