"""`foundry bridge` commands."""

from __future__ import annotations

import argparse
import logging
from typing import Any

from foundry_cli.command_context import CommandContext
from foundry_cli.errors import error, ok
from foundry_cli.judgment_bridge.server import DEFAULT_AGENT_PATH, serve_judgment_bridge


def cmd_bridge_start(args: argparse.Namespace) -> dict[str, Any]:
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx

    host = str(getattr(args, "host", None) or "127.0.0.1")
    port = int(getattr(args, "port", None) or 8791)
    agent_path = str(getattr(args, "path", None) or DEFAULT_AGENT_PATH)

    log_level = str(getattr(args, "log_level", None) or "INFO").upper()
    logging.basicConfig(level=log_level, format="%(levelname)s %(name)s %(message)s")

    try:
        from foundry_cli.judgment_bridge.keys import resolve_cursor_api_key

        resolve_cursor_api_key()
    except RuntimeError as exc:
        return error("CONFIGURATION_ERROR", str(exc))

    serve_judgment_bridge(
        host=host,
        port=port,
        workspace=ctx.workspace,
        foundry_bundle=ctx.bundle,
        agent_path=agent_path,
    )
    return ok(stopped=True)
