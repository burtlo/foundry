"""Socket timeouts for job host RPC clients."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from foundry_cli.engine.agent.tasks import max_judgment_task_timeout_seconds
from foundry_cli.foundry_config import resolve_registry_bundle
from foundry_cli.host_config import advance_client_section, load_host_config

# Default for read-only / fast host methods (health, run.get, run.events, …).
DEFAULT_HOST_CLIENT_TIMEOUT_SECONDS = 30.0

# Per agent round inside one run.advance: adapter HTTP + host accept + follow-up advance slice.
_DEFAULT_PER_AGENT_ROUND_SLACK_SECONDS = 15.0

# Connection and JSON framing overhead for a single RPC.
_DEFAULT_BASE_RPC_SLACK_SECONDS = 10.0

_DEFAULT_ADVANCE_STEP_BUDGET = 8

_FALLBACK_JUDGMENT_MAX_SECONDS = 300

_ENV_JUDGMENT_MAX = "FOUNDRY_HOST_CLIENT_JUDGMENT_MAX_SECONDS"
_ENV_BASE_SLACK = "FOUNDRY_HOST_CLIENT_BASE_SLACK_SECONDS"
_ENV_PER_ROUND_SLACK = "FOUNDRY_HOST_CLIENT_PER_ROUND_SLACK_SECONDS"
_ENV_CLIENT_MAX = "FOUNDRY_HOST_CLIENT_MAX_SECONDS"


def _resolve_bundle(workspace: Path | None) -> Path | None:
    if workspace is None:
        return None
    try:
        bundle, _source = resolve_registry_bundle(workspace.resolve())
        return bundle
    except (FileNotFoundError, ValueError, OSError):
        return None


def _float_env(name: str) -> float | None:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _resolve_judgment_max_seconds(bundle: Path | None, host_config: dict[str, Any]) -> int:
    env_max = _float_env(_ENV_JUDGMENT_MAX)
    if env_max is not None:
        return max(1, int(env_max))
    advance = advance_client_section(host_config)
    yaml_max = advance.get("judgment_max_seconds")
    if yaml_max is not None:
        try:
            return max(1, int(yaml_max))
        except (TypeError, ValueError):
            pass
    if bundle is not None:
        return max_judgment_task_timeout_seconds(bundle)
    return _FALLBACK_JUDGMENT_MAX_SECONDS


def _resolve_base_slack(host_config: dict[str, Any]) -> float:
    env_val = _float_env(_ENV_BASE_SLACK)
    if env_val is not None:
        return max(0.0, env_val)
    advance = advance_client_section(host_config)
    yaml_val = advance.get("base_slack_seconds")
    if yaml_val is not None:
        try:
            return max(0.0, float(yaml_val))
        except (TypeError, ValueError):
            pass
    return _DEFAULT_BASE_RPC_SLACK_SECONDS


def _resolve_per_round_slack(host_config: dict[str, Any]) -> float:
    env_val = _float_env(_ENV_PER_ROUND_SLACK)
    if env_val is not None:
        return max(0.0, env_val)
    advance = advance_client_section(host_config)
    yaml_val = advance.get("per_round_slack_seconds")
    if yaml_val is not None:
        try:
            return max(0.0, float(yaml_val))
        except (TypeError, ValueError):
            pass
    return _DEFAULT_PER_AGENT_ROUND_SLACK_SECONDS


def _resolve_client_max_cap(host_config: dict[str, Any]) -> float | None:
    env_val = _float_env(_ENV_CLIENT_MAX)
    if env_val is not None:
        return max(1.0, env_val)
    advance = advance_client_section(host_config)
    yaml_val = advance.get("max_seconds")
    if yaml_val is not None:
        try:
            return max(1.0, float(yaml_val))
        except (TypeError, ValueError):
            pass
    return None


def client_timeout_for_run_advance(
    params: dict[str, Any],
    *,
    workspace: Path | None = None,
    bundle: Path | None = None,
) -> float:
    """
    Client socket timeout for a single run.advance host call.

    One advance may run up to step_budget agent dispatch rounds; each round may use
    the longest judgment task timeout in the registry plus host overhead.
    """
    resolved_bundle = bundle if bundle is not None else _resolve_bundle(workspace)
    host_config = load_host_config(workspace, bundle=resolved_bundle)

    raw_budget = params.get("step_budget")
    try:
        step_budget = int(raw_budget) if raw_budget is not None else _DEFAULT_ADVANCE_STEP_BUDGET
    except (TypeError, ValueError):
        step_budget = _DEFAULT_ADVANCE_STEP_BUDGET
    if step_budget < 1:
        step_budget = 1

    judgment_max = _resolve_judgment_max_seconds(resolved_bundle, host_config)
    base_slack = _resolve_base_slack(host_config)
    per_round_slack = _resolve_per_round_slack(host_config)
    per_round = float(judgment_max) + per_round_slack
    computed = base_slack + (step_budget * per_round)

    hint = params.get("client_timeout_hint_seconds")
    if hint is not None:
        try:
            computed = max(computed, float(hint))
        except (TypeError, ValueError):
            pass

    cap = _resolve_client_max_cap(host_config)
    if cap is not None:
        computed = min(computed, cap)

    return computed


def client_timeout_for_method(
    method: str,
    params: dict[str, Any] | None,
    *,
    workspace: Path | None = None,
    bundle: Path | None = None,
) -> float:
    """Resolve socket read timeout for a host control-plane method."""
    body = params if isinstance(params, dict) else {}
    if method == "run.advance":
        return client_timeout_for_run_advance(body, workspace=workspace, bundle=bundle)
    if method == "run.events":
        try:
            block_ms = int(body.get("block_ms") or 0)
        except (TypeError, ValueError):
            block_ms = 0
        block_ms = max(0, min(block_ms, 120_000))
        return DEFAULT_HOST_CLIENT_TIMEOUT_SECONDS + (block_ms / 1000.0) + 2.0
    return DEFAULT_HOST_CLIENT_TIMEOUT_SECONDS
