"""Step definitions for run_context.feature."""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, then, when

from foundry_cli.validate import validate_payload
from tests.acceptance.helpers import collect_context_field_failures, invoke_foundry


@given(parsers.parse('the foundry registry flow "{flow_id}"'))
def registry_flow(acceptance, flow_id: str) -> None:
    acceptance["flow_id"] = flow_id


@given("workspace is the repository root")
def workspace_root(acceptance, repo_root) -> None:
    acceptance["workspace"] = repo_root


@given(parsers.parse('run fixture "{fixture_name}"'))
def run_fixture(acceptance, fixture_name: str) -> None:
    acceptance["fixture_name"] = fixture_name
    acceptance["run_id"] = None


@when(parsers.parse('I invoke "{command}" with json output'))
def invoke_with_json(acceptance, command: str) -> None:
    acceptance["command"] = command
    acceptance["json_output"] = True
    acceptance["markdown_output"] = False
    invoke_foundry(acceptance)


@when(parsers.parse('I invoke "{command}" with markdown output'))
def invoke_with_markdown(acceptance, command: str) -> None:
    acceptance["command"] = command
    acceptance["markdown_output"] = True
    acceptance["json_output"] = False
    invoke_foundry(acceptance)


@when(parsers.parse('I invoke "{command}" with json output and flag "{flag}"'))
def invoke_with_json_and_flag(acceptance, command: str, flag: str) -> None:
    acceptance["command"] = command
    acceptance["json_output"] = True
    acceptance["markdown_output"] = False
    acceptance["extra_flags"] = [flag]
    invoke_foundry(acceptance)


@when(parsers.parse('I invoke "{command}" with run id "{run_id}" and json output'))
def invoke_with_run_id(acceptance, command: str, run_id: str) -> None:
    acceptance["command"] = command
    acceptance["run_id"] = run_id
    acceptance["fixture_name"] = None
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


@then(parsers.parse('response error code equals "{code}"'))
def assert_error_code(acceptance, code: str) -> None:
    payload = acceptance["payload"]
    assert payload is not None
    assert payload.get("error", {}).get("code") == code


@then("no ledger events are appended")
def assert_no_ledger_append(acceptance) -> None:
    assert acceptance.get("ledger_before") == acceptance.get("ledger_after")


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
