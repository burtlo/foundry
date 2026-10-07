"""Validate workspace .foundry/foundry.yaml and resolve registry bundles."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from foundry_cli.engine.registry_refs import validate_registry_instruction_refs
from foundry_cli.errors import ok
from foundry_cli.constants import DEFAULT_FLOW_ID
from foundry_cli.flow_registry import (
    flow_registry_display_path,
    flow_registry_exists,
    flow_registry_path,
)
from foundry_cli.registry import load_registry
from foundry_cli.validate import validate_payload

SCHEMA_VERSION = 1
DEFAULT_REGISTRY_REF = "../foundry/.cursor/foundry"


def foundry_config_path(workspace: Path) -> Path:
    return workspace / ".foundry" / "foundry.yaml"


def resolve_registry_path_from_config(registry_ref: str, workspace: Path) -> Path:
    workspace = workspace.resolve()
    ref = registry_ref.strip()
    if not ref:
        raise ValueError("registry path must not be empty")
    if ref.startswith(("/", "\\")):
        raise ValueError(f"registry path must be relative to workspace, not absolute: {ref!r}")
    if len(ref) >= 2 and ref[1] == ":":
        raise ValueError(f"registry path must be relative to workspace, not absolute: {ref!r}")
    return (workspace / ref).resolve()


def _validate_registry_bundle(bundle: Path, flow_id: str = DEFAULT_FLOW_ID) -> None:
    if not bundle.is_dir():
        raise FileNotFoundError(f"Registry bundle is not a directory: {bundle}")
    if not flow_registry_exists(bundle, flow_id):
        rel = flow_registry_path(bundle, flow_id).relative_to(bundle).as_posix()
        raise FileNotFoundError(f"Registry bundle missing {rel}: {bundle}")


def _find_workspace_bundle(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        bundle = candidate / ".cursor" / "foundry"
        if flow_registry_exists(bundle, DEFAULT_FLOW_ID):
            return bundle
    return None


def load_foundry_config(workspace: Path) -> tuple[Path, dict[str, Any]]:
    path = foundry_config_path(workspace)
    if not path.is_file():
        raise FileNotFoundError(f"Missing foundry config: {path}")
    try:
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Foundry config must be a mapping")
    return path, data


def _schema_bundle_for_workspace(workspace: Path) -> Path:
    bundle, _ = resolve_registry_bundle(workspace)
    return bundle


def validate_foundry_config(workspace: Path) -> dict[str, Any]:
    path = foundry_config_path(workspace)
    if not path.is_file():
        return {"ok": False, "errors": [f"Missing foundry config: {path}"]}
    try:
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        return {"ok": False, "errors": [f"Invalid YAML: {exc}"]}
    if not isinstance(data, dict):
        return {"ok": False, "errors": ["Foundry config must be a mapping"]}

    errors: list[str] = []
    schema_bundle: Path | None = None
    registry_ref = data.get("registry")
    if isinstance(registry_ref, str) and registry_ref.strip():
        try:
            resolved = resolve_registry_path_from_config(registry_ref, workspace)
            if flow_registry_exists(resolved, DEFAULT_FLOW_ID):
                schema_bundle = resolved
            else:
                rel = flow_registry_path(resolved, DEFAULT_FLOW_ID).relative_to(resolved).as_posix()
                errors.append(
                    f"registry path does not resolve to a bundle with {rel}: {resolved}"
                )
        except ValueError as exc:
            errors.append(str(exc))

    if schema_bundle is None:
        try:
            schema_bundle = _schema_bundle_for_workspace(workspace)
        except FileNotFoundError as exc:
            errors.append(str(exc))
            return {"ok": False, "errors": errors, "flow": data.get("flow")}

    errors.extend(validate_payload(data, "foundry-config.schema.json", schema_bundle))
    if errors:
        return {"ok": False, "errors": errors, "flow": data.get("flow")}

    flow_id = data.get("flow") or DEFAULT_FLOW_ID
    try:
        document, flow = load_registry(schema_bundle, flow_id=flow_id)
        raw_flow = document.get("flow")
        ref_result = validate_registry_instruction_refs(
            flow,
            schema_bundle,
            raw_flow=raw_flow if isinstance(raw_flow, dict) else None,
        )
        if not ref_result.get("ok"):
            missing = ref_result.get("missing") or []
            if missing:
                errors.append(
                    f"{ref_result.get('code', 'REFERENCE_NOT_FOUND')}: "
                    f"{ref_result.get('message', 'missing registry refs')}: {', '.join(missing)}"
                )
            for item in ref_result.get("errors") or []:
                errors.append(f"NODE_CONTRACT_INVALID: {item}")
    except (FileNotFoundError, ValueError) as exc:
        errors.append(str(exc))

    if errors:
        return {"ok": False, "errors": errors, "flow": data.get("flow")}
    return ok(
        flow=data.get("flow") or DEFAULT_FLOW_ID,
        registry=str(resolve_registry_path_from_config(str(registry_ref), workspace)),
        errors=[],
    )


def resolve_registry_bundle(
    workspace: Path,
    explicit_registry: Path | None = None,
) -> tuple[Path, str]:
    workspace = workspace.resolve()

    if explicit_registry is not None:
        bundle = explicit_registry.resolve()
        _validate_registry_bundle(bundle)
        return bundle, "cli_flag"

    env_registry = os.environ.get("FOUNDRY_REGISTRY")
    if env_registry:
        bundle = Path(env_registry).resolve()
        _validate_registry_bundle(bundle)
        return bundle, "env"

    config_path = foundry_config_path(workspace)
    if config_path.is_file():
        _, data = load_foundry_config(workspace)
        registry_ref = data.get("registry")
        if not isinstance(registry_ref, str) or not registry_ref.strip():
            raise FileNotFoundError(
                f"Foundry config {config_path} is missing a non-empty registry field"
            )
        bundle = resolve_registry_path_from_config(registry_ref, workspace)
        _validate_registry_bundle(bundle)
        return bundle, "foundry.yaml"

    bundle = _find_workspace_bundle(workspace)
    if bundle is not None:
        return bundle, "workspace_bundle"

    raise FileNotFoundError(
        "Could not locate Foundry registry bundle. Add .foundry/foundry.yaml with a "
        "registry path, set FOUNDRY_REGISTRY, pass --registry, or run from a workspace "
        f"that contains .cursor/foundry/{flow_registry_display_path(DEFAULT_FLOW_ID)}. "
        "Run `foundry config init` to create foundry.yaml."
    )


def probe_sibling_registry(workspace: Path) -> str | None:
    try:
        candidate = resolve_registry_path_from_config(DEFAULT_REGISTRY_REF, workspace)
    except ValueError:
        return None
    if flow_registry_exists(candidate, DEFAULT_FLOW_ID):
        return DEFAULT_REGISTRY_REF
    return None


def _ordered_config(config: dict[str, Any]) -> dict[str, Any]:
    order = ("schema_version", "registry", "flow")
    return {key: config[key] for key in order if key in config}


def render_foundry_config(config: dict[str, Any]) -> str:
    return yaml.safe_dump(
        _ordered_config(config),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )


def init_foundry_config(
    workspace: Path,
    foundry_bundle: Path,
    *,
    registry_ref: str | None = None,
    flow: str | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    root = workspace.resolve()
    if not root.is_dir():
        raise ValueError(f"Workspace does not exist: {root}")

    resolved_registry_ref = registry_ref or probe_sibling_registry(root) or DEFAULT_REGISTRY_REF
    resolved_bundle = resolve_registry_path_from_config(resolved_registry_ref, root)
    _validate_registry_bundle(resolved_bundle)

    config: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "registry": resolved_registry_ref,
    }
    flow_id = flow or DEFAULT_FLOW_ID
    if flow_id != DEFAULT_FLOW_ID:
        config["flow"] = flow_id

    errors = validate_payload(config, "foundry-config.schema.json", foundry_bundle)
    if errors:
        raise ValueError("Foundry config validation failed: " + "; ".join(errors))

    target = foundry_config_path(root)
    rendered = render_foundry_config(config)
    target_existed = target.is_file()
    existing_same = False
    if target_existed:
        try:
            _, existing = load_foundry_config(root)
            existing_same = existing == config
        except (FileNotFoundError, ValueError):
            existing_same = False
        if not existing_same and not force and not dry_run:
            raise FileExistsError(f"Foundry config already exists: {target}")

    changed = not existing_same
    written = False
    if not dry_run and changed:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
        written = True

    validation = validate_foundry_config(root) if written or (target_existed and existing_same) else {
        "ok": True,
        "flow": flow_id,
        "errors": [],
    }

    return {
        "workspace": str(root),
        "foundry_config_path": str(target),
        "registry": resolved_registry_ref,
        "flow": flow_id,
        "dry_run": dry_run,
        "changed": changed,
        "written": written,
        "force": force,
        "requires_force": bool(target_existed and changed and not force),
        "rendered_config": rendered if dry_run else None,
        "validated": validation.get("ok") is True,
        "validation_errors": validation.get("errors") or [],
    }
