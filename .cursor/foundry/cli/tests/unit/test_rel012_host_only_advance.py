"""REL-012 (G4): host-only execute/verify intake and execute.test — no worker wait."""

from __future__ import annotations

from foundry_cli.engine.advance import _boundary_wait_for_visit
from foundry_cli.engine.node_runtime_matrix import implementation_flow_node_ids
from foundry_cli.engine.node_runtime_profile import load_node_runtime_profile
from foundry_cli.registry import get_node, load_registry
from tests.conftest import FOUNDRY_ROOT

BUNDLE = FOUNDRY_ROOT


def test_flow_nodes_have_no_worker_binding() -> None:
    _, flow = load_registry(BUNDLE)
    host_only_node_ids = [
        node_id
        for node_id in implementation_flow_node_ids(BUNDLE, "implementation")
        if load_node_runtime_profile(node_id, flow, BUNDLE).host_only_boundary
    ]
    for node_id in host_only_node_ids:
        node = get_node(flow, node_id)
        assert node.get("worker") is None


def test_host_only_steps_do_not_emit_worker_wait_at_boundary_fallback() -> None:
    _, flow = load_registry(BUNDLE)
    host_only_node_ids = [
        node_id
        for node_id in implementation_flow_node_ids(BUNDLE, "implementation")
        if load_node_runtime_profile(node_id, flow, BUNDLE).host_only_boundary
    ]
    for node_id in host_only_node_ids:
        visit = {
            "id": f"v-{node_id}",
            "node_id": node_id,
            "kind": "step",
            "lifecycle": "opened",
        }
        wait = _boundary_wait_for_visit(
            snapshot={"status": "running", "ledger": [], "wait": None, "state": {}},
            visit=visit,
            flow=flow,
            foundry_bundle=BUNDLE,
        )
        assert wait is None or wait.get("kind") != "agent"
