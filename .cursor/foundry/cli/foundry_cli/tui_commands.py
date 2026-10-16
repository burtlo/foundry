"""CLI entry for ``foundry tui``."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from foundry_cli.user_cli import cmd_attach

_TUI_DEPRECATION = (
    "foundry tui is deprecated; use foundry attach (or foundry attach RUN) instead."
)


def cmd_tui(args: argparse.Namespace) -> dict[str, Any]:
    print(_TUI_DEPRECATION, file=sys.stderr)
    return cmd_attach(args)
