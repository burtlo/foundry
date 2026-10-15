"""``foundry help`` — curriculum index, full list, and per-command help."""

from __future__ import annotations

import argparse
from typing import Any

from foundry_cli.errors import error, ok
from foundry_cli.help_catalog import (
    format_all_commands_help,
    format_curriculum_help,
    top_level_subparsers,
)
from foundry_cli.parser import build_parser


def cmd_help(args: argparse.Namespace) -> dict[str, Any]:
    root = build_parser()
    if getattr(args, "help_command", None):
        subparsers = top_level_subparsers(root)
        name = str(args.help_command)
        subparser = subparsers.get(name)
        if subparser is None:
            return error("UNKNOWN_COMMAND", f"unknown command '{name}'")
        return ok(help_text=subparser.format_help())
    if getattr(args, "help_all", False):
        return ok(help_text=format_all_commands_help(root))
    return ok(help_text=format_curriculum_help(root))
