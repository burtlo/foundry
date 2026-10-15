"""Operator help curriculum: listed commands by journey section (spec D6–D7)."""

from __future__ import annotations

import argparse
from typing import Iterable

# Journey-ordered sections for default ``foundry -h`` (cli-operator-ux spec table).
LISTED_HELP_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Set up the workspace", ("config", "app")),
    ("Local Foundry", ("up", "down")),
    ("Start and watch runs", ("shape", "runs", "status", "attach")),
    ("When the run needs you", ("answer", "decide", "start")),
    ("Recover or stop a run", ("retry", "cancel")),
)

UNLISTED_TOP_LEVEL_COMMANDS: frozenset[str] = frozenset(
    {
        "run",
        "visit",
        "gate",
        "artifact",
        "receipt",
        "ledger",
        "host",
        "bridge",
        "tui",
        "cli",
        "catalog",
        "doc",
        "dev",
        "help",
    }
)


def listed_command_names() -> frozenset[str]:
    names: set[str] = set()
    for _, commands in LISTED_HELP_SECTIONS:
        names.update(commands)
    return frozenset(names)


def subcommand_help_map(parser: argparse.ArgumentParser) -> dict[str, str]:
    """Map top-level subcommand name to its one-line argparse help string."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            help_by_name: dict[str, str] = {}
            for choice_action in getattr(action, "_choices_actions", ()):
                help_text = getattr(choice_action, "help", None)
                if help_text is None or help_text is argparse.SUPPRESS:
                    continue
                help_by_name[choice_action.dest] = str(help_text).strip()
            out: dict[str, str] = {}
            for name, subparser in action.choices.items():
                if name is argparse.SUPPRESS:
                    continue
                text = help_by_name.get(name, "")
                if not text:
                    text = (getattr(subparser, "help", None) or subparser.description or "").strip()
                out[name] = text
            return out
    return {}


def _format_command_rows(
    commands: Iterable[str],
    command_helps: dict[str, str],
    *,
    name_width: int = 22,
) -> list[str]:
    lines: list[str] = []
    for name in commands:
        desc = command_helps.get(name, "")
        if len(name) >= name_width:
            lines.append(f"  {name}")
            if desc:
                lines.append(f"    {desc}")
        else:
            pad = " " * (name_width - len(name))
            lines.append(f"  {name}{pad}{desc}")
    return lines


def format_listed_sections(command_helps: dict[str, str]) -> str:
    """Body of curriculum help: section headers and listed commands only."""
    blocks: list[str] = []
    for title, commands in LISTED_HELP_SECTIONS:
        blocks.append(f"{title}:")
        blocks.extend(_format_command_rows(commands, command_helps))
        blocks.append("")
    return "\n".join(blocks).rstrip() + "\n"


def format_global_options_block(parser: argparse.ArgumentParser) -> str:
    formatter = parser._get_formatter()
    option_actions = [
        action
        for action in parser._actions
        if action.option_strings and not isinstance(action, argparse._SubParsersAction)
    ]
    lines: list[str] = ["options:"]
    for action in option_actions:
        for line in formatter._format_action(action).splitlines():
            lines.append(f"  {line}" if line else line)
    return "\n".join(lines) + "\n"


def format_curriculum_help(parser: argparse.ArgumentParser) -> str:
    """Full root help: usage, global options, journey sections (listed commands only)."""
    command_helps = subcommand_help_map(parser)
    usage = f"usage: {parser.prog} [-h] [--workspace WORKSPACE] [--registry REGISTRY] [--json]\n\n"
    options = format_global_options_block(parser)
    sections = format_listed_sections(command_helps)
    return usage + options + "\n" + sections


def all_top_level_command_names(command_helps: dict[str, str]) -> tuple[str, ...]:
    """Listed journey order first, then remaining unlisted names (for ``help -a``)."""
    listed = [cmd for _, cmds in LISTED_HELP_SECTIONS for cmd in cmds]
    unlisted = sorted(name for name in command_helps if name not in listed_command_names())
    return tuple(listed + unlisted)


def top_level_subparsers(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    """Map top-level subcommand name to its subparser instance."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return {
                name: subparser
                for name, subparser in action.choices.items()
                if name is not argparse.SUPPRESS
            }
    return {}


def format_all_commands_help(parser: argparse.ArgumentParser) -> str:
    """Full command list for ``foundry help -a`` (git help -a analogue)."""
    command_helps = subcommand_help_map(parser)
    names = all_top_level_command_names(command_helps)
    usage = "usage: foundry help [-a] [<command>]\n\n"
    body_lines = ["All commands:"]
    body_lines.extend(_format_command_rows(names, command_helps))
    return usage + "\n".join(body_lines) + "\n"
