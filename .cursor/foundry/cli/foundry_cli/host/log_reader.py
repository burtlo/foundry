"""Read and follow workspace host log files."""

from __future__ import annotations

import time
from collections import deque
from pathlib import Path

HOST_START_MARKER_PREFIX = "FOUNDRY_HOST_START"


def format_host_start_marker(start_id: str, at: str) -> str:
    """Single-line marker written to host.log on successful host start/up."""
    return f"{HOST_START_MARKER_PREFIX} start_id={start_id} at={at}"


def append_host_start_marker(path: Path, start_id: str, at: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(format_host_start_marker(start_id, at) + "\n")


def _marker_line_index(lines: list[str], start_id: str) -> int | None:
    needle = f"start_id={start_id}"
    last: int | None = None
    for index, line in enumerate(lines):
        if HOST_START_MARKER_PREFIX in line and needle in line:
            last = index
    return last


def _iso_prefix_index(lines: list[str], marker_timestamp: str) -> int:
    prefix = marker_timestamp[:19]
    at_needle = f"at={marker_timestamp}"
    for index, line in enumerate(lines):
        if at_needle in line:
            return index
        if line >= prefix:
            return index
    return len(lines)


def read_log_since_marker(
    path: Path,
    *,
    marker_timestamp: str | None = None,
    start_id: str | None = None,
    max_lines: int,
) -> list[str]:
    """Return trailing lines from the latest host start marker onward."""
    if max_lines <= 0 or not path.is_file():
        return []
    if not marker_timestamp and not start_id:
        return read_log_tail(path, max_lines=max_lines)

    all_lines: list[str] = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            all_lines.append(line.rstrip("\n"))

    start_index = 0
    if start_id:
        found = _marker_line_index(all_lines, start_id)
        if found is not None:
            start_index = found
        elif marker_timestamp:
            start_index = _iso_prefix_index(all_lines, marker_timestamp)
    elif marker_timestamp:
        start_index = _iso_prefix_index(all_lines, marker_timestamp)

    sliced = all_lines[start_index:]
    if len(sliced) > max_lines:
        sliced = sliced[-max_lines:]
    return sliced


def read_log_tail(path: Path, *, max_lines: int) -> list[str]:
    """Return up to ``max_lines`` trailing lines from ``path`` (without line endings)."""
    if max_lines <= 0 or not path.is_file():
        return []
    tail: deque[str] = deque(maxlen=max_lines)
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            tail.append(line.rstrip("\n"))
    return list(tail)


def follow_log(
    path: Path,
    *,
    max_lines: int,
    marker_timestamp: str | None = None,
    start_id: str | None = None,
    poll_seconds: float = 0.25,
) -> None:
    """Print trailing lines then stream new lines until interrupted."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.touch()
    if marker_timestamp or start_id:
        initial = read_log_since_marker(
            path,
            marker_timestamp=marker_timestamp,
            start_id=start_id,
            max_lines=max_lines,
        )
    else:
        initial = read_log_tail(path, max_lines=max_lines)
    for line in initial:
        print(line)
    with path.open(encoding="utf-8", errors="replace") as handle:
        handle.seek(0, 2)
        while True:
            line = handle.readline()
            if line:
                print(line.rstrip("\n"))
            else:
                time.sleep(poll_seconds)
