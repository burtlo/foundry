"""Protocol method handlers delegating to run engine and CLI logic."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from foundry_cli.command_context import CommandContext
from foundry_cli.errors import error, ok
from foundry_cli.foundry_config import validate_foundry_config
from foundry_cli.host.protocol import ProtocolError
from foundry_cli.engine.agent.adapter import AgentAdapter
from foundry_cli.run_service import (
    advance_run_durable,
    answer_run_durable,
    cancel_run_durable,
    create_run,
    decide_run_durable,
    execute_start_durable,
    get_run,
    list_runs,
    recover_nonterminal_runs,
    retry_run_durable,
    run_events,
    submit_agent_result_durable,
)
from foundry_cli.util import now_iso

HandlerResult = dict[str, Any]


class HostHandlers:
    def __init__(
        self,
        workspace: Path,
        bundle: Path,
        *,
        on_stop: Callable[[], None] | None = None,
        agent_adapter: AgentAdapter | None = None,
    ) -> None:
        self.workspace = workspace.resolve()
        self.bundle = bundle.resolve()
        self._on_stop = on_stop
        self._agent_adapter = agent_adapter
        self._idempotency: dict[str, dict[str, Any]] = {}

    def dispatch(self, method: str, params: dict[str, Any], request_id: str) -> HandlerResult:
        if method in {"run.advance", "run.agent.submit", "host.stop"}:
            key = str(params.get("idempotency_key"))
            cached = self._idempotency.get(key)
            if cached is not None:
                return cached

        if method in {"run.create", "run.answer", "run.decide", "run.start", "run.retry", "run.cancel"}:
            key = str(params.get("idempotency_key"))
            cached = self._idempotency.get(key)
            if cached is not None:
                return cached

        if method == "health":
            result = self.health()
        elif method == "run.get":
            result = self.run_get(params)
        elif method == "run.list":
            result = self.run_list()
        elif method == "run.events":
            result = self.run_events(params)
        elif method == "run.create":
            result = self.run_create(params)
        elif method == "run.advance":
            result = self.run_advance(params)
        elif method == "run.answer":
            result = self.run_answer(params)
        elif method == "run.decide":
            result = self.run_decide(params)
        elif method == "run.start":
            result = self.run_start(params)
        elif method == "run.retry":
            result = self.run_retry(params)
        elif method == "run.cancel":
            result = self.run_cancel(params)
        elif method == "run.agent.submit":
            result = self.run_agent_submit(params)
        elif method == "host.stop":
            result = self.host_stop()
        else:
            raise ProtocolError("UNKNOWN_METHOD", f"Unknown method {method!r}")

        if method in {"run.advance", "run.agent.submit", "host.stop"}:
            self._idempotency[str(params.get("idempotency_key"))] = result
        if method in {"run.create", "run.answer", "run.decide", "run.start", "run.retry", "run.cancel"}:
            self._idempotency[str(params.get("idempotency_key"))] = result
        return result

    def health(self) -> HandlerResult:
        config = validate_foundry_config(self.workspace)
        return ok(
            status="ready",
            workspace=str(self.workspace),
            registry=str(self.bundle),
            registry_valid=bool(config.get("ok")),
            at=now_iso(),
        )

    def run_get(self, params: dict[str, Any]) -> HandlerResult:
        return get_run(
            self.workspace,
            run_id=params.get("run_id"),
            run_dir=Path(params["run_dir"]).resolve() if params.get("run_dir") else None,
        )

    def run_list(self) -> HandlerResult:
        return list_runs(self.workspace)

    def run_events(self, params: dict[str, Any]) -> HandlerResult:
        after_seq = int(params.get("after_seq") or 0)
        return run_events(
            self.workspace,
            run_id=params.get("run_id"),
            run_dir=Path(params["run_dir"]).resolve() if params.get("run_dir") else None,
            after_seq=after_seq,
        )

    def run_create(self, params: dict[str, Any]) -> HandlerResult:
        return create_run(
            workspace=self.workspace,
            bundle=self.bundle,
            work_prompt=str(params.get("work_prompt") or ""),
            flow_id=params.get("flow_id"),
            run_id=params.get("run_id"),
        )

    def run_advance(self, params: dict[str, Any]) -> HandlerResult:
        step_budget = int(params.get("step_budget") or 8)
        expected = int(params["expected_revision"])
        return advance_run_durable(
            workspace=self.workspace,
            bundle=self.bundle,
            run_id=params.get("run_id"),
            run_dir=Path(params["run_dir"]).resolve() if params.get("run_dir") else None,
            flow_id=params.get("flow_id"),
            expected_revision=expected,
            step_budget=step_budget,
            agent_adapter=self._agent_adapter,
        )

    def run_agent_submit(self, params: dict[str, Any]) -> HandlerResult:
        expected = int(params["expected_revision"])
        result_body = params.get("result")
        if not isinstance(result_body, dict):
            return error("INVALID_REQUEST", "params.result must be an object")
        return submit_agent_result_durable(
            workspace=self.workspace,
            bundle=self.bundle,
            run_id=params.get("run_id"),
            run_dir=Path(params["run_dir"]).resolve() if params.get("run_dir") else None,
            request_id=str(params["request_id"]),
            result=result_body,
            expected_revision=expected,
        )

    def run_answer(self, params: dict[str, Any]) -> HandlerResult:
        expected = int(params["expected_revision"])
        answers = params.get("answers")
        if not isinstance(answers, dict):
            return error("INVALID_REQUEST", "params.answers must be an object")
        normalized = {str(k): str(v) for k, v in answers.items()}
        return answer_run_durable(
            workspace=self.workspace,
            bundle=self.bundle,
            run_id=params.get("run_id"),
            run_dir=Path(params["run_dir"]).resolve() if params.get("run_dir") else None,
            answers=normalized,
            expected_revision=expected,
        )

    def run_decide(self, params: dict[str, Any]) -> HandlerResult:
        expected = int(params["expected_revision"])
        return decide_run_durable(
            workspace=self.workspace,
            bundle=self.bundle,
            run_id=params.get("run_id"),
            run_dir=Path(params["run_dir"]).resolve() if params.get("run_dir") else None,
            decision=str(params["decision"]),
            expected_revision=expected,
        )

    def run_start(self, params: dict[str, Any]) -> HandlerResult:
        expected = int(params["expected_revision"])
        return execute_start_durable(
            workspace=self.workspace,
            bundle=self.bundle,
            run_id=params.get("run_id"),
            run_dir=Path(params["run_dir"]).resolve() if params.get("run_dir") else None,
            expected_revision=expected,
        )

    def run_retry(self, params: dict[str, Any]) -> HandlerResult:
        expected = int(params["expected_revision"])
        reason = params.get("reason")
        return retry_run_durable(
            workspace=self.workspace,
            bundle=self.bundle,
            run_id=params.get("run_id"),
            run_dir=Path(params["run_dir"]).resolve() if params.get("run_dir") else None,
            expected_revision=expected,
            reason=str(reason) if reason is not None else None,
        )

    def run_cancel(self, params: dict[str, Any]) -> HandlerResult:
        expected = int(params["expected_revision"])
        return cancel_run_durable(
            workspace=self.workspace,
            bundle=self.bundle,
            run_id=params.get("run_id"),
            run_dir=Path(params["run_dir"]).resolve() if params.get("run_dir") else None,
            expected_revision=expected,
            reason=str(params.get("reason") or ""),
        )

    def host_stop(self) -> HandlerResult:
        if self._on_stop is not None:
            self._on_stop()
        return ok(stopped=True)

    def startup_recover(self) -> list[dict[str, Any]]:
        return recover_nonterminal_runs(self.workspace, self.bundle)


def resolve_host_context(
    workspace: Path,
    registry: Path | None,
) -> CommandContext | dict[str, Any]:
    import argparse

    args = argparse.Namespace(workspace=str(workspace), registry=str(registry) if registry else None)
    ctx = CommandContext.from_args(args)
    if isinstance(ctx, dict):
        return ctx
    if registry is None:
        config = validate_foundry_config(workspace)
        if not config.get("ok"):
            return error(
                "FOUNDRY_CONFIG_INVALID",
                (config.get("errors") or ["Foundry config validation failed"])[0],
            )
    return ctx
