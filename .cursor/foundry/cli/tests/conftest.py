"""Shared pytest configuration for the Foundry CLI test suite."""

from __future__ import annotations

from pathlib import Path

CLI_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = CLI_DIR.parents[2]
FOUNDRY_ROOT = REPO_ROOT / ".cursor" / "foundry"

pytest_plugins = [
    "tests.acceptance.steps.run_context",
    "tests.acceptance.steps.catalog_build",
    "tests.acceptance.steps.doc_build",
    "tests.acceptance.steps.dev_commands",
    "tests.acceptance.steps.shape_intake",
    "tests.acceptance.steps.shape_examine",
]
