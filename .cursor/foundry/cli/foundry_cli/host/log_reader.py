"""Read and follow workspace host log files."""

from __future__ import annotations

import time
from collections import deque
from pathlib import Path


def read_log_tail(path: Path, *, max_lines: int) -> list[str]:
    """Return up to ``max_lines`` trailing lines from ``path`` (without line endings)."""
    if max_lines <= 0 or not path.is_file():
        return []
    tail: deque[str] = deque(maxlen=max_lines)
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            tail.append(line.rstrip("\n"))
    return list(tail)


def follow_log(path: Path, *, max_lines: int, poll_seconds: float = 0.25) -> None:
    """Print trailing lines then stream new lines until interrupted."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.touch()
    for line in read_log_tail(path, max_lines=max_lines):
        print(line)
    with path.open(encoding="utf-8", errors="replace") as handle:
        handle.seek(0, 2)
        while True:
            line = handle.readline()
            if line:
                print(line.rstrip("\n"))
            else:
                time.sleep(poll_seconds)
