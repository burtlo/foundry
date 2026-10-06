"""Foundry path grammar: registry:, run:, workspace:"""

from __future__ import annotations

from pathlib import Path


def foundry_root(start: Path | None = None) -> Path:
    """Locate the Foundry registry bundle for a workspace (backward-compatible wrapper)."""
    from foundry_cli.foundry_config import resolve_registry_bundle

    workspace = (start or Path.cwd()).resolve()
    bundle, _ = resolve_registry_bundle(workspace)
    return bundle


def cursor_root(foundry_bundle: Path) -> Path:
    return foundry_bundle.parent


def repo_root_from_bundle(foundry_bundle: Path) -> Path:
    """Repository root containing `.cursor/foundry`."""
    return foundry_bundle.parent.parent


def default_generated_docs_dir(repo_root: Path) -> Path:
    """Canonical output root for `doc build` / `dev docs` (…/docs)."""
    return (repo_root / "docs").resolve()


def resolve_generated_docs_dir(repo_root: Path, override: Path | None) -> Path:
    """Resolve doc generation output; reject nested layouts that duplicate CLI under nodes/."""
    docs_root = default_generated_docs_dir(repo_root)
    if override is None:
        return docs_root
    resolved = override.resolve()
    try:
        rel = resolved.relative_to(docs_root)
    except ValueError:
        return resolved
    if rel.parts == ("nodes",):
        raise ValueError(
            f"doc output must be {docs_root}, not {resolved}. "
            "Using docs/nodes creates duplicate docs/nodes/cli/ and docs/nodes/nodes/ trees."
        )
    if rel.parts and rel.parts[0] == "nodes":
        raise ValueError(
            f"doc output must not be under docs/nodes (got {resolved}). "
            f"Use --output {docs_root}."
        )
    return resolved


def cli_script_path(foundry_bundle: Path) -> Path:
    """Absolute path to `foundry.sh` for a resolved registry bundle."""
    return (foundry_bundle / "cli" / "foundry.sh").resolve()


def resolve_cli_path(foundry_bundle: Path, workspace: Path) -> str:
    """Return `foundry.sh` relative to workspace when possible, else absolute."""
    cli = cli_script_path(foundry_bundle)
    workspace = workspace.resolve()
    try:
        return cli.relative_to(workspace).as_posix()
    except ValueError:
        return str(cli)


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
