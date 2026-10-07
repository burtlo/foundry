"""Shared stub execute/verify environment for tests."""

from __future__ import annotations

import os

import pytest


def apply_passing_stub_execute_env() -> None:
    """Set process env for passing stub execute (Gherkin steps without monkeypatch)."""
    os.environ["FOUNDRY_EXECUTE_STUB"] = "1"
    os.environ.setdefault("FOUNDRY_VERIFY_ACCEPTANCE_DECISION", "pass")
    os.environ.pop("FOUNDRY_EXECUTE_TEST_EXIT_CODE", None)
    os.environ.pop("FOUNDRY_EXECUTE_BUILD_EXIT_CODE", None)
    os.environ.pop("FOUNDRY_EXECUTE_COMMIT_EXIT_CODE", None)
    os.environ.pop("FOUNDRY_EXECUTE_CODE_QUALITY_EXIT_CODE", None)


def configure_stub_execute_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_EXECUTE_STUB", "1")
    monkeypatch.setenv("FOUNDRY_VERIFY_ACCEPTANCE_DECISION", "pass")
    monkeypatch.delenv("FOUNDRY_EXECUTE_TEST_EXIT_CODE", raising=False)
    monkeypatch.delenv("FOUNDRY_EXECUTE_COMMIT_EXIT_CODE", raising=False)
    monkeypatch.delenv("FOUNDRY_EXECUTE_CODE_QUALITY_EXIT_CODE", raising=False)
