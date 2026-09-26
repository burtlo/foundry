"""Shared bootstrap context for CLI command handlers."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from foundry_cli.errors import error
from foundry_cli.foundry_config import foundry_config_path, resolve_registry_bundle
from foundry_cli.registry import load_registry
from foundry_cli.run_store import RunStoreError, load_snapshot, resolve_run_dir, select_visit


@dataclass
class CommandContext:
    workspace: Path
    bundle: Path
    registry_source: str | None = None
    foundry_config_path: Path | None = None

    @classmethod
    def from_args(
        cls,
        args: argparse.Namespace,
        *,
        require_registry: bool = True,
    ) -> CommandContext | dict[str, Any]:
        workspace = Path(args.workspace).resolve()
        if not require_registry:
            return cls(workspace=workspace, bundle=workspace)

        explicit_registry = Path(args.registry).resolve() if args.registry else None
        try:
            bundle, registry_source = resolve_registry_bundle(
                workspace,
                explicit_registry=explicit_registry,
            )
        except FileNotFoundError as exc:
            return error("REGISTRY_NOT_FOUND", str(exc))

        config_path = foundry_config_path(workspace)
        return cls(
            workspace=workspace,
            bundle=bundle,
            registry_source=registry_source,
            foundry_config_path=config_path if config_path.is_file() else None,
        )

    def load_run(
        self,
        args: argparse.Namespace,
    ) -> dict[str, Any] | tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
        try:
            run_dir = resolve_run_dir(
                run_id=getattr(args, "run", None),
                run_dir=Path(args.run_dir).resolve() if getattr(args, "run_dir", None) else None,
                workspace=self.workspace,
            )
            snapshot = load_snapshot(run_dir)
            visit = select_visit(snapshot, getattr(args, "visit", None))
            flow_id = getattr(args, "flow", None) or str(snapshot.get("flow_id") or "implementation")
            _, flow = load_registry(self.bundle, flow_id=flow_id)
            return run_dir, snapshot, visit, flow
        except RunStoreError as exc:
            return error(exc.code, exc.message)
        except (FileNotFoundError, ValueError, KeyError) as exc:
            return error("INVALID_REQUEST", str(exc))
