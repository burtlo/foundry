"""Connection routing and when-expression evaluation."""

from __future__ import annotations

from typing import Any

from foundry_cli.engine.examination_state import derive_open_clarifying_questions_count
from foundry_cli.ledger import count_events, last_event


class WhenExpressionError(Exception):
    """Raised when a when expression is unknown or cannot be evaluated safely."""

    def __init__(self, expr: str, message: str | None = None) -> None:
        self.expr = expr
        super().__init__(message or f"Unknown or unsupported when expression: {expr!r}")


class RoutingDefinitionError(Exception):
    def __init__(self, code: str, message: str, eligible_count: int) -> None:
        self.code = code
        self.eligible_count = eligible_count
        super().__init__(message)


def flow_checks(flow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    checks = flow.get("checks") or {}
    if isinstance(checks, dict):
        return {str(key): value for key, value in checks.items() if isinstance(value, dict)}
    return {}


def flow_connections(flow: dict[str, Any]) -> list[dict[str, Any]]:
    connections = flow.get("connections") or []
    return [item for item in connections if isinstance(item, dict)]


def _snapshot_state_value(snapshot: dict[str, Any], key: str) -> Any:
    state = snapshot.get("state")
    if not isinstance(state, dict):
        return None
    return state.get(key)


def _visit_sealed_check(snapshot: dict[str, Any], node_id: str, expr: str) -> bool:
    event = last_event(snapshot, "visit.sealed", node_id=node_id)
    if event is None:
        return "!= null" not in expr
    payload = event.get("payload") or {}
    if "outcome in ['completed', 'not_applicable']" in expr:
        return payload.get("outcome") in ("completed", "not_applicable")
    if "outcome == 'completed'" in expr:
        return payload.get("outcome") == "completed"
    if "outcome == 'not_applicable'" in expr:
        return payload.get("outcome") == "not_applicable"
    return event is not None


def _config_limit(snapshot: dict[str, Any], name: str, default: int) -> int:
    config = snapshot.get("config")
    if isinstance(config, dict):
        limits = config.get("limits")
        if isinstance(limits, dict):
            value = limits.get(name)
            if isinstance(value, (int, float)):
                return int(value)
    return default


def _config_review_enabled(snapshot: dict[str, Any]) -> bool:
    config = snapshot.get("config")
    if not isinstance(config, dict):
        return False
    review = config.get("review")
    if not isinstance(review, dict):
        return False
    return bool(review.get("enabled"))


def _gate_last_decision(snapshot: dict[str, Any], node_id: str) -> str | None:
    event = last_event(snapshot, "gate.resolved", node_id=node_id)
    if event is None:
        return None
    payload = event.get("payload") or {}
    decision = payload.get("decision")
    return str(decision) if decision is not None else None


def _visit_sealed_outcome(snapshot: dict[str, Any], node_id: str) -> str | None:
    event = last_event(snapshot, "visit.sealed", node_id=node_id)
    if event is None:
        return None
    payload = event.get("payload") or {}
    outcome = payload.get("outcome")
    return str(outcome) if outcome is not None else None


def _expression_is_supported(expr: str) -> bool:
    markers = (
        "history.count('receipt.linked'",
        "history.count('connection.taken'",
        "history.count('visit.sealed'",
        "config.limits.",
        "config.review.enabled",
        "!config.review.enabled",
        "history.last('gate.resolved'",
        "state.open_clarifying_questions_count",
        "state.approved_ac_version",
        "state.feature_branch",
        "state.execution_graph_id",
        "state.final_commit_sha",
        "history.last('visit.sealed'",
    )
    return any(marker in expr for marker in markers)


def evaluate_when_expression(snapshot: dict[str, Any], visit: dict[str, Any], expr: str) -> bool:
    """Evaluator for catalog when expressions used in the shape vertical slice."""
    expr = expr.strip()
    if not _expression_is_supported(expr):
        raise WhenExpressionError(expr)

    visit_id = str(visit.get("id", ""))

    if "history.count('receipt.linked'" in expr and "intake-receipt" in expr:
        receipt_visit_id = visit_id
        gate_node = str(visit.get("node_id") or "")
        if gate_node in ("execute.intake.gate", "verify.intake.gate"):
            from foundry_cli.engine.hooks import _latest_sealed_visit_id

            intake_node = "execute.intake" if gate_node.startswith("execute.") else "verify.intake"
            prior_intake = _latest_sealed_visit_id(snapshot, intake_node)
            if prior_intake:
                receipt_visit_id = prior_intake
        return (
            count_events(
                snapshot,
                "receipt.linked",
                visit_id=receipt_visit_id,
                schema="registry:schemas/intake-receipt.schema.json",
            )
            >= 1
        )
    if "history.count('receipt.linked'" in expr and "agent-receipt" in expr:
        return (
            count_events(
                snapshot,
                "receipt.linked",
                visit_id=visit_id,
                schema="registry:schemas/agent-receipt.schema.json",
            )
            >= 1
        )
    if "state.open_clarifying_questions_count == 0" in expr:
        state = snapshot.get("state")
        if not isinstance(state, dict):
            return False
        return derive_open_clarifying_questions_count(state) == 0
    if "state.open_clarifying_questions_count != 0" in expr:
        state = snapshot.get("state")
        if not isinstance(state, dict):
            return False
        return derive_open_clarifying_questions_count(state) != 0
    if "state.approved_ac_version >= 1" in expr:
        version = _snapshot_state_value(snapshot, "approved_ac_version")
        return isinstance(version, (int, float)) and version >= 1
    if "state.feature_branch != null" in expr:
        return _snapshot_state_value(snapshot, "feature_branch") is not None
    if "state.execution_graph_id != null" in expr:
        return _snapshot_state_value(snapshot, "execution_graph_id") is not None
    if "state.final_commit_sha != null" in expr:
        return _snapshot_state_value(snapshot, "final_commit_sha") is not None
    if expr.strip() == "config.review.enabled":
        return _config_review_enabled(snapshot)
    if "history.last('gate.resolved', node_id='verify.acceptance.gate')" in expr and ".decision == 'pass'" in expr:
        return _gate_last_decision(snapshot, "verify.acceptance.gate") == "pass"
    if "history.last('gate.resolved', node_id='verify.code_review.gate')" in expr and ".decision == 'accept'" in expr:
        return _gate_last_decision(snapshot, "verify.code_review.gate") == "accept"
    if "code-quality-done-or-skipped" in expr or (
        "!config.review.enabled" in expr and "verify.code_quality" in expr
    ):
        if not _config_review_enabled(snapshot):
            return True
        outcome = _visit_sealed_outcome(snapshot, "verify.code_quality")
        return outcome in ("completed", "not_applicable")
    if (
        "history.count('connection.taken'" in expr
        and "loop='repair'" in expr
        and "config.limits.repair" in expr
    ):
        repair_count = count_events(snapshot, "connection.taken", loop="repair")
        limit = _config_limit(snapshot, "repair", 2)
        if "<= config.limits.repair" in expr:
            return repair_count <= limit
        if "< config.limits.repair" in expr:
            return repair_count < limit
        if ">= config.limits.repair" in expr:
            return repair_count >= limit
        if "> config.limits.repair" in expr:
            return repair_count > limit
    if (
        "history.count('visit.sealed', node_id='verify.intake')" in expr
        and "config.limits.reverify" in expr
    ):
        sealed_count = count_events(snapshot, "visit.sealed", node_id="verify.intake")
        limit = _config_limit(snapshot, "reverify", 2)
        if "<= config.limits.reverify" in expr:
            return sealed_count <= limit
        if "< config.limits.reverify" in expr:
            return sealed_count < limit
        if ">= config.limits.reverify" in expr:
            return sealed_count >= limit
        if "> config.limits.reverify" in expr:
            return sealed_count > limit
    prior_nodes = (
        "shape.intake",
        "shape.examine",
        "shape.present",
        "shape.record",
        "execute.intake",
        "execute.commit",
        "execute.build",
        "execute.test",
        "verify.intake",
        "verify.acceptance",
    )
    for node_id in prior_nodes:
        marker = f"history.last('visit.sealed', node_id='{node_id}')"
        if marker in expr:
            return _visit_sealed_check(snapshot, node_id, expr)

    raise WhenExpressionError(expr)


def eligible_connections(
    snapshot: dict[str, Any],
    from_node_id: str,
    flow: dict[str, Any],
    outcome: str = "completed",
    *,
    visit: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    from foundry_cli.engine.lifecycle import active_visit

    active = visit if visit is not None else active_visit(snapshot)
    eligible: list[dict[str, Any]] = []
    for connection in flow_connections(flow):
        if connection.get("from") != from_node_id:
            continue
        on_block = connection.get("on") or {}
        outcomes = on_block.get("outcomes") or []
        if outcome not in outcomes:
            continue
        decisions = on_block.get("decisions") or []
        if decisions:
            visit_decision = active.get("decision")
            if visit_decision not in decisions:
                continue
        when_expr = connection.get("when")
        if when_expr:
            if evaluate_when_expression(snapshot, active, str(when_expr)):
                eligible.append(connection)
        else:
            eligible.append(connection)
    return eligible


def select_connection(
    snapshot: dict[str, Any],
    from_node_id: str,
    flow: dict[str, Any],
    outcome: str = "completed",
    *,
    visit: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    eligible = eligible_connections(
        snapshot,
        from_node_id,
        flow,
        outcome=outcome,
        visit=visit,
    )
    if len(eligible) == 1:
        return eligible[0]
    if len(eligible) == 0:
        raise RoutingDefinitionError(
            code="NO_ELIGIBLE_CONNECTION",
            message=f"No eligible connection from {from_node_id!r} for outcome {outcome!r}",
            eligible_count=0,
        )
    raise RoutingDefinitionError(
        code="AMBIGUOUS_CONNECTION",
        message=f"Multiple eligible connections from {from_node_id!r} ({len(eligible)} matches)",
        eligible_count=len(eligible),
    )
