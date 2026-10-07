"""Mechanism action registry and baseline handlers (Step 5 skeleton)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from foundry_cli.engine.execute_step_executor import (
    run_execute_branch_complete,
    run_execute_build_boundary_park,
    run_execute_build_complete,
    run_execute_commit_complete,
    run_execute_intake_complete,
    run_execute_test_complete,
)
from foundry_cli.engine.verify_step_executor import (
    run_deliver_stub_complete,
    run_verify_code_quality_complete,
    run_verify_code_review_complete,
    run_verify_complete_complete,
    run_verify_intake_complete,
)
from foundry_cli.engine.lifecycle import transition_visit
from foundry_cli.engine.intake_executor import run_shape_intake_complete

ActionResult = dict[str, Any]
ActionHandler = Callable[["ActionExecutionContext", dict[str, Any]], ActionResult]


@dataclass
class ActionExecutionContext:
    """Runtime data available to mechanism action handlers."""

    snapshot: dict[str, Any]
    visit: dict[str, Any]
    flow: dict[str, Any]
    workspace: Path
    foundry_bundle: Path
    run_dir: Path
    outputs: dict[str, Any] = field(default_factory=dict)


class ActionRegistry:
    """String action name -> callable handler."""

    def __init__(self, handlers: dict[str, ActionHandler] | None = None) -> None:
        self._handlers: dict[str, ActionHandler] = dict(handlers or {})

    def register(self, action: str, handler: ActionHandler) -> None:
        self._handlers[action] = handler

    def has(self, action: str) -> bool:
        return action in self._handlers

    def execute(self, action: str, ctx: ActionExecutionContext, step: dict[str, Any]) -> ActionResult:
        if action not in self._handlers:
            raise KeyError(action)
        return self._handlers[action](ctx, step)


def _noop_action(_ctx: ActionExecutionContext, _step: dict[str, Any]) -> ActionResult:
    """Placeholder for mechanism actions migrated in later steps."""
    return {"ok": True}


def _visit_state_patch_action(ctx: ActionExecutionContext, step: dict[str, Any]) -> ActionResult:
    raw_set = step.get("set")
    if not isinstance(raw_set, dict):
        return {"ok": False, "code": "INVALID_STEP", "message": "visit.state_patch requires mapping field `set`"}
    state = ctx.snapshot.setdefault("state", {})
    if not isinstance(state, dict):
        return {"ok": False, "code": "INVALID_SNAPSHOT_STATE", "message": "snapshot.state must be a mapping"}
    applied: dict[str, Any] = {}
    for key, value in raw_set.items():
        if not isinstance(key, str):
            continue
        state[key] = value
        applied[key] = value
    return {"ok": True, "patched": applied}


def _visit_transition_action(ctx: ActionExecutionContext, step: dict[str, Any]) -> ActionResult:
    summary = step.get("summary")
    result = transition_visit(
        ctx.snapshot,
        ctx.visit,
        ctx.flow,
        workspace=ctx.workspace,
        foundry_bundle=ctx.foundry_bundle,
        run_dir=ctx.run_dir,
        summary=str(summary) if isinstance(summary, str) else None,
    )
    return {
        **result,
        "transitioned": bool(result.get("ok")),
    }


def _subprocess_action(_ctx: ActionExecutionContext, step: dict[str, Any]) -> ActionResult:
    """Skeleton subprocess action for Step 5 tests."""
    commands = step.get("commands")
    if isinstance(commands, list):
        return {"ok": True, "commands": commands}
    return {"ok": True, "commands": []}


def _run_advance_park_action(_ctx: ActionExecutionContext, step: dict[str, Any]) -> ActionResult:
    wait = step.get("wait")
    if not isinstance(wait, dict):
        wait = {
            "kind": "boundary",
            "summary": str(step.get("summary") or "Mechanism parked"),
            "request_ref": str(step.get("request_ref") or step.get("id") or "mechanism"),
        }
    return {"ok": True, "wait": wait}


def _work_prompt_from_snapshot(snapshot: dict[str, Any]) -> str | None:
    config = snapshot.get("config")
    if isinstance(config, dict):
        shape = config.get("shape")
        if isinstance(shape, dict):
            prompt = shape.get("work_prompt")
            if isinstance(prompt, str) and prompt.strip():
                return prompt
        direct = config.get("work_prompt")
        if isinstance(direct, str) and direct.strip():
            return direct
    state = snapshot.get("state")
    if isinstance(state, dict):
        prompt = state.get("work_prompt")
        if isinstance(prompt, str) and prompt.strip():
            return prompt
    return None


def _source_from_snapshot(snapshot: dict[str, Any]) -> tuple[str, str | None]:
    config = snapshot.get("config")
    if isinstance(config, dict):
        shape = config.get("shape")
        if isinstance(shape, dict):
            source_type = str(shape.get("source_type") or "chat")
            source_ref = shape.get("source_ref")
            if source_ref is not None and not isinstance(source_ref, str):
                source_ref = None
            return source_type, source_ref
    return "chat", None


def _visit_intake_complete_action(ctx: ActionExecutionContext, _step: dict[str, Any]) -> ActionResult:
    node_id = str(ctx.visit.get("node_id") or "")
    if node_id == "execute.intake":
        return run_execute_intake_complete(
            ctx.snapshot,
            ctx.visit,
            ctx.flow,
            workspace=ctx.workspace,
            foundry_bundle=ctx.foundry_bundle,
            run_dir=ctx.run_dir,
        )
    if node_id == "verify.intake":
        return run_verify_intake_complete(
            ctx.snapshot,
            ctx.visit,
            ctx.flow,
            workspace=ctx.workspace,
            foundry_bundle=ctx.foundry_bundle,
            run_dir=ctx.run_dir,
        )

    source_type, source_ref = _source_from_snapshot(ctx.snapshot)
    return run_shape_intake_complete(
        ctx.snapshot,
        ctx.visit,
        ctx.flow,
        workspace=ctx.workspace,
        foundry_bundle=ctx.foundry_bundle,
        run_dir=ctx.run_dir,
        work_prompt=_work_prompt_from_snapshot(ctx.snapshot),
        source_type=source_type,
        source_ref=source_ref,
    )


def _visit_execute_branch_complete_action(
    ctx: ActionExecutionContext,
    _step: dict[str, Any],
) -> ActionResult:
    return run_execute_branch_complete(
        ctx.snapshot,
        ctx.visit,
        ctx.flow,
        workspace=ctx.workspace,
        foundry_bundle=ctx.foundry_bundle,
        run_dir=ctx.run_dir,
    )


def _visit_execute_build_complete_action(
    ctx: ActionExecutionContext,
    _step: dict[str, Any],
) -> ActionResult:
    return run_execute_build_complete(
        ctx.snapshot,
        ctx.visit,
        ctx.flow,
        workspace=ctx.workspace,
        foundry_bundle=ctx.foundry_bundle,
        run_dir=ctx.run_dir,
    )


def _visit_execute_test_complete_action(
    ctx: ActionExecutionContext,
    _step: dict[str, Any],
) -> ActionResult:
    return run_execute_test_complete(
        ctx.snapshot,
        ctx.visit,
        ctx.flow,
        workspace=ctx.workspace,
        foundry_bundle=ctx.foundry_bundle,
        run_dir=ctx.run_dir,
    )


def _visit_execute_commit_complete_action(
    ctx: ActionExecutionContext,
    _step: dict[str, Any],
) -> ActionResult:
    return run_execute_commit_complete(
        ctx.snapshot,
        ctx.visit,
        ctx.flow,
        workspace=ctx.workspace,
        foundry_bundle=ctx.foundry_bundle,
        run_dir=ctx.run_dir,
    )


def _execute_build_boundary_park_action(
    ctx: ActionExecutionContext,
    _step: dict[str, Any],
) -> ActionResult:
    return run_execute_build_boundary_park(ctx.snapshot, ctx.visit)


def _visit_verify_code_quality_complete_action(
    ctx: ActionExecutionContext,
    _step: dict[str, Any],
) -> ActionResult:
    return run_verify_code_quality_complete(
        ctx.snapshot,
        ctx.visit,
        ctx.flow,
        workspace=ctx.workspace,
        foundry_bundle=ctx.foundry_bundle,
        run_dir=ctx.run_dir,
    )


def _visit_verify_code_review_complete_action(
    ctx: ActionExecutionContext,
    _step: dict[str, Any],
) -> ActionResult:
    return run_verify_code_review_complete(
        ctx.snapshot,
        ctx.visit,
        ctx.flow,
        workspace=ctx.workspace,
        foundry_bundle=ctx.foundry_bundle,
        run_dir=ctx.run_dir,
    )


def _visit_verify_complete_complete_action(
    ctx: ActionExecutionContext,
    _step: dict[str, Any],
) -> ActionResult:
    return run_verify_complete_complete(
        ctx.snapshot,
        ctx.visit,
        ctx.flow,
        workspace=ctx.workspace,
        foundry_bundle=ctx.foundry_bundle,
        run_dir=ctx.run_dir,
    )


def _visit_deliver_stub_complete_action(
    ctx: ActionExecutionContext,
    _step: dict[str, Any],
) -> ActionResult:
    return run_deliver_stub_complete(
        ctx.snapshot,
        ctx.visit,
        ctx.flow,
        workspace=ctx.workspace,
        foundry_bundle=ctx.foundry_bundle,
        run_dir=ctx.run_dir,
    )


def default_action_registry() -> ActionRegistry:
    registry = ActionRegistry()
    for action in (
        "receipt.seal",
        "artifact.publish",
        "file.write",
        "ledger.show",
        "receipt.draft",
        "host.git_diff",
        "host.validate",
        "policy.resolve",
        "run.advance",
    ):
        registry.register(action, _noop_action)
    registry.register("visit.transition", _visit_transition_action)
    registry.register("subprocess", _subprocess_action)
    registry.register("visit.state_patch", _visit_state_patch_action)
    registry.register("visit.intake.complete", _visit_intake_complete_action)
    registry.register("visit.execute.branch.complete", _visit_execute_branch_complete_action)
    registry.register("visit.execute.build.complete", _visit_execute_build_complete_action)
    registry.register("visit.execute.test.complete", _visit_execute_test_complete_action)
    registry.register("visit.execute.commit.complete", _visit_execute_commit_complete_action)
    registry.register("visit.verify.code_quality.complete", _visit_verify_code_quality_complete_action)
    registry.register("visit.verify.code_review.complete", _visit_verify_code_review_complete_action)
    registry.register("visit.verify.complete.complete", _visit_verify_complete_complete_action)
    registry.register("visit.deliver.stub.complete", _visit_deliver_stub_complete_action)
    registry.register("execute.build.boundary.park", _execute_build_boundary_park_action)
    registry.register("run.advance.park", _run_advance_park_action)
    return registry
