"""Human porcelain output for ``foundry up``."""

from __future__ import annotations

import argparse

import pytest

from foundry import _format_result
from foundry_cli.readiness.formatting import format_up_human


def _ready_result() -> dict:
    return {
        "ok": True,
        "ready": True,
        "workspace": "/tmp/app",
        "bridge": {"ok": True, "url": "http://127.0.0.1:18791/v1/agent"},
        "host": {
            "process": {"ok": True, "pid": 5252},
            "health": {"ok": True, "detail": "health RPC ok"},
        },
        "adapter": {"ok": True, "configured": True, "reachable": True},
    }


def test_format_up_human_ready_default(capsys: pytest.CaptureFixture[str]) -> None:
    args = argparse.Namespace(verbose=False)
    format_up_human(args, _ready_result())
    out = capsys.readouterr().out
    assert out.startswith("Foundry is ready\n")
    assert "Next: foundry shape" in out
    assert "bridge: http://127.0.0.1:18791/v1/agent" in out
    assert "host pid: 5252" in out
    assert "ok=True" not in out


def test_format_up_human_verbose_includes_dimensions(capsys: pytest.CaptureFixture[str]) -> None:
    args = argparse.Namespace(verbose=True)
    format_up_human(args, _ready_result())
    out = capsys.readouterr().out
    assert "bridge ok=True" in out
    assert "host process ok=True" in out
    assert "adapter ok=True" in out


def test_format_up_human_not_ready(capsys: pytest.CaptureFixture[str]) -> None:
    payload = _ready_result()
    payload["ok"] = False
    payload["ready"] = False
    payload["bridge"] = {"ok": False, "detail": "connection refused"}
    payload["error"] = {
        "code": "READINESS_INCOMPLETE",
        "message": "One or more readiness dimensions are not ready",
    }
    args = argparse.Namespace(verbose=False)
    format_up_human(args, payload)
    out = capsys.readouterr().out
    assert out.startswith("Foundry is not ready\n")
    assert "Failed: judgment bridge" in out
    assert "Next: foundry up" in out
    assert "ok=False" not in out


def test_format_result_up_not_ready_on_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    payload = _ready_result()
    payload["ok"] = False
    payload["ready"] = False
    payload["bridge"] = {"ok": False, "url": None, "detail": "down"}
    payload["error"] = {
        "code": "READINESS_INCOMPLETE",
        "message": "One or more readiness dimensions are not ready",
    }
    args = argparse.Namespace(command="up", json=False, verbose=False)
    _format_result(args, payload)
    captured = capsys.readouterr()
    assert captured.out.startswith("Foundry is not ready\n")
    assert captured.err == ""
