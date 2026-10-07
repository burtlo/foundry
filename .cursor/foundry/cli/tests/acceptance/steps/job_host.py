"""Step definitions for job_host.feature."""

from __future__ import annotations

import subprocess
import sys
import time

import pytest
from pytest_bdd import given, parsers, when

from tests.acceptance.helpers import invoke_foundry
from tests.conftest import CLI_DIR, FOUNDRY_ROOT


@given("the foreground job host is running for the workspace")
def foreground_host(acceptance) -> None:
    workspace = acceptance["workspace"]
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "foundry_cli.host",
            "--workspace",
            str(workspace),
            "--registry",
            str(FOUNDRY_ROOT),
        ],
        cwd=str(CLI_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    acceptance["host_proc"] = proc
    status = None
    for _ in range(50):
        acceptance["command"] = "host status"
        acceptance["json_output"] = True
        acceptance["extra_argv"] = []
        acceptance["extra_flags"] = []
        invoke_foundry(acceptance)
        if acceptance["exit_code"] == 0 and acceptance["payload"].get("running"):
            return
        time.sleep(0.1)
    proc.terminate()
    pytest.fail("foreground job host did not become ready")


@when(parsers.parse('I invoke "run create" with work prompt "{prompt}"'))
def invoke_run_create_with_prompt(acceptance, prompt: str) -> None:
    acceptance["command"] = "run create"
    acceptance["json_output"] = True
    acceptance["markdown_output"] = False
    acceptance["extra_argv"] = ["--work-prompt", prompt]
    acceptance["extra_flags"] = []
    invoke_foundry(acceptance)


def _stop_host_if_needed(acceptance) -> None:
    proc = acceptance.pop("host_proc", None)
    if proc is None:
        return
    acceptance["command"] = "host stop"
    acceptance["json_output"] = True
    acceptance["extra_argv"] = []
    acceptance["extra_flags"] = []
    invoke_foundry(acceptance)
    if acceptance["exit_code"] != 0:
        proc.terminate()
    proc.wait(timeout=15)


@pytest.fixture(autouse=True)
def _job_host_teardown(request):
    acceptance = None
    if "acceptance" in request.fixturenames:
        acceptance = request.getfixturevalue("acceptance")
    yield
    if acceptance is not None:
        _stop_host_if_needed(acceptance)
