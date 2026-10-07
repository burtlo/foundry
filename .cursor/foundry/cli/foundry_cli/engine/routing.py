"""Connection routing and when-expression evaluation."""

from __future__ import annotations

from typing import Any

from foundry_cli.engine.expressions import WhenExpressionError, evaluate_when_expression


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
