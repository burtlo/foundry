"""Fail if plugin-shipped surfaces still contain org-specific Foundry branding."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

FOUNDRY_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = FOUNDRY_ROOT.parents[1]

SKIP_NAMES = {
    "foundry_docs_iot.py",
    "test_docs.py",
    "test_docs_models.py",
    "test_plugin_neutrality.py",
}
SKIP_DIR_NAMES = {"__pycache__", ".git"}
TEXT_SUFFIXES = {
    ".md",
    ".mdc",
    ".py",
    ".yaml",
    ".yml",
    ".json",
    ".txt",
    ".feature",
    ".ps1",
    ".sh",
    ".example",
}
SCOPES = (
    REPO_ROOT / ".cursor-plugin",
    REPO_ROOT / ".cursor" / "commands",
    REPO_ROOT / ".cursor" / "skills",
    REPO_ROOT / ".cursor" / "agents",
    REPO_ROOT / ".cursor" / "rules",
    REPO_ROOT / ".cursor" / "foundry",
)
ALLOWED = re.compile(r"iot-agents-prd")
FORBIDDEN = (
    re.compile(r"KT\.IoT"),
    re.compile(r"KT\.ComponentLibrary"),
    re.compile(r"kwik-trip", re.I),
    re.compile(r"kwiktrip", re.I),
    re.compile(r"Kwik Trip"),
    re.compile(r"Kwik Things"),
    re.compile(r"DOTNETIOT"),
    re.compile(r"iot-dotnetiot"),
    re.compile(r"iot-ticket-workflow"),
    re.compile(r"iot-documentation-workflow"),
    re.compile(r"iot-prd-regenerate"),
    re.compile(r"iot-branch-to-jira"),
    re.compile(r"analyze-next-sprint"),
    re.compile(r"IoT Tools"),
)


def _iter_files() -> list[Path]:
    files: list[Path] = []
    for scope in SCOPES:
        if not scope.exists():
            continue
        for path in scope.rglob("*"):
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            if not path.is_file() or path.name in SKIP_NAMES:
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            files.append(path)
    return files


class PluginNeutralityTests(unittest.TestCase):
    def test_plugin_shipped_paths_have_no_org_branding(self) -> None:
        hits: list[str] = []
        for path in _iter_files():
            text = path.read_text(encoding="utf-8")
            for index, line in enumerate(text.splitlines(), start=1):
                if ALLOWED.search(line) and not any(
                    pattern.search(ALLOWED.sub("", line)) for pattern in FORBIDDEN
                ):
                    continue
                for pattern in FORBIDDEN:
                    if pattern.search(line):
                        rel = path.relative_to(REPO_ROOT).as_posix()
                        hits.append(f"{rel}:{index}: {line.strip()}")
                        break
        self.assertEqual(hits, [], "\n".join(hits[:50]))


if __name__ == "__main__":
    unittest.main()
