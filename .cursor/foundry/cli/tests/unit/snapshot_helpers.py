"""Snapshot navigation and bounded advance helpers for unit tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from foundry_cli.engine.advance import advance_run
from foundry_cli.engine.gates import resolve_engine_gate_decision
from foundry_cli.run_store import save_snapshot

_BOUNDARY_REASONS = frozenset({"execute_build_boundary", "repair_reentry_boundary"})


def find_visit(snapshot: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    return next(
        (v for v in snapshot.get("visits", []) if v.get("node_id") == node_id),
        None,
    )


def gate_visit_for_engine(visit: dict[str, Any], node_id: str) -> dict[str, Any]:
    return {"id": visit["id"], "node_id": node_id, "kind": "gate"}


def resolve_gate_at_node(
    snapshot: dict[str, Any],
    flow: dict[str, Any],
    run_dir: Path,
    node_id: str,
    *,
    visit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved = visit if visit is not None else find_visit(snapshot, node_id)
    if resolved is None:
        raise AssertionError(f"visit not found for node {node_id!r}")
    return resolve_engine_gate_decision(
        snapshot,
        gate_visit_for_engine(resolved, node_id),
        flow,
        run_dir=run_dir,
    )


def advance_run_steps(
    snapshot: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
    max_steps: int = 48,
    stop_when_active: str | None = None,
    stop_when_visit: str | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """Advance with step_budget=1 until a stop condition or idle."""
    for _ in range(max_steps):
        if stop_when_active:
            active = snapshot.get("active_visit") or {}
            if active.get("node_id") == stop_when_active:
                break
        if stop_when_visit and find_visit(snapshot, stop_when_visit) is not None:
            break
        outcome = advance_run(
            snapshot,
            flow,
            workspace=workspace,
            foundry_bundle=foundry_bundle,
            run_dir=run_dir,
            step_budget=1,
        )
        if not outcome.get("steps_taken"):
            reason = str(outcome.get("reason") or "")
            if reason in _BOUNDARY_REASONS:
                continue
            break
    if save:
        save_snapshot(run_dir, snapshot)
    return snapshot
