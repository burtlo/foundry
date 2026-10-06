"""Step definitions for user_cli.feature."""

from __future__ import annotations

from pytest_bdd import parsers, then, when

from tests.acceptance.helpers import invoke_foundry


@when(
    parsers.parse(
        'I invoke "shape" with json output and input "{text}" and flag "{flag}"'
    )
)
def invoke_shape_with_input(acceptance, text: str, flag: str) -> None:
    acceptance["command"] = "shape"
    acceptance["json_output"] = True
    acceptance["markdown_output"] = False
    acceptance["extra_argv"] = ["--input", text]
    acceptance["extra_flags"] = [flag]
    invoke_foundry(acceptance)


@when(parsers.parse('I invoke "decide" with json output and option "{option}" and flag "{flag}"'))
def invoke_decide_with_option(acceptance, option: str, flag: str) -> None:
    acceptance["command"] = "decide"
    acceptance["json_output"] = True
    acceptance["markdown_output"] = False
    acceptance["extra_argv"] = [option]
    acceptance["extra_flags"] = [flag]
    invoke_foundry(acceptance)


@when(parsers.parse('I invoke "attach" with json output and flags "{flags}"'))
def invoke_attach_with_flags(acceptance, flags: str) -> None:
    acceptance["command"] = "attach"
    acceptance["json_output"] = True
    acceptance["markdown_output"] = False
    acceptance["extra_argv"] = []
    acceptance["extra_flags"] = flags.split()
    invoke_foundry(acceptance)


@then(parsers.parse('response field "{field_path}" equals "stored run id"'))
def assert_response_equals_stored_run_id(acceptance, field_path: str) -> None:
    from tests.acceptance.helpers import resolve_json_path

    payload = acceptance["payload"]
    assert payload is not None
    expected = acceptance.get("run_id")
    assert expected, "run_id not stored in acceptance state"
    actual = resolve_json_path(payload, field_path)
    assert str(actual) == str(expected), f"{field_path}: expected {expected!r}, got {actual!r}"
