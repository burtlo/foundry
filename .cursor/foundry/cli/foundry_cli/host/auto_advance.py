"""Background advancement for non-terminal runs (optional host daemon)."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from foundry_cli.engine.advance import TERMINAL_RUN_STATUSES
from foundry_cli.engine.agent.adapter import AgentAdapter
from foundry_cli.host.auto_advance_status import (
    merge_failures,
    read_auto_advance_status,
    write_auto_advance_status,
)
from foundry_cli.run_service import advance_run_durable
from foundry_cli.run_store import RunStoreError, get_revision, load_snapshot
from foundry_cli.util import now_iso

logger = logging.getLogger(__name__)

_AUTO_ADVANCE_WAIT_KINDS = frozenset({"agent"})
_HUMAN_WAIT_KINDS = frozenset({"decision", "user_input", "operator"})

DEFAULT_INTERVAL_SECONDS = 2.0
MAX_INTERVAL_SECONDS = 30.0
DEFAULT_STEP_BUDGET = 4


def should_auto_advance_snapshot(snapshot: dict[str, Any]) -> bool:
    """Return True when the daemon may call advance_run_durable without human input."""
    status = str(snapshot.get("status") or "")
    if status in TERMINAL_RUN_STATUSES:
        return False
    if status == "paused":
        return False

    wait = snapshot.get("wait")
    if wait is None:
        return True
    if not isinstance(wait, dict):
        return False
    kind = str(wait.get("kind") or "")
    if kind in _HUMAN_WAIT_KINDS:
        return False
    if kind in _AUTO_ADVANCE_WAIT_KINDS:
        return True
    return False


def _wait_kind(snapshot: dict[str, Any]) -> str | None:
    wait = snapshot.get("wait")
    if wait is None:
        return None
    if isinstance(wait, dict):
        kind = wait.get("kind")
        return str(kind) if kind is not None else None
    return None


def _iter_run_directories(workspace: Path) -> list[Path]:
    runs_root = workspace / ".foundry" / "runs"
    if not runs_root.is_dir():
        return []
    return sorted(
        child
        for child in runs_root.iterdir()
        if child.is_dir() and (child / "snapshot.json").is_file()
    )


class AutoAdvanceLoop:
    """Periodically advances runs that do not require human gates or answers."""

    def __init__(
        self,
        *,
        workspace: Path,
        bundle: Path,
        agent_adapter: AgentAdapter | None = None,
        interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
        step_budget: int = DEFAULT_STEP_BUDGET,
        stop_event: threading.Event | None = None,
    ) -> None:
        self.workspace = workspace.resolve()
        self.bundle = bundle.resolve()
        self._agent_adapter = agent_adapter
        self._base_interval = max(0.25, float(interval_seconds))
        self._step_budget = max(1, int(step_budget))
        self._stop_event = stop_event or threading.Event()
        self._thread: threading.Thread | None = None
        self._idle_interval = self._base_interval

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run,
            name="foundry-auto-advance",
            daemon=True,
        )
        self._thread.start()
        write_auto_advance_status(
            self.workspace,
            {
                "running": True,
                "base_interval_seconds": self._base_interval,
                "idle_interval_seconds": self._idle_interval,
                "step_budget": self._step_budget,
                "started_at": now_iso(),
            },
        )
        logger.info(
            "Auto-advance loop started (interval=%.2fs, step_budget=%s)",
            self._base_interval,
            self._step_budget,
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self._base_interval + 5.0)
            self._thread = None
        write_auto_advance_status(
            self.workspace,
            {
                "running": False,
                "stopped_at": now_iso(),
                "base_interval_seconds": self._base_interval,
            },
        )
        logger.info("Auto-advance loop stopped")

    def tick_once(self) -> int:
        """Run one scan; return count of runs advanced successfully."""
        run_dirs = _iter_run_directories(self.workspace)
        progressed = 0
        failures: list[dict[str, Any]] = []
        eligible = 0
        logger.info(
            "Auto-advance tick: scanning %s run(s) (idle_interval=%.2fs)",
            len(run_dirs),
            self._idle_interval,
        )
        for run_dir in run_dirs:
            try:
                snapshot = load_snapshot(run_dir)
            except RunStoreError as exc:
                logger.warning(
                    "Auto-advance skip run_dir=%s: could not load snapshot (%s)",
                    run_dir.name,
                    exc.message,
                )
                failures.append(
                    {
                        "run_id": run_dir.name,
                        "code": exc.code,
                        "message": exc.message,
                        "at": now_iso(),
                    }
                )
                continue
            run_id = str(snapshot.get("run_id") or run_dir.name)
            if not should_auto_advance_snapshot(snapshot):
                logger.debug(
                    "Auto-advance skip run=%s status=%s wait=%s",
                    run_id,
                    snapshot.get("status"),
                    _wait_kind(snapshot),
                )
                continue
            eligible += 1
            revision = get_revision(snapshot)
            wait_kind = _wait_kind(snapshot)
            logger.info(
                "Auto-advance attempting run=%s revision=%s wait=%s",
                run_id,
                revision,
                wait_kind,
            )
            outcome = advance_run_durable(
                workspace=self.workspace,
                bundle=self.bundle,
                run_dir=run_dir,
                expected_revision=revision,
                step_budget=self._step_budget,
                agent_adapter=self._agent_adapter,
            )
            if outcome.get("ok"):
                progressed += 1
                logger.info(
                    "Auto-advance succeeded run=%s revision=%s node=%s wait=%s steps=%s",
                    run_id,
                    outcome.get("revision"),
                    outcome.get("active_node_id"),
                    (outcome.get("wait") or {}).get("kind")
                    if isinstance(outcome.get("wait"), dict)
                    else outcome.get("wait"),
                    outcome.get("steps_taken"),
                )
            else:
                err = outcome.get("error") if isinstance(outcome.get("error"), dict) else {}
                code = str(err.get("code") or "ADVANCE_FAILED")
                message = str(err.get("message") or "advance_run_durable returned not ok")
                logger.warning(
                    "Auto-advance failed run=%s revision=%s code=%s message=%s",
                    run_id,
                    revision,
                    code,
                    message,
                )
                failures.append(
                    {
                        "run_id": run_id,
                        "code": code,
                        "message": message,
                        "revision": revision,
                        "at": now_iso(),
                    }
                )
        prior = read_auto_advance_status(self.workspace)
        write_auto_advance_status(
            self.workspace,
            {
                "running": True,
                "base_interval_seconds": self._base_interval,
                "idle_interval_seconds": self._idle_interval,
                "step_budget": self._step_budget,
                "last_tick_at": now_iso(),
                "runs_scanned": len(run_dirs),
                "runs_eligible": eligible,
                "runs_advanced": progressed,
                "recent_failures": merge_failures(
                    (prior or {}).get("recent_failures")
                    if isinstance((prior or {}).get("recent_failures"), list)
                    else None,
                    failures,
                ),
            },
        )
        logger.info(
            "Auto-advance tick complete: advanced=%s eligible=%s scanned=%s",
            progressed,
            eligible,
            len(run_dirs),
        )
        return progressed

    def _run(self) -> None:
        while not self._stop_event.wait(self._idle_interval):
            try:
                count = self.tick_once()
            except Exception:  # noqa: BLE001 — keep daemon alive
                logger.exception("Auto-advance tick failed")
                count = 0
            if count > 0:
                self._idle_interval = self._base_interval
            else:
                self._idle_interval = min(
                    MAX_INTERVAL_SECONDS,
                    self._idle_interval * 1.5,
                )
