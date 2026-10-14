"""Unit tests for host status latency probe cap logic (fixture baselines)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_CLI_DIR = Path(__file__).resolve().parents[2]
_PROBE_PATH = _CLI_DIR / "scripts" / "probe_host_status_latency.py"


def _load_probe_module():
    spec = importlib.util.spec_from_file_location("probe_host_status_latency", _PROBE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(name="probe")
def probe_fixture():
    return _load_probe_module()


@pytest.mark.parametrize(
    ("scenario", "elapsed", "expect_exit"),
    [
        ("absent", 0.05, 0),
        ("ready", 0.12, 0),
        ("stale", 0.20, 0),
        ("absent", 3.5, 1),
        ("ready", 6.0, 1),
        ("stale", 9.0, 1),
    ],
)
def test_probe_cap_ok_fail(
    probe,
    tmp_path: Path,
    scenario: str,
    elapsed: float,
    expect_exit: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(probe, "_run_status", lambda _workspace, _registry: (elapsed, 0))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "probe_host_status_latency.py",
            "--workspace",
            str(tmp_path),
            "--scenario",
            scenario,
        ],
    )
    assert probe.main() == expect_exit
