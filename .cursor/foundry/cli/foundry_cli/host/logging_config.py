"""Configure process logging for the job host."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from foundry_cli.host.discovery import restrict_host_dir_permissions
from foundry_cli.host.paths import host_dir, host_log_path

_HOST_LOGGER_NAME = "foundry_cli"


def configure_host_logging(workspace: Path, *, level: str | None = None) -> Path:
    """Send host log records to ``.foundry/host/host.log`` and stderr."""
    workspace = workspace.resolve()
    restrict_host_dir_permissions(host_dir(workspace))
    log_path = host_log_path(workspace)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    resolved_level = (level or os.environ.get("FOUNDRY_HOST_LOG_LEVEL") or "INFO").upper()
    numeric = getattr(logging, resolved_level, logging.INFO)

    logger = logging.getLogger(_HOST_LOGGER_NAME)
    logger.setLevel(numeric)
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    for handler in list(logger.handlers):
        if isinstance(handler, logging.FileHandler):
            logger.removeHandler(handler)
            handler.close()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(numeric)
    logger.addHandler(file_handler)

    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(numeric)
        logger.addHandler(stream_handler)

    logging.getLogger("foundry_cli.host").info(
        "Host logging configured path=%s level=%s",
        log_path,
        resolved_level,
    )
    return log_path
