"""Step definitions for user_cli.feature."""

from __future__ import annotations

from pytest_bdd import parsers, then, when

from tests.acceptance.acceptance_invoke import invoke_acceptance_command
from tests.acceptance.helpers import resolve_json_path


@when(
    parsers.parse(
        'I invoke "shape" with json output and input "{text}" and flag "{flag}"'
    )
)
def invoke_shape_with_input(acceptance, text: str, flag: str) -> None:
    invoke_acceptance_command(acceptance, "shape", extra_argv=["--input", text], extra_flags=[flag])


@when(
    parsers.parse(
        'I invoke "answer" with json output and answers \'{answers}\' and flag "{flag}"'
    )
)
def invoke_answer_with_answers(acceptance, answers: str, flag: str) -> None:
    invoke_acceptance_command(acceptance, "answer", extra_argv=["--answers", answers], extra_flags=[flag])


@when(parsers.parse('I invoke "decide" with json output and option "{option}" and flag "{flag}"'))
def invoke_decide_with_option(acceptance, option: str, flag: str) -> None:
    invoke_acceptance_command(acceptance, "decide", extra_argv=[option], extra_flags=[flag])


@when(parsers.parse('I invoke "attach" with json output and flags "{flags}"'))
def invoke_attach_with_flags(acceptance, flags: str) -> None:
    invoke_acceptance_command(acceptance, "attach", extra_flags=flags.split())


@then(parsers.parse('response field "{field_path}" equals "stored run id"'))
def assert_response_equals_stored_run_id(acceptance, field_path: str) -> None:
    payload = acceptance["payload"]
    assert payload is not None
    expected = acceptance.get("run_id")
    assert expected, "run_id not stored in acceptance state"
    actual = resolve_json_path(payload, field_path)
    assert str(actual) == str(expected), f"{field_path}: expected {expected!r}, got {actual!r}"
