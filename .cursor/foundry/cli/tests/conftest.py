"""Shared pytest configuration for the Foundry CLI test suite."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("FOUNDRY_ALLOW_STUB_ADAPTER", "1")

CLI_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = CLI_DIR.parents[2]
FOUNDRY_ROOT = REPO_ROOT / ".cursor" / "foundry"

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
    "tests.acceptance.steps.execute_slice_2a",
    "tests.acceptance.steps.job_host",
    "tests.acceptance.steps.run_storage",
]
