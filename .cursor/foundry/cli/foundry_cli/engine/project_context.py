"""Bounded repository context for agent judgment requests."""

from __future__ import annotations

from pathlib import Path

MAX_CONTEXT_ENTRIES = 8
MAX_CHARS_PER_ENTRY = 2000


def select_bounded_project_context(
    workspace: Path,
    *,
    max_entries: int = MAX_CONTEXT_ENTRIES,
    max_chars_per_entry: int = MAX_CHARS_PER_ENTRY,
) -> list[dict[str, str]]:
    """Return small path + excerpt records for examination input (no secrets)."""
    candidates: list[tuple[str, Path]] = [
        ("AGENTS.md", workspace / "AGENTS.md"),
        ("README.md", workspace / "README.md"),
        (".foundry/app.yaml", workspace / ".foundry" / "app.yaml"),
    ]
    entries: list[dict[str, str]] = []
    for label, path in candidates:
        if len(entries) >= max_entries:
            break
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if len(text) > max_chars_per_entry:
            text = text[:max_chars_per_entry] + "\n…"
        entries.append({"path": label, "excerpt": text})
    return entries
