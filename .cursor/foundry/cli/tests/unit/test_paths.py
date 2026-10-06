"""Unit tests for foundry_cli.paths."""

from __future__ import annotations

import sys

import pytest

from foundry_cli.paths import (
    cli_script_path,
    foundry_root,
    resolve_cli_path,
    resolve_registry_path,
    resolve_run_uri,
    substitute_visit_id,
    workspace_from_run_dir,
)
from tests.conftest import REPO_ROOT
from tests.unit.constants import (
    REGISTRY_SCRIBE_AGENT,
    REGISTRY_INTAKE_CHECKER_CONTRACT,
    VISIT_V001,
)


def test_substitute_visit_id_replaces_placeholder() -> None:
    assert (
        substitute_visit_id("run:artifacts/{visit_id}/ticket.json", VISIT_V001)
        == f"run:artifacts/{VISIT_V001}/ticket.json"
    )


def test_substitute_visit_id_leaves_literal_segments() -> None:
    assert substitute_visit_id("run:ticket.json", VISIT_V001) == "run:ticket.json"


def test_resolve_run_uri_maps_under_run_dir(tmp_path) -> None:
    result = resolve_run_uri(f"run:artifacts/{VISIT_V001}/ticket.json", tmp_path, VISIT_V001)
    assert result == (tmp_path / f"artifacts/{VISIT_V001}/ticket.json").resolve()


def test_resolve_run_uri_rejects_non_run_uri(tmp_path) -> None:
    with pytest.raises(ValueError, match="Not a run path"):
        resolve_run_uri("workspace:README.md", tmp_path, VISIT_V001)


def test_resolve_registry_path_nodes_instructions() -> None:
    bundle = foundry_root()
    ref = "registry:nodes/shape.examine/judgment.md"
    result = resolve_registry_path(ref, bundle)
    assert result == bundle / "nodes/shape.examine/judgment.md"
    assert result.is_file()


def test_resolve_registry_path_workers_contract() -> None:
    bundle = foundry_root()
    result = resolve_registry_path(REGISTRY_INTAKE_CHECKER_CONTRACT, bundle)
    assert result == bundle / "workers/intake-checker.shape/contract.yaml"
    assert result.is_file()


def test_resolve_registry_path_agents_under_cursor() -> None:
    bundle = foundry_root()
    result = resolve_registry_path(REGISTRY_SCRIBE_AGENT, bundle)
    assert result == bundle.parent / "agents/scribe.md"
    assert result.is_file()


def test_resolve_registry_path_rejects_non_registry_ref() -> None:
    bundle = foundry_root()
    with pytest.raises(ValueError, match="Not a registry path"):
        resolve_registry_path("run:ticket.json", bundle)


def test_workspace_from_run_dir_infers_workspace(tmp_path) -> None:
    workspace = tmp_path / "my-app"
    run_dir = workspace / ".foundry" / "runs" / "foundry-test-0001"
    run_dir.mkdir(parents=True)
    assert workspace_from_run_dir(run_dir) == workspace.resolve()


def test_cli_script_path_points_at_foundry_sh(bundle) -> None:
    cli = cli_script_path(bundle)
    assert cli.is_file()
    assert cli.name == "foundry.sh"


def test_resolve_cli_path_relative_inside_workspace(bundle) -> None:
    cli_path = resolve_cli_path(bundle, REPO_ROOT)
    assert cli_path == ".cursor/foundry/cli/foundry.sh"
    assert (REPO_ROOT / cli_path).is_file()


def test_resolve_cli_path_absolute_outside_workspace(bundle, tmp_path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    cli_path = resolve_cli_path(bundle, workspace)
    assert cli_path == str(cli_script_path(bundle))


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="symlink creation requires elevated privileges on some Windows hosts",
)
def test_workspace_from_run_dir_resolves_symlinks(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    runs = workspace / ".foundry" / "runs"
    runs.mkdir(parents=True)
    actual_run = runs / "run-0001"
    actual_run.mkdir()
    link = tmp_path / "linked-run"
    link.symlink_to(actual_run)
    assert workspace_from_run_dir(link) == workspace.resolve()


def test_resolve_generated_docs_dir_defaults_to_repo_docs(tmp_path) -> None:
    repo = tmp_path / "foundry"
    repo.mkdir()
    (repo / "docs").mkdir()
    from foundry_cli.paths import default_generated_docs_dir, resolve_generated_docs_dir

    assert default_generated_docs_dir(repo) == repo / "docs"
    assert resolve_generated_docs_dir(repo, None) == (repo / "docs").resolve()


def test_resolve_generated_docs_dir_rejects_docs_nodes(tmp_path) -> None:
    repo = tmp_path / "foundry"
    docs = repo / "docs"
    (docs / "nodes").mkdir(parents=True)
    from foundry_cli.paths import resolve_generated_docs_dir

    with pytest.raises(ValueError, match="docs/nodes"):
        resolve_generated_docs_dir(repo, docs / "nodes")
