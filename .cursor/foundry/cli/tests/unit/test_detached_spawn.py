"""Headless detached child spawn helpers."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from foundry_cli.detached_spawn import detached_python_executable, popen_kwargs_for_detached_child


def test_detached_python_executable_prefers_pythonw_on_windows() -> None:
    if sys.platform != "win32":
        assert detached_python_executable() == sys.executable
        return
    exe = Path(sys.executable)
    if exe.name.lower() != "python.exe":
        return
    pythonw = exe.with_name("pythonw.exe")
    if pythonw.is_file():
        assert detached_python_executable() == str(pythonw)


def test_popen_kwargs_for_detached_child_win32() -> None:
    kwargs = popen_kwargs_for_detached_child()
    if sys.platform == "win32":
        assert "startupinfo" in kwargs
        assert kwargs["creationflags"] == subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        assert kwargs == {"start_new_session": True}
