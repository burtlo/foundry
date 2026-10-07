"""Shared execute-phase workspace and stub env steps for acceptance scenarios."""

from __future__ import annotations

from pathlib import Path

from pytest_bdd import given, then

from tests.acceptance.acceptance_flow_helpers import ensure_execute_workspace_manifest_and_clean_git
from tests.unit.stub_execute_env import apply_passing_stub_execute_env


def _prepare_execute_workspace(acceptance) -> None:
    ensure_execute_workspace_manifest_and_clean_git(Path(acceptance["workspace"]))


@given("execute workspace has app manifest and clean git")
def execute_workspace_ready_given(acceptance) -> None:
    _prepare_execute_workspace(acceptance)


@then("execute workspace has app manifest and clean git")
def execute_workspace_ready_then(acceptance) -> None:
    _prepare_execute_workspace(acceptance)


@given("execute stub verification passes")
def execute_stub_verification_passes() -> None:
    apply_passing_stub_execute_env()
