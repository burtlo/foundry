"""cursor-sdk bridge platform compatibility."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap

import pytest

from foundry_cli.judgment_bridge.sdk_platform import ensure_cursor_sdk_platform_compat


def test_ensure_cursor_sdk_platform_compat_patches_bridge_module() -> None:
    pytest.importorskip("cursor_sdk")
    ensure_cursor_sdk_platform_compat()
    import cursor_sdk._bridge as bridge_mod

    assert bridge_mod._read_discovery.__name__ == "_read_discovery"
    assert bridge_mod.subprocess.Popen.__name__ == "popen"


@pytest.mark.skipif(sys.platform != "win32", reason="WinError 10038 reproduces on Windows selectors")
def test_read_discovery_polling_reads_bridge_ready_line() -> None:
    pytest.importorskip("cursor_sdk")
    from cursor_sdk._bridge import parse_discovery_line
    from cursor_sdk.errors import CursorSDKError

    from foundry_cli.judgment_bridge.sdk_platform import read_discovery_polling

    payload = {
        "schemaVersion": 1,
        "transport": "tcp",
        "protocol": "connect",
        "url": "http://127.0.0.1:59999",
        "authToken": "token",
    }
    line = f"cursor-sdk-bridge ready {json.dumps(payload)}\n"
    script = textwrap.dedent(
        f"""
        import sys, time
        sys.stderr.write({line!r})
        sys.stderr.flush()
        time.sleep(2)
        """
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        discovery = read_discovery_polling(
            proc,
            5.0,
            parse_discovery_line=parse_discovery_line,
            error_type=CursorSDKError,
        )
    finally:
        proc.kill()
        proc.wait(timeout=5)
    assert discovery.get("url") == payload["url"]
    assert discovery.get("authToken") == payload["authToken"]
