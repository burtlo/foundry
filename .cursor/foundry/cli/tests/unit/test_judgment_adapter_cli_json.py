"""CLI JSON envelope when judgment adapter dispatch fails."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import foundry as foundry_module

from foundry_cli.judgment_bridge.diagnostics import JudgmentAdapterFailure
from foundry_cli.run_service import advance_run_durable
from foundry_cli.run_store import get_revision, save_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.shape_flow_helpers import intake_open_run, shape_test_workspace

BUNDLE = FOUNDRY_ROOT

JUDGMENT_ADAPTER_FAILED_ENVELOPE: dict[str, Any] = {
    "ok": False,
    "error": {
        "code": "JUDGMENT_ADAPTER_FAILED",
        "message": "Agent HTTP adapter (provider) failed HTTP 502: validation failed.",
    },
    "diagnostics": {
        "layer": "provider",
        "recovery_hint": "Fix judgment task output schema",
        "upstream_status": 502,
    },
    "upstream_status": 502,
}


class _FailingJudgmentAdapter:
    def invoke(self, _request: dict[str, Any]) -> None:
        raise JudgmentAdapterFailure(
            "Agent HTTP adapter (provider) failed HTTP 502: validation failed. "
            "Fix judgment task output schema (upstream_status=502)",
            diagnostics={
                "layer": "provider",
                "recovery_hint": "Fix judgment task output schema",
                "upstream_status": 502,
            },
            http_status=502,
        )


def test_advance_run_durable_returns_structured_judgment_adapter_error(tmp_path: Path) -> None:
    workspace = shape_test_workspace(tmp_path)
    run_dir, snapshot, _flow = intake_open_run(workspace, work_prompt="Adapter failure path")
    save_snapshot(run_dir, snapshot)

    outcome = advance_run_durable(
        workspace=workspace,
        bundle=BUNDLE,
        run_dir=run_dir,
        expected_revision=get_revision(snapshot),
        agent_adapter=_FailingJudgmentAdapter(),
    )

    assert outcome["ok"] is False
    assert outcome["error"]["code"] == "JUDGMENT_ADAPTER_FAILED"
    assert "502" in outcome["error"]["message"]
    # Envelope: diagnostics nested; upstream_status duplicated at top level for CLI consumers.
    diagnostics = outcome["diagnostics"]
    assert diagnostics["layer"] == "provider"
    assert diagnostics["recovery_hint"] == "Fix judgment task output schema"
    assert diagnostics["upstream_status"] == 502
    assert outcome["upstream_status"] == 502


def test_foundry_run_advance_json_emits_diagnostics(tmp_path: Path, capsys) -> None:
    workspace = shape_test_workspace(tmp_path)
    run_dir, snapshot, _flow = intake_open_run(workspace, work_prompt="Adapter failure path")
    save_snapshot(run_dir, snapshot)

    argv_base = [
        "--workspace",
        str(workspace),
        "--registry",
        str(BUNDLE),
        "run",
        "advance",
        "--local",
        "--run-dir",
        str(run_dir),
    ]

    with patch(
        "foundry_cli.commands.advance_run_durable",
        return_value=JUDGMENT_ADAPTER_FAILED_ENVELOPE,
    ):
        assert foundry_module.main(["--json", *argv_base]) == 1
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "JUDGMENT_ADAPTER_FAILED"
    assert payload["diagnostics"]["layer"] == "provider"
    assert payload["diagnostics"]["recovery_hint"] == "Fix judgment task output schema"
    assert payload["upstream_status"] == 502

    with patch(
        "foundry_cli.commands.advance_run_durable",
        return_value=JUDGMENT_ADAPTER_FAILED_ENVELOPE,
    ):
        assert foundry_module.main(argv_base) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "judgment layer=provider" in captured.err
    assert "recovery: Fix judgment task output schema" in captured.err
