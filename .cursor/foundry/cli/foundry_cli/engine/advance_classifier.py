"""Advance node classification and step-backend dispatch (REL-007 / engine-kernel Phase 2)."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Callable

from foundry_cli.constants import LIFECYCLE_OPENED
from foundry_cli.engine.agent.dispatch import (
    ensure_execute_plan_request,
    ensure_shape_examine_request,
    ensure_shape_present_request,
    ensure_shape_record_request,
    ensure_verify_acceptance_request,
    visit_has_accepted_proceed_plan,
    visit_has_accepted_proceed_presentation,
    visit_has_accepted_proceed_record,
    visit_has_accepted_task_result,
)
from foundry_cli.engine.agent.tasks import (
    EXECUTE_PLAN_TASK_ID,
    SHAPE_EXAMINE_TASK_ID,
    SHAPE_PRESENT_TASK_ID,
    SHAPE_RECORD_TASK_ID,
    VERIFY_ACCEPTANCE_TASK_ID,
    task_registry_binding_exists,
)
from foundry_cli.engine.execute_step_executor import (
    EXECUTE_BRANCH_NODE,
    EXECUTE_BUILD_NODE,
    EXECUTE_COMMIT_NODE,
    EXECUTE_INTAKE_NODE,
    EXECUTE_TEST_NODE,
    run_execute_branch_complete,
    run_execute_build_complete,
    run_execute_commit_complete,
    run_execute_intake_complete,
    run_execute_plan_complete,
    run_execute_test_complete,
)
from foundry_cli.engine.examination_state import derive_open_clarifying_questions_count
from foundry_cli.engine.intake_executor import run_shape_intake_complete
from foundry_cli.engine.node_capability import (
    _HOST_IMPLEMENTED_STEP_NODES,
    is_post_shape_flow_node,
)
from foundry_cli.engine.shape_step_executor import (
    SHAPE_PRESENT_NODE,
    SHAPE_RECORD_NODE,
    run_shape_examine_complete,
    run_shape_present_complete,
    run_shape_record_complete,
)
from foundry_cli.engine.verify_step_executor import (
    DELIVER_STUB_NODE,
    VERIFY_ACCEPTANCE_NODE,
    VERIFY_CODE_QUALITY_NODE,
    VERIFY_CODE_REVIEW_NODE,
    VERIFY_COMPLETE_NODE,
    VERIFY_INTAKE_NODE,
    run_deliver_stub_complete,
    run_verify_acceptance_complete,
    run_verify_code_quality_complete,
    run_verify_code_review_complete,
    run_verify_complete_complete,
    run_verify_intake_complete,
)
from foundry_cli.engine.wait_state import set_run_wait
from foundry_cli.registry import get_node

BoundaryWaitFn = Callable[
    [dict[str, Any], dict[str, Any], dict[str, Any]],
    dict[str, Any] | None,
]
AdvanceStepFn = Callable[
    [dict[str, Any], dict[str, Any], dict[str, Any]],
    dict[str, Any] | None,
]

AdvanceContextKwargs = dict[str, Any]


class AdvanceNodeClass(str, Enum):
    USER_GATE = "user_gate"
    ENGINE_GATE = "engine_gate"
    TASK_BOUND_STEP = "task_bound_step"
    GIT_MECHANICAL_STEP = "git_mechanical_step"
    HOST_STEP = "host_step"
    UNSUPPORTED = "unsupported"


TASK_BOUND_STEP_NODE_IDS: tuple[str, ...] = (
    SHAPE_EXAMINE_TASK_ID,
    SHAPE_PRESENT_TASK_ID,
    SHAPE_RECORD_TASK_ID,
    EXECUTE_PLAN_TASK_ID,
    VERIFY_ACCEPTANCE_NODE,
)

GIT_MECHANICAL_STEP_NODE_IDS: tuple[str, ...] = (EXECUTE_BRANCH_NODE,)


def _node_kind(node_id: str, flow: dict[str, Any]) -> str:
    try:
        node = get_node(flow, node_id)
    except KeyError:
        return ""
    return str(node.get("kind") or "")


def _gate_decider(node_id: str, flow: dict[str, Any]) -> str:
    try:
        node = get_node(flow, node_id)
    except KeyError:
        return ""
    return str(node.get("decider") or "")


def classify_advance_node(
    node_id: str,
    flow: dict[str, Any],
    *,
    foundry_bundle: Path | None = None,
) -> AdvanceNodeClass:
    """Classify how advancement should treat this node (visit context assumed step/gate elsewhere)."""
    kind = _node_kind(node_id, flow)
    if kind == "gate":
        if _gate_decider(node_id, flow) == "user":
            return AdvanceNodeClass.USER_GATE
        return AdvanceNodeClass.ENGINE_GATE
    if node_id in GIT_MECHANICAL_STEP_NODE_IDS:
        return AdvanceNodeClass.GIT_MECHANICAL_STEP
    if node_id in _HOST_IMPLEMENTED_STEP_NODES:
        return AdvanceNodeClass.HOST_STEP
    if (
        foundry_bundle is not None
        and task_registry_binding_exists(node_id, foundry_bundle)
    ):
        return AdvanceNodeClass.TASK_BOUND_STEP
    if is_post_shape_flow_node(node_id):
        return AdvanceNodeClass.UNSUPPORTED
    return AdvanceNodeClass.UNSUPPORTED


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


def _work_prompt_is_present(snapshot: dict[str, Any]) -> bool:
    prompt = _work_prompt_from_snapshot(snapshot)
    return isinstance(prompt, str) and bool(prompt.strip())


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


def _ctx(
    *,
    workspace: Path | None,
    foundry_bundle: Path | None,
    run_dir: Path | None,
) -> AdvanceContextKwargs:
    return {
        "workspace": workspace,
        "foundry_bundle": foundry_bundle,
        "run_dir": run_dir,
    }


def _execution_error_outcome(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "progressed": True,
        "reason": "execution_error",
        "error": result,
    }


def _complete_outcome(reason: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "progressed": True,
        "reason": reason,
        "detail": result,
    }


# --- Task-bound step backends ---


def _task_bound_boundary_wait_shape_examine(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    **ctx: Any,
) -> dict[str, Any] | None:
    visit_id = str(visit.get("id", ""))
    node_id = str(visit.get("node_id", ""))
    if visit_has_accepted_task_result(
        snapshot,
        visit_id=visit_id,
        task_id=SHAPE_EXAMINE_TASK_ID,
    ):
        state = snapshot.get("state") if isinstance(snapshot.get("state"), dict) else {}
        open_count = derive_open_clarifying_questions_count(state)
        if open_count > 0:
            return set_run_wait(
                snapshot,
                kind="user_input",
                visit_id=visit_id,
                summary=f"{open_count} clarifying question(s) need answers",
                request_ref=f"questions:{visit_id}",
            )
        return None
    request_ref = f"task:{node_id}"
    workspace, foundry_bundle, run_dir = (
        ctx.get("workspace"),
        ctx.get("foundry_bundle"),
        ctx.get("run_dir"),
    )
    if workspace is not None and foundry_bundle is not None and run_dir is not None:
        request_ref = ensure_shape_examine_request(
            snapshot,
            visit,
            flow,
            foundry_bundle=foundry_bundle,
            workspace=workspace,
            run_dir=run_dir,
        )
    return set_run_wait(
        snapshot,
        kind="agent",
        visit_id=visit_id,
        summary="Shape examination judgment required",
        request_ref=request_ref,
    )


def _task_bound_advance_shape_examine(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    **ctx: Any,
) -> dict[str, Any] | None:
    if str(visit.get("lifecycle")) != LIFECYCLE_OPENED:
        return None
    if not visit_has_accepted_task_result(
        snapshot,
        visit_id=str(visit.get("id")),
        task_id=SHAPE_EXAMINE_TASK_ID,
    ):
        return None
    result = run_shape_examine_complete(
        snapshot,
        visit,
        flow,
        workspace=ctx["workspace"],
        foundry_bundle=ctx["foundry_bundle"],
        run_dir=ctx["run_dir"],
    )
    if not result.get("ok"):
        snapshot["status"] = "execution_error"
        return _execution_error_outcome(result)
    from foundry_cli.engine.wait_state import clear_run_wait

    clear_run_wait(snapshot)
    return _complete_outcome("examine_complete", result)


def _task_bound_boundary_wait_agent_task(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    accepted_predicate: Callable[[dict[str, Any], str], bool],
    ensure_request: Callable[..., str],
    summary: str,
    **ctx: Any,
) -> dict[str, Any] | None:
    visit_id = str(visit.get("id", ""))
    node_id = str(visit.get("node_id", ""))
    if accepted_predicate(snapshot, visit_id):
        return None
    request_ref = f"task:{node_id}"
    workspace, foundry_bundle, run_dir = (
        ctx.get("workspace"),
        ctx.get("foundry_bundle"),
        ctx.get("run_dir"),
    )
    if workspace is not None and foundry_bundle is not None and run_dir is not None:
        request_ref = ensure_request(
            snapshot,
            visit,
            flow,
            foundry_bundle=foundry_bundle,
            workspace=workspace,
            run_dir=run_dir,
        )
    return set_run_wait(
        snapshot,
        kind="agent",
        visit_id=visit_id,
        summary=summary,
        request_ref=request_ref,
    )


def _task_bound_advance_when_accepted(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    accepted_predicate: Callable[[dict[str, Any], str], bool],
    run_complete: Callable[..., dict[str, Any]],
    complete_reason: str,
    **ctx: Any,
) -> dict[str, Any] | None:
    if str(visit.get("lifecycle")) != LIFECYCLE_OPENED:
        return None
    visit_id = str(visit.get("id"))
    if not accepted_predicate(snapshot, visit_id):
        return None
    result = run_complete(
        snapshot,
        visit,
        flow,
        workspace=ctx["workspace"],
        foundry_bundle=ctx["foundry_bundle"],
        run_dir=ctx["run_dir"],
    )
    if not result.get("ok"):
        snapshot["status"] = "execution_error"
        return _execution_error_outcome(result)
    from foundry_cli.engine.wait_state import clear_run_wait

    clear_run_wait(snapshot)
    return _complete_outcome(complete_reason, result)


# --- Host step backends ---


def _host_boundary_wait_shape_intake(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    **ctx: Any,
) -> dict[str, Any] | None:
    if not _work_prompt_is_present(snapshot):
        return set_run_wait(
            snapshot,
            kind="operator",
            visit_id=str(visit.get("id", "")),
            summary="Shape intake requires work_prompt in run config or state",
            request_ref="intake:work_prompt",
        )
    return None


def _host_advance_shape_intake(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    **ctx: Any,
) -> dict[str, Any] | None:
    if str(visit.get("lifecycle")) != LIFECYCLE_OPENED:
        return None
    source_type, source_ref = _source_from_snapshot(snapshot)
    result = run_shape_intake_complete(
        snapshot,
        visit,
        flow,
        workspace=ctx["workspace"],
        foundry_bundle=ctx["foundry_bundle"],
        run_dir=ctx["run_dir"],
        work_prompt=_work_prompt_from_snapshot(snapshot),
        source_type=source_type,
        source_ref=source_ref,
    )
    if not result.get("ok"):
        snapshot["status"] = "execution_error"
        return _execution_error_outcome(result)
    from foundry_cli.engine.wait_state import clear_run_wait

    clear_run_wait(snapshot)
    return _complete_outcome("intake_complete", result)


def _host_advance_simple_complete(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    run_complete: Callable[..., dict[str, Any]],
    complete_reason: str,
    allowed_lifecycles: tuple[str, ...] = (LIFECYCLE_OPENED,),
    reopened_reason: str | None = None,
    **ctx: Any,
) -> dict[str, Any] | None:
    lifecycle = str(visit.get("lifecycle"))
    if lifecycle not in allowed_lifecycles:
        return None
    result = run_complete(
        snapshot,
        visit,
        flow,
        workspace=ctx["workspace"],
        foundry_bundle=ctx["foundry_bundle"],
        run_dir=ctx["run_dir"],
    )
    if not result.get("ok"):
        if reopened_reason and result.get("reopened"):
            return {"progressed": True, "reason": reopened_reason, "detail": result}
        snapshot["status"] = "execution_error"
        return _execution_error_outcome(result)
    if result.get("transitioned") is False and result.get("intake_status") == "blocked":
        from foundry_cli.engine.blocked_intake import apply_blocked_intake_wait

        apply_blocked_intake_wait(snapshot, visit, result)
        return {"progressed": True, "reason": "intake_blocked", "detail": result}
    from foundry_cli.engine.run_status_reason import clear_status_reason
    from foundry_cli.engine.wait_state import clear_run_wait

    clear_status_reason(snapshot)
    clear_run_wait(snapshot)
    return _complete_outcome(complete_reason, result)


def _host_advance_deliver_stub(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    **ctx: Any,
) -> dict[str, Any] | None:
    outcome = _host_advance_simple_complete(
        snapshot,
        visit,
        flow,
        run_complete=run_deliver_stub_complete,
        complete_reason="deliver_stub_complete",
        **ctx,
    )
    if (
        outcome is not None
        and outcome.get("reason") == "deliver_stub_complete"
        and str(snapshot.get("status")) != "completed"
    ):
        snapshot["status"] = "completed"
    return outcome


_TASK_BOUND_BOUNDARY_WAIT: dict[str, BoundaryWaitFn] = {
    SHAPE_EXAMINE_TASK_ID: _task_bound_boundary_wait_shape_examine,
    SHAPE_PRESENT_TASK_ID: lambda s, v, f, **c: _task_bound_boundary_wait_agent_task(
        s,
        v,
        f,
        accepted_predicate=lambda snap, vid: visit_has_accepted_proceed_presentation(
            snap, visit_id=vid
        ),
        ensure_request=ensure_shape_present_request,
        summary="Shape presentation judgment required",
        **c,
    ),
    SHAPE_RECORD_TASK_ID: lambda s, v, f, **c: _task_bound_boundary_wait_agent_task(
        s,
        v,
        f,
        accepted_predicate=lambda snap, vid: visit_has_accepted_proceed_record(
            snap, visit_id=vid
        ),
        ensure_request=ensure_shape_record_request,
        summary="Shape record judgment required",
        **c,
    ),
    EXECUTE_PLAN_TASK_ID: lambda s, v, f, **c: _task_bound_boundary_wait_agent_task(
        s,
        v,
        f,
        accepted_predicate=lambda snap, vid: visit_has_accepted_proceed_plan(
            snap, visit_id=vid
        ),
        ensure_request=ensure_execute_plan_request,
        summary="Execute plan judgment required",
        **c,
    ),
    VERIFY_ACCEPTANCE_NODE: lambda s, v, f, **c: _task_bound_boundary_wait_agent_task(
        s,
        v,
        f,
        accepted_predicate=lambda snap, vid: visit_has_accepted_task_result(
            snap,
            visit_id=vid,
            task_id=VERIFY_ACCEPTANCE_TASK_ID,
        ),
        ensure_request=ensure_verify_acceptance_request,
        summary="Verify acceptance judgment required",
        **c,
    ),
}

_TASK_BOUND_ADVANCE: dict[str, AdvanceStepFn] = {
    SHAPE_EXAMINE_TASK_ID: _task_bound_advance_shape_examine,
    SHAPE_PRESENT_TASK_ID: lambda s, v, f, **c: _task_bound_advance_when_accepted(
        s,
        v,
        f,
        accepted_predicate=lambda snap, vid: visit_has_accepted_proceed_presentation(
            snap, visit_id=vid
        ),
        run_complete=run_shape_present_complete,
        complete_reason="present_complete",
        **c,
    ),
    SHAPE_RECORD_TASK_ID: lambda s, v, f, **c: _task_bound_advance_when_accepted(
        s,
        v,
        f,
        accepted_predicate=lambda snap, vid: visit_has_accepted_proceed_record(
            snap, visit_id=vid
        ),
        run_complete=run_shape_record_complete,
        complete_reason="record_complete",
        **c,
    ),
    EXECUTE_PLAN_TASK_ID: lambda s, v, f, **c: _task_bound_advance_when_accepted(
        s,
        v,
        f,
        accepted_predicate=lambda snap, vid: visit_has_accepted_proceed_plan(
            snap, visit_id=vid
        ),
        run_complete=run_execute_plan_complete,
        complete_reason="execute_plan_complete",
        **c,
    ),
    VERIFY_ACCEPTANCE_NODE: lambda s, v, f, **c: _task_bound_advance_when_accepted(
        s,
        v,
        f,
        accepted_predicate=lambda snap, vid: visit_has_accepted_task_result(
            snap,
            visit_id=vid,
            task_id=VERIFY_ACCEPTANCE_TASK_ID,
        ),
        run_complete=run_verify_acceptance_complete,
        complete_reason="verify_acceptance_complete",
        **c,
    ),
}

_HOST_BOUNDARY_WAIT: dict[str, BoundaryWaitFn] = {
    "shape.intake": _host_boundary_wait_shape_intake,
}

_HOST_ADVANCE: dict[str, AdvanceStepFn] = {
    "shape.intake": _host_advance_shape_intake,
    EXECUTE_INTAKE_NODE: lambda s, v, f, **c: _host_advance_simple_complete(
        s, v, f, run_complete=run_execute_intake_complete, complete_reason="execute_intake_complete", **c
    ),
    EXECUTE_BUILD_NODE: lambda s, v, f, **c: _host_advance_simple_complete(
        s,
        v,
        f,
        run_complete=run_execute_build_complete,
        complete_reason="execute_build_complete",
        reopened_reason="execute_build_reopened",
        **c,
    ),
    EXECUTE_TEST_NODE: lambda s, v, f, **c: _host_advance_simple_complete(
        s,
        v,
        f,
        run_complete=run_execute_test_complete,
        complete_reason="execute_test_complete",
        reopened_reason="execute_test_reopened",
        **c,
    ),
    EXECUTE_COMMIT_NODE: lambda s, v, f, **c: _host_advance_simple_complete(
        s, v, f, run_complete=run_execute_commit_complete, complete_reason="execute_commit_complete", **c
    ),
    VERIFY_INTAKE_NODE: lambda s, v, f, **c: _host_advance_simple_complete(
        s, v, f, run_complete=run_verify_intake_complete, complete_reason="verify_intake_complete", **c
    ),
    VERIFY_CODE_QUALITY_NODE: lambda s, v, f, **c: _host_advance_simple_complete(
        s,
        v,
        f,
        run_complete=run_verify_code_quality_complete,
        complete_reason="verify_code_quality_complete",
        allowed_lifecycles=(LIFECYCLE_OPENED, "examined"),
        **c,
    ),
    VERIFY_CODE_REVIEW_NODE: lambda s, v, f, **c: _host_advance_simple_complete(
        s, v, f, run_complete=run_verify_code_review_complete, complete_reason="verify_code_review_complete", **c
    ),
    VERIFY_COMPLETE_NODE: lambda s, v, f, **c: _host_advance_simple_complete(
        s, v, f, run_complete=run_verify_complete_complete, complete_reason="verify_complete_complete", **c
    ),
    DELIVER_STUB_NODE: _host_advance_deliver_stub,
}

_GIT_MECHANICAL_BOUNDARY_WAIT: dict[str, BoundaryWaitFn] = {}

_GIT_MECHANICAL_ADVANCE: dict[str, AdvanceStepFn] = {
    EXECUTE_BRANCH_NODE: lambda s, v, f, **c: _host_advance_simple_complete(
        s, v, f, run_complete=run_execute_branch_complete, complete_reason="execute_branch_complete", **c
    ),
}


def dispatch_task_bound_boundary_wait(
    node_id: str,
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path | None = None,
    foundry_bundle: Path | None = None,
    run_dir: Path | None = None,
) -> dict[str, Any] | None:
    handler = _TASK_BOUND_BOUNDARY_WAIT.get(node_id)
    if handler is None:
        return None
    return handler(
        snapshot,
        visit,
        flow,
        **_ctx(workspace=workspace, foundry_bundle=foundry_bundle, run_dir=run_dir),
    )


def dispatch_host_step_boundary_wait(
    node_id: str,
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path | None = None,
    foundry_bundle: Path | None = None,
    run_dir: Path | None = None,
) -> dict[str, Any] | None:
    from foundry_cli.engine.blocked_intake import host_boundary_wait_blocked_intake

    blocked_wait = host_boundary_wait_blocked_intake(
        snapshot,
        visit,
        workspace=workspace,
        run_dir=run_dir,
    )
    if blocked_wait is not None:
        return blocked_wait
    handler = _HOST_BOUNDARY_WAIT.get(node_id)
    if handler is None:
        return None
    return handler(
        snapshot,
        visit,
        flow,
        **_ctx(workspace=workspace, foundry_bundle=foundry_bundle, run_dir=run_dir),
    )


def dispatch_task_bound_advance(
    node_id: str,
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
) -> dict[str, Any] | None:
    handler = _TASK_BOUND_ADVANCE.get(node_id)
    if handler is None:
        return None
    return handler(
        snapshot,
        visit,
        flow,
        **_ctx(workspace=workspace, foundry_bundle=foundry_bundle, run_dir=run_dir),
    )


def dispatch_host_step_advance(
    node_id: str,
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
) -> dict[str, Any] | None:
    handler = _HOST_ADVANCE.get(node_id)
    if handler is None:
        return None
    return handler(
        snapshot,
        visit,
        flow,
        **_ctx(workspace=workspace, foundry_bundle=foundry_bundle, run_dir=run_dir),
    )


def dispatch_git_mechanical_boundary_wait(
    node_id: str,
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path | None = None,
    foundry_bundle: Path | None = None,
    run_dir: Path | None = None,
) -> dict[str, Any] | None:
    handler = _GIT_MECHANICAL_BOUNDARY_WAIT.get(node_id)
    if handler is None:
        return None
    return handler(
        snapshot,
        visit,
        flow,
        **_ctx(workspace=workspace, foundry_bundle=foundry_bundle, run_dir=run_dir),
    )


def dispatch_git_mechanical_advance(
    node_id: str,
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
) -> dict[str, Any] | None:
    handler = _GIT_MECHANICAL_ADVANCE.get(node_id)
    if handler is None:
        return None
    return handler(
        snapshot,
        visit,
        flow,
        **_ctx(workspace=workspace, foundry_bundle=foundry_bundle, run_dir=run_dir),
    )
