"""Acceptance: stub execute/verify run completes at deliver.stub with handoff."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.acceptance.deliver_stub_handoff_helpers import assert_full_path_reaches_deliver_stub_with_handoff
from tests.unit.stub_execute_env import configure_stub_execute_commands


@pytest.fixture(autouse=True)
def _stub_execute_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_stub_execute_commands(monkeypatch)


def test_full_path_reaches_deliver_stub_with_handoff(tmp_path: Path) -> None:
    assert_full_path_reaches_deliver_stub_with_handoff(tmp_path)
