"""Unit tests for foundry_cli.node_view."""

from __future__ import annotations

from foundry_cli.node_view import (
    NodeDocView,
    ledger_excerpt_config,
    ledger_excerpt_section,
    lifecycle_hooks,
    reads_table,
    worker_id_from_contract,
)
from foundry_cli.registry import get_node
from tests.unit.constants import NODE_SHAPE_INTAKE


def test_lifecycle_hooks_collects_authored_checks(flow_bundle) -> None:
    flow, _bundle = flow_bundle
    node = get_node(flow, NODE_SHAPE_INTAKE)
    hooks = lifecycle_hooks(node)
    assert "on_open" in hooks
    assert hooks["on_open"][0]["check"] == "validate-manifest"


def test_reads_table_lists_config_and_artifacts(flow_bundle) -> None:
    flow, _bundle = flow_bundle
    node = get_node(flow, NODE_SHAPE_INTAKE)
    table = reads_table(node)
    assert "| `config` |" in table
    assert "`workspace`" in table


def test_node_doc_view_is_full_when_annotated(flow_bundle) -> None:
    flow, bundle = flow_bundle
    annotations = {"status": "draft", "summary": "test"}
    view = NodeDocView.build(NODE_SHAPE_INTAKE, flow, annotations)
    assert view.is_full_doc is True
    assert view.status == "draft"


def test_node_doc_view_not_full_without_annotations(flow_bundle) -> None:
    flow, _bundle = flow_bundle
    view = NodeDocView.build(NODE_SHAPE_INTAKE, flow, None)
    assert view.is_full_doc is False


def test_ledger_excerpt_config_from_doc_yaml(flow_bundle) -> None:
    flow, bundle = flow_bundle
    from foundry_cli.docgen import load_node_annotations

    annotations = load_node_annotations(NODE_SHAPE_INTAKE, bundle)
    config = ledger_excerpt_config(annotations)
    assert config == {"fixture_run": "porcelain-0007-v001", "visit_id": "v-001"}


def test_ledger_excerpt_section_renders_fixture_events(flow_bundle) -> None:
    flow, bundle = flow_bundle
    from foundry_cli.docgen import load_node_annotations

    annotations = load_node_annotations(NODE_SHAPE_INTAKE, bundle)
    excerpt = ledger_excerpt_section(NODE_SHAPE_INTAKE, bundle, annotations)
    assert "porcelain-0007-v001" in excerpt
    assert "| 7 | `artifact.linked` |" in excerpt


def test_worker_id_from_contract() -> None:
    assert (
        worker_id_from_contract("registry:workers/intake-checker.shape/contract.yaml")
        == "intake-checker.shape"
    )
