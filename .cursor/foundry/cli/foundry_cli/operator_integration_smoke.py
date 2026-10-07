"""
Operator integration smoke: judgment bridge (mocked SDK) + HTTP host + shape advance.

Used by ``just integration-smoke`` (`python -m foundry_cli.operator_integration_smoke`) and unit tests.
Does not call the real Cursor API when ``mock_judgment=True`` (default).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from unittest.mock import patch

from foundry_cli.engine.agent.adapter import (
    default_stub_examination_result,
    default_stub_presentation_result,
    default_stub_record_result,
)
from foundry_cli.judgment_bridge.server import DEFAULT_AGENT_PATH, JudgmentBridgeHandler

_CLI_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_BUNDLE = _CLI_ROOT.parent

_HOST_POLL_INTERVAL_S = 0.05
_HOST_POLL_ATTEMPTS = 80
_ADVANCE_POLL_INTERVAL_S = 0.1
_ADVANCE_POLL_ATTEMPTS = 120


def _stub_judgment_response(task_id: str) -> dict[str, Any]:
    mapping: dict[str, dict[str, Any]] = {
        "shape.examine": default_stub_examination_result(),
        "shape.present": default_stub_presentation_result(),
        "shape.record": default_stub_record_result(),
    }
    result = mapping.get(task_id)
    if result is None:
        raise ValueError(f"integration smoke mock does not handle task_id={task_id!r}")
    return {
        "provider_request_id": "integration-smoke-mock",
        "finish_reason": "stop",
        "usage": {},
        "result": result,
    }


def mock_invoke_judgment(
    request: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
) -> dict[str, Any]:
    task_id = str(request.get("task_id") or "")
    return _stub_judgment_response(task_id)


def _integration_workspace(root: Path, bundle: Path) -> Path:
    workspace = root / "app"
    workspace.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        bundle / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
    )
    return workspace


def _run_cli(
    cli_path: Path,
    workspace: Path,
    bundle: Path,
    *argv: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(cli_path),
            "--json",
            "--workspace",
            str(workspace),
            "--registry",
            str(bundle),
            *argv,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _host_running(cli_path: Path, workspace: Path, bundle: Path) -> bool:
    status = _run_cli(cli_path, workspace, bundle, "host", "status")
    if status.returncode != 0:
        return False
    try:
        return bool(json.loads(status.stdout).get("running"))
    except json.JSONDecodeError:
        return False


def _wait_for_host(cli_path: Path, workspace: Path, bundle: Path) -> None:
    for _ in range(_HOST_POLL_ATTEMPTS):
        if _host_running(cli_path, workspace, bundle):
            return
        time.sleep(_HOST_POLL_INTERVAL_S)
    raise RuntimeError("job host did not become ready")


def _wait_for_shape_present_gate(
    cli_path: Path,
    workspace: Path,
    bundle: Path,
    run_id: str,
) -> dict[str, Any]:
    for _ in range(_ADVANCE_POLL_ATTEMPTS):
        get = _run_cli(cli_path, workspace, bundle, "run", "get", "--run", run_id)
        if get.returncode != 0:
            time.sleep(_ADVANCE_POLL_INTERVAL_S)
            continue
        body = json.loads(get.stdout)
        if (
            body.get("active_node_id") == "shape.present.gate"
            and body.get("wait_kind") == "decision"
        ):
            return body
        time.sleep(_ADVANCE_POLL_INTERVAL_S)
    raise RuntimeError(
        f"run {run_id} did not reach shape.present.gate with decision wait "
        f"within {_ADVANCE_POLL_ATTEMPTS * _ADVANCE_POLL_INTERVAL_S:.0f}s"
    )


def _start_bridge(
    workspace: Path,
    bundle: Path,
    *,
    mock_judgment: bool,
) -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    agent_path = DEFAULT_AGENT_PATH

    class Handler(JudgmentBridgeHandler):
        pass

    Handler.workspace = workspace.resolve()
    Handler.foundry_bundle = bundle.resolve()
    Handler.agent_path = agent_path

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = int(server.server_address[1])

    if mock_judgment:
        patch_target = "foundry_cli.judgment_bridge.server.invoke_judgment"

        def serve_with_mock() -> None:
            with patch(patch_target, side_effect=mock_invoke_judgment):
                server.serve_forever()

        thread = threading.Thread(target=serve_with_mock, daemon=True)
    else:
        thread = threading.Thread(target=server.serve_forever, daemon=True)

    thread.start()
    url = f"http://127.0.0.1:{port}{agent_path}"
    return server, thread, url


def run_operator_integration_smoke(
    *,
    workspace: Path | None = None,
    bundle: Path | None = None,
    mock_judgment: bool = True,
    use_auto_advance: bool = True,
    work_prompt: str = "Integration smoke shape path",
) -> dict[str, Any]:
    """
    Run bridge + host + create/advance; return ``{ok, run_id, active_node_id, bridge_url, ...}``.
    """
    bundle = (bundle or _DEFAULT_BUNDLE).resolve()
    cli_path = bundle / "cli" / "foundry.py"
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if workspace is None:
        temp_dir = tempfile.TemporaryDirectory(prefix="foundry-integration-smoke-")
        workspace = _integration_workspace(Path(temp_dir.name), bundle)
    else:
        workspace = workspace.resolve()

    bridge_server: ThreadingHTTPServer | None = None
    host_proc: subprocess.Popen[Any] | None = None
    try:
        bridge_server, _bridge_thread, bridge_url = _start_bridge(
            workspace,
            bundle,
            mock_judgment=mock_judgment,
        )
        host_env = {
            **dict(__import__("os").environ),
            "FOUNDRY_AGENT_ADAPTER": "http",
            "FOUNDRY_AGENT_HTTP_URL": bridge_url,
        }
        host_argv = [
            sys.executable,
            "-m",
            "foundry_cli.host",
            "--workspace",
            str(workspace),
            "--registry",
            str(bundle),
        ]
        if use_auto_advance:
            host_argv.append("--auto-advance")
        host_proc = subprocess.Popen(
            host_argv,
            cwd=str(bundle / "cli"),
            env=host_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _wait_for_host(cli_path, workspace, bundle)

        create = _run_cli(
            cli_path,
            workspace,
            bundle,
            "run",
            "create",
            "--work-prompt",
            work_prompt,
        )
        if create.returncode != 0:
            return {
                "ok": False,
                "code": "RUN_CREATE_FAILED",
                "message": create.stderr or create.stdout,
            }
        run_id = str(json.loads(create.stdout).get("run_id") or "")
        if not run_id:
            return {"ok": False, "code": "RUN_CREATE_FAILED", "message": "missing run_id"}

        advance = _run_cli(cli_path, workspace, bundle, "run", "advance", "--run", run_id)
        if advance.returncode != 0:
            return {
                "ok": False,
                "code": "RUN_ADVANCE_FAILED",
                "message": advance.stderr or advance.stdout,
                "run_id": run_id,
            }

        final = _wait_for_shape_present_gate(cli_path, workspace, bundle, run_id)
        status = _run_cli(cli_path, workspace, bundle, "host", "status")
        host_status = json.loads(status.stdout) if status.returncode == 0 else {}

        return {
            "ok": True,
            "run_id": run_id,
            "active_node_id": final.get("active_node_id"),
            "wait_kind": final.get("wait_kind"),
            "revision": final.get("revision"),
            "bridge_url": bridge_url,
            "auto_advance": use_auto_advance,
            "mock_judgment": mock_judgment,
            "host_auto_advance": host_status.get("auto_advance"),
        }
    finally:
        if host_proc is not None:
            stop = _run_cli(cli_path, workspace, bundle, "host", "stop")
            if stop.returncode != 0:
                host_proc.terminate()
            host_proc.wait(timeout=20)
        if bridge_server is not None:
            bridge_server.shutdown()
        if temp_dir is not None:
            temp_dir.cleanup()


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Foundry operator integration smoke")
    parser.add_argument(
        "--workspace",
        help="Application workspace (default: ephemeral copy of foundry-test fixture)",
    )
    parser.add_argument("--registry", help="Foundry bundle root")
    parser.add_argument(
        "--real-cursor",
        action="store_true",
        help="Use real Cursor SDK on the bridge (requires FOUNDRY_CURSOR_API_KEY)",
    )
    parser.add_argument(
        "--no-auto-advance",
        action="store_true",
        help="Start host without --auto-advance",
    )
    args = parser.parse_args(argv)
    workspace = Path(args.workspace).resolve() if args.workspace else None
    bundle = Path(args.registry).resolve() if args.registry else None
    result = run_operator_integration_smoke(
        workspace=workspace,
        bundle=bundle,
        mock_judgment=not args.real_cursor,
        use_auto_advance=not args.no_auto_advance,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
