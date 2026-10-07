"""Configure acceptance state and invoke the Foundry CLI."""

from __future__ import annotations

from typing import Any

from tests.acceptance.helpers import invoke_foundry


def reset_acceptance_invoke_argv(acceptance: dict[str, Any]) -> None:
    acceptance["extra_argv"] = []
    acceptance["extra_flags"] = []


def invoke_acceptance_command(
    acceptance: dict[str, Any],
    command: str,
    *,
    json_output: bool = True,
    markdown_output: bool = False,
    extra_argv: list[str] | None = None,
    extra_flags: list[str] | None = None,
) -> None:
    acceptance["command"] = command
    acceptance["json_output"] = json_output
    acceptance["markdown_output"] = markdown_output
    acceptance["extra_argv"] = list(extra_argv or [])
    acceptance["extra_flags"] = list(extra_flags or [])
    invoke_foundry(acceptance)
