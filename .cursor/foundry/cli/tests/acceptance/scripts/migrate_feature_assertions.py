"""One-off migration: simplify invokes and consolidate CLI assertions in .feature files."""

from __future__ import annotations

import re
from pathlib import Path

FEATURES = Path(__file__).resolve().parents[1] / "features"

INVOKE_REPLACEMENTS = [
    (' with json output schema "', ' with schema "'),
    (" with json output and ", " with "),
    (" with json output", ""),
    (' and json output', ""),
    ("visit examine complete with json output", "visit examine complete"),
    ('"visit plan complete" with json output', '"visit plan complete"'),
    ('"visit present complete" with json output', '"visit present complete"'),
    ('"visit record complete" with json output', '"visit record complete"'),
]

FAILURE_BLOCK = re.compile(
    r"([ \t]*)Then the CLI exit code is 1\n"
    r"(?:[ \t]*And response ok is false\n)?"
    r'[ \t]*And response error code equals "([^"]+)"\n',
    re.MULTILINE,
)

SUCCESS_OK_FIELD = re.compile(
    r"([ \t]*)Then the CLI exit code is 0\n"
    r"[ \t]*And response ok is true\n"
    r"((?:[ \t]*And response field \"[^\"]+\" equals \"[^\"]*\"\n)+)",
    re.MULTILINE,
)

SUCCESS_FIELDS_ONLY = re.compile(
    r"([ \t]*)Then the CLI exit code is 0\n"
    r"((?:[ \t]*And response field \"[^\"]+\" equals \"[^\"]*\"\n)+)",
    re.MULTILINE,
)

FIELD_LINE = re.compile(r'[ \t]*And response field "([^"]+)" equals "([^"]*)"\n')


def _fields_to_table(indent: str, field_block: str) -> str:
    rows = FIELD_LINE.findall(field_block + "\n")
    if not rows:
        return ""
    lines = [f"{indent}Then the CLI succeeds with:", f"{indent}  | field | expected |"]
    for field_path, expected in rows:
        lines.append(f"{indent}  | {field_path} | {expected} |")
    return "\n".join(lines) + "\n"


def migrate_text(text: str) -> str:
    for old, new in INVOKE_REPLACEMENTS:
        text = text.replace(old, new)

    text = FAILURE_BLOCK.sub(
        lambda m: f'{m.group(1)}Then the CLI fails with error "{m.group(2)}"\n',
        text,
    )

    def replace_success_ok(m: re.Match[str]) -> str:
        return _fields_to_table(m.group(1), m.group(2))

    text = SUCCESS_OK_FIELD.sub(replace_success_ok, text)
    text = SUCCESS_FIELDS_ONLY.sub(replace_success_ok, text)

    # exit 0 + ok true with no following response fields -> the CLI succeeds
    text = re.sub(
        r"([ \t]*)Then the CLI exit code is 0\n[ \t]*And response ok is true\n(?![ \t]*And response field)",
        r"\1Then the CLI succeeds\n",
        text,
        flags=re.MULTILINE,
    )

    text = text.replace(
        "Then the CLI exit code is 0\n    And I store",
        "Then the CLI succeeds\n    And I store",
    )

    # lone exit 0 lines (no ok, no response field on next line) -> succeeds
    text = re.sub(
        r"([ \t]*)Then the CLI exit code is 0\n"
        r"(?![ \t]*(?:And response |And I store|And context |And the run |And markdown |And catalog |And generated |And file |And workspace |And inline |And response suites))",
        r"\1Then the CLI succeeds\n",
        text,
        flags=re.MULTILINE,
    )

    return text


def main() -> None:
    for path in sorted(FEATURES.glob("*.feature")):
        original = path.read_text(encoding="utf-8")
        updated = migrate_text(original)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            print(f"updated {path.name}")


if __name__ == "__main__":
    main()
