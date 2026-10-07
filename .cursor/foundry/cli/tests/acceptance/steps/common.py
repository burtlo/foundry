"""Shared step definitions used across acceptance features."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when

from foundry_cli.validate import validate_payload
from tests.acceptance.acceptance_flow_helpers import (
    copy_foundry_test_app_manifest,
    install_run_fixture_at_workspace_root,
)
from tests.acceptance.acceptance_invoke import invoke_acceptance_command, reset_acceptance_invoke_argv
from tests.acceptance.helpers import (
    collect_context_field_failures,
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
    copy_foundry_test_app_manifest(workspace)
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
    workspace, run_id = install_run_fixture_at_workspace_root(tmp_path, fixture_name)
    acceptance["workspace"] = workspace
    acceptance["run_id"] = run_id
    acceptance["fixture_name"] = None


@when(parsers.parse('I invoke "{command}" with markdown output'))
def invoke_with_markdown(acceptance, command: str) -> None:
    reset_acceptance_invoke_argv(acceptance)
    invoke_acceptance_command(acceptance, command, json_output=False, markdown_output=True)


@when(parsers.parse('I invoke "{command}" with flag "{flag}"'))
def invoke_with_flag(acceptance, command: str, flag: str) -> None:
    invoke_acceptance_command(acceptance, command, extra_flags=[flag])


@when(parsers.parse('I invoke "{command}" with flags "{flags}"'))
def invoke_with_flags(acceptance, command: str, flags: str) -> None:
    invoke_acceptance_command(acceptance, command, extra_flags=flags.split())


@when(parsers.parse('I invoke "{command}" with run id "{run_id}"'))
def invoke_with_run_id(acceptance, command: str, run_id: str) -> None:
    acceptance["run_id"] = run_id
    acceptance["fixture_name"] = None
    reset_acceptance_invoke_argv(acceptance)
    invoke_acceptance_command(acceptance, command)


@when(parsers.parse('I invoke "gate decide" with decision "{decision}"'))
def invoke_gate_decide(acceptance, decision: str) -> None:
    invoke_acceptance_command(acceptance, "gate decide", extra_argv=["--decision", decision])


@when(parsers.parse('I invoke "{command}" with set \'{patch}\''))
def invoke_patch(acceptance, command: str, patch: str) -> None:
    invoke_acceptance_command(acceptance, command, extra_argv=["--set", patch])


@when(parsers.parse('I invoke "{command}" with summary "{summary}"'))
def invoke_transition(acceptance, command: str, summary: str) -> None:
    invoke_acceptance_command(acceptance, command, extra_argv=["--summary", summary])


@when(parsers.parse('I invoke "{command}" with types "{types}"'))
def invoke_ledger_types(acceptance, command: str, types: str) -> None:
    invoke_acceptance_command(acceptance, command, extra_argv=["--types", types])


@when(
    parsers.parse(
        'I invoke "{command}" with artifact "{artifact}" from "{source}"'
    )
)
def invoke_artifact_publish(acceptance, command: str, artifact: str, source: str) -> None:
    invoke_acceptance_command(
        acceptance,
        command,
        extra_argv=["--artifact", artifact, "--source", source],
    )


@when(
    parsers.parse(
        'I invoke "{command}" with schema "{schema}" file "{file_path}"'
    )
)
def invoke_receipt_seal(acceptance, command: str, schema: str, file_path: str) -> None:
    invoke_acceptance_command(
        acceptance,
        command,
        extra_argv=["--schema", schema, "--file", file_path],
    )


@when(parsers.re(r'^I invoke "(?P<command>[^"]+)"$'))
def invoke_command(acceptance, command: str) -> None:
    reset_acceptance_invoke_argv(acceptance)
    invoke_acceptance_command(acceptance, command)


def _assert_cli_exit_and_ok(acceptance: dict, exit_code: int, ok: bool | None) -> None:
    assert acceptance["exit_code"] == exit_code, acceptance.get("stderr") or acceptance.get("stdout")
    if ok is None:
        return
    payload = acceptance.get("payload")
    assert payload is not None, "expected JSON response payload"
    assert payload.get("ok") is ok, payload


@then("the CLI succeeds")
def assert_cli_succeeds(acceptance) -> None:
    assert acceptance["exit_code"] == 0, acceptance.get("stderr") or acceptance.get("stdout")
    if acceptance.get("markdown_output"):
        return
    _assert_cli_exit_and_ok(acceptance, 0, True)


@then("the CLI succeeds with:")
def assert_cli_succeeds_with(acceptance, datatable) -> None:
    _assert_cli_exit_and_ok(acceptance, 0, True)
    payload = acceptance["payload"]
    assert payload is not None
    failures: list[str] = []
    for row in datatable[1:]:
        field_path = row[0].strip()
        expected = row[1].strip()
        try:
            if expected == "(file exists)":
                path_value = resolve_json_path(payload, field_path)
                if not Path(str(path_value)).is_file():
                    failures.append(f"{field_path}: expected file to exist at {path_value!r}")
                continue
            actual = resolve_json_path(payload, field_path)
            if str(actual) != expected:
                failures.append(f"{field_path}: expected {expected!r}, got {actual!r}")
        except KeyError:
            failures.append(f"{field_path}: path not found in response")
        except (TypeError, ValueError, IndexError) as exc:
            failures.append(f"{field_path}: {exc}")
    if failures:
        message = "response field expectation failures:\n" + "\n".join(
            f"  - {item}" for item in failures
        )
        pytest.fail(message)


@then(parsers.parse('the CLI fails with error "{code}"'))
def assert_cli_fails_with_error(acceptance, code: str) -> None:
    _assert_cli_exit_and_ok(acceptance, 1, False)
    payload = acceptance["payload"]
    assert payload is not None
    assert payload.get("error", {}).get("code") == code, payload


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


@then(parsers.parse('response field "{field_path}" exists as file'))
def assert_response_field_is_file(acceptance, field_path: str) -> None:
    payload = acceptance["payload"]
    assert payload is not None
    raw = str(resolve_json_path(payload, field_path))
    path = Path(raw)
    if not path.is_file():
        workspace = Path(acceptance["workspace"])
        path = (workspace / raw).resolve()
    assert path.is_file(), f"expected file at {path}"


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


@then("context allow files write uris are empty")
def assert_write_uris_empty(acceptance) -> None:
    grants = acceptance["payload"]["context"]["allow"]["files"]["write"]
    assert grants == []


@then(parsers.parse('context json does not have field "{field_path}"'))
def assert_context_missing_field(acceptance, field_path: str) -> None:
    context = acceptance["payload"]["context"]
    assert field_path not in context, f"unexpected field {field_path!r} in context"


@then(parsers.parse('context allow state includes "{state_path}"'))
def assert_allow_state(acceptance, state_path: str) -> None:
    actual = acceptance["payload"]["context"]["allow"]["state"]
    assert state_path in actual


@then("context allow user ask is true")
def assert_allow_user_ask(acceptance) -> None:
    actual = acceptance["payload"]["context"]["allow"]["user"]["ask"]
    assert actual is True


@then("context allow user ask is false")
def assert_allow_user_ask_false(acceptance) -> None:
    actual = acceptance["payload"]["context"]["allow"]["user"]["ask"]
    assert actual is False


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


@then(parsers.parse('markdown output does not contain "{text}"'))
def assert_markdown_not_contains(acceptance, text: str) -> None:
    markdown = acceptance.get("markdown") or acceptance.get("stdout") or ""
    assert text not in markdown, f"{text!r} unexpectedly found in markdown output"


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
