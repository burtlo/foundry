"""Unit tests for advance node classification (REL-007)."""

from __future__ import annotations

import pytest

from foundry_cli.engine.advance_classifier import AdvanceNodeClass, classify_advance_node
from foundry_cli.engine.execute_step_executor import EXECUTE_BRANCH_NODE
from foundry_cli.engine.node_runtime_profile import AdvanceMode, load_node_runtime_profile
from foundry_cli.engine.node_runtime_matrix import implementation_flow_node_ids
from foundry_cli.registry import get_node, load_registry
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import IMPLEMENTATION_FLOW

BUNDLE = FOUNDRY_ROOT


@pytest.fixture(scope="module")
def flow() -> dict:
    _, loaded = load_registry(BUNDLE)
    return loaded


def _implementation_node_ids() -> list[str]:
    return implementation_flow_node_ids(BUNDLE, IMPLEMENTATION_FLOW)


def test_task_bound_nodes_have_runtime_task_advance(flow: dict) -> None:
    for node_id in _implementation_node_ids():
        node = get_node(flow, node_id)
        runtime = node.get("runtime")
        if not isinstance(runtime, dict) or runtime.get("advance") != "task":
            continue
        assert runtime.get("advance") == "task", node_id


def test_git_mechanical_nodes_classify_as_git_mechanical_step(flow: dict) -> None:
    git_ids = [
        node_id
        for node_id in _implementation_node_ids()
        if load_node_runtime_profile(node_id, flow, BUNDLE).advance_mode
        == AdvanceMode.GIT_MECHANICAL
    ]
    assert EXECUTE_BRANCH_NODE in git_ids
    for node_id in git_ids:
        assert (
            classify_advance_node(node_id, flow, foundry_bundle=BUNDLE)
            == AdvanceNodeClass.GIT_MECHANICAL_STEP
        )


@pytest.mark.parametrize("node_id", ["shape.examine", "shape.present", "shape.record"])
def test_classify_shape_task_nodes(flow: dict, node_id: str) -> None:
    assert (
        classify_advance_node(node_id, flow, foundry_bundle=BUNDLE)
        == AdvanceNodeClass.TASK_BOUND_STEP
    )


def test_classify_unsupported_execute_step_without_host_or_task(flow: dict) -> None:
    assert (
        classify_advance_node("execute.unknown.step", flow, foundry_bundle=BUNDLE)
        == AdvanceNodeClass.UNSUPPORTED
    )
