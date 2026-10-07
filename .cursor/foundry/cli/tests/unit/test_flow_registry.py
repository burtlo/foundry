"""Unit tests for flow registry path resolution and node packages."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.flow_registry import (
    flow_registry_path,
    is_node_registry_ref,
    resolve_node_registry_ref,
)
from foundry_cli.registry import get_node, load_registry
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import IMPLEMENTATION_FLOW

NODE_EXECUTE_BRANCH = "execute.branch"


def test_flow_registry_path_uses_flow_id_directory() -> None:
    path = flow_registry_path(FOUNDRY_ROOT, IMPLEMENTATION_FLOW)
    assert path == FOUNDRY_ROOT / "flows" / "implementation" / "registry.yaml"
    assert path.is_file()


def test_is_node_registry_ref() -> None:
    assert is_node_registry_ref("registry:nodes/execute.branch/node.yaml")
    assert not is_node_registry_ref("registry:nodes/execute.branch/doc.yaml")


def test_load_registry_expands_node_packages() -> None:
    document, flow = load_registry(FOUNDRY_ROOT, flow_id=IMPLEMENTATION_FLOW)
    raw_nodes = document["flow"]["nodes"]
    assert all(is_node_registry_ref(item) for item in raw_nodes)
    node = get_node(flow, NODE_EXECUTE_BRANCH)
    assert node["title"] == "Create the feature branch"


def test_resolve_node_registry_ref_matches_flow_node(tmp_path: Path) -> None:
    import shutil

    bundle = tmp_path / "bundle"
    shutil.copytree(FOUNDRY_ROOT, bundle)
    ref = f"registry:nodes/{NODE_EXECUTE_BRANCH}/node.yaml"
    resolved = resolve_node_registry_ref(ref, bundle)
    _, flow = load_registry(bundle, flow_id=IMPLEMENTATION_FLOW)
    assert get_node(flow, NODE_EXECUTE_BRANCH) == resolved
