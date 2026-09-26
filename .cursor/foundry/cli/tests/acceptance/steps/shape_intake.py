"""Step definitions for shape_intake.feature."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when

from tests.acceptance.helpers import collect_context_field_failures, invoke_foundry
from tests.conftest import FOUNDRY_ROOT

FIXTURE_APP = FOUNDRY_ROOT / "fixtures" / "apps" / "foundry-test" / ".foundry" / "app.yaml"


@given(parsers.parse('the foundry registry flow "{flow_id}"'))
def registry_flow(acceptance, flow_id: str) -> None:
    acceptance["flow_id"] = flow_id


@given("a temporary workspace with valid app manifest")
def temp_workspace_with_manifest(acceptance, tmp_path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir(parents=True)
    dest = workspace / ".foundry"
    dest.mkdir(parents=True)
    shutil.copy2(FIXTURE_APP, dest / "app.yaml")
    acceptance["workspace"] = workspace
    acceptance["fixture_name"] = None
    acceptance["run_id"] = None


@given("a temporary workspace without app manifest")
def temp_workspace_without_manifest(acceptance, tmp_path) -> None:
    workspace = tmp_path / "bare"
    workspace.mkdir(parents=True)
    acceptance["workspace"] = workspace
    acceptance["fixture_name"] = None
    acceptance["run_id"] = None


@given(parsers.parse('run fixture "{fixture_name}"'))
def run_fixture(acceptance, fixture_name: str, repo_root) -> None:
    acceptance["fixture_name"] = fixture_name
    acceptance["run_id"] = None
    acceptance["workspace"] = repo_root


@when(parsers.parse('I invoke "{command}" with json output'))
def invoke_with_json(acceptance, command: str) -> None:
    acceptance["command"] = command
    acceptance["json_output"] = True
    acceptance["markdown_output"] = False
    acceptance["extra_argv"] = []
    invoke_foundry(acceptance)


@when(parsers.parse('I invoke "{command}" with json output and set \'{patch}\''))
def invoke_patch(acceptance, command: str, patch: str) -> None:
    acceptance["command"] = command
    acceptance["json_output"] = True
    acceptance["extra_argv"] = ["--set", patch]
    invoke_foundry(acceptance)


@when(parsers.parse('I invoke "{command}" with json output and summary "{summary}"'))
def invoke_transition(acceptance, command: str, summary: str) -> None:
    acceptance["command"] = command
    acceptance["json_output"] = True
    acceptance["extra_argv"] = ["--summary", summary]
    invoke_foundry(acceptance)


@when(parsers.parse('I invoke "{command}" with json output and types "{types}"'))
def invoke_ledger_types(acceptance, command: str, types: str) -> None:
    acceptance["command"] = command
    acceptance["json_output"] = True
    acceptance["extra_argv"] = ["--types", types]
    invoke_foundry(acceptance)


@when(
    parsers.parse(
        'I invoke "{command}" with json output and artifact "{artifact}" from "{source}"'
    )
)
def invoke_artifact_publish(acceptance, command: str, artifact: str, source: str) -> None:
    acceptance["command"] = command
    acceptance["json_output"] = True
    acceptance["extra_argv"] = ["--artifact", artifact, "--source", source]
    invoke_foundry(acceptance)


@when(
    parsers.parse(
        'I invoke "{command}" with json output schema "{schema}" file "{file_path}"'
    )
)
def invoke_receipt_seal(acceptance, command: str, schema: str, file_path: str) -> None:
    acceptance["command"] = command
    acceptance["json_output"] = True
    acceptance["extra_argv"] = ["--schema", schema, "--file", file_path]
    invoke_foundry(acceptance)


@then(parsers.parse("the CLI exit code is {exit_code:d}"))
def assert_exit_code(acceptance, exit_code: int) -> None:
    assert acceptance["exit_code"] == exit_code, acceptance.get("stderr") or acceptance.get("stdout")


@then(parsers.parse("response ok is {value}"))
def assert_response_ok(acceptance, value: str) -> None:
    expected = value.lower() == "true"
    payload = acceptance["payload"]
    assert payload is not None
    assert payload.get("ok") is expected, payload


@then(parsers.parse('response field "{field_path}" equals "{expected}"'))
def assert_response_field_equals(acceptance, field_path: str, expected: str) -> None:
    from tests.acceptance.helpers import resolve_json_path

    payload = acceptance["payload"]
    assert payload is not None
    actual = resolve_json_path(payload, field_path)
    assert str(actual) == expected, f"{field_path}: expected {expected!r}, got {actual!r}"


@then(parsers.parse('response error code equals "{code}"'))
def assert_error_code(acceptance, code: str) -> None:
    payload = acceptance["payload"]
    assert payload is not None
    assert payload.get("error", {}).get("code") == code


@then(parsers.parse('response field "{field_path}" exists as directory'))
def assert_response_field_is_dir(acceptance, field_path: str) -> None:
    from tests.acceptance.helpers import resolve_json_path

    payload = acceptance["payload"]
    assert payload is not None
    path = Path(str(resolve_json_path(payload, field_path)))
    assert path.is_dir(), f"expected directory at {path}"


@then(parsers.parse('I store run id from response field "{field_path}"'))
def store_run_id(acceptance, field_path: str) -> None:
    from tests.acceptance.helpers import resolve_json_path

    payload = acceptance["payload"]
    assert payload is not None
    acceptance["run_id"] = str(resolve_json_path(payload, field_path))
    acceptance["fixture_name"] = None


@then("I write ticket draft to the run directory")
def write_ticket_draft(acceptance) -> None:
    run_dir = _run_dir(acceptance)
    ticket = {
        "schema_version": "2.2.0",
        "raw_input": "Add shape intake vertical slice",
        "normalized_translation": "Implement shape.intake CLI commands and engine hooks.",
        "source_type": "chat",
        "source_ref": None,
        "issue_key": None,
    }
    path = run_dir / "ticket.json"
    path.write_text(json.dumps(ticket, indent=2) + "\n", encoding="utf-8")


@then("I write receipt drafts to the run directory")
def write_receipt_drafts(acceptance) -> None:
    run_dir = _run_dir(acceptance)
    receipts_dir = run_dir / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    intake = {
        "schema_version": "2.2.0",
        "step_id": "shape.intake",
        "status": "passed",
        "checks": [{"id": "validate-manifest", "status": "pass", "summary": "Manifest valid"}],
        "agent_assessment": {"summary_markdown": "Proceed"},
    }
    agent = {
        "schema_version": "2.2.0",
        "agent": {"name": "intake-checker.shape", "mode": "shape"},
        "status": "completed",
        "recommended_next_state": "shape.examine",
        "outputs": {"summary_markdown": "Ticket fields proposed."},
    }
    (receipts_dir / "intake.json").write_text(json.dumps(intake, indent=2) + "\n", encoding="utf-8")
    (receipts_dir / "agent.json").write_text(json.dumps(agent, indent=2) + "\n", encoding="utf-8")


@then("context fields match:")
def assert_context_fields(acceptance, datatable) -> None:
    context = acceptance["payload"]["context"]
    failures = collect_context_field_failures(context, datatable)
    if failures:
        message = "context field expectation failures:\n" + "\n".join(f"  - {item}" for item in failures)
        pytest.fail(message)


@given("I record ledger event count")
def record_ledger_count(acceptance) -> None:
    from tests.acceptance.helpers import FIXTURES_ROOT

    if acceptance.get("fixture_name"):
        snapshot_path = FIXTURES_ROOT / str(acceptance["fixture_name"]) / "snapshot.json"
    else:
        snapshot_path = _run_dir(acceptance) / "snapshot.json"
    ledger = json.loads(snapshot_path.read_text(encoding="utf-8")).get("ledger") or []
    acceptance["ledger_count_before"] = len(ledger)


@then(parsers.parse('the run snapshot has no ledger event type "{event_type}"'))
def assert_no_ledger_event_type(acceptance, event_type: str) -> None:
    snapshot_path = _snapshot_path(acceptance)
    ledger = json.loads(snapshot_path.read_text(encoding="utf-8")).get("ledger") or []
    matches = [event for event in ledger if isinstance(event, dict) and event.get("type") == event_type]
    assert not matches, f"expected no {event_type!r} events, found {len(matches)}"


@then("ledger event count is unchanged")
def assert_ledger_unchanged(acceptance) -> None:
    from tests.acceptance.helpers import FIXTURES_ROOT

    if acceptance.get("fixture_name"):
        snapshot_path = FIXTURES_ROOT / str(acceptance["fixture_name"]) / "snapshot.json"
    else:
        snapshot_path = _run_dir(acceptance) / "snapshot.json"
    ledger = json.loads(snapshot_path.read_text(encoding="utf-8")).get("ledger") or []
    assert len(ledger) == acceptance.get("ledger_count_before")


def _run_dir(acceptance) -> Path:
    workspace = Path(acceptance["workspace"])
    run_id = acceptance.get("run_id")
    assert run_id, "run_id not set in acceptance state"
    return workspace / ".foundry" / "runs" / str(run_id)


def _snapshot_path(acceptance) -> Path:
    from tests.acceptance.helpers import FIXTURES_ROOT

    if acceptance.get("fixture_name"):
        return FIXTURES_ROOT / str(acceptance["fixture_name"]) / "snapshot.json"
    return _run_dir(acceptance) / "snapshot.json"
