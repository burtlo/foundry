"""Host-only RPC client for the Foundry Textual TUI."""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path
from typing import Any

from foundry_cli.host.client import call_host
from foundry_cli.host.discovery import host_is_running
from foundry_cli.host_commands import cmd_host_start


def open_clarifying_questions(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Return open clarifying questions from a run.context JSON packet."""
    reads = context.get("reads") if isinstance(context.get("reads"), dict) else {}
    state = reads.get("state") if isinstance(reads.get("state"), dict) else {}
    questions = state.get("clarifying_questions")
    if not isinstance(questions, list):
        return []
    open_items: list[dict[str, Any]] = []
    for item in questions:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "open")).lower()
        if status in ("resolved", "answered", "closed"):
            continue
        qid = item.get("id")
        if qid is None:
            continue
        open_items.append(item)
    return open_items


def gate_options(context: dict[str, Any]) -> list[str]:
    produces = context.get("produces") if isinstance(context.get("produces"), dict) else {}
    raw = produces.get("options")
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if item is not None and str(item).strip()]


class HostClient:
    """Thin wrapper over ``call_host`` for TUI screens."""

    def __init__(self, workspace: Path, *, registry: str | None = None) -> None:
        self.workspace = workspace.resolve()
        self.registry = registry

    def running(self) -> bool:
        return host_is_running(self.workspace)

    def start_host(self, *, auto_advance: bool = False) -> dict[str, Any]:
        args = argparse.Namespace(
            workspace=str(self.workspace),
            registry=self.registry,
            auto_advance=auto_advance,
            auto_advance_interval=2.0,
        )
        return cmd_host_start(args)

    def _call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return call_host(self.workspace, method, params or {})

    def list_runs(self) -> dict[str, Any]:
        return self._call("run.list", {})

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self._call("run.get", {"run_id": run_id})

    def run_context_json(self, run_id: str) -> dict[str, Any]:
        return self._call("run.context", {"run_id": run_id, "format": "json"})

    def run_context_markdown(self, run_id: str) -> dict[str, Any]:
        return self._call("run.context", {"run_id": run_id, "format": "markdown"})

    def run_events(
        self,
        run_id: str,
        *,
        after_seq: int = 0,
        block_ms: int = 0,
    ) -> dict[str, Any]:
        return self._call(
            "run.events",
            {"run_id": run_id, "after_seq": after_seq, "block_ms": block_ms},
        )

    def advance(
        self,
        run_id: str,
        *,
        expected_revision: int,
        step_budget: int = 8,
    ) -> dict[str, Any]:
        return self._call(
            "run.advance",
            {
                "run_id": run_id,
                "expected_revision": expected_revision,
                "step_budget": step_budget,
                "idempotency_key": str(uuid.uuid4()),
            },
        )

    def decide(
        self,
        run_id: str,
        *,
        decision: str,
        expected_revision: int,
    ) -> dict[str, Any]:
        return self._call(
            "run.decide",
            {
                "run_id": run_id,
                "decision": decision,
                "expected_revision": expected_revision,
                "idempotency_key": str(uuid.uuid4()),
            },
        )

    def answer(
        self,
        run_id: str,
        *,
        answers: dict[str, str],
        expected_revision: int,
    ) -> dict[str, Any]:
        return self._call(
            "run.answer",
            {
                "run_id": run_id,
                "answers": answers,
                "expected_revision": expected_revision,
                "idempotency_key": str(uuid.uuid4()),
            },
        )

    def start_execute(
        self,
        run_id: str,
        *,
        expected_revision: int,
    ) -> dict[str, Any]:
        return self._call(
            "run.start",
            {
                "run_id": run_id,
                "expected_revision": expected_revision,
                "idempotency_key": str(uuid.uuid4()),
            },
        )
