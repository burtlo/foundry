"""pytest fixtures for Gherkin acceptance scenarios."""

from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import FOUNDRY_ROOT, REPO_ROOT

pytest_plugins = [
    "tests.acceptance.steps.common",
    "tests.acceptance.steps.run_context",
    "tests.acceptance.steps.catalog_build",
    "tests.acceptance.steps.doc_build",
    "tests.acceptance.steps.dev_commands",
    "tests.acceptance.steps.shape_intake",
    "tests.acceptance.steps.shape_examine",
    "tests.acceptance.steps.shape_examine_gate",
    "tests.acceptance.steps.shape_present",
    "tests.acceptance.steps.shape_present_gate",
    "tests.acceptance.steps.shape_record",
    "tests.acceptance.steps.shape_record_gate",
    "tests.acceptance.steps.shape_phase_e2e",
    "tests.acceptance.steps.app_bootstrap",
    "tests.acceptance.steps.foundry_config",
    "tests.acceptance.steps.run_archive",
    "tests.acceptance.steps.user_cli",
    "tests.acceptance.steps.execute_workspace",
    "tests.acceptance.steps.execute_plan",
    "tests.acceptance.steps.job_host",
    "tests.acceptance.steps.run_storage",
]


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
