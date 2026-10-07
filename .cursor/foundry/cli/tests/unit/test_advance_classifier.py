"""Unit tests for advance node classification (REL-007)."""

from __future__ import annotations

import pytest

from foundry_cli.engine.advance_classifier import AdvanceNodeClass, classify_advance_node
from foundry_cli.engine.execute_step_executor import EXECUTE_BRANCH_NODE
from foundry_cli.engine.node_capability import EXECUTE_VERIFY_DELIVER_NODE_IDS
from foundry_cli.engine.node_runtime_profile import GIT_MECHANICAL_STEP_NODE_IDS
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT

BUNDLE = FOUNDRY_ROOT

_SHAPE_TASK_NODE_IDS = (
    "shape.examine",
    "shape.present",
    "shape.record",
)

_TASK_BOUND_NODE_IDS = (
    "shape.examine",
    "shape.present",
    "shape.record",
    "execute.plan",
    "verify.acceptance",
)

_EXPECTED_CLASS: dict[str, AdvanceNodeClass] = {
    "execute.start": AdvanceNodeClass.USER_GATE,
    "execute.intake": AdvanceNodeClass.HOST_STEP,
    "execute.intake.gate": AdvanceNodeClass.ENGINE_GATE,
    "execute.branch": AdvanceNodeClass.GIT_MECHANICAL_STEP,
    "execute.plan": AdvanceNodeClass.TASK_BOUND_STEP,
    "execute.build": AdvanceNodeClass.HOST_STEP,
    "execute.test": AdvanceNodeClass.HOST_STEP,
    "execute.test.gate": AdvanceNodeClass.ENGINE_GATE,
    "execute.repair.limit.gate": AdvanceNodeClass.ENGINE_GATE,
    "execute.commit": AdvanceNodeClass.HOST_STEP,
    "execute.commit.gate": AdvanceNodeClass.ENGINE_GATE,
    "verify.intake": AdvanceNodeClass.HOST_STEP,
    "verify.intake.gate": AdvanceNodeClass.ENGINE_GATE,
    "verify.acceptance": AdvanceNodeClass.TASK_BOUND_STEP,
    "verify.acceptance.gate": AdvanceNodeClass.ENGINE_GATE,
    "verify.code_quality": AdvanceNodeClass.HOST_STEP,
    "verify.code_quality.gate": AdvanceNodeClass.ENGINE_GATE,
    "verify.code_review": AdvanceNodeClass.HOST_STEP,
    "verify.code_review.gate": AdvanceNodeClass.USER_GATE,
    "verify.complete": AdvanceNodeClass.HOST_STEP,
    "verify.complete.gate": AdvanceNodeClass.USER_GATE,
    "deliver.stub": AdvanceNodeClass.HOST_STEP,
    "shape.intake": AdvanceNodeClass.HOST_STEP,
    "shape.examine": AdvanceNodeClass.TASK_BOUND_STEP,
    "shape.present": AdvanceNodeClass.TASK_BOUND_STEP,
    "shape.record": AdvanceNodeClass.TASK_BOUND_STEP,
}


@pytest.fixture(scope="module")
def flow() -> dict:
    _, loaded = load_registry(BUNDLE)
    return loaded


def test_task_bound_nodes_have_runtime_task_advance(flow: dict) -> None:
    from foundry_cli.registry import get_node

    for node_id in _TASK_BOUND_NODE_IDS:
        node = get_node(flow, node_id)
        runtime = node.get("runtime")
        assert isinstance(runtime, dict), node_id
        assert runtime.get("advance") == "task", node_id


def test_git_mechanical_step_node_ids_pilot_execute_branch(flow: dict) -> None:
    assert GIT_MECHANICAL_STEP_NODE_IDS == (EXECUTE_BRANCH_NODE,)
    assert (
        classify_advance_node(EXECUTE_BRANCH_NODE, flow, foundry_bundle=BUNDLE)
        == AdvanceNodeClass.GIT_MECHANICAL_STEP
    )


@pytest.mark.parametrize("node_id", EXECUTE_VERIFY_DELIVER_NODE_IDS)
def test_classify_execute_verify_deliver_nodes(
    flow: dict,
    node_id: str,
) -> None:
    expected = _EXPECTED_CLASS[node_id]
    assert (
        classify_advance_node(node_id, flow, foundry_bundle=BUNDLE)
        == expected
    )


@pytest.mark.parametrize("node_id", _SHAPE_TASK_NODE_IDS)
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
