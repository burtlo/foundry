"""Shared pytest configuration for the Foundry CLI test suite."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("FOUNDRY_ALLOW_STUB_ADAPTER", "1")
os.environ.setdefault("FOUNDRY_EXECUTE_STUB", "1")
os.environ.setdefault("FOUNDRY_VERIFY_ACCEPTANCE_DECISION", "pass")

CLI_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = CLI_DIR.parents[2]
FOUNDRY_ROOT = REPO_ROOT / ".cursor" / "foundry"
