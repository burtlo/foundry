"""Agent wait + submit helpers for Gherkin acceptance state."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from foundry_cli.engine.wait_state import set_run_wait
from foundry_cli.registry import load_registry
from foundry_cli.run_store import load_snapshot, save_snapshot
from tests.acceptance.acceptance_invoke import invoke_acceptance_command
from tests.acceptance.helpers import run_dir, snapshot_path
from tests.conftest import FOUNDRY_ROOT

EnsureRequestFn = Callable[..., str]


def active_agent_request_id(acceptance: dict[str, Any]) -> str:
    snap = json.loads(snapshot_path(acceptance).read_text(encoding="utf-8"))
    wait = snap.get("wait")
    assert isinstance(wait, dict), "expected agent wait on snapshot"
    request_ref = wait.get("request_ref")
    assert isinstance(request_ref, str) and request_ref.strip(), "missing agent request_ref"
    return request_ref


def invoke_agent_submit(acceptance: dict[str, Any], result: dict[str, Any]) -> None:
    request_id = active_agent_request_id(acceptance)
    invoke_acceptance_command(
        acceptance,
        "run agent submit",
        extra_flags=[
            "--request-id",
            request_id,
            "--result-json",
            json.dumps(result),
            "--local",
        ],
    )


def set_agent_wait_without_submit(
    acceptance: dict[str, Any],
    *,
    ensure_request: EnsureRequestFn,
    summary: str,
) -> None:
    workspace = Path(acceptance["workspace"])
    rd = run_dir(acceptance)
    snapshot = load_snapshot(rd)
    _, flow = load_registry(FOUNDRY_ROOT)
    visit = snapshot["active_visit"]
    request_id = ensure_request(
        snapshot,
        visit,
        flow,
        foundry_bundle=FOUNDRY_ROOT,
        workspace=workspace,
        run_dir=rd,
    )
    set_run_wait(
        snapshot,
        kind="agent",
        visit_id=str(visit["id"]),
        summary=summary,
        request_ref=request_id,
    )
    save_snapshot(rd, snapshot)


def invoke_visit_lifecycle_complete(acceptance: dict[str, Any], command: str, *, extra_flags: list[str] | None = None) -> None:
    invoke_acceptance_command(acceptance, command, extra_flags=list(extra_flags or []))


def invoke_run_advance_local(acceptance: dict[str, Any]) -> None:
    invoke_acceptance_command(acceptance, "run advance", extra_flags=["--local"])

