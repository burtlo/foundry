"""Foundry path grammar: registry:, run:, workspace:"""

from __future__ import annotations

from pathlib import Path


def foundry_root(start: Path | None = None) -> Path:
    """Locate `.cursor/foundry` from cwd or explicit start."""
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        bundle = candidate / ".cursor" / "foundry"
        if (bundle / "flows" / "factory-flow.yaml").is_file():
            return bundle
    raise FileNotFoundError("Could not locate .cursor/foundry (factory-flow.yaml missing)")


def cursor_root(foundry_bundle: Path) -> Path:
    return foundry_bundle.parent


def repo_root_from_bundle(foundry_bundle: Path) -> Path:
    """Repository root containing `.cursor/foundry`."""
    return foundry_bundle.parent.parent


def resolve_registry_path(ref: str, foundry_bundle: Path) -> Path:
    if not ref.startswith("registry:"):
        raise ValueError(f"Not a registry path: {ref!r}")
    relative = ref.removeprefix("registry:")
    if relative.startswith("agents/"):
        return cursor_root(foundry_bundle) / "agents" / relative.removeprefix("agents/")
    return foundry_bundle / relative


def substitute_visit_id(value: str, visit_id: str) -> str:
    return value.replace("{visit_id}", visit_id)


def resolve_run_uri(uri: str, run_dir: Path, visit_id: str) -> Path:
    if not uri.startswith("run:"):
        raise ValueError(f"Not a run path: {uri!r}")
    relative = substitute_visit_id(uri.removeprefix("run:"), visit_id)
    return (run_dir / relative).resolve()


def resolve_workspace_uri(uri: str, workspace: Path) -> Path:
    if not uri.startswith("workspace:"):
        raise ValueError(f"Not a workspace path: {uri!r}")
    relative = uri.removeprefix("workspace:")
    return (workspace / relative).resolve()


def workspace_from_run_dir(run_dir: Path) -> Path:
    """Infer workspace from run_dir assuming layout {workspace}/.foundry/runs/{id}."""
    return run_dir.resolve().parent.parent.parent
