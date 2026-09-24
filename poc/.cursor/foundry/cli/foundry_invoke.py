"""Foundry-invoke fence parsing, template resolution, and step-unit validation."""

from __future__ import annotations

import re
import shlex
import sys
from pathlib import Path
from typing import Any

FOUNDRY_INVOKE_FENCE_RE = re.compile(r"```foundry-invoke\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
RUN_CONTEXT_PLACEHOLDERS = frozenset(
    {
        "factory_root",
        "app_folder",
        "state_path",
        "config_path",
        "run_dir",
        "run_id",
        "issue_key",
        "current_step",
    }
)
FORBIDDEN_INVOKE_MARKERS = (
    "foundry_cli",
    "foundry.py",
)


def quote_for_agent_shell(value: str) -> str:
    """Quote a path for the agent Shell tool (PowerShell 5.1 on Windows, bash elsewhere)."""
    if sys.platform == "win32":
        return "'" + value.replace("'", "''") + "'"
    return shlex.quote(value)


def format_foundry_cli(python_executable: str, script_path: str | Path) -> str:
    """Shell-safe ``foundry_cli`` prefix: interpreter + foundry.py."""
    python_q = quote_for_agent_shell(python_executable)
    script_q = quote_for_agent_shell(str(script_path))
    if sys.platform == "win32":
        return f"& {python_q} {script_q}"
    return f"{python_q} {script_q}"


def format_launcher_cli(launcher_path: str | Path) -> str:
    """Shell-safe ``foundry_cli`` prefix for the platform launcher script."""
    launcher_q = quote_for_agent_shell(str(launcher_path))
    if sys.platform == "win32":
        return f"& {launcher_q}"
    return f"bash {launcher_q}"


def extract_foundry_invokes(markdown: str) -> list[str]:
    return [match.group(1).strip() for match in FOUNDRY_INVOKE_FENCE_RE.finditer(markdown) if match.group(1).strip()]


def resolve_invoke_tail(tail: str, context: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in context and context[key] is not None:
            return str(context[key])
        return match.group(0)

    return re.sub(r"\{([a-z_][a-z0-9_]*)\}", replace, tail.strip())


def render_foundry_invoke(
    tail: str,
    foundry_cli: str,
    context: dict[str, Any],
) -> dict[str, str]:
    argv_tail = resolve_invoke_tail(tail, context)
    shell = f"{foundry_cli} {argv_tail}".strip()
    return {
        "argv_tail": argv_tail,
        "shell": shell,
        "foundry_cli": foundry_cli,
    }


def validate_foundry_invoke_body(body: str, *, source: str) -> list[str]:
    errors: list[str] = []
    normalized = body.strip()
    if not normalized:
        errors.append(f"{source}: foundry-invoke fence is empty")
        return errors

    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    if len(lines) != 1:
        errors.append(f"{source}: foundry-invoke must contain exactly one invocation line")

    line = lines[0] if lines else normalized
    lowered = line.lower()
    for marker in FORBIDDEN_INVOKE_MARKERS:
        if marker in lowered:
            errors.append(f"{source}: foundry-invoke must not include {marker!r}")
    if lowered.startswith("python "):
        errors.append(f"{source}: foundry-invoke must not include the python interpreter")
    return errors


def validate_markdown(markdown: str, *, source: str) -> list[str]:
    errors: list[str] = []
    for index, body in enumerate(extract_foundry_invokes(markdown), start=1):
        errors.extend(validate_foundry_invoke_body(body, source=f"{source} foundry-invoke[{index}]"))

    if re.search(r"```(?:bash|shell)\s*\n[^\n]*foundry_cli", markdown, re.IGNORECASE):
        errors.append(f"{source}: use ```foundry-invoke instead of bash/shell fences for Foundry CLI")
    if re.search(r"```text\s*\n[^\n]*foundry_cli", markdown, re.IGNORECASE):
        errors.append(f"{source}: use ```foundry-invoke instead of text fences for Foundry CLI")

    for match in re.finditer(r"```(\w+)\s*\n(.*?)```", markdown, re.DOTALL | re.IGNORECASE):
        lang = match.group(1).lower()
        body = match.group(2)
        if lang == "foundry-invoke":
            continue
        if re.search(r"foundry\.py|foundry\.ps1", body, re.IGNORECASE):
            errors.append(
                f"{source}: Foundry CLI must use ```foundry-invoke (found {lang} fence with foundry.py/ps1)"
            )

    inline_pattern = re.compile(r"`\{foundry_cli\}[^`]+`")
    if inline_pattern.search(markdown):
        errors.append(f"{source}: use ```foundry-invoke fences instead of inline `{{foundry_cli}} ...` commands")
    return errors


def validate_step_units(steps_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    checked = 0
    for path in sorted(steps_root.glob("*.md")):
        checked += 1
        errors.extend(
            validate_markdown(
                path.read_text(encoding="utf-8"),
                source=str(path.relative_to(steps_root.parent)),
            )
        )
    return {"valid": not errors, "checked": checked, "errors": errors}


def validate_steward_docs(paths: list[Path]) -> dict[str, Any]:
    errors: list[str] = []
    checked = 0
    for path in paths:
        if not path.is_file():
            continue
        checked += 1
        errors.extend(validate_markdown(path.read_text(encoding="utf-8"), source=str(path)))
    return {"valid": not errors, "checked": checked, "errors": errors}
