"""Shared step definitions used across acceptance features."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when

from foundry_cli.validate import validate_payload
from tests.acceptance.constants import FIXTURE_APP
from tests.acceptance.helpers import (
    FIXTURES_ROOT,
    collect_context_field_failures,
    invoke_foundry,
    load_snapshot,
    resolve_json_path,
)


@given(parsers.parse('the foundry registry flow "{flow_id}"'))
def registry_flow(acceptance, flow_id: str) -> None:
    acceptance["flow_id"] = flow_id


@given("workspace is the repository root")
def workspace_root(acceptance, repo_root) -> None:
    acceptance["workspace"] = repo_root


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


@given(parsers.parse('run fixture "{fixture_name}" in temporary workspace'))
def run_fixture_in_temp_workspace(acceptance, fixture_name: str, tmp_path) -> None:
    src = FIXTURES_ROOT / fixture_name
    snapshot = json.loads((src / "snapshot.json").read_text(encoding="utf-8"))
    run_id = str(snapshot.get("run_id") or fixture_name)
    dest = tmp_path / ".foundry" / "runs" / run_id
    shutil.copytree(src, dest)
    acceptance["workspace"] = tmp_path
    acceptance["run_id"] = run_id
    acceptance["fixture_name"] = None


def _reset_invoke_argv(acceptance) -> None:
    acceptance["extra_argv"] = []
    acceptance["extra_flags"] = []


@when(parsers.parse('I invoke "{command}" with json output'))
def invoke_with_json(acceptance, command: str) -> None:
    acceptance["command"] = command
    acceptance["json_output"] = True
    acceptance["markdown_output"] = False
    _reset_invoke_argv(acceptance)
    invoke_foundry(acceptance)


@when(parsers.parse('I invoke "{command}" with markdown output'))
def invoke_with_markdown(acceptance, command: str) -> None:
    acceptance["command"] = command
    acceptance["markdown_output"] = True
    acceptance["json_output"] = False
    _reset_invoke_argv(acceptance)
    invoke_foundry(acceptance)


@when(parsers.parse('I invoke "{command}" with json output and flag "{flag}"'))
def invoke_with_json_and_flag(acceptance, command: str, flag: str) -> None:
    acceptance["command"] = command
    acceptance["json_output"] = True
    acceptance["markdown_output"] = False
    acceptance["extra_argv"] = []
    acceptance["extra_flags"] = [flag]
    invoke_foundry(acceptance)


@when(parsers.parse('I invoke "{command}" with json output and flags "{flags}"'))
def invoke_with_json_and_flags(acceptance, command: str, flags: str) -> None:
    acceptance["command"] = command
    acceptance["json_output"] = True
    acceptance["markdown_output"] = False
    acceptance["extra_argv"] = []
    acceptance["extra_flags"] = flags.split()
    invoke_foundry(acceptance)


@when(parsers.parse('I invoke "{command}" with run id "{run_id}" and json output'))
def invoke_with_run_id(acceptance, command: str, run_id: str) -> None:
    acceptance["command"] = command
    acceptance["run_id"] = run_id
    acceptance["fixture_name"] = None
    acceptance["json_output"] = True
    acceptance["markdown_output"] = False
    _reset_invoke_argv(acceptance)
    invoke_foundry(acceptance)


@when(parsers.parse('I invoke "gate decide" with json output and decision "{decision}"'))
def invoke_gate_decide(acceptance, decision: str) -> None:
    acceptance["command"] = "gate decide"
    acceptance["json_output"] = True
    acceptance["extra_argv"] = ["--decision", decision]
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
    payload = acceptance["payload"]
    assert payload is not None
    actual = resolve_json_path(payload, field_path)
    assert str(actual) == expected, f"{field_path}: expected {expected!r}, got {actual!r}"


@then(parsers.parse('response field "{field_path}" exists as directory'))
def assert_response_field_is_dir(acceptance, field_path: str) -> None:
    payload = acceptance["payload"]
    assert payload is not None
    path = Path(str(resolve_json_path(payload, field_path)))
    assert path.is_dir(), f"expected directory at {path}"


@then(parsers.parse('response error code equals "{code}"'))
def assert_error_code(acceptance, code: str) -> None:
    payload = acceptance["payload"]
    assert payload is not None
    assert payload.get("error", {}).get("code") == code


@then(parsers.parse('I store run id from response field "{field_path}"'))
def store_run_id(acceptance, field_path: str) -> None:
    payload = acceptance["payload"]
    assert payload is not None
    acceptance["run_id"] = str(resolve_json_path(payload, field_path))
    acceptance["fixture_name"] = None


@then(parsers.parse('context validates against schema "{schema_name}"'))
def assert_schema(acceptance, schema_name: str, foundry_root) -> None:
    payload = acceptance["payload"]
    assert payload is not None and payload.get("ok") is True
    context = payload["context"]
    errors = validate_payload(context, schema_name, foundry_root)
    assert not errors, "; ".join(errors)


@then("context fields match:")
def assert_context_fields(acceptance, datatable) -> None:
    context = acceptance["payload"]["context"]
    failures = collect_context_field_failures(context, datatable)
    if failures:
        message = "context field expectation failures:\n" + "\n".join(
            f"  - {item}" for item in failures
        )
        pytest.fail(message)


@then("context allow cli equals:")
def assert_allow_cli(acceptance, datatable) -> None:
    rows = datatable
    expected = [row[0] for row in rows[1:]]
    actual = acceptance["payload"]["context"]["allow"]["cli"]
    assert actual == expected


@then("context allow files write uris include:")
def assert_write_uris(acceptance, datatable) -> None:
    rows = datatable
    expected = [row[0] for row in rows[1:]]
    grants = acceptance["payload"]["context"]["allow"]["files"]["write"]
    actual = [grant["uri"] for grant in grants]
    for uri in expected:
        assert uri in actual, f"missing {uri!r} in {actual}"


@then(parsers.parse('context allow state includes "{state_path}"'))
def assert_allow_state(acceptance, state_path: str) -> None:
    actual = acceptance["payload"]["context"]["allow"]["state"]
    assert state_path in actual


@then("context allow user ask is true")
def assert_allow_user_ask(acceptance) -> None:
    actual = acceptance["payload"]["context"]["allow"]["user"]["ask"]
    assert actual is True


@then("context allow user decide is true")
def assert_allow_user_decide(acceptance) -> None:
    actual = acceptance["payload"]["context"]["allow"]["user"]["decide"]
    assert actual is True


@then("context produces options equal:")
def assert_produces_options(acceptance, datatable) -> None:
    rows = datatable
    expected = [row[0] for row in rows[1:]]
    actual = acceptance["payload"]["context"]["produces"]["options"]
    assert actual == expected


@then("no ledger events are appended")
def assert_no_ledger_append(acceptance) -> None:
    assert acceptance.get("ledger_before") == acceptance.get("ledger_after")


@given("I record ledger event count")
def record_ledger_count(acceptance) -> None:
    snapshot = load_snapshot(acceptance)
    ledger = snapshot.get("ledger") or []
    acceptance["ledger_count_before"] = len(ledger)


@then(parsers.parse('the run snapshot has no ledger event type "{event_type}"'))
def assert_no_ledger_event_type(acceptance, event_type: str) -> None:
    snapshot = load_snapshot(acceptance)
    ledger = snapshot.get("ledger") or []
    matches = [event for event in ledger if isinstance(event, dict) and event.get("type") == event_type]
    assert not matches, f"expected no {event_type!r} events, found {len(matches)}"


@then("ledger event count is unchanged")
def assert_ledger_unchanged(acceptance) -> None:
    snapshot = load_snapshot(acceptance)
    ledger = snapshot.get("ledger") or []
    assert len(ledger) == acceptance.get("ledger_count_before")


@then(parsers.parse('context warnings mention lifecycle "{lifecycle}"'))
def assert_lifecycle_warning(acceptance, lifecycle: str) -> None:
    warnings = acceptance["payload"]["context"].get("warnings") or []
    assert warnings, "expected warnings in context packet"
    joined = " ".join(warnings).lower()
    assert lifecycle.lower() in joined


@then(parsers.parse('markdown output contains "{text}"'))
def assert_markdown_contains(acceptance, text: str) -> None:
    markdown = acceptance.get("markdown") or acceptance.get("stdout") or ""
    assert text in markdown, f"{text!r} not found in markdown output"


@then(parsers.parse('the run snapshot status is "{status}"'))
def assert_snapshot_status(acceptance, status: str) -> None:
    snapshot = load_snapshot(acceptance)
    assert snapshot.get("status") == status


@then(parsers.parse('file exists at response field "{field_path}" relative "{relative_path}"'))
def assert_file_at_response_field(acceptance, field_path: str, relative_path: str) -> None:
    payload = acceptance["payload"]
    assert payload is not None
    base = Path(str(resolve_json_path(payload, field_path)))
    target = base / relative_path
    assert target.is_file(), f"expected file at {target}"


@then(parsers.parse('response suites passed include "{suite_name}"'))
def assert_suite_passed(acceptance, suite_name: str) -> None:
    payload = acceptance["payload"]
    assert payload is not None
    suites = payload.get("suites_passed") or []
    assert suite_name in suites, payload
