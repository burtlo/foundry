"""Operator integration smoke (bridge mock + host + shape path)."""

from __future__ import annotations

from pathlib import Path

import pytest

from foundry_cli.operator_integration_smoke import run_operator_integration_smoke
from tests.conftest import FOUNDRY_ROOT

pytestmark = pytest.mark.xdist_group(name="operator_integration_smoke")

BUNDLE = FOUNDRY_ROOT


def test_operator_integration_smoke_reaches_present_gate(tmp_path: Path) -> None:
    result = run_operator_integration_smoke(
        workspace=None,
        bundle=BUNDLE,
        mock_judgment=True,
        use_auto_advance=True,
    )
    assert result.get("ok") is True
    assert result.get("active_node_id") == "shape.present.gate"
    assert result.get("wait_kind") == "decision"
    assert result.get("mock_judgment") is True
    assert result.get("auto_advance") is True
