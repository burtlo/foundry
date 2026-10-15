"""Human-readable readiness output for ``foundry up``."""

from __future__ import annotations

import argparse
from typing import Any

_DIMENSION_LABELS: dict[str, str] = {
    "bridge": "judgment bridge",
    "host_process": "host process",
    "host_health": "host health",
    "adapter": "agent adapter",
}


def _section(result: dict[str, Any], key: str) -> dict[str, Any]:
    value = result.get(key)
    return value if isinstance(value, dict) else {}


def _failed_dimensions(result: dict[str, Any]) -> list[tuple[str, str]]:
    failures: list[tuple[str, str]] = []
    bridge = _section(result, "bridge")
    if not bridge.get("ok"):
        detail = str(bridge.get("detail") or "not reachable")
        failures.append((_DIMENSION_LABELS["bridge"], detail))

    host = _section(result, "host")
    process = host.get("process") if isinstance(host.get("process"), dict) else {}
    if not process.get("ok"):
        detail = str(process.get("detail") or "not running")
        failures.append((_DIMENSION_LABELS["host_process"], detail))

    health = host.get("health") if isinstance(host.get("health"), dict) else {}
    if not health.get("ok"):
        detail = str(health.get("detail") or "unhealthy")
        failures.append((_DIMENSION_LABELS["host_health"], detail))

    adapter = _section(result, "adapter")
    if not adapter.get("ok"):
        detail = str(adapter.get("detail") or "not ready")
        failures.append((_DIMENSION_LABELS["adapter"], detail))
    return failures


def _suggest_next_command(result: dict[str, Any], *, ready: bool) -> str:
    if ready:
        return "foundry shape"
    adapter = _section(result, "adapter")
    hint = adapter.get("recovery_hint")
    if isinstance(hint, str) and "foundry up" in hint.lower():
        return "foundry up"
    bridge = _section(result, "bridge")
    if not bridge.get("ok"):
        return "foundry up"
    host = _section(result, "host")
    process = host.get("process") if isinstance(host.get("process"), dict) else {}
    health = host.get("health") if isinstance(host.get("health"), dict) else {}
    if not process.get("ok") or not health.get("ok"):
        return "foundry up"
    if not adapter.get("ok"):
        return "foundry up"
    return "foundry up"


def _compact_detail_lines(result: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    workspace = result.get("workspace")
    if workspace:
        lines.append(f"workspace: {workspace}")

    bridge = _section(result, "bridge")
    url = bridge.get("url")
    if url:
        lines.append(f"bridge: {url}")

    host = _section(result, "host")
    process = host.get("process") if isinstance(host.get("process"), dict) else {}
    pid = process.get("pid")
    if pid:
        lines.append(f"host pid: {pid}")
    return lines


def _verbose_dimension_lines(result: dict[str, Any]) -> list[str]:
    bridge = _section(result, "bridge")
    host = _section(result, "host")
    process = host.get("process") if isinstance(host.get("process"), dict) else {}
    health = host.get("health") if isinstance(host.get("health"), dict) else {}
    adapter = _section(result, "adapter")
    return [
        f"bridge ok={bridge.get('ok')} url={bridge.get('url')} detail={bridge.get('detail')}",
        f"host process ok={process.get('ok')} pid={process.get('pid')} detail={process.get('detail')}",
        f"host health ok={health.get('ok')} detail={health.get('detail')}",
        (
            f"adapter ok={adapter.get('ok')} configured={adapter.get('configured')} "
            f"reachable={adapter.get('reachable')} detail={adapter.get('detail')}"
        ),
    ]


def format_up_human(args: argparse.Namespace, result: dict[str, Any]) -> None:
    """Print porcelain ``foundry up`` output for human operators."""
    ready = bool(result.get("ready"))
    verbose = bool(getattr(args, "verbose", False))

    if ready:
        print("Foundry is ready")
    else:
        print("Foundry is not ready")
        failures = _failed_dimensions(result)
        if failures:
            labels = ", ".join(label for label, _ in failures)
            print(f"Failed: {labels}")

    print(f"Next: {_suggest_next_command(result, ready=ready)}")

    for line in _compact_detail_lines(result):
        print(line)

    if verbose:
        for line in _verbose_dimension_lines(result):
            print(line)


def is_up_readiness_result(result: dict[str, Any]) -> bool:
    """True when ``result`` carries an ``up`` readiness payload for porcelain output."""
    return "bridge" in result and "host" in result and result.get("workspace") is not None


def format_down_human(_args: argparse.Namespace, result: dict[str, Any]) -> None:
    """Print porcelain ``foundry down`` output for human operators."""
    message = result.get("message")
    if isinstance(message, str) and message.strip():
        print(message)
    elif result.get("already_stopped"):
        print("Foundry is already stopped for this workspace.")
    else:
        print("Stopped host and judgment bridge for this workspace.")

    workspace = result.get("workspace")
    if workspace:
        print(f"workspace: {workspace}")

    print("Next: foundry up")
