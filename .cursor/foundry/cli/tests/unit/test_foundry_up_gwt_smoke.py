"""P4 GWT smoke: ``foundry up`` then shape reaches judgment (mocked bridge)."""

from __future__ import annotations

from pathlib import Path

import pytest

from foundry_cli.operator_integration_smoke import run_foundry_up_gwt_smoke
from tests.conftest import FOUNDRY_ROOT

pytestmark = pytest.mark.xdist_group(name="foundry_up_gwt_smoke")

BUNDLE = FOUNDRY_ROOT


def test_foundry_up_gwt_smoke_reaches_judgment_gate() -> None:
    result = run_foundry_up_gwt_smoke(
        workspace=None,
        bundle=BUNDLE,
        mock_judgment=True,
    )
    assert result.get("ok") is True
    assert result.get("active_node_id") == "shape.present.gate"
    assert result.get("wait_kind") == "decision"
    assert result.get("mock_judgment") is True
    assert Path(str(result.get("shape_input") or "")).as_posix() == "docs/plans/foundry-up.md"
    assert result.get("up_ready") is True
