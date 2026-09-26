"""Step definitions for dev_commands.feature."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when

from tests.acceptance.helpers import collect_context_field_failures, invoke_foundry


@given("workspace is the repository root")
def workspace_root(acceptance, repo_root) -> None:
    acceptance["workspace"] = repo_root


@given("dev docs output directory is a temporary directory")
def dev_docs_output_dir(acceptance, tmp_path) -> None:
    output_dir = tmp_path / "generated"
    output_dir.mkdir(parents=True)
    acceptance["output_dir"] = output_dir


@when(parsers.parse('I invoke "{command}" with json output'))
def invoke_with_json(acceptance, command: str) -> None:
    acceptance["command"] = command
    acceptance["json_output"] = True
    invoke_foundry(acceptance)


@when(parsers.parse('I invoke "{command}" with json output and flag "{flag}"'))
def invoke_with_json_and_flag(acceptance, command: str, flag: str) -> None:
    acceptance["command"] = command
    acceptance["json_output"] = True
    acceptance["extra_flags"] = [flag]
    invoke_foundry(acceptance)


@when(parsers.parse('I invoke "{command}" with json output and flags "{flags}"'))
def invoke_with_json_and_flags(acceptance, command: str, flags: str) -> None:
    acceptance["command"] = command
    acceptance["json_output"] = True
    acceptance["extra_flags"] = flags.split()
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
    failures = collect_context_field_failures(payload, [["field", "expected"], [field_path, expected]])
    if failures:
        pytest.fail(failures[0])


@then(parsers.parse('file exists at response field "{field_path}" relative "{relative_path}"'))
def assert_file_at_response_field(acceptance, field_path: str, relative_path: str) -> None:
    from tests.acceptance.helpers import resolve_json_path

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
