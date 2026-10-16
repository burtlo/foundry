"""Platform fixes for cursor-sdk bridge launch (Windows pipes + headless child)."""

from __future__ import annotations

import codecs
import os
import subprocess
import sys
import time
from collections.abc import Mapping
from typing import Any

from foundry_cli.detached_spawn import popen_kwargs_for_detached_child

_PATCHED = False


def read_discovery_polling(
    process: subprocess.Popen[str],
    timeout: float,
    *,
    parse_discovery_line: Any,
    error_type: type[BaseException],
) -> Mapping[str, Any]:
    """Read bridge discovery from stderr without ``selectors`` (Windows pipe-safe)."""
    if process.stderr is None:
        raise error_type("Bridge process stderr is unavailable")
    stderr_fd = process.stderr.fileno()
    was_blocking = os.get_blocking(stderr_fd)
    os.set_blocking(stderr_fd, False)

    try:
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        deadline = time.monotonic() + timeout
        stderr_lines: list[str] = []
        pending = ""

        def drain_available() -> Mapping[str, Any] | None:
            nonlocal pending
            while True:
                try:
                    chunk = os.read(stderr_fd, 8192)
                except BlockingIOError:
                    return None
                if not chunk:
                    final_text = decoder.decode(b"", final=True)
                    if final_text:
                        pending += final_text
                    if pending:
                        line = pending
                        pending = ""
                        stderr_lines.append(line)
                        return parse_discovery_line(line)
                    return None
                pending += decoder.decode(chunk)
                while "\n" in pending:
                    line, pending = pending.split("\n", 1)
                    line += "\n"
                    stderr_lines.append(line)
                    discovery = parse_discovery_line(line)
                    if discovery is not None:
                        return discovery
            return None

        while time.monotonic() < deadline:
            discovery = drain_available()
            if discovery is not None:
                return discovery
            exit_code = process.poll()
            if exit_code is not None:
                discovery = drain_available()
                if discovery is not None:
                    return discovery
                raise error_type(
                    f"Bridge exited before discovery with status {exit_code}: "
                    + "".join(stderr_lines)
                    + pending
                )
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
        raise error_type("Timed out waiting for bridge discovery")
    finally:
        os.set_blocking(stderr_fd, was_blocking)


def _wrap_bridge_popen(original: Any) -> Any:
    headless_kwargs = popen_kwargs_for_detached_child() if sys.platform == "win32" else {}

    def popen(*args: Any, **kwargs: Any) -> subprocess.Popen[Any]:
        if headless_kwargs:
            for key, value in headless_kwargs.items():
                kwargs.setdefault(key, value)
        return original(*args, **kwargs)

    return popen


def ensure_cursor_sdk_platform_compat() -> None:
    """Patch cursor-sdk bridge I/O for Windows (idempotent)."""
    global _PATCHED
    if _PATCHED:
        return
    try:
        import cursor_sdk._bridge as bridge_mod
    except ImportError:
        return

    from cursor_sdk.errors import CursorSDKError

    def _read_discovery(process: subprocess.Popen[str], timeout: float) -> Mapping[str, Any]:
        return read_discovery_polling(
            process,
            timeout,
            parse_discovery_line=bridge_mod.parse_discovery_line,
            error_type=CursorSDKError,
        )

    bridge_mod._read_discovery = _read_discovery
    bridge_mod.subprocess.Popen = _wrap_bridge_popen(bridge_mod.subprocess.Popen)
    _PATCHED = True
