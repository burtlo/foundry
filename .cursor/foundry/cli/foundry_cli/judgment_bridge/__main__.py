"""Detached judgment bridge entrypoint (``python -m foundry_cli.judgment_bridge``)."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from foundry_cli.judgment_bridge.sdk_platform import ensure_cursor_sdk_platform_compat
from foundry_cli.judgment_bridge.server import DEFAULT_AGENT_PATH, serve_judgment_bridge


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="foundry_cli.judgment_bridge")
    parser.add_argument("--workspace", required=True, help="Application workspace root")
    parser.add_argument("--registry", required=True, help="Foundry bundle root")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8791)
    parser.add_argument("--path", default=DEFAULT_AGENT_PATH, help="Agent HTTP path")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=str(args.log_level).upper(),
        format="%(levelname)s %(name)s %(message)s",
    )
    ensure_cursor_sdk_platform_compat()

    serve_judgment_bridge(
        host=str(args.host),
        port=int(args.port),
        workspace=Path(args.workspace).resolve(),
        foundry_bundle=Path(args.registry).resolve(),
        agent_path=str(args.path),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
