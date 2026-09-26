"""Connection routing and when-expression evaluation."""

from __future__ import annotations

from typing import Any

from foundry_cli.ledger import count_events, last_event


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
    if "outcome == 'completed'" in expr:
        return payload.get("outcome") == "completed"
    return event is not None


def evaluate_when_expression(snapshot: dict[str, Any], visit: dict[str, Any], expr: str) -> bool:
    """Minimal evaluator for catalog when expressions used in shape vertical slice."""
    expr = expr.strip()
    visit_id = str(visit.get("id", ""))

    if "history.count('receipt.linked'" in expr and "intake-receipt" in expr:
        return (
            count_events(
                snapshot,
                "receipt.linked",
                visit_id=visit_id,
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
        return _snapshot_state_value(snapshot, "open_clarifying_questions_count") == 0
    if "state.open_clarifying_questions_count != 0" in expr:
        count = _snapshot_state_value(snapshot, "open_clarifying_questions_count")
        return count is not None and count != 0
    if "state.approved_ac_version >= 1" in expr:
        version = _snapshot_state_value(snapshot, "approved_ac_version")
        return isinstance(version, (int, float)) and version >= 1
    for node_id in ("shape.intake", "shape.examine", "shape.present", "shape.record"):
        marker = f"history.last('visit.sealed', node_id='{node_id}')"
        if marker in expr:
            return _visit_sealed_check(snapshot, node_id, expr)
    return False


def select_connection(
    snapshot: dict[str, Any],
    from_node_id: str,
    flow: dict[str, Any],
    outcome: str = "completed",
    *,
    visit: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    from foundry_cli.engine.lifecycle import active_visit

    active = visit if visit is not None else active_visit(snapshot)
    unconditional: list[dict[str, Any]] = []
    conditional: list[dict[str, Any]] = []
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
                conditional.append(connection)
        else:
            unconditional.append(connection)
    if conditional:
        return conditional[0]
    if unconditional:
        return unconditional[0]
    return None
