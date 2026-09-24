"""Cross-platform verification helper for the Python reference fixture."""

from __future__ import annotations

import sys

phase = sys.argv[1] if len(sys.argv) > 1 else "unknown"
print(f"{phase} ok")
