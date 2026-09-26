"""Unit tests for foundry_cli.paths."""

from __future__ import annotations

import pytest

from foundry_cli.paths import foundry_root, resolve_registry_path, resolve_run_uri, substitute_visit_id


def test_substitute_visit_id_replaces_placeholder() -> None:
    assert (
        substitute_visit_id("run:artifacts/{visit_id}/ticket.json", "v-001")
        == "run:artifacts/v-001/ticket.json"
    )


def test_substitute_visit_id_leaves_literal_segments() -> None:
    assert substitute_visit_id("run:ticket.json", "v-001") == "run:ticket.json"


def test_resolve_run_uri_maps_under_run_dir(tmp_path) -> None:
    result = resolve_run_uri("run:artifacts/v-001/ticket.json", tmp_path, "v-001")
    assert result == (tmp_path / "artifacts/v-001/ticket.json").resolve()


def test_resolve_run_uri_rejects_non_run_uri(tmp_path) -> None:
    with pytest.raises(ValueError, match="Not a run path"):
        resolve_run_uri("workspace:README.md", tmp_path, "v-001")


def test_resolve_registry_path_nodes_instructions() -> None:
    bundle = foundry_root()
    result = resolve_registry_path(
        "registry:nodes/shape.intake/instructions.md",
        bundle,
    )
    assert result == bundle / "nodes/shape.intake/instructions.md"
    assert result.is_file()


def test_resolve_registry_path_workers_contract() -> None:
    bundle = foundry_root()
    result = resolve_registry_path(
        "registry:workers/intake-checker.shape/contract.yaml",
        bundle,
    )
    assert result == bundle / "workers/intake-checker.shape/contract.yaml"
    assert result.is_file()


def test_resolve_registry_path_agents_under_cursor() -> None:
    bundle = foundry_root()
    result = resolve_registry_path(
        "registry:agents/intake-checker.shape.md",
        bundle,
    )
    assert result == bundle.parent / "agents/intake-checker.shape.md"


def test_resolve_registry_path_rejects_non_registry_ref() -> None:
    bundle = foundry_root()
    with pytest.raises(ValueError, match="Not a registry path"):
        resolve_registry_path("run:ticket.json", bundle)
