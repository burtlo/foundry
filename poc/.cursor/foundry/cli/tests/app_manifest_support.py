"""Shared app-manifest fixtures for runtime tests."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

import foundry_app


def manifest_value(
    *,
    app_id: str = "test-app",
    builders: dict[str, Any] | None = None,
) -> dict[str, Any]:
    command = {
        "default": {
            "argv": [sys.executable, "-c", "print('foundry manifest command')"],
            "cwd": ".",
            "timeout_seconds": 30,
        }
    }
    return {
        "schema_version": 1,
        "id": app_id,
        "tags": ["test"],
        "commands": {
            "build": command,
            "test": command,
        },
        "verification": {
            "implementation": ["build", "test"],
            "post_repair": ["build", "test"],
        },
        "builders": builders
        if builders is not None
        else {
            "default_owner": "feature-builder",
            "routes": [],
        },
        "documentation": {
            "model": "feature-records",
            "config": {},
        },
    }


def routed_builders() -> dict[str, Any]:
    return {
        "default_owner": "feature-builder",
        "routes": [
            {
                "id": "client",
                "owner": "client-builder",
                "priority": 200,
                "globs": ["Client/**"],
            },
            {
                "id": "backend",
                "owner": "backend-builder",
                "priority": 100,
                "globs": ["**/*.cs", "internal/**"],
            },
        ],
    }


def write_app_manifest(
    app: Path,
    *,
    app_id: str = "test-app",
    manifest: dict[str, Any] | None = None,
    builders: dict[str, Any] | None = None,
) -> Path:
    target = app / ".foundry" / "app.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        manifest
        if manifest is not None
        else manifest_value(app_id=app_id, builders=builders)
    )
    target.write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )
    return target


def attach_run_manifest(
    state: dict[str, Any],
    app: Path,
    run_dir: Path,
    *,
    app_id: str = "test-app",
    builders: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not (app / ".foundry" / "app.yaml").is_file():
        write_app_manifest(app, app_id=app_id, manifest=manifest, builders=builders)
    context = foundry_app.validate_app_manifest(
        app,
        run_mode=str(state.get("run_mode") or "implementation"),
    )
    state["app_manifest_id"] = context["app_manifest_id"]
    state["app_manifest_hash"] = context["app_manifest_hash"]
    state["app_manifest_platform"] = context["platform"]
    foundry_app.write_run_manifest_snapshot(run_dir, context["manifest"])
    return state
