"""Boundary status for implementation flow (REL-015 / G7)."""

from __future__ import annotations

import pytest

from foundry_cli.engine.agent.tasks import (
    SHAPE_EXAMINE_TASK_ID,
    SHAPE_PRESENT_TASK_ID,
    SHAPE_RECORD_TASK_ID,
)
from foundry_cli.engine.node_capability import boundary_status
from foundry_cli.engine.node_runtime_matrix import execute_verify_deliver_flow_node_ids
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import IMPLEMENTATION_FLOW

BUNDLE = FOUNDRY_ROOT


def test_execute_verify_deliver_slice_has_no_unsupported_boundary_status() -> None:
    _, flow = load_registry(BUNDLE)
    for node_id in execute_verify_deliver_flow_node_ids(BUNDLE, IMPLEMENTATION_FLOW):
        status = boundary_status(node_id, flow, foundry_bundle=BUNDLE)
        assert status != "unsupported", node_id


@pytest.mark.parametrize(
    "node_id",
    [SHAPE_EXAMINE_TASK_ID, SHAPE_PRESENT_TASK_ID, SHAPE_RECORD_TASK_ID],
)
def test_shape_judgment_boundary_status_implemented(
    node_id: str,
) -> None:
    _, flow = load_registry(BUNDLE)
    assert boundary_status(node_id, flow, foundry_bundle=BUNDLE) == "implemented"
    assert boundary_status(node_id, flow) == "implemented"
