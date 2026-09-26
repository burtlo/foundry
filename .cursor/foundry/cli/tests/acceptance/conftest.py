"""pytest fixtures for Gherkin acceptance scenarios."""

from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import FOUNDRY_ROOT, REPO_ROOT


@pytest.fixture
def repo_root():
    return REPO_ROOT


@pytest.fixture
def foundry_root():
    return FOUNDRY_ROOT


@pytest.fixture
def acceptance() -> dict[str, Any]:
    """Mutable state shared across steps in one scenario."""
    return {
        "flow_id": "implementation",
        "workspace": REPO_ROOT,
        "registry": FOUNDRY_ROOT,
        "fixture_name": None,
        "run_id": None,
        "extra_argv": [],
        "command": None,
        "exit_code": None,
        "stdout": "",
        "stderr": "",
        "payload": None,
        "ledger_before": None,
    }
