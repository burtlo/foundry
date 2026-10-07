"""Unit tests for node runtime profile loader (engine DSL Step 1)."""

from __future__ import annotations

import pytest

from foundry_cli.engine.advance_classifier import AdvanceNodeClass, classify_advance_node
from foundry_cli.engine.node_runtime_matrix import implementation_flow_node_ids
from foundry_cli.engine.node_runtime_profile import (
    AdvanceMode,
    advance_mode_for_classifier_parity,
    load_node_runtime_profile,
)
from foundry_cli.registry import load_registry
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import IMPLEMENTATION_FLOW

BUNDLE = FOUNDRY_ROOT


@pytest.fixture(scope="module")
def flow() -> dict:
    _, loaded = load_registry(BUNDLE)
    return loaded


def test_shape_intake_profile(flow: dict) -> None:
    profile = load_node_runtime_profile("shape.intake", flow, BUNDLE)
    assert profile.advance_mode == AdvanceMode.HOST
    assert profile.task_id is None
    assert profile.requires_work_prompt is True
    assert profile.work_prompt_wait_summary is not None
    assert profile.work_prompt_request_ref == "intake:work_prompt"
    assert profile.blocked_intake is False
    assert profile.host_only_boundary is False
    assert profile.engine_gate_resolver is None
    assert profile.operations_file_exists is True
    assert profile.operations_ref == "registry:nodes/shape.intake/operations.yaml"
    assert profile.task_file_exists is False


def test_shape_examine_profile(flow: dict) -> None:
    profile = load_node_runtime_profile("shape.examine", flow, BUNDLE)
    assert profile.advance_mode == AdvanceMode.TASK
    assert profile.task_id == "shape.examine"
    assert profile.pending_open_questions is True
    assert profile.task_file_exists is True
    assert profile.blocked_intake is False
    assert profile.host_only_boundary is False
    assert profile.engine_gate_resolver is None


def test_execute_build_profile(flow: dict) -> None:
    profile = load_node_runtime_profile("execute.build", flow, BUNDLE)
    assert profile.advance_mode == AdvanceMode.HOST
    assert profile.task_id is None
    assert profile.blocked_intake is False
    assert profile.host_only_boundary is False
    assert profile.engine_gate_resolver is None
    assert profile.operations_file_exists is True


def test_execute_test_gate_profile(flow: dict) -> None:
    profile = load_node_runtime_profile("execute.test.gate", flow, BUNDLE)
    assert profile.advance_mode == AdvanceMode.GATE_ENGINE
    assert profile.engine_gate_resolver == "execute.test.gate"
    assert profile.task_id is None
    assert profile.blocked_intake is False
    assert profile.host_only_boundary is False


@pytest.mark.parametrize("node_id", list(implementation_flow_node_ids(BUNDLE, IMPLEMENTATION_FLOW)))
def test_profile_advance_mode_matches_classify_advance_node(flow: dict, node_id: str) -> None:
    profile = load_node_runtime_profile(node_id, flow, BUNDLE)
    expected = classify_advance_node(node_id, flow, foundry_bundle=BUNDLE)
    assert advance_mode_for_classifier_parity(profile.advance_mode) == expected.value


def test_blocked_intake_and_host_only_flags(flow: dict) -> None:
    execute_intake = load_node_runtime_profile("execute.intake", flow, BUNDLE)
    assert execute_intake.blocked_intake is True
    assert execute_intake.host_only_boundary is True

    execute_test = load_node_runtime_profile("execute.test", flow, BUNDLE)
    assert execute_test.blocked_intake is False
    assert execute_test.host_only_boundary is True

    user_gate = load_node_runtime_profile("verify.code_review.gate", flow, BUNDLE)
    assert user_gate.advance_mode == AdvanceMode.GATE_USER
    assert user_gate.engine_gate_resolver is None


def test_engine_gate_without_resolver_still_gate_engine(flow: dict) -> None:
    """User gates are gate_user; engine gates without resolver keep mode gate_engine."""
    profile = load_node_runtime_profile("execute.start", flow, BUNDLE)
    assert profile.advance_mode == AdvanceMode.GATE_USER
    assert (
        classify_advance_node("execute.start", flow, foundry_bundle=BUNDLE)
        == AdvanceNodeClass.USER_GATE
    )
