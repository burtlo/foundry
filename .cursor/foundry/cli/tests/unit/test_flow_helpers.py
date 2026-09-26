"""Unit tests for foundry_cli.flow_helpers."""

from __future__ import annotations

from foundry_cli.flow_helpers import node_connections, normalize_connection
from foundry_cli.registry import get_node
from tests.unit.constants import NODE_SHAPE_EXAMINE, NODE_SHAPE_INTAKE


def test_normalize_connection_preserves_optional_fields() -> None:
    connection = {
        "id": f"verify.acceptance.gate-to-{NODE_SHAPE_INTAKE}-reshape",
        "from": "verify.acceptance.gate",
        "to": NODE_SHAPE_INTAKE,
        "loop": "reshape",
        "on": {"outcomes": ["completed"], "decisions": ["reshape"]},
    }
    normalized = normalize_connection(connection)
    assert normalized["id"] == connection["id"]
    assert normalized["from"] == "verify.acceptance.gate"
    assert normalized["to"] == NODE_SHAPE_INTAKE
    assert normalized["loop"] == "reshape"
    assert normalized["on"] == connection["on"]
    assert "when" not in normalized


def test_node_connections_groups_incoming_and_outgoing(flow: dict) -> None:
    connections = node_connections(flow, NODE_SHAPE_INTAKE)
    assert connections["out"][0]["to"] == NODE_SHAPE_EXAMINE
    assert len(connections["in"]) == 2
    assert all("id" in connection for connection in connections["in"])
    assert all("from" in connection for connection in connections["out"])


def test_node_connections_skips_non_dict_entries() -> None:
    flow = {
        "connections": [
            {"id": "a-to-b", "from": "a", "to": "b"},
            "invalid",
            None,
        ]
    }
    connections = node_connections(flow, "a")
    assert len(connections["out"]) == 1
    assert connections["out"][0]["to"] == "b"
    assert connections["in"] == []


def test_node_connections_returns_empty_for_unknown_node(flow: dict) -> None:
    node = get_node(flow, NODE_SHAPE_INTAKE)
    assert node["id"] == NODE_SHAPE_INTAKE
    connections = node_connections(flow, "missing.node")
    assert connections == {"in": [], "out": []}
