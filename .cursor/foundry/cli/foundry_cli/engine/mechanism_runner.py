"""Declarative mechanism execution (Step 5 skeleton)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from foundry_cli.engine.actions import ActionExecutionContext, ActionRegistry, default_action_registry
from foundry_cli.engine.expressions import WhenExpressionError, evaluate_when_expression
from foundry_cli.node_operations import load_operations


@dataclass
class MechanismRunner:
    """Run `mechanism:` steps from a node operations manifest."""

    actions: ActionRegistry | None = None

    def __post_init__(self) -> None:
        if self.actions is None:
            self.actions = default_action_registry()

    def run(
        self,
        snapshot: dict[str, Any],
        visit: dict[str, Any],
        flow: dict[str, Any],
        *,
        operations_ref: str,
        workspace: Path,
        foundry_bundle: Path,
        run_dir: Path,
    ) -> dict[str, Any]:
        operations = load_operations(operations_ref, foundry_bundle)
        mechanism = operations.get("mechanism")
        if not isinstance(mechanism, list):
            return {
                "ok": False,
                "status": "error",
                "code": "MECHANISM_INVALID",
                "message": "operations manifest missing list field `mechanism`",
                "steps": [],
            }

        assert self.actions is not None
        ctx = ActionExecutionContext(
            snapshot=snapshot,
            visit=visit,
            flow=flow,
            workspace=workspace,
            foundry_bundle=foundry_bundle,
            run_dir=run_dir,
        )
        step_records: list[dict[str, Any]] = []
        transitioned = False

        for index, raw in enumerate(mechanism):
            if not isinstance(raw, dict):
                return self._error_outcome(
                    code="MECHANISM_STEP_INVALID",
                    message=f"step[{index}] must be a mapping",
                    steps=step_records,
                )
            step = dict(raw)
            step_id = str(step.get("id") or f"step-{index + 1}")
            action = str(step.get("action") or "")
            if not action:
                return self._error_outcome(
                    code="MECHANISM_STEP_INVALID",
                    message=f"step {step_id} missing required field `action`",
                    steps=step_records,
                )

            when_expr = step.get("when")
            if isinstance(when_expr, str):
                try:
                    should_run = evaluate_when_expression(snapshot, visit, when_expr)
                except WhenExpressionError as exc:
                    return self._error_outcome(
                        code="WHEN_EVAL_ERROR",
                        message=str(exc),
                        steps=step_records,
                        step_id=step_id,
                        action=action,
                    )
                if not should_run:
                    step_records.append(
                        {
                            "id": step_id,
                            "action": action,
                            "when": when_expr,
                            "executed": False,
                            "skipped": True,
                        }
                    )
                    continue

            try:
                result = self.actions.execute(action, ctx, step)
            except KeyError:
                return self._error_outcome(
                    code="UNKNOWN_ACTION",
                    message=f"action {action!r} is not registered",
                    steps=step_records,
                    step_id=step_id,
                    action=action,
                )
            except Exception as exc:  # pragma: no cover - defensive boundary
                return self._error_outcome(
                    code="ACTION_EXCEPTION",
                    message=f"{action}: {exc}",
                    steps=step_records,
                    step_id=step_id,
                    action=action,
                )

            if not isinstance(result, dict):
                result = {"ok": True, "result": result}

            ctx.outputs[step_id] = result
            step_records.append(
                {
                    "id": step_id,
                    "action": action,
                    "executed": True,
                    "skipped": False,
                    "result": result,
                }
            )

            if not bool(result.get("ok", True)):
                return {
                    "ok": False,
                    "status": "error",
                    "code": str(result.get("code") or "ACTION_FAILED"),
                    "message": str(result.get("message") or f"action failed: {action}"),
                    "step_id": step_id,
                    "action": action,
                    "result": result,
                    "steps": step_records,
                }

            if result.get("wait") is not None:
                return {
                    "ok": True,
                    "status": "wait",
                    "wait": result.get("wait"),
                    "transitioned": transitioned,
                    "steps": step_records,
                }

            if bool(result.get("transitioned")):
                transitioned = True

        return {
            "ok": True,
            "status": "transitioned" if transitioned else "ok",
            "transitioned": transitioned,
            "steps": step_records,
        }

    def _error_outcome(
        self,
        *,
        code: str,
        message: str,
        steps: list[dict[str, Any]],
        step_id: str | None = None,
        action: str | None = None,
    ) -> dict[str, Any]:
        outcome: dict[str, Any] = {
            "ok": False,
            "status": "error",
            "code": code,
            "message": message,
            "steps": steps,
        }
        if step_id is not None:
            outcome["step_id"] = step_id
        if action is not None:
            outcome["action"] = action
        return outcome

