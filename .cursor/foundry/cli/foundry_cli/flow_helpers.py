"""Flow graph helpers shared across catalog and docgen."""

from __future__ import annotations

from typing import Any


def normalize_connection(connection: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {
        "id": str(connection["id"]),
        "from": str(connection["from"]),
        "to": str(connection["to"]),
    }
    if "on" in connection:
        normalized["on"] = connection["on"]
    if "when" in connection:
        normalized["when"] = connection["when"]
    if "loop" in connection:
        normalized["loop"] = connection["loop"]
    return normalized


def node_connections(flow: dict[str, Any], node_id: str) -> dict[str, list[dict[str, Any]]]:
    connections = flow.get("connections") or []
    incoming: list[dict[str, Any]] = []
    outgoing: list[dict[str, Any]] = []
    for connection in connections:
        if not isinstance(connection, dict):
            continue
        if connection.get("from") == node_id:
            outgoing.append(normalize_connection(connection))
        if connection.get("to") == node_id:
            incoming.append(normalize_connection(connection))
    return {"in": incoming, "out": outgoing}
