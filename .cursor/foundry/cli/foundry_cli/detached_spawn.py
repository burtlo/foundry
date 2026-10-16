"""Spawn detached background children without visible console windows."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any


def detached_python_executable() -> str:
    """Interpreter for background ``python -m ...`` children (no console on Windows)."""
    exe = Path(sys.executable)
    if sys.platform == "win32" and exe.name.lower() == "python.exe":
        pythonw = exe.with_name("pythonw.exe")
        if pythonw.is_file():
            return str(pythonw)
    return sys.executable


def popen_kwargs_for_detached_child() -> dict[str, Any]:
    """Extra ``subprocess.Popen`` keyword args for a headless background child."""
    if sys.platform != "win32":
        return {"start_new_session": True}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0  # SW_HIDE
    return {
        "creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
        "startupinfo": startupinfo,
    }
