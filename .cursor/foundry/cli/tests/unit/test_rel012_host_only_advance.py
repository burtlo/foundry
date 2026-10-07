"""REL-012 (G4): host-only execute/verify intake and execute.test — no worker wait."""

from __future__ import annotations

from foundry_cli.engine.advance import _boundary_wait_for_visit
from foundry_cli.engine.blocked_intake import HOST_ONLY_STEP_NODE_IDS
from foundry_cli.registry import get_node, load_registry
from tests.conftest import FOUNDRY_ROOT

BUNDLE = FOUNDRY_ROOT


def test_flow_nodes_have_no_worker_binding() -> None:
    _, flow = load_registry(BUNDLE)
    for node_id in HOST_ONLY_STEP_NODE_IDS:
        node = get_node(flow, node_id)
        assert node.get("worker") is None


def test_host_only_steps_do_not_emit_worker_wait_at_boundary_fallback() -> None:
    _, flow = load_registry(BUNDLE)
    for node_id in HOST_ONLY_STEP_NODE_IDS:
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
