"""Host client timeout policy: registry max and .foundry/host.yaml overrides."""

from __future__ import annotations

from pathlib import Path

import pytest

from foundry_cli.engine.agent.tasks import max_judgment_task_timeout_seconds
from foundry_cli.host.timeout_policy import client_timeout_for_run_advance
from tests.conftest import FOUNDRY_ROOT

BUNDLE = FOUNDRY_ROOT


def test_registry_max_judgment_timeout_is_verify_acceptance_limit() -> None:
    assert max_judgment_task_timeout_seconds(BUNDLE) == 300


def test_host_yaml_overrides_slack_and_judgment_max(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    foundry_dir = workspace / ".foundry"
    foundry_dir.mkdir(parents=True)
    (foundry_dir / "host.yaml").write_text(
        "schema_version: 1\n"
        "advance_client:\n"
        "  base_slack_seconds: 1\n"
        "  per_round_slack_seconds: 1\n"
        "  judgment_max_seconds: 2\n",
        encoding="utf-8",
    )
    timeout = client_timeout_for_run_advance(
        {"step_budget": 1},
        workspace=workspace,
        bundle=BUNDLE,
    )
    assert timeout == 4.0


def test_host_yaml_max_seconds_caps_computed_timeout(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    foundry_dir = workspace / ".foundry"
    foundry_dir.mkdir(parents=True)
    (foundry_dir / "host.yaml").write_text(
        "schema_version: 1\n"
        "advance_client:\n"
        "  max_seconds: 5\n",
        encoding="utf-8",
    )
    timeout = client_timeout_for_run_advance(
        {"step_budget": 8},
        workspace=workspace,
        bundle=BUNDLE,
    )
    assert timeout == 5.0


def test_env_judgment_max_overrides_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    monkeypatch.setenv("FOUNDRY_HOST_CLIENT_JUDGMENT_MAX_SECONDS", "4")
    monkeypatch.setenv("FOUNDRY_HOST_CLIENT_BASE_SLACK_SECONDS", "1")
    monkeypatch.setenv("FOUNDRY_HOST_CLIENT_PER_ROUND_SLACK_SECONDS", "1")
    timeout = client_timeout_for_run_advance(
        {"step_budget": 1},
        workspace=workspace,
        bundle=BUNDLE,
    )
    assert timeout == 6.0
