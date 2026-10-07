"""CLI entry for ``foundry tui``."""

from __future__ import annotations

import argparse
from typing import Any

from foundry_cli.command_context import CommandContext
from foundry_cli.errors import error, ok


def cmd_tui(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    try:
        from foundry_cli.tui import run_tui
    except ImportError as exc:
        return error(
            "TUI_DEPENDENCY_MISSING",
            "Textual is required for foundry tui. Install with: pip install textual",
            detail=str(exc),
        )

    run_tui(
        workspace=ctx.workspace,
        registry=getattr(args, "registry", None),
        run_id=getattr(args, "run", None),
    )
    return ok(launched=True)
