"""
Foundry CLI — deterministic state engine for Software Factory v2.

The parent agent drives every run through this CLI. Subagents never call it.

    python "{factory_root}/.cursor/foundry/cli/foundry.py" <command> ...

Run context: `cli resolve` (pre-run), `run init` / `run context` / `flow orchestrator-packet`
(return `foundry_cli` plus `state_path`, `config_path`, `run_dir`, …).

Stdout is JSON. Non-zero exit includes errorCode / message / recoverable, the
same envelope the v1 `foundry.py` uses.

Step order, gates, and skip rules live in `flows/factory-flow.yaml`. Nothing in
this file hardcodes the pipeline; it only enforces the registry.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

try:
    import yaml
except ImportError:  # pragma: no cover - dependency guard
    yaml = None

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - dependency guard
    Draft202012Validator = None

import foundry_invoke  # noqa: E402
import foundry_handoff  # noqa: E402
import foundry_app  # noqa: E402
import foundry_context  # noqa: E402
import foundry_integrations  # noqa: E402
import foundry_lineage  # noqa: E402
import foundry_outcome  # noqa: E402
import foundry_protocol  # noqa: E402
import foundry_store  # noqa: E402
import foundry_tickets  # noqa: E402

SCHEMA_VERSION = foundry_protocol.PROTOCOL_VERSION
FACTORY_VERSION = "foundry"

FOUNDRY_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = FOUNDRY_ROOT.parents[1]
SCHEMAS_DIR = FOUNDRY_ROOT / "schemas"
DEFAULT_FLOW_PATH = FOUNDRY_ROOT / "flows" / "factory-flow.yaml"
DEFAULT_DIAGRAM_PATH = FOUNDRY_ROOT / "flows" / "factory-flow.generated.mmd"
DEFAULT_PROFILE_PATH = FOUNDRY_ROOT / "profiles" / "default.yaml"
FACTORY_CONFIG_SCHEMA_PATH = SCHEMAS_DIR / "factory-config.schema.json"
SHARED_MECHANICS_PATH = Path(__file__).resolve().parent / "foundry_mechanics.py"

STEP_ID_RE = re.compile(r"^[a-z]+\.[a-z_]+$")

SCHEMA_ALIASES = {
    "run-state": "factory-run-state.schema.json",
    "state": "factory-run-state.schema.json",
    "event": "factory-event.schema.json",
    "receipt": "agent-receipt.schema.json",
    "execution-graph": "execution-graph.schema.json",
    "flow": "factory-flow.schema.json",
    "config": "factory-config.schema.json",
    "app-manifest": "app-manifest.schema.json",
    "ticket": "packets/ticket.schema.json",
    "craft": "packets/agent-craft.schema.json",
    "agent-craft": "packets/agent-craft.schema.json",
    "worker-launch": "packets/worker-launch-packet.schema.json",
    "resume": "packets/resume-packet.schema.json",
    "handoff": "packets/handoff.schema.json",
    "outcome": "outcome-observation.schema.json",
}

CONFIG_ROLES = (
    "parent",
    "backend-builder",
    "client-builder",
    "feature-builder",
    "devops-builder",
    "documentation-writer",
    "story-writer",
    "codebase-researcher",
    "implementation-validator",
    "build-with-tests",
    "ticket-workflow",
    "documentation-workflow",
)

GATE_DECISIONS_SATISFYING = {"approve", "post", "edit", "skip", "accept_risk", "pass"}
HUMAN_GATE_KINDS = frozenset({"human_approval", "human_confirm", "two_turn_stop"})
GATE_MANAGED_STATE_SUFFIXES = frozenset(
    {
        "approved",
        "human_approved",
        "gate_decision",
        "gate_outcome",
        "gate_presented",
        "gate_presented_at",
        "gate_resolved",
        "gate_source",
    }
)
VALIDATOR_GAP_DECISIONS = frozenset({"accept_gaps", "pass_with_gaps", "approve_with_gaps"})
PRE_PR_RISK_DECISIONS = frozenset({"accept_risk"})
ORCHESTRATION_STEP_ID = "implement.build"
BUILD_STEP_VERIFY_COMMAND = "build-step verify"
TOOLING_FAILURE_COMMANDS = frozenset(
    {
        "build-step",
        "transition",
        "build",
        "test",
        "delivery-check",
        "graph",
        "worker",
        "observability",
    }
)
AUTO_BLOCK_ERROR_CODES = frozenset(
    {
        "BUILD_FAILED",
        "TEST_FAILED",
        "BUILD_VERIFY_NOT_RUN",
        "BUILD_VERIFY_RECEIPT_FORGED",
        "BUILD_VERIFY_MISSING",
        "CLI_EVIDENCE_MISSING",
        "ORCHESTRATION_ANOMALY",
        "RECEIPT_PROVENANCE_INVALID",
        "RECEIPT_PARENT_AUTHORED",
        "RECEIPT_STAGING_MISMATCH",
        "INVALID_RECEIPT",
        "RECEIPT_TELEMETRY_FORBIDDEN",
        "RECEIPT_SEMANTIC_INVALID",
        "LAUNCH_ID_REQUIRED",
        "LAUNCH_ID_UNKNOWN",
        "BUILD_GRAPH_INCOMPLETE",
        "BUILD_DELEGATION_UNPROVEN",
        "BUILD_STEP_RECEIPT_INVALID",
        "BUILD_ITEM_INCOMPLETE",
        "BUILD_RECEIPT_INVALID",
        "BUILD_RECEIPT_THIN",
        "COMMAND_FAILED",
        "POST_REPAIR_NOT_RUN",
    }
)
DEFAULT_ORCHESTRATOR_SETTINGS = {
    "strict_mode": True,
    "stop_on_tooling_failure": True,
    "stop_on_receipt_anomaly": True,
    "forbid_parent_app_edits": True,
    "thin_context": True,
    "allow_force_unblock": False,
    "allow_raw_dotnet_commands": False,
}


class FoundryError(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        recoverable: bool = True,
        required_input: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.recoverable = recoverable
        self.required_input = required_input
        self.extra = extra or {}


def emit_success(payload: dict[str, Any]) -> int:
    sys.stdout.write(json.dumps({"success": True, **payload}, indent=2) + "\n")
    return 0


def emit_error(exc: FoundryError) -> int:
    payload: dict[str, Any] = {
        "success": False,
        "errorCode": exc.error_code,
        "message": exc.message,
        "recoverable": exc.recoverable,
    }
    if exc.required_input:
        payload["requiredInput"] = exc.required_input
    payload.update(exc.extra)
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return 1


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def cli_exit_code(result: dict[str, Any]) -> int:
    value = result.get("exitCode")
    if value is None:
        value = result.get("exit_code")
    if value is None:
        return 1
    return int(value)


def orchestrator_settings(config: dict[str, Any] | None) -> dict[str, bool]:
    raw = {}
    if isinstance(config, dict):
        foundry_cfg = resolve_path(config, ["foundry"]) or {}
        if isinstance(foundry_cfg, dict) and isinstance(foundry_cfg.get("orchestrator"), dict):
            raw = foundry_cfg["orchestrator"]
    strict = bool(raw.get("strict_mode", DEFAULT_ORCHESTRATOR_SETTINGS["strict_mode"]))

    def flag(key: str) -> bool:
        default = bool(DEFAULT_ORCHESTRATOR_SETTINGS[key])
        value = bool(raw.get(key, default))
        if key in ("stop_on_tooling_failure", "stop_on_receipt_anomaly"):
            return strict and value
        return value

    return {
        "strict_mode": strict,
        "stop_on_tooling_failure": flag("stop_on_tooling_failure"),
        "stop_on_receipt_anomaly": flag("stop_on_receipt_anomaly"),
        "forbid_parent_app_edits": flag("forbid_parent_app_edits"),
        "thin_context": flag("thin_context"),
        "allow_force_unblock": flag("allow_force_unblock"),
        "allow_raw_dotnet_commands": flag("allow_raw_dotnet_commands"),
        "strict_receipts": strict and flag("stop_on_receipt_anomaly"),
    }


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def resolve_path(root: Any, parts: list[str]) -> Any:
    """Dotted lookup that prefers the longest literal key.

    `steps` is keyed by dotted step IDs, so `steps.implement.build.status`
    must resolve `steps["implement.build"]["status"]`.
    """
    if not parts:
        return root
    if not isinstance(root, dict):
        return None
    for size in range(len(parts), 0, -1):
        key = ".".join(parts[:size])
        if key in root:
            return resolve_path(root[key], parts[size:])
    return None


def nested_set(target: dict[str, Any], dotted: str, value: Any) -> None:
    """Set a dotted key, reusing an existing longest-prefix key when present."""
    parts = dotted.split(".")
    for size in range(len(parts), 1, -1):
        key = ".".join(parts[:size])
        if key in target and size < len(parts):
            child = target[key]
            if isinstance(child, dict):
                nested_set(child, ".".join(parts[size:]), value)
                return
    head, rest = parts[0], parts[1:]
    if not rest:
        target[head] = value
        return
    child = target.setdefault(head, {})
    if not isinstance(child, dict):
        raise FoundryError("INVALID_STATE_KEY", f"Cannot descend into {head!r} for {dotted!r}.")
    nested_set(child, ".".join(rest), value)


def coerce_scalar(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def read_json(path: Path, error_code: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FoundryError(error_code, f"Could not read JSON at {path}: {exc}") from exc


def load_shared_mechanics() -> Any:
    """Load Foundry mechanical helpers (issue-key, git, build/test, config slice)."""
    spec = importlib.util.spec_from_file_location("foundry_mechanics", SHARED_MECHANICS_PATH)
    if spec is None or spec.loader is None:
        raise FoundryError("MISSING_SHARED_CLI", f"Could not import mechanics at {SHARED_MECHANICS_PATH}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SHARED_MECHANICS = load_shared_mechanics()


def call_shared(function_name: str, *args: Any, **kwargs: Any) -> Any:
    try:
        return getattr(SHARED_MECHANICS, function_name)(*args, **kwargs)
    except SHARED_MECHANICS.FactoryError as exc:
        raise FoundryError(
            exc.error_code,
            exc.message,
            recoverable=exc.recoverable,
            required_input=exc.required_input,
            extra=exc.extra,
        ) from exc


# --------------------------------------------------------------------------
# Expression language
# --------------------------------------------------------------------------

TOKEN_RE = re.compile(
    r"""\s*(?:
        (?P<op>&&|\|\||==|!=|<=|>=|<|>|!|\(|\))
      | (?P<number>-?\d+(?:\.\d+)?)
      | (?P<string>'[^']*'|"[^"]*")
      | (?P<ident>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)
    )""",
    re.VERBOSE,
)

KEYWORD_LITERALS = {"always": True, "true": True, "false": False, "null": None}


def tokenize(text: str) -> list[tuple[str, Any]]:
    tokens: list[tuple[str, Any]] = []
    pos = 0
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
            continue
        match = TOKEN_RE.match(text, pos)
        if not match:
            raise FoundryError("INVALID_EXPRESSION", f"Unparsable token at offset {pos} in {text!r}.")
        pos = match.end()
        if match.group("op"):
            tokens.append(("op", match.group("op")))
        elif match.group("number") is not None:
            raw = match.group("number")
            tokens.append(("lit", float(raw) if "." in raw else int(raw)))
        elif match.group("string") is not None:
            tokens.append(("lit", match.group("string")[1:-1]))
        else:
            ident = match.group("ident")
            if ident in KEYWORD_LITERALS:
                tokens.append(("lit", KEYWORD_LITERALS[ident]))
            else:
                tokens.append(("path", ident))
    return tokens


class _Parser:
    def __init__(self, tokens: list[tuple[str, Any]], source: str) -> None:
        self.tokens = tokens
        self.source = source
        self.index = 0

    def peek(self) -> tuple[str, Any] | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def take(self) -> tuple[str, Any]:
        token = self.peek()
        if token is None:
            raise FoundryError("INVALID_EXPRESSION", f"Unexpected end of expression {self.source!r}.")
        self.index += 1
        return token

    def accept_op(self, *ops: str) -> str | None:
        token = self.peek()
        if token and token[0] == "op" and token[1] in ops:
            self.index += 1
            return token[1]
        return None

    def parse(self) -> tuple:
        node = self.parse_or()
        if self.peek() is not None:
            raise FoundryError("INVALID_EXPRESSION", f"Trailing tokens in expression {self.source!r}.")
        return node

    def parse_or(self) -> tuple:
        node = self.parse_and()
        while self.accept_op("||"):
            node = ("or", node, self.parse_and())
        return node

    def parse_and(self) -> tuple:
        node = self.parse_not()
        while self.accept_op("&&"):
            node = ("and", node, self.parse_not())
        return node

    def parse_not(self) -> tuple:
        if self.accept_op("!"):
            return ("not", self.parse_not())
        return self.parse_cmp()

    def parse_cmp(self) -> tuple:
        left = self.parse_primary()
        op = self.accept_op("==", "!=", "<=", ">=", "<", ">")
        if op is None:
            return left
        return ("cmp", op, left, self.parse_primary())

    def parse_primary(self) -> tuple:
        if self.accept_op("("):
            node = self.parse_or()
            if not self.accept_op(")"):
                raise FoundryError("INVALID_EXPRESSION", f"Missing ')' in expression {self.source!r}.")
            return node
        kind, value = self.take()
        if kind in ("lit", "path"):
            return (kind, value)
        raise FoundryError("INVALID_EXPRESSION", f"Unexpected token {value!r} in {self.source!r}.")


def parse_expression(text: str) -> tuple:
    return _Parser(tokenize(text), text).parse()


def evaluate(node: tuple, context: dict[str, Any]) -> Any:
    kind = node[0]
    if kind == "lit":
        return node[1]
    if kind == "path":
        return resolve_path(context, node[1].split("."))
    if kind == "not":
        return not evaluate(node[1], context)
    if kind == "and":
        return bool(evaluate(node[1], context)) and bool(evaluate(node[2], context))
    if kind == "or":
        return bool(evaluate(node[1], context)) or bool(evaluate(node[2], context))
    if kind == "cmp":
        _, op, left_node, right_node = node
        left = evaluate(left_node, context)
        right = evaluate(right_node, context)
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if left is None or right is None:
            return False
        try:
            if op == "<":
                return left < right
            if op == "<=":
                return left <= right
            if op == ">":
                return left > right
            return left >= right
        except TypeError:
            return False
    raise FoundryError("INVALID_EXPRESSION", f"Unknown expression node {kind!r}.")


def truthy(expression: str, context: dict[str, Any]) -> bool:
    return bool(evaluate(parse_expression(expression), context))


def build_context(
    state: dict[str, Any],
    config: dict[str, Any],
    decision: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    context: dict[str, Any] = {"config": config, "state": state, "decision": decision}
    context.update(extra)
    return context


# --------------------------------------------------------------------------
# Config and registry loading
# --------------------------------------------------------------------------


def require_yaml() -> None:
    if yaml is None:
        raise FoundryError(
            "MISSING_DEPENDENCY",
            "PyYAML is required. pip install -r .cursor/foundry/cli/requirements.txt",
            required_input="pyyaml",
        )


def require_jsonschema() -> None:
    if Draft202012Validator is None:
        raise FoundryError(
            "MISSING_DEPENDENCY",
            "jsonschema is required. pip install -r .cursor/foundry/cli/requirements.txt",
            required_input="jsonschema",
        )


def resolve_profile_path(path: str | Path | None, factory_root: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    if factory_root is not None:
        candidate = Path(factory_root) / ".cursor" / "foundry" / "profiles" / DEFAULT_PROFILE_PATH.name
        if candidate.is_file():
            return candidate
    return DEFAULT_PROFILE_PATH


def load_config(
    path: str | Path | None,
    *,
    factory_root: str | Path | None = None,
) -> dict[str, Any]:
    """Load, validate, default, and path-resolve one Foundry team profile."""
    config_path = resolve_profile_path(path, factory_root)
    if not config_path.is_file():
        raise FoundryError("MISSING_CONFIG", f"Config not found: {config_path}", required_input="config")
    text = config_path.read_text(encoding="utf-8")
    if config_path.suffix == ".json":
        data = json.loads(text)
    else:
        require_yaml()
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise FoundryError("INVALID_CONFIG", f"Config at {config_path} is not a mapping.")
    if "profile_version" not in data or "team" not in data:
        require_yaml()
        baseline = yaml.safe_load(DEFAULT_PROFILE_PATH.read_text(encoding="utf-8"))
        if not isinstance(baseline, dict):
            raise FoundryError("INVALID_CONFIG", f"Default profile at {DEFAULT_PROFILE_PATH} is not a mapping.")
        data = deep_merge(baseline, data)
    require_jsonschema()
    schema = read_json(FACTORY_CONFIG_SCHEMA_PATH, "MISSING_SCHEMA")
    errors = [
        f"{'/'.join(str(p) for p in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(Draft202012Validator(schema).iter_errors(data), key=str)
    ]
    if errors:
        raise FoundryError(
            "CONFIG_INVALID",
            f"{config_path} failed factory-config.schema.json: {len(errors)} error(s)",
            extra={"errors": errors, "profile": str(config_path)},
        )
    resolved = call_shared("apply_defaults", data)
    root = Path(factory_root).resolve() if factory_root else REPO_ROOT
    resolved = call_shared("resolve_template_paths", resolved, root)
    return normalize_intake_config(resolved)


def normalize_intake_config(config: dict[str, Any]) -> dict[str, Any]:
    """Ensure intake.source is jira|local|chat; default from jira.enabled."""
    intake = config.get("intake")
    if not isinstance(intake, dict):
        intake = {}
        config["intake"] = intake
    source = intake.get("source")
    if source not in ("jira", "local", "chat"):
        jira = config.get("jira") if isinstance(config.get("jira"), dict) else {}
        source = "jira" if jira.get("enabled", True) else "chat"
        intake["source"] = source
    intake.setdefault("tickets_root", "tickets")
    jira = config.setdefault("jira", {})
    if isinstance(jira, dict):
        jira["enabled"] = source == "jira"
    return config


def intake_source_of(config: dict[str, Any]) -> str:
    intake = config.get("intake") if isinstance(config.get("intake"), dict) else {}
    source = intake.get("source")
    if source in ("jira", "local", "chat"):
        return str(source)
    jira = config.get("jira") if isinstance(config.get("jira"), dict) else {}
    return "jira" if jira.get("enabled", True) else "chat"


def profile_hash(config: dict[str, Any]) -> str:
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def slice_config(
    config: dict[str, Any],
    role: str,
    *,
    app_folder: str | None,
    factory_root: str | None,
) -> dict[str, Any]:
    if role not in CONFIG_ROLES:
        raise FoundryError(
            "UNKNOWN_ROLE",
            f"Unknown role: {role}",
            required_input="role",
            extra={"knownRoles": list(CONFIG_ROLES)},
        )
    return call_shared(
        "slice_role",
        config,
        role,
        app_folder=app_folder,
        factory_root=factory_root,
    )


def config_get(
    *,
    factory_root: str,
    role: str,
    app_folder: str | None,
    profile_path: str | None,
) -> dict[str, Any]:
    root = Path(factory_root).resolve()
    config = load_config(profile_path, factory_root=root)
    packet = slice_config(
        config,
        role,
        app_folder=app_folder,
        factory_root=str(root),
    )
    packet["resolved_profile_hash"] = profile_hash(config)
    return packet


def load_registry(path: str | Path | None = None) -> dict[str, Any]:
    require_yaml()
    flow_path = Path(path) if path else DEFAULT_FLOW_PATH
    if not flow_path.is_file():
        raise FoundryError("MISSING_FLOW", f"Flow registry not found: {flow_path}", required_input="flow")
    data = yaml.safe_load(flow_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise FoundryError("INVALID_FLOW", f"Flow registry at {flow_path} is not a mapping.")
    data["_path"] = str(flow_path)
    return data


def get_flow(registry: dict[str, Any], run_mode: str) -> dict[str, Any]:
    flow = (registry.get("flows") or {}).get(run_mode)
    if not isinstance(flow, dict):
        raise FoundryError(
            "UNKNOWN_FLOW",
            f"No flow defined for run_mode {run_mode!r}.",
            required_input="runMode",
        )
    return flow


def get_step(flow: dict[str, Any], step_id: str) -> dict[str, Any]:
    step = (flow.get("steps") or {}).get(step_id)
    if not isinstance(step, dict):
        raise FoundryError(
            "UNKNOWN_STEP",
            f"Step {step_id!r} is not defined in this flow.",
            required_input="stepId",
            extra={"knownSteps": sorted((flow.get("steps") or {}).keys())},
        )
    return step


def parse_step_id(step_id: str) -> dict[str, str]:
    """Infer phase from dotted step ID (first segment before '.')."""
    text = str(step_id or "").strip()
    if not text:
        return {"phase": "", "step": ""}
    if "." not in text:
        return {"phase": text, "step": ""}
    phase, step = text.split(".", 1)
    return {"phase": phase, "step": step}


def step_title(step: dict[str, Any]) -> str | None:
    """Human-readable step label from the flow registry."""
    title = step.get("title")
    if isinstance(title, str) and title.strip():
        return title
    meta = step.get("metadata")
    if isinstance(meta, dict) and isinstance(meta.get("title"), str):
        return meta["title"]
    return None


def step_metadata(step: dict[str, Any]) -> dict[str, Any]:
    """Backward-compatible display accessor (title only)."""
    title = step_title(step)
    return {"title": title} if title else {}


def step_message(step: dict[str, Any], kind: str) -> str | None:
    """Read intro.message or outro.message from the step registry."""
    block = step.get(kind)
    if isinstance(block, dict) and isinstance(block.get("message"), str):
        return block["message"]
    if kind == "outro":
        meta = step.get("metadata")
        if isinstance(meta, dict) and isinstance(meta.get("handoff_blurb"), str):
            return meta["handoff_blurb"]
        legacy = step.get("handoff_blurb")
        if isinstance(legacy, str):
            return legacy
    return None


def step_state_json_permissions(step: dict[str, Any]) -> list[str]:
    """Dot-path keys in {run_dir}/state.json this step may write via transition --set or receipt state_patch."""
    state_json = step.get("state_json")
    if isinstance(state_json, dict):
        return [str(key) for key in (state_json.get("permissions") or [])]
    run_state = step.get("run_state")
    if isinstance(run_state, dict):
        return [str(key) for key in (run_state.get("writes") or [])]
    legacy = step.get("state")
    if isinstance(legacy, dict):
        return [str(key) for key in (legacy.get("owns") or [])]
    return []


def step_run_state_writes(step: dict[str, Any]) -> list[str]:
    """Backward-compatible alias for step_state_json_permissions."""
    return step_state_json_permissions(step)


WORKER_RECEIPT_KIND = "worker"
INTAKE_RECEIPT_KIND = "intake"
VALID_RECEIPT_KINDS = frozenset({WORKER_RECEIPT_KIND, INTAKE_RECEIPT_KIND})
WORKER_RECEIPT_SCHEMA = "schemas/agent-receipt.schema.json"
INTAKE_RECEIPT_SCHEMA = "schemas/intake-receipt.schema.json"


def step_instructions(step: dict[str, Any]) -> str | None:
    """Path to the steward/worker instruction markdown for this step."""
    instructions = step.get("instructions")
    if isinstance(instructions, str) and instructions.strip():
        return instructions.strip()
    unit = step.get("unit")
    if isinstance(unit, str) and unit.strip():
        return unit.strip()
    return None


def step_worker(step: dict[str, Any]) -> dict[str, str] | None:
    """Worker binding when this step launches a Task subagent."""
    worker = step.get("worker")
    if isinstance(worker, dict):
        prompt = worker.get("prompt")
        contract = worker.get("contract")
        mode = worker.get("mode")
        if (
            isinstance(prompt, str)
            and prompt.strip()
            and isinstance(contract, str)
            and contract.strip()
            and isinstance(mode, str)
            and mode.strip()
        ):
            prompt = prompt.strip()
            contract = contract.strip()
            mode = mode.strip()
            agent = foundry_protocol.contract_id_from_path(contract)
            return {
                "prompt": prompt,
                "contract": contract,
                "mode": mode,
                "agent": agent,
            }
        agent = worker.get("agent")
        mode = worker.get("mode")
        if isinstance(agent, str) and agent.strip() and isinstance(mode, str) and mode.strip():
            agent = agent.strip()
            mode = mode.strip()
            return {
                "prompt": f"agents/{agent}.md",
                "contract": f"contracts/{agent}.yaml",
                "mode": mode,
                "agent": agent,
            }
        return None
    subagent = step.get("subagent")
    if subagent in (None, "", False):
        return None
    mode = step.get("subagent_mode")
    if not isinstance(mode, str) or not mode.strip():
        return None
    agent = str(subagent)
    return {
        "prompt": f"agents/{agent}.md",
        "contract": f"contracts/{agent}.yaml",
        "mode": mode.strip(),
        "agent": agent,
    }


def step_worker_agent(step: dict[str, Any]) -> str | None:
    worker = step_worker(step)
    return worker["agent"] if worker else None


def step_worker_mode(step: dict[str, Any]) -> str | None:
    worker = step_worker(step)
    return worker["mode"] if worker else None


def step_worker_prompt(step: dict[str, Any]) -> str | None:
    worker = step_worker(step)
    return worker["prompt"] if worker else None


def step_worker_contract(step: dict[str, Any]) -> str | None:
    worker = step_worker(step)
    return worker["contract"] if worker else None


def step_has_worker(step: dict[str, Any]) -> bool:
    return step_worker(step) is not None


def _normalize_receipt_path(value: str) -> str:
    text = str(value).strip().replace("\\", "/")
    if text == INTAKE_RECEIPT_KIND:
        return INTAKE_RECEIPT_SCHEMA
    if text == WORKER_RECEIPT_KIND:
        return WORKER_RECEIPT_SCHEMA
    return text


def step_receipt_schemas(step: dict[str, Any]) -> list[str]:
    """Receipt JSON Schema paths required before leaving this step."""
    paths: list[str] = []
    receipts = step.get("receipts")
    if isinstance(receipts, str) and receipts.strip():
        paths.append(_normalize_receipt_path(receipts))
    elif isinstance(receipts, list):
        for item in receipts:
            text = str(item).strip()
            if text:
                paths.append(_normalize_receipt_path(text))
    elif step_has_worker(step):
        paths.append(WORKER_RECEIPT_SCHEMA)
    if step.get("receipt_required") is True and WORKER_RECEIPT_SCHEMA not in paths:
        paths.append(WORKER_RECEIPT_SCHEMA)
    if step.get("intake_receipt_required") is True and INTAKE_RECEIPT_SCHEMA not in paths:
        paths.append(INTAKE_RECEIPT_SCHEMA)
    return list(dict.fromkeys(paths))


def step_receipt_kinds(step: dict[str, Any]) -> set[str]:
    """Backward-compatible receipt kind names derived from schema paths."""
    kinds: set[str] = set()
    for path in step_receipt_schemas(step):
        if path == INTAKE_RECEIPT_SCHEMA:
            kinds.add(INTAKE_RECEIPT_KIND)
        elif path == WORKER_RECEIPT_SCHEMA:
            kinds.add(WORKER_RECEIPT_KIND)
    return kinds


def worker_receipt_required(step: dict[str, Any]) -> bool:
    return WORKER_RECEIPT_SCHEMA in step_receipt_schemas(step)


def intake_receipt_required(step: dict[str, Any]) -> bool:
    return INTAKE_RECEIPT_SCHEMA in step_receipt_schemas(step)


def outgoing_edges(flow: dict[str, Any], step_id: str) -> list[dict[str, Any]]:
    edges = [edge for edge in (flow.get("edges") or []) if edge.get("from") == step_id]
    return sorted(edges, key=lambda edge: (-int(edge.get("priority", 0)), str(edge.get("to"))))


def edge_matches(edge: dict[str, Any], context: dict[str, Any]) -> bool:
    when = edge.get("when")
    if when in (None, "", "always"):
        return True
    return truthy(str(when), context)


def step_evidence(state: dict[str, Any], step_id: str) -> dict[str, Any]:
    evidence = (state.get("steps") or {}).get(step_id)
    return evidence if isinstance(evidence, dict) else {}


def skip_reasons(step: dict[str, Any], context: dict[str, Any]) -> list[str]:
    return [expr for expr in (step.get("when_skip") or []) if truthy(str(expr), context)]


def unmet_requires(step: dict[str, Any], context: dict[str, Any]) -> list[str]:
    return [expr for expr in (step.get("requires") or []) if not truthy(str(expr), context)]


def gate_blockers(step_id: str, step: dict[str, Any], context: dict[str, Any]) -> list[str]:
    """Reasons the run may not leave `step_id` yet."""
    gate = step.get("gate")
    if not isinstance(gate, dict):
        return []
    evidence = step_evidence(context["state"], step_id)
    if evidence.get("status") == "skipped":
        return []
    require = gate.get("require")
    if require:
        return [expr for expr in require if not truthy(str(expr), context)]
    kind = gate.get("kind")
    if kind == "human_approval":
        ok = evidence.get("human_approved") is True
    elif kind == "human_confirm":
        ok = (
            evidence.get("approved") is True
            or evidence.get("gate_decision") in GATE_DECISIONS_SATISFYING
        )
    elif kind == "two_turn_stop":
        ok = evidence.get("human_approved") is True and evidence.get("gate_decision") is not None
    elif kind == "evidence_only":
        # No human evidence to wait on. Machine enforcement lives on the
        # successors, which carry `require_delivery_check`.
        ok = True
    else:
        ok = True
    return [] if ok else [f"gate {kind} on {step_id} is unresolved"]


# --------------------------------------------------------------------------
# Run state
# --------------------------------------------------------------------------


FOUNDRY_CLI_SCRIPT = Path(__file__).resolve()


def resolve_foundry_script(factory_root: str | None = None) -> Path:
    if factory_root:
        candidate = Path(factory_root).resolve() / ".cursor" / "foundry" / "cli" / "foundry.py"
        if candidate.is_file():
            return candidate
    return FOUNDRY_CLI_SCRIPT


def resolve_foundry_launcher(cli_dir: Path) -> Path | None:
    if sys.platform == "win32":
        candidate = cli_dir / "foundry.ps1"
    else:
        candidate = cli_dir / "foundry.sh"
    return candidate if candidate.is_file() else None


def resolve_foundry_cli(factory_root: str | None = None) -> str:
    """Copy-pasteable Shell-tool prefix for foundry.py (launcher when present)."""
    script = resolve_foundry_script(factory_root)
    launcher = resolve_foundry_launcher(script.parent)
    if launcher is not None:
        return foundry_invoke.format_launcher_cli(launcher)
    return foundry_invoke.format_foundry_cli(sys.executable, script)


def format_foundry_command(foundry_cli: str, tail: str) -> str:
    tail = tail.strip()
    if not tail:
        return foundry_cli
    return f"{foundry_cli} {tail}"


def run_context(state_path: Path) -> dict[str, Any]:
    state = load_state(state_path)
    run_directory = state_path.parent
    resolved_factory_root = str(state.get("factory_root") or REPO_ROOT)
    return {
        "foundry_cli": resolve_foundry_cli(resolved_factory_root),
        "factory_root": resolved_factory_root,
        "app_folder": str(state.get("app_folder") or ""),
        "state_path": str(state_path.resolve()),
        "config_path": str((run_directory / "config.json").resolve()),
        "run_dir": str(run_directory.resolve()),
        "run_id": str(state.get("run_id") or ""),
        "app_manifest_path": str(
            (run_directory / foundry_app.RUN_MANIFEST_FILENAME).resolve()
        ),
        "app_manifest_id": state.get("app_manifest_id"),
        "app_manifest_hash": state.get("app_manifest_hash"),
        "app_manifest_platform": state.get("app_manifest_platform"),
        "issue_key": state.get("issue_key"),
        "current_step": str(state.get("current_step") or ""),
    }


def cli_resolve(factory_root: str | None) -> dict[str, Any]:
    resolved = str(Path(factory_root).resolve()) if factory_root else str(REPO_ROOT)
    script = resolve_foundry_script(resolved)
    return {
        "foundry_cli": resolve_foundry_cli(resolved),
        "factory_root": resolved,
        "script_path": str(script),
    }


def run_dir(app_folder: Path, run_id: str) -> Path:
    return app_folder / ".foundry" / "runs" / run_id


def load_state(path: Path) -> dict[str, Any]:
    data = read_json(path, "INVALID_STATE")
    if not isinstance(data, dict):
        raise FoundryError("INVALID_STATE", "Run state must be a JSON object.")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise FoundryError(
            "UNSUPPORTED_PROTOCOL_VERSION",
            f"Run state must use Foundry protocol {SCHEMA_VERSION}; found {data.get('schema_version')!r}.",
            recoverable=False,
        )
    return data


def write_state(path: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    expected_revision = (
        int(state["state_revision"])
        if "state_revision" in state
        else foundry_store.read_revision(path)
    )
    try:
        foundry_store.write_state_cas(path, state, expected_revision=expected_revision)
    except foundry_store.StoreError as exc:
        raise FoundryError(exc.error_code, exc.message, extra=exc.extra) from exc


def load_run_config(
    state_path: Path,
    state: dict[str, Any],
    override_path: str | None,
) -> dict[str, Any]:
    resolved_path: str | Path | None = override_path
    stored_path = state_path.parent / "config.json"
    if resolved_path is None and stored_path.is_file():
        resolved_path = stored_path
    if resolved_path is None and state.get("resolved_profile_hash"):
        raise FoundryError(
            "MISSING_RESOLVED_PROFILE",
            f"Resolved run profile not found: {stored_path}",
            required_input="config",
        )
    config = load_config(
        resolved_path,
        factory_root=state.get("factory_root"),
    )
    expected = state.get("resolved_profile_hash")
    actual = profile_hash(config)
    if expected and actual != expected:
        raise FoundryError(
            "PROFILE_HASH_MISMATCH",
            "Resolved profile does not match the hash recorded at run init.",
            extra={"expected": expected, "actual": actual},
        )
    return config


def append_event(events_path: Path, event: dict[str, Any]) -> None:
    state_path = events_path.parent / "state.json"
    if "transaction_id" not in event and state_path.is_file():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            transaction_id = state.get("last_transaction_id")
            if isinstance(transaction_id, str):
                event["transaction_id"] = transaction_id
        except json.JSONDecodeError:
            pass
    try:
        foundry_store.append_jsonl(events_path, event)
    except foundry_store.StoreError as exc:
        raise FoundryError(exc.error_code, exc.message, extra=exc.extra) from exc


def make_event(
    run_id: str,
    event_type: str,
    actor: str,
    *,
    step_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(uuid.uuid4()),
        "run_id": run_id,
        "timestamp": now_iso(),
        "event_type": event_type,
        "actor": actor,
    }
    if step_id is not None:
        event["step_id"] = step_id
    if payload is not None:
        event["payload"] = payload
    return event


def resolve_entry_step(
    flow: dict[str, Any],
    context: dict[str, Any],
) -> tuple[str, list[str]]:
    """Walk past entry steps whose `when_skip` matches. Returns (step_id, skipped)."""
    current = flow.get("entry")
    if not isinstance(current, str):
        raise FoundryError("INVALID_FLOW", "Flow is missing an `entry` step.")
    skipped: list[str] = []
    for _ in range(len(flow.get("steps") or {}) + 1):
        step = get_step(flow, current)
        if not skip_reasons(step, context):
            return current, skipped
        skipped.append(current)
        following = [
            edge for edge in outgoing_edges(flow, current) if edge_matches(edge, context)
        ]
        if not following:
            raise FoundryError(
                "FLOW_DEAD_END",
                f"Entry step {current!r} is skipped and has no matching outgoing edge.",
            )
        current = str(following[0]["to"])
    raise FoundryError("FLOW_CYCLE", "Entry resolution exceeded the step count; check when_skip rules.")


def run_init(
    *,
    app_folder: str,
    issue_key: str | None,
    run_mode: str,
    factory_root: str | None,
    config_path: str | None,
    developer_first_name: str | None,
    risk_tier: str,
    flow_path: str | None,
    run_id: str | None,
    interaction_mode: str | None = None,
    ticket_file: str | None = None,
    ticket_text: str | None = None,
    ticket_source_override: str | None = None,
    start_point: str | None = None,
) -> dict[str, Any]:
    app = Path(app_folder).resolve()
    if not app.is_dir():
        raise FoundryError("MISSING_APP_FOLDER", f"App folder not found: {app}", required_input="appFolder")

    manifest_context = call_app(
        "validate_app_manifest",
        app,
        run_mode=run_mode,
    )
    registry = load_registry(flow_path)
    resolved_factory_root = str(Path(factory_root).resolve()) if factory_root else str(REPO_ROOT)
    config = load_config(config_path, factory_root=resolved_factory_root)
    ticket_source = intake_source_of(config)
    sealed_ticket: dict[str, Any] | None = None

    if ticket_file or ticket_text:
        try:
            if ticket_file:
                sealed_ticket = foundry_tickets.ingest_ticket(
                    file=Path(ticket_file),
                    source=ticket_source_override or "local_file",
                )
            else:
                sealed_ticket = foundry_tickets.ingest_ticket(
                    text=ticket_text,
                    issue_key=issue_key,
                    source=ticket_source_override or "paste",
                )
        except foundry_tickets.TicketError as exc:
            raise FoundryError(
                exc.error_code,
                exc.message,
                required_input=exc.required_input,
            ) from exc
        issue_key = str(sealed_ticket["id"])
        ticket_source = "paste" if sealed_ticket["source"] == "paste" else "local"
        if sealed_ticket["source"] == "jira":
            ticket_source = "jira"

    jira = config.get("jira") if isinstance(config.get("jira"), dict) else {}
    pattern = jira.get("issue_key_pattern") if ticket_source == "jira" else None

    try:
        foundry_tickets.validate_issue_key_for_source(
            issue_key,
            ticket_source=ticket_source,
            pattern=pattern if isinstance(pattern, str) else None,
        )
    except foundry_tickets.TicketError as exc:
        raise FoundryError(
            exc.error_code,
            exc.message,
            required_input=exc.required_input,
        ) from exc

    # Auto-seal from tickets_root when local intake + issue_key and no explicit ingest
    if sealed_ticket is None and ticket_source == "local" and issue_key:
        intake = config.get("intake") if isinstance(config.get("intake"), dict) else {}
        try:
            root = foundry_tickets.resolve_tickets_root(
                app_folder=str(app),
                factory_root=resolved_factory_root,
                tickets_root=intake.get("tickets_root") if isinstance(intake.get("tickets_root"), str) else None,
            )
            candidate = root / f"{issue_key}.md"
            if candidate.is_file():
                sealed_ticket = foundry_tickets.ingest_ticket(file=candidate, source="local_file")
        except foundry_tickets.TicketError as exc:
            raise FoundryError(
                exc.error_code,
                exc.message,
                required_input=exc.required_input,
            ) from exc

    flow = get_flow(registry, run_mode)

    resolved_mode = interaction_mode
    if not resolved_mode:
        foundry_cfg = config.get("foundry") if isinstance(config.get("foundry"), dict) else {}
        orch = foundry_cfg.get("orchestrator") if isinstance(foundry_cfg.get("orchestrator"), dict) else {}
        resolved_mode = orch.get("default_interaction_mode") or "interactive"
    if resolved_mode not in foundry_handoff.INTERACTION_MODES:
        raise FoundryError(
            "INVALID_INTERACTION_MODE",
            f"interaction_mode must be one of {foundry_handoff.INTERACTION_MODES}",
            required_input="interactionMode",
        )

    resolved_run_id = run_id or str(uuid.uuid4())
    timestamp = now_iso()
    state: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": resolved_run_id,
        "factory_version": FACTORY_VERSION,
        "run_mode": run_mode,
        "interaction_mode": resolved_mode,
        "current_step": flow["entry"],
        "issue_key": issue_key,
        "ticket_source": ticket_source,
        "app_folder": str(app),
        "factory_root": resolved_factory_root,
        "resolved_profile_hash": profile_hash(config),
        "app_manifest_id": manifest_context["app_manifest_id"],
        "app_manifest_hash": manifest_context["app_manifest_hash"],
        "app_manifest_platform": manifest_context["platform"],
        "risk_tier": risk_tier,
        "risk_tier_source": "auto",
        "steps": {},
        "pr_extras_register": [],
        "receipt_ids": [],
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    if developer_first_name:
        state["developer_first_name"] = developer_first_name
    resolved_start_point = (start_point or "").strip() or None
    if resolved_start_point:
        state["start_point"] = resolved_start_point
    if sealed_ticket is not None:
        state["ticket_sealed"] = True
        state["ticket_path"] = "ticket.json"

    entry, skipped = resolve_entry_step(flow, build_context(state, config))
    for step_id in skipped:
        state["steps"][step_id] = {"status": "skipped", "completed_at": timestamp}
    state["current_step"] = entry
    state["steps"][entry] = {"status": "in_progress", "started_at": timestamp}

    directory = run_dir(app, resolved_run_id)
    state_path = directory / "state.json"
    if state_path.exists():
        raise FoundryError("RUN_EXISTS", f"Run state already exists: {state_path}", required_input="runId")
    (directory / "receipts").mkdir(parents=True, exist_ok=True)
    manifest_snapshot_path = call_app(
        "write_run_manifest_snapshot",
        directory,
        manifest_context["manifest"],
    )
    resolved_config_path = directory / "config.json"
    resolved_config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    if sealed_ticket is not None:
        foundry_tickets.seal_ticket_to_run(directory, sealed_ticket)
    write_state(state_path, state)
    events_path = directory / "events.jsonl"
    events_path.touch()
    append_event(
        events_path,
        make_event(
            resolved_run_id,
            "run_started",
            "engine",
            step_id=entry,
            payload={
                "run_mode": run_mode,
                "interaction_mode": resolved_mode,
                "factory_version": FACTORY_VERSION,
                "resolved_profile_hash": state["resolved_profile_hash"],
                "app_manifest_id": state["app_manifest_id"],
                "app_manifest_hash": state["app_manifest_hash"],
                "app_manifest_platform": state["app_manifest_platform"],
                "skipped": skipped,
                "ticket_sealed": sealed_ticket is not None,
                "start_point": resolved_start_point,
            },
        ),
    )
    payload = {
        "run_id": resolved_run_id,
        "run_dir": str(directory),
        "state_path": str(state_path),
        "config_path": str(resolved_config_path),
        "app_manifest_path": str(manifest_snapshot_path),
        "events_path": str(events_path),
        "current_step": entry,
        "interaction_mode": resolved_mode,
        "skipped_entry_steps": skipped,
        "ticket_path": str(directory / "ticket.json") if sealed_ticket is not None else None,
        "start_point": resolved_start_point,
    }
    payload.update(run_context(state_path))
    return payload


def resolve_state_path(state: str | None, app_folder: str | None, run_id: str | None) -> Path:
    if state:
        return Path(state)
    if app_folder and run_id:
        return run_dir(Path(app_folder).resolve(), run_id) / "state.json"
    raise FoundryError(
        "MISSING_STATE",
        "Pass --state, or both --app-folder and --run-id.",
        required_input="state",
    )


def run_show(state_path: Path) -> dict[str, Any]:
    state = load_state(state_path)
    steps = state.get("steps") or {}
    return {
        "run_id": state.get("run_id"),
        "factory_version": state.get("factory_version"),
        "run_mode": state.get("run_mode"),
        "interaction_mode": state.get("interaction_mode"),
        "current_step": state.get("current_step"),
        "issue_key": state.get("issue_key"),
        "feature_branch": state.get("feature_branch"),
        "risk_tier": state.get("risk_tier"),
        "resolved_profile_hash": state.get("resolved_profile_hash"),
        "app_manifest_id": state.get("app_manifest_id"),
        "app_manifest_hash": state.get("app_manifest_hash"),
        "app_manifest_platform": state.get("app_manifest_platform"),
        "blocked": state.get("blocked"),
        "rework": state.get("rework"),
        "pr_extras_count": len(state.get("pr_extras_register") or []),
        "resolved_pr_title": state.get("resolved_pr_title"),
        "pr_url": state.get("pr_url"),
        "receipt_count": len(state.get("receipt_ids") or []),
        "step_evidence": {
            step_id: {
                key: value
                for key, value in evidence.items()
                if key
                in (
                    "status",
                    "approved",
                    "human_approved",
                    "report",
                    "gate_decision",
                    "gate_source",
                    "receipt_id",
                )
            }
            for step_id, evidence in sorted(steps.items())
        },
    }


def run_is_blocked(state: dict[str, Any]) -> dict[str, Any] | None:
    blocked = state.get("blocked")
    if isinstance(blocked, dict) and blocked.get("reason"):
        return blocked
    return None


def assert_run_not_blocked(
    state: dict[str, Any],
    config: dict[str, Any] | None,
    *,
    force: bool = False,
) -> None:
    blocked = run_is_blocked(state)
    if blocked is None:
        return
    settings = orchestrator_settings(config)
    if force and settings["allow_force_unblock"]:
        return
    raise FoundryError(
        "RUN_BLOCKED",
        f"Run is blocked: {blocked.get('reason')}",
        extra={"blocked": blocked, "allow_force_unblock": settings["allow_force_unblock"]},
    )


def run_block(
    state_path: Path,
    *,
    reason: str,
    step_id: str | None = None,
) -> dict[str, Any]:
    state = load_state(state_path)
    existing = run_is_blocked(state)
    current_step = str(step_id or state.get("current_step") or "")
    if existing is not None:
        return {"blocked": existing, "already_blocked": True, "state_path": str(state_path)}
    blocked = {
        "reason": reason,
        "step_id": current_step,
        "since": now_iso(),
    }
    state["blocked"] = blocked
    write_state(state_path, state)
    append_event(
        state_path.parent / "events.jsonl",
        make_event(
            str(state["run_id"]),
            "blocked",
            "engine",
            step_id=current_step or None,
            payload={"reason": reason, "step_id": current_step},
        ),
    )
    return {"blocked": blocked, "already_blocked": False, "state_path": str(state_path)}


def run_unblock(
    state_path: Path,
    *,
    decision: str,
) -> dict[str, Any]:
    state = load_state(state_path)
    previous = run_is_blocked(state)
    if previous is None:
        raise FoundryError("RUN_NOT_BLOCKED", "Run is not blocked.")
    state.pop("blocked", None)
    write_state(state_path, state)
    append_event(
        state_path.parent / "events.jsonl",
        make_event(
            str(state["run_id"]),
            "unblocked",
            "human",
            step_id=str(previous.get("step_id") or state.get("current_step") or "") or None,
            payload={"decision": decision, "previous": previous},
        ),
    )
    return {"blocked": None, "decision": decision, "previous": previous, "state_path": str(state_path)}


def maybe_auto_block_on_failure(
    state_path: Path | None,
    *,
    command: str,
    error_code: str,
    message: str,
    config: dict[str, Any] | None,
) -> None:
    if state_path is None or config is None:
        return
    settings = orchestrator_settings(config)
    if not settings["stop_on_tooling_failure"]:
        return
    root = command.split()[0] if command else ""
    command_matches = root in TOOLING_FAILURE_COMMANDS or command in TOOLING_FAILURE_COMMANDS
    if not command_matches:
        return
    if (
        root in ("build-step", "build", "test", "observability")
        or command == "observability"
        or error_code in AUTO_BLOCK_ERROR_CODES
    ):
        try:
            run_block(
                state_path,
                reason=f"{error_code}: {message}. Run metrics classify if this is a rework loop.",
            )
        except FoundryError:
            pass


def is_build_step_verify_event(event: dict[str, Any]) -> bool:
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    command = str(payload.get("command") or "")
    argv = payload.get("argv") if isinstance(payload.get("argv"), list) else []
    haystack = f"{command} {' '.join(str(part) for part in argv)}".lower()
    return "build-step" in haystack and "verify" in haystack


def latest_successful_build_step_verify_event(
    events: list[dict[str, Any]],
    *,
    step_id: str = ORCHESTRATION_STEP_ID,
    started_at: str | None = None,
) -> dict[str, Any] | None:
    match: dict[str, Any] | None = None
    for event in events:
        if event.get("event_type") != "cli_invoked":
            continue
        if event.get("step_id") not in (None, step_id):
            continue
        if not is_build_step_verify_event(event):
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if cli_exit_code(payload) != 0:
            continue
        timestamp = str(event.get("timestamp") or "")
        if started_at and timestamp and timestamp < started_at:
            continue
        match = event
    return match


def log_step_cli(
    state_path: Path,
    state: dict[str, Any],
    config: dict[str, Any],
    *,
    command: str,
    argv: list[str],
    exit_code: int,
    extra: dict[str, Any] | None = None,
) -> None:
    settings = observability_settings(config)
    call_observability(
        "log_cli_invoked",
        run_id=str(state["run_id"]),
        events_path=state_path.parent / "events.jsonl",
        command=command,
        argv=argv,
        append_event=append_event,
        make_event=make_event,
        emit_events=settings["emit_events"],
        step_id=str(state.get("current_step")),
        exit_code=exit_code,
        extra=extra,
    )


# --------------------------------------------------------------------------
# flow current / next
# --------------------------------------------------------------------------


def flow_current(state_path: Path, config_path: str | None, flow_path: str | None) -> dict[str, Any]:
    state = load_state(state_path)
    registry = load_registry(flow_path)
    config = load_run_config(state_path, state, config_path)
    flow = get_flow(registry, str(state.get("run_mode")))
    step_id = str(state.get("current_step"))
    step = get_step(flow, step_id)
    context = build_context(state, config)
    gate = step.get("gate") if isinstance(step.get("gate"), dict) else None
    gate_prompt = None
    if gate and gate.get("prompt_key"):
        gate_prompt = (registry.get("gates") or {}).get(gate["prompt_key"], {}).get("prompt")
    step_parts = parse_step_id(step_id)
    payload = {
        "run_id": state.get("run_id"),
        "run_mode": state.get("run_mode"),
        "step_id": step_id,
        "phase": step_parts["phase"] or None,
        "step": step_parts["step"] or None,
        "title": step_title(step),
        "instructions": step_instructions(step),
        "unit": str(FOUNDRY_ROOT / step_instructions(step))
        if step_instructions(step)
        else None,
        "unit_relative": step_instructions(step),
        "worker": step_worker(step),
        "receipts": step_receipt_schemas(step),
        "subagent": step_worker_agent(step),
        "subagent_mode": step_worker_mode(step),
        "blocked": run_is_blocked(state),
        "inputs": step.get("inputs") or [],
        "delivery_gate": bool(step.get("delivery_gate")),
        "requires_delivery_check": bool(step.get("require_delivery_check")),
        "state_json_permissions": step_state_json_permissions(step),
        "owns_state_keys": step_state_json_permissions(step),
        "intro": step_message(step, "intro"),
        "outro": step_message(step, "outro"),
        "skip_reasons": skip_reasons(step, context),
        "unmet_requires": unmet_requires(step, context),
        "gate": None
        if gate is None
        else {
            "kind": gate.get("kind"),
            "prompt_key": gate.get("prompt_key"),
            "prompt": gate_prompt,
            "options": (registry.get("gates") or {})
            .get(gate.get("prompt_key") or "", {})
            .get("options", []),
            "blocks": gate.get("blocks") or [],
            "unresolved": gate_blockers(step_id, step, context),
        },
    }
    if step_worker_agent(step):
        role = str(step_worker_agent(step))
        if role not in CONFIG_ROLES:
            role = "parent"
        packet = slice_config(
            config,
            role,
            app_folder=str(state.get("app_folder")),
            factory_root=str(state.get("factory_root")),
        )
        packet["resolved_profile_hash"] = state.get("resolved_profile_hash") or profile_hash(config)
        payload["factory_config"] = packet
    if step_id == ORCHESTRATION_STEP_ID:
        graph_path = state_path.parent / "execution-graph.json"
        payload["orchestration"] = {
            "kind": "execution_graph_work_items",
            "graph_path": str(graph_path) if graph_path.is_file() else None,
            "commands": [
                "graph ready",
                "worker next-builder",
                "worker builder-packet",
                "worker launch-packet --work-item",
                "observability subagent complete --launch-id",
                "worker complete-item",
                "build-step verify",
            ],
        }
    return payload


def orchestrator_next_argv_tails(step_id: str, state_path: Path) -> list[str]:
    state_arg = "{state_path}"
    graph = "{run_dir}/execution-graph.json"
    config_arg = "{config_path}"
    common = [
        f'flow orchestrator-packet --state "{state_arg}" --config "{config_arg}"',
        f'run handoff --state "{state_arg}"',
        f'run block --state "{state_arg}" --reason "..." --step-id {step_id}',
        f'run integrity-check --state "{state_arg}"',
    ]
    by_step: dict[str, list[str]] = {
        "intake.local": [
            'ticket list --app-folder "{app_folder}"',
            'ticket load --file "{tickets_root}/{id}.md"',
            'ticket pick --app-folder "{app_folder}" --selection {n_or_id}',
            'ticket ingest --file "{tickets_root}/{id}.md"',
            'ticket save --tickets-root "{tickets_root}" --stdin',
            f'transition --state "{state_arg}" --to intake.pivot --config "{config_arg}"',
        ],
        "intake.jira": [
            f'transition --state "{state_arg}" --to intake.pivot --config "{config_arg}"',
        ],
        "intake.free_text": [
            'ticket ingest --text "..." --issue-key {id}',
            f'transition --state "{state_arg}" --to intake.pivot --config "{config_arg}"',
        ],
        "intake.pivot": [
            f'transition --state "{state_arg}" --to intake.refine --config "{config_arg}"',
        ],
        "intake.refine": [
            f'worker launch-packet --state "{state_arg}" --config "{config_arg}"',
            f'observability subagent complete --state "{state_arg}" --receipt "{{craft_staging_path}}" --launch-id {{launch_id}} --config "{config_arg}"',
            f'transition --state "{state_arg}" --to intake.grill --config "{config_arg}"',
        ],
        "intake.grill": [
            f'worker launch-packet --state "{state_arg}" --config "{config_arg}"',
            f'observability subagent complete --state "{state_arg}" --receipt "{{craft_staging_path}}" --launch-id {{launch_id}} --config "{config_arg}"',
            f'gate resolve --state "{state_arg}" --config "{config_arg}" --source human --decision approve',
            f'gate resolve --state "{state_arg}" --config "{config_arg}" --source auto --decision approve',
            f'transition --state "{state_arg}" --to intake.present_ac --config "{config_arg}"',
        ],
        "intake.present_ac": [
            f'transition --state "{state_arg}" --to intake.approve_ac --config "{config_arg}"',
        ],
        "intake.approve_ac": [
            f'transition --state "{state_arg}" --to plan.research --config "{config_arg}"',
        ],
        ORCHESTRATION_STEP_ID: [
            f'worker next-builder --state "{state_arg}" --graph "{graph}" --config "{config_arg}"',
            f'build-step verify --state "{state_arg}" --graph "{graph}" --config "{config_arg}"',
            f'worker launch-packet --state "{state_arg}" --agent {{owner}} --mode implement --work-item {{id}} --config "{config_arg}"',
            f'observability subagent complete --state "{state_arg}" --receipt "{{craft_staging_path}}" --launch-id {{launch_id}} --config "{config_arg}"',
        ],
    }
    tails = list(common)
    tails.extend(by_step.get(step_id, [f'transition --state "{state_arg}" --to {{next_step}} --config "{config_arg}"']))
    return tails


def steward_allowlist_for_step(
    step_id: str,
    state_path: Path,
    *,
    task_subagent_type: str | None,
    unit_relative: str | None,
) -> dict[str, Any]:
    tails = orchestrator_next_argv_tails(step_id, state_path)
    prefixes: list[list[str]] = []
    for tail in tails:
        # First tokens of argv tail (ignore placeholders values)
        parts = []
        for token in tail.replace('"', "").split():
            if token.startswith("{") or token.startswith("--"):
                if token.startswith("--"):
                    break
                continue
            parts.append(token)
            if len(parts) >= 3:
                break
        if parts:
            prefixes.append(parts)
    run_directory = "{run_dir}"
    read_paths = [
        f"{run_directory}/ticket.json",
        f"{run_directory}/handoff.md",
        f"{run_directory}/state.json",
        f"{run_directory}/presented_ac.json",
    ]
    if unit_relative:
        read_paths.append(unit_relative)
    return {
        "shell_argv_prefixes": prefixes,
        "task_subagent_type": task_subagent_type,
        "read_paths": read_paths,
        "write_paths": [],
        "ask_question": True,
    }


def orchestrator_next_invocations(
    step_id: str,
    state_path: Path,
    foundry_cli: str,
    context: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        foundry_invoke.render_foundry_invoke(tail, foundry_cli, context)
        for tail in orchestrator_next_argv_tails(step_id, state_path)
    ]


def orchestrator_next_commands(step_id: str, state_path: Path, foundry_cli: str) -> list[str]:
    context = run_context(state_path)
    return [item["shell"] for item in orchestrator_next_invocations(step_id, state_path, foundry_cli, context)]


def flow_orchestrator_packet(
    state_path: Path,
    config_path: str | None,
    flow_path: str | None,
) -> dict[str, Any]:
    current = flow_current(state_path, config_path, flow_path)
    state = load_state(state_path)
    launches = state.get("open_subagent_launches") or []
    if not isinstance(launches, list):
        launches = []
    forbidden = [
        "app_source_edits",
        "hand_written_receipts",
        "invent_transition_target",
        "load_full_events_jsonl",
        "load_all_receipts",
        "parent_write_brief_md",
        "parent_write_execution_graph_json",
    ]
    config = load_run_config(state_path, state, config_path)
    settings = orchestrator_settings(config)
    if not settings["allow_raw_dotnet_commands"]:
        forbidden.append("raw_dotnet")
    if settings.get("forbid_parent_app_edits"):
        forbidden.append("Write_StrReplace_under_app_folder_except_run_dir")
    ctx = run_context(state_path)
    foundry_cli = str(ctx["foundry_cli"])
    step_id = str(current.get("step_id"))
    run_directory = state_path.parent
    registry = load_registry(flow_path)
    flow = get_flow(registry, str(state.get("run_mode")))
    step_meta = get_step(flow, step_id)
    gate_policy = foundry_handoff.gate_policy_for_step(
        step_id, state, config, step_meta, run_directory
    )
    has_subagent = bool(
        current.get("subagent") or step_has_worker(step_meta) or step_id in ("plan.brief", "plan.graph", "intake.grill")
    )
    # Planner owns brief and graph authorship
    if step_id == "plan.brief":
        current = {**current, "subagent": "planner", "subagent_mode": "brief"}
        has_subagent = True
    if step_id == "plan.graph" and state.get("risk_tier") == "low":
        current = {**current, "subagent": None, "subagent_mode": None}
        has_subagent = False
    elif step_id == "plan.graph" and not current.get("subagent"):
        current = {**current, "subagent": "planner", "subagent_mode": "plan"}
        has_subagent = True
    if step_id == "intake.grill":
        has_subagent = True
    task_type = current.get("subagent")
    allowlist = steward_allowlist_for_step(
        step_id,
        state_path,
        task_subagent_type=str(task_type) if task_type else None,
        unit_relative=current.get("unit_relative"),
    )
    packet = {
        **ctx,
        "step_title": current.get("title"),
        "unit_relative": current.get("unit_relative"),
        "task_subagent_type": current.get("subagent"),
        "subagent_mode": current.get("subagent_mode") or current.get("subagent_mode"),
        "blocked": current.get("blocked"),
        "gate": current.get("gate"),
        "interaction_mode": foundry_handoff.interaction_mode_of(state, config),
        "gate_policy": gate_policy,
        "session_stop_hint": foundry_handoff.session_stop_hint(
            step_id, gate_policy, has_subagent=has_subagent
        ),
        "valid_intents": foundry_handoff.valid_intents_for_step(step_id, state),
        "intro": step_message(step_meta, "intro"),
        "outro": step_message(step_meta, "outro")
        or foundry_handoff.HANDOFF_BLURBS.get(step_id, ""),
        "handoff_blurb": step_message(step_meta, "outro")
        or foundry_handoff.HANDOFF_BLURBS.get(step_id, ""),
        "worker_launch_contract": ".cursor/foundry/docs/worker-launch-contract.md",
        "next_invocations": orchestrator_next_invocations(step_id, state_path, foundry_cli, ctx),
        "next_commands": orchestrator_next_commands(step_id, state_path, foundry_cli),
        "steward_allowlist": allowlist,
        "forbidden": forbidden,
        "allowed": [
            "foundry_cli",
            "Task_typed_subagent",
            "AskQuestion_gate",
            "read_only_inspection",
        ],
        "open_subagent_launches": launches,
    }
    if step_id == "plan.brief":
        packet["task_subagent_type"] = "planner"
        packet["subagent_mode"] = "brief"
    if step_id == "plan.graph":
        packet["task_subagent_type"] = "planner"
        packet["subagent_mode"] = packet.get("subagent_mode") or "plan"
    return packet


def flow_resume_packet(
    state_path: Path,
    config_path: str | None,
    flow_path: str | None,
) -> dict[str, Any]:
    orch = flow_orchestrator_packet(state_path, config_path, flow_path)
    state = load_state(state_path)
    step_id = str(state.get("current_step"))
    packet = {
        "schema_version": SCHEMA_VERSION,
        "run_id": state.get("run_id"),
        "issue_key": state.get("issue_key"),
        "app_folder": state.get("app_folder"),
        "run_dir": orch.get("run_dir"),
        "state_path": orch.get("state_path"),
        "config_path": orch.get("config_path"),
        "foundry_cli": orch.get("foundry_cli"),
        "current_step": step_id,
        "interaction_mode": orch.get("interaction_mode"),
        "unit_relative": orch.get("unit_relative"),
        "task_subagent_type": orch.get("task_subagent_type"),
        "subagent_mode": orch.get("subagent_mode"),
        "blocked": orch.get("blocked"),
        "open_subagent_launches": orch.get("open_subagent_launches"),
        "feature_branch": state.get("feature_branch"),
        "feature_branch_head": state.get("feature_branch_head"),
        "session_stop_hint": orch.get("session_stop_hint"),
        "gate_policy": orch.get("gate_policy"),
        "valid_intents": orch.get("valid_intents"),
        "inputs": foundry_handoff.step_inputs(step_id, state, state_path.parent),
        "forbidden": orch.get("forbidden"),
        "steward_allowlist": orch.get("steward_allowlist"),
        "worker_launch_contract": orch.get("worker_launch_contract"),
        "next_commands": orch.get("next_commands"),
        "intro": orch.get("intro"),
        "outro": orch.get("outro"),
        "handoff_blurb": orch.get("outro") or orch.get("handoff_blurb"),
    }
    try:
        foundry_protocol.validate_schema(
            packet,
            "packets/resume-packet.schema.json",
            artifact="resume packet",
        )
    except foundry_protocol.ProtocolError as exc:
        raise FoundryError(exc.error_code, exc.message, extra={"errors": exc.errors}) from exc
    return packet


def gate_resolve(
    state_path: Path,
    *,
    decision: str,
    source: str = "human",
    config_path: str | None = None,
    flow_path: str | None = None,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if source not in ("human", "auto"):
        raise FoundryError("INVALID_GATE_SOURCE", "source must be human or auto", required_input="source")
    state = load_state(state_path)
    config = load_run_config(state_path, state, config_path)
    step_id = str(state.get("current_step"))
    registry = load_registry(flow_path)
    flow = get_flow(registry, str(state.get("run_mode")))
    gate = get_step(flow, step_id).get("gate")
    gate_kind = gate.get("kind") if isinstance(gate, dict) else None
    if gate_kind not in HUMAN_GATE_KINDS:
        raise FoundryError(
            "GATE_NOT_RESOLVABLE",
            f"Step {step_id!r} does not have a human gate.",
            extra={"step_id": step_id, "gate_kind": gate_kind},
        )
    prompt_key = gate.get("prompt_key")
    options = ((registry.get("gates") or {}).get(prompt_key) or {}).get("options") or []
    if decision not in options and source != "auto":
        raise FoundryError(
            "INVALID_GATE_DECISION",
            f"Decision {decision!r} is not configured for gate {prompt_key!r}.",
            required_input="decision",
            extra={"step_id": step_id, "options": options},
        )
    run_directory = state_path.parent
    if source == "auto":
        auto = foundry_handoff.gate_auto_decision(
            step_id, state, config, run_directory, extras=extras
        )
        if not auto:
            raise FoundryError(
                "AUTO_GATE_NOT_ELIGIBLE",
                f"Step {step_id} is not auto-eligible under interaction_mode="
                f"{foundry_handoff.interaction_mode_of(state, config)}",
                required_input="decision",
            )
        decision = str(auto["decision"])
        if decision not in options:
            raise FoundryError(
                "INVALID_GATE_DECISION",
                f"Automatic decision {decision!r} is not configured for gate {prompt_key!r}.",
                extra={"step_id": step_id, "options": options},
            )
    elif not step_evidence(state, step_id).get("gate_presented"):
        events = call_observability("load_events", state_path.parent / "events.jsonl")
        if not call_observability("gate_presented_for_step", events, step_id):
            raise FoundryError(
                "GATE_NOT_PRESENTED",
                f"Gate on {step_id!r} must be presented before a human resolves it.",
                required_input="gate_presented",
                extra={"step_id": step_id, "decision": decision},
            )
    evidence = state.setdefault("steps", {}).setdefault(step_id, {})
    events_path = state_path.parent / "events.jsonl"
    prior_events = call_observability("load_events", events_path)
    prior = next(
        (
            event
            for event in reversed(prior_events)
            if event.get("event_type") == "gate_resolved"
            and event.get("step_id") == step_id
            and isinstance(event.get("payload"), dict)
            and event["payload"].get("decision") == decision
            and (
                event["payload"].get("gate_source")
                or event["payload"].get("source")
                or ("auto" if event.get("actor") == "engine" else "human")
            )
            == source
        ),
        None,
    )
    if prior is not None and evidence.get("gate_decision") == decision:
        return {
            "step_id": step_id,
            "decision": decision,
            "gate_source": source,
            "interaction_mode": foundry_handoff.interaction_mode_of(state, config),
            "idempotent": True,
            "event_id": prior.get("event_id"),
        }
    evidence["gate_decision"] = decision
    evidence["gate_outcome"] = decision
    evidence["gate_source"] = source
    evidence["gate_resolved"] = True
    if foundry_lineage.gate_artifact_available(step_id, state, run_directory):
        evidence["approved_digest"] = foundry_lineage.gate_artifact_digest(
            step_id,
            state,
            run_directory,
        )
    evidence["human_approved"] = decision in GATE_DECISIONS_SATISFYING
    evidence["gate_presented"] = True
    if "gate_presented_at" not in evidence:
        evidence["gate_presented_at"] = now_iso()
    # Map common decisions onto approved flags
    if decision in ("approve", "pass", "post", "skip", "accept_risk"):
        evidence["approved"] = True
    gate_policy = foundry_handoff.gate_policy_for_step(
        step_id,
        state,
        config,
        get_step(flow, step_id),
        run_directory,
    )
    if source == "human" and foundry_handoff.session_stop_hint(
        step_id, gate_policy
    ) == "stop_after_hard_gate":
        state["session_stop_obligation"] = {
            "reason": "stop_after_hard_gate",
            "step_id": step_id,
            "created_at": now_iso(),
        }
    if step_id == "plan.graph" and decision in GATE_DECISIONS_SATISFYING:
        ensure_execution_graph_reference(state_path, state)
    write_state(state_path, state)
    append_event(
        events_path,
        make_event(
            str(state["run_id"]),
            "gate_resolved",
            "engine" if source == "auto" else "human",
            step_id=step_id,
            payload={
                "gate_kind": gate_kind,
                "decision": decision,
                "gate_source": source,
                "source": source,
                "material_change": decision not in GATE_DECISIONS_SATISFYING,
                "artifact_digest": evidence.get("approved_digest"),
            },
        ),
    )
    return {
        "step_id": step_id,
        "decision": decision,
        "gate_source": source,
        "interaction_mode": foundry_handoff.interaction_mode_of(state, config),
    }


def run_list(app_folder: str) -> dict[str, Any]:
    return foundry_handoff.list_runs(Path(app_folder).resolve())


def run_latest(app_folder: str, issue_key: str | None = None) -> dict[str, Any]:
    return foundry_handoff.latest_run(Path(app_folder).resolve(), issue_key=issue_key)


def run_handoff(
    state_path: Path,
    *,
    config_path: str | None = None,
    flow_path: str | None = None,
    what_happened: str | None = None,
    what_next: str | None = None,
) -> dict[str, Any]:
    state = load_state(state_path)
    assert_run_manifest_current(state_path, state)
    config = load_run_config(state_path, state, config_path)
    orch = ((config.get("foundry") or {}).get("orchestrator") or {})
    if orch.get("require_integrity_check"):
        import foundry_integrity  # noqa: PLC0415

        integrity = foundry_integrity.run_integrity_check(state_path)
        if not integrity.get("ok"):
            raise FoundryError(
                "INTEGRITY_CHECK_FAILED",
                "Run integrity check failed before handoff.",
                recoverable=True,
                required_input="integrity",
                extra={"issues": integrity.get("issues") or []},
            )
    packet = flow_orchestrator_packet(state_path, config_path, flow_path)
    try:
        result = foundry_handoff.write_handoff(
            state=state,
            run_dir=state_path.parent,
            state_path=state_path,
            next_commands=list(packet.get("next_commands") or []),
            what_happened=what_happened,
            what_next=what_next or packet.get("outro") or packet.get("handoff_blurb"),
        )
    except foundry_protocol.ProtocolError as exc:
        raise FoundryError(exc.error_code, exc.message, extra={"errors": exc.errors}) from exc
    obligation = state.get("session_stop_obligation")
    if isinstance(obligation, dict):
        obligation["handoff_written_at"] = now_iso()
        obligation["source_conversation_id"] = state.get("active_conversation_id")
    state["last_handoff_at"] = now_iso()
    write_state(state_path, state)
    append_event(
        state_path.parent / "events.jsonl",
        make_event(
            str(state["run_id"]),
            "handoff_written",
            "engine",
            step_id=str(state.get("current_step")),
            payload={
                "handoff_md": result["handoff_md"],
                "fulfilled_obligation": None,
                "pending_obligation": obligation,
                "session_id": state.get("active_conversation_id"),
            },
        ),
    )
    return result


def run_finalize_learning(
    state_path: Path,
    *,
    outcome_status: str = "completed",
    abandon_reason: str | None = None,
) -> dict[str, Any]:
    state = load_state(state_path)
    events_path = state_path.parent / "events.jsonl"
    events = []
    if events_path.is_file():
        for line in events_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    record = foundry_handoff.build_learning_record(
        state,
        events,
        outcome_status=outcome_status,
        pr_url=state.get("pr_url") if isinstance(state.get("pr_url"), str) else None,
        abandon_reason=abandon_reason,
    )
    record_path = state_path.parent / "learning_record.json"
    review_path = state_path.parent / "learning_review.md"
    record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    foundry_handoff.write_learning_review(record, review_path)
    append_event(
        events_path,
        make_event(
            str(state["run_id"]),
            "learning_finalized",
            "engine",
            step_id=str(state.get("current_step")),
            payload={"learning_record": str(record_path)},
        ),
    )
    return {
        "learning_record": str(record_path),
        "learning_review": str(review_path),
        "record": record,
    }


def run_abandon(state_path: Path, *, reason: str) -> dict[str, Any]:
    state = load_state(state_path)
    state["outcome_status"] = "abandoned"
    state["abandon_reason"] = reason
    write_state(state_path, state)
    append_event(
        state_path.parent / "events.jsonl",
        make_event(
            str(state["run_id"]),
            "run_abandoned",
            "human",
            step_id=str(state.get("current_step")),
            payload={"reason": reason},
        ),
    )
    learning = run_finalize_learning(
        state_path, outcome_status="abandoned", abandon_reason=reason
    )
    return {"abandoned": True, "reason": reason, **learning}


def run_sync(state_path: Path, *, push: bool = False) -> dict[str, Any]:
    state = load_state(state_path)
    config = load_run_config(state_path, state, None)
    foundry_cfg = config.get("foundry") if isinstance(config.get("foundry"), dict) else {}
    sync = foundry_cfg.get("sync") if isinstance(foundry_cfg.get("sync"), dict) else {}
    mode = sync.get("mode") or "off"
    if mode == "off":
        raise FoundryError(
            "SYNC_DISABLED",
            "foundry.sync.mode is off. Local handoff only; enable git_wip/http later.",
            recoverable=True,
        )
    raise FoundryError(
        "SYNC_NOT_IMPLEMENTED",
        f"foundry.sync.mode={mode!r} is reserved; implement after lease/redaction.",
        recoverable=True,
    )


def compute_next(
    registry: dict[str, Any],
    state: dict[str, Any],
    config: dict[str, Any],
    decision: str | None,
) -> dict[str, Any]:
    flow = get_flow(registry, str(state.get("run_mode")))
    step_id = str(state.get("current_step"))
    step = get_step(flow, step_id)
    if decision is None and isinstance(step.get("gate"), dict):
        evidence = step_evidence(state, step_id)
        decision = evidence.get("gate_outcome") or evidence.get("gate_decision")
        if decision is None:
            decision = "approve"
    context = build_context(state, config, decision)

    blockers = gate_blockers(step_id, step, context)
    matching = [edge for edge in outgoing_edges(flow, step_id) if edge_matches(edge, context)]
    if not matching:
        return {
            "from_step": step_id,
            "next_step": None,
            "terminal": not outgoing_edges(flow, step_id),
            "blocked_by": blockers,
            "skipped": [],
        }
    edge = matching[0]
    if blockers and not edge.get("rework"):
        return {
            "from_step": step_id,
            "next_step": None,
            "candidate_step": edge["to"],
            "terminal": False,
            "blocked_by": blockers,
            "skipped": [],
        }

    target, skipped = walk_route(flow, edge, context)
    if target in skipped:
        # The skip chain ran out of outgoing edges before reaching a live step.
        return {
            "from_step": step_id,
            "next_step": None,
            "terminal": True,
            "skipped": skipped,
            "blocked_by": blockers,
        }
    return {
        "from_step": step_id,
        "next_step": target,
        "edge": {k: v for k, v in edge.items() if k in ("from", "to", "when", "priority", "rework")},
        "rework": bool(edge.get("rework")),
        "skipped": skipped,
        "unmet_requires": unmet_requires(get_step(flow, target), context),
        "blocked_by": blockers if edge.get("rework") else [],
        "terminal": False,
    }


def flow_next(
    state_path: Path,
    config_path: str | None,
    flow_path: str | None,
    decision: str | None,
) -> dict[str, Any]:
    state = load_state(state_path)
    registry = load_registry(flow_path)
    config = load_run_config(state_path, state, config_path)
    blocked = run_is_blocked(state)
    if blocked is not None:
        return {
            "from_step": str(state.get("current_step")),
            "next_step": None,
            "terminal": False,
            "blocked_by": [blocked.get("reason")],
            "blocked": blocked,
            "skipped": [],
        }
    return compute_next(registry, state, config, decision)


# --------------------------------------------------------------------------
# transition
# --------------------------------------------------------------------------


def assert_state_patch_owned(
    step_id: str,
    step: dict[str, Any],
    patch: Iterable[tuple[str, Any]],
    *,
    source: str,
) -> list[tuple[str, Any]]:
    owned = set(step_state_json_permissions(step))
    flattened = list(patch)
    for key, _value in flattened:
        if key not in owned:
            raise FoundryError(
                "STATE_KEY_NOT_OWNED",
                f"{step_id!r} cannot mutate state key {key!r}.",
                required_input="set",
                extra={"step_id": step_id, "key": key, "owned": sorted(owned), "source": source},
            )
        if key.rsplit(".", 1)[-1] in GATE_MANAGED_STATE_SUFFIXES:
            raise FoundryError(
                "GATE_STATE_REQUIRES_RESOLVE",
                f"Gate state {key!r} must be changed with `gate resolve`.",
                required_input="gate",
                extra={"step_id": step_id, "key": key, "source": source},
            )
    return flattened


def apply_evidence(
    state: dict[str, Any],
    step_id: str,
    step: dict[str, Any],
    evidence_path: Path | None,
    assignments: Iterable[str],
) -> list[str]:
    refs: list[str] = []
    if evidence_path is not None:
        receipt = read_json(evidence_path, "INVALID_EVIDENCE")
        if not isinstance(receipt, dict):
            raise FoundryError("INVALID_EVIDENCE", "Evidence file must contain a JSON object.")
        receipt_id = receipt.get("receipt_id")
        if receipt_id:
            refs.append(str(receipt_id))
            ids = state.setdefault("receipt_ids", [])
            if receipt_id not in ids:
                ids.append(receipt_id)
        patch = receipt.get("state_patch")
        already_bound = bool(
            receipt_id
            and step_evidence(state, step_id).get("receipt_id") == str(receipt_id)
        )
        if isinstance(patch, dict) and not already_bound:
            for dotted, value in assert_state_patch_owned(
                step_id, step, flatten_patch(patch), source="receipt"
            ):
                nested_set(state, dotted, value)
    parsed_assignments: list[tuple[str, Any]] = []
    for assignment in assignments or []:
        if "=" not in assignment:
            raise FoundryError(
                "INVALID_SET",
                f"--set expects key=value, got {assignment!r}.",
                required_input="set",
            )
        key, raw = assignment.split("=", 1)
        parsed_assignments.append((key.strip(), coerce_scalar(raw.strip())))
    for key, value in assert_state_patch_owned(
        step_id, step, parsed_assignments, source="assignment"
    ):
        nested_set(state, key, value)
    return refs


def flatten_patch(patch: dict[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    flat: list[tuple[str, Any]] = []
    for key, value in patch.items():
        dotted = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.extend(flatten_patch(value, f"{dotted}."))
        else:
            flat.append((dotted, value))
    return flat


INTAKE_ON_ENTER_CHECKS = frozenset(
    {
        "validate_manifest",
        "validate_git_clean_execute",
        "validate_verify_context",
    }
)


def run_on_enter_action(
    action: str,
    *,
    state_path: Path,
    state: dict[str, Any],
    step_id: str,
) -> None:
    if action == "ensure_execution_graph_reference":
        ensure_execution_graph_reference(state_path, state)
        return
    if action in INTAKE_ON_ENTER_CHECKS:
        # v1 stub: declare required intake CLI checks on the step. The steward/worker
        # runs them during the step and seals pass/fail in the intake receipt.
        steps = state.setdefault("steps", {})
        if not isinstance(steps, dict):
            steps = {}
            state["steps"] = steps
        record = steps.setdefault(step_id, {})
        required = record.setdefault("required_intake_checks", [])
        if action not in required:
            required.append(action)
        return
    raise FoundryError("UNKNOWN_FLOW_ACTION", f"Unsupported on_enter action {action!r}.")


def ensure_execution_graph_reference(state_path: Path, state: dict[str, Any]) -> dict[str, Any] | None:
    graph_path = state_path.parent / "execution-graph.json"
    if graph_path.is_file():
        graph = load_execution_graph(graph_path)
        if state.get("risk_tier") == "low":
            validate_low_risk_graph(graph)
    elif state.get("risk_tier") != "low":
        return None
    else:
        _, snapshot = load_run_manifest(state_path)
        default_owner = (snapshot.get("builders") or {}).get("default_owner")
        if not default_owner:
            raise FoundryError(
                "APP_MANIFEST_DEFAULT_BUILDER_REQUIRED",
                "Low-risk execution graph requires builders.default_owner in the run snapshot.",
            )
        ac_refs = [
            str(item["id"])
            for item in (state.get("approved_ac") or [])
            if isinstance(item, dict) and item.get("id")
        ]
        graph_id = str(
            uuid.uuid5(uuid.UUID(str(state["run_id"])), "low-risk-execution-graph")
        )
        graph = {
            "schema_version": SCHEMA_VERSION,
            "graph_id": graph_id,
            "run_id": state["run_id"],
            "issue_key": state.get("issue_key"),
            "risk_tier": "low",
            "approved_ac_version": int(state.get("approved_ac_version") or 1),
            "topology": "single_worker",
            "work_items": [
                {
                    "id": "implement",
                    "description": "Implement the approved acceptance criteria.",
                    "owner": default_owner,
                    "depends_on": [],
                    "ac_refs": ac_refs,
                    "status": "pending",
                }
            ],
            "verification_plan": [
                {
                    "step": "implementation-validator",
                    "after": ["implement"],
                    "required": True,
                },
                {
                    "step": "documentation-writer",
                    "after": ["implement.code_review"],
                    "required": True,
                },
            ],
            "plan_stability": {"changes_after_build_started": 0},
            "created_at": now_iso(),
        }
        foundry_lineage.stamp_graph(graph, state)
        graph_path.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    state["execution_graph_id"] = graph["graph_id"]
    return {"file": str(graph_path), "graph_id": graph["graph_id"]}


def mark_bypassed_skippable_steps(
    flow: dict[str, Any],
    *,
    from_step: str,
    target: str,
    context: dict[str, Any],
    steps: dict[str, Any],
    timestamp: str,
) -> list[str]:
    """Record delivery-gate steps bypassed because `when_skip` matched."""
    bypass_targets = {
        ("implement.code_review", "implement.pre_pr_review"): ["implement.devops_review"],
        ("implement.code_review", "implement.documentation"): [
            "implement.devops_review",
            "implement.pre_pr_review",
        ],
        ("implement.devops_review", "implement.documentation"): ["implement.pre_pr_review"],
        ("deliver.gate", "deliver.ship"): ["deliver.scope_comment"],
    }
    marked: list[str] = []
    for step_id in bypass_targets.get((from_step, target), []):
        step = (flow.get("steps") or {}).get(step_id)
        if not isinstance(step, dict):
            continue
        if not skip_reasons(step, context):
            continue
        evidence = steps.setdefault(step_id, {})
        if evidence.get("status"):
            continue
        evidence["status"] = "skipped"
        evidence["completed_at"] = timestamp
        marked.append(step_id)
    return marked


def load_step_receipt(state: dict[str, Any], step_id: str, state_path: Path) -> dict[str, Any] | None:
    receipt_id = step_evidence(state, step_id).get("receipt_id")
    if not isinstance(receipt_id, str):
        return None
    return load_receipt(state_path.parent / "receipts", receipt_id)


def assert_gate_presented_before_resolve(
    state_path: Path,
    flow: dict[str, Any],
    from_step: str,
    decision: str | None,
    *,
    rework: bool,
) -> None:
    if rework or not decision:
        return
    step = get_step(flow, from_step)
    gate = step.get("gate")
    if not isinstance(gate, dict) or gate.get("kind") not in HUMAN_GATE_KINDS:
        return
    state = load_state(state_path)
    evidence = step_evidence(state, from_step)
    if evidence.get("gate_presented") is True:
        return
    events = call_observability("load_events", state_path.parent / "events.jsonl")
    if call_observability("gate_presented_for_step", events, from_step):
        return
    raise FoundryError(
        "GATE_NOT_PRESENTED",
        (
            f"Gate on {from_step!r} was not presented to a human. "
            "Run observability gate present before resolving with --decision."
        ),
        required_input="gate_presented",
        extra={"step_id": from_step, "decision": decision},
    )


def assert_brief_snapshot_for_graph(state: dict[str, Any], target: str) -> None:
    if target != "plan.graph":
        return
    if isinstance(state.get("brief_snapshot"), dict) and state["brief_snapshot"].get("hash"):
        return
    raise FoundryError(
        "BRIEF_SNAPSHOT_MISSING",
        "plan.graph requires a recorded brief snapshot. Run plan record-brief first.",
        required_input="brief_snapshot",
    )


def assert_validator_transition_allowed(
    state: dict[str, Any],
    state_path: Path,
    *,
    from_step: str,
    target: str,
    decision: str | None,
) -> None:
    if from_step != "implement.validate" or target != "implement.code_review":
        return
    if decision == "critical_findings":
        return
    receipt = load_step_receipt(state, "implement.validate", state_path)
    if receipt is None:
        return
    outputs = receipt.get("outputs") if isinstance(receipt.get("outputs"), dict) else {}
    critical_count = int(outputs.get("critical_count") or 0)
    if critical_count > 0:
        raise FoundryError(
            "VALIDATOR_CRITICAL_OPEN",
            "Cannot leave implement.validate while critical findings remain. "
            "Use --decision critical_findings to route back to implement.build.",
            extra={"critical_count": critical_count},
        )
    important_count = int(outputs.get("important_count") or 0)
    if important_count > 0 and (decision is None or decision not in VALIDATOR_GAP_DECISIONS):
        raise FoundryError(
            "VALIDATOR_GAPS_UNACKNOWLEDGED",
            "Validator reported important gaps. Use --decision accept_gaps to proceed.",
            extra={"important_count": important_count, "decision": decision},
        )


def assert_pre_pr_transition_allowed(
    state: dict[str, Any],
    state_path: Path,
    *,
    from_step: str,
    target: str,
    decision: str | None,
    config: dict[str, Any] | None = None,
    git_snapshot: dict[str, str] | None = None,
) -> None:
    if from_step != "implement.pre_pr_review" or target != "implement.documentation":
        return
    if decision in ("fix_findings", "workflows_changed"):
        return
    resolved_config = config or {}
    review = resolve_path(resolved_config, ["review"]) or {}
    if review.get("enabled") and review.get("run_before_pr"):
        assert_critic_receipts_for_state(
            state,
            resolved_config,
            state_path=state_path,
            git_snapshot=git_snapshot,
        )
    assert_post_repair_satisfied(state, state_path=state_path, git_snapshot=git_snapshot)
    receipt = load_step_receipt(state, "implement.pre_pr_review", state_path)
    if receipt is None:
        return
    outputs = receipt.get("outputs") if isinstance(receipt.get("outputs"), dict) else {}
    highs = int(outputs.get("bugbot_high") or 0) + int(outputs.get("security_high") or 0)
    findings = outputs.get("findings") if isinstance(outputs.get("findings"), list) else []
    if highs > 0 or findings:
        if decision not in PRE_PR_RISK_DECISIONS:
            raise FoundryError(
                "PRE_PR_FINDINGS_UNACKNOWLEDGED",
                "Pre-PR review reported high findings. Use --decision accept_risk to proceed.",
                extra={"bugbot_high": outputs.get("bugbot_high"), "security_high": outputs.get("security_high")},
            )


def assert_no_orchestration_anomaly(
    state_path: Path,
    state: dict[str, Any],
    config: dict[str, Any],
    *,
    from_step: str,
) -> None:
    settings = orchestrator_settings(config)
    if not settings["stop_on_receipt_anomaly"]:
        return
    metrics = observability_metrics_summarize(state_path)
    eval_signals = metrics.get("eval_signals") if isinstance(metrics.get("eval_signals"), dict) else {}
    orphan_completions = int(
        eval_signals.get("orphan_completions")
        or metrics.get("orphan_completions")
        or 0
    )
    if orphan_completions > 0:
        reason = f"ORCHESTRATION_ANOMALY: orphan_completions={orphan_completions}"
        run_block(state_path, reason=reason, step_id=from_step)
        raise FoundryError(
            "ORCHESTRATION_ANOMALY",
            "Strict mode blocked the transition because receipt completions lack matching launches.",
            extra={"orphan_completions": orphan_completions, "fromStep": from_step},
        )


def assert_worker_exit_receipt(
    state_path: Path,
    state: dict[str, Any],
    *,
    step_id: str,
    step: dict[str, Any],
) -> None:
    if not worker_receipt_required(step):
        return
    record = step_evidence(state, step_id)
    receipt_id = record.get("receipt_id")
    launch_id = record.get("launch_id")
    if not isinstance(receipt_id, str) or not isinstance(launch_id, str):
        raise FoundryError(
            "WORKER_RECEIPT_REQUIRED",
            f"Step {step_id!r} requires a completed provenance-bound worker receipt.",
            required_input="receipt",
        )
    receipt = load_receipt(state_path.parent / "receipts", receipt_id)
    expected_agent = str(step_worker_agent(step) or (receipt.get("agent") or {}).get("name") or "")
    expected_mode = str(step_worker_mode(step) or (receipt.get("agent") or {}).get("mode") or "")
    try:
        foundry_protocol.validate_receipt_contract(
            receipt,
            expected_run_id=str(state["run_id"]),
            expected_launch_id=launch_id,
            expected_step_id=step_id,
            expected_agent=expected_agent,
            expected_mode=expected_mode,
        )
    except foundry_protocol.ProtocolError as exc:
        raise FoundryError(exc.error_code, exc.message, extra={"errors": exc.errors}) from exc
    events = call_observability("load_events", state_path.parent / "events.jsonl")
    if not any(
        event.get("event_type") == "subagent_completed"
        and event.get("step_id") == step_id
        and (event.get("payload") or {}).get("launch_id") == launch_id
        and (event.get("payload") or {}).get("receipt_id") == receipt_id
        for event in events
    ):
        raise FoundryError(
            "WORKER_COMPLETION_EVENT_REQUIRED",
            f"Receipt {receipt_id!r} has no matching completed launch event.",
        )


def assert_intake_exit_receipt(
    state: dict[str, Any],
    *,
    step_id: str,
    step: dict[str, Any],
) -> None:
    if not intake_receipt_required(step):
        return
    record = step_evidence(state, step_id)
    if not isinstance(record.get("intake_receipt_id"), str):
        raise FoundryError(
            "INTAKE_RECEIPT_REQUIRED",
            f"Step {step_id!r} requires a sealed intake receipt before transition.",
            required_input="intake_receipt",
            extra={"step_id": step_id},
        )


def transition(
    state_path: Path,
    target: str,
    *,
    config_path: str | None,
    flow_path: str | None,
    evidence: str | None,
    decision: str | None,
    assignments: Iterable[str],
    force: bool = False,
) -> dict[str, Any]:
    state = load_state(state_path)
    registry = load_registry(flow_path)
    config = load_run_config(state_path, state, config_path)
    assert_run_not_blocked(state, config, force=force)
    flow = get_flow(registry, str(state.get("run_mode")))

    from_step = str(state.get("current_step"))
    from_step_meta = get_step(flow, from_step)
    target_step = get_step(flow, target)

    evidence_refs = apply_evidence(
        state,
        from_step,
        from_step_meta,
        Path(evidence) if evidence else None,
        assignments,
    )
    obligation = state.get("session_stop_obligation")
    if isinstance(obligation, dict):
        raise FoundryError(
            "SESSION_HANDOFF_REQUIRED",
            "This session reached a worker or gate boundary. Record a handoff and a new host conversation before continuing.",
            required_input="handoff",
            extra={"obligation": obligation},
        )
    gate = from_step_meta.get("gate")
    if isinstance(gate, dict) and gate.get("kind") in HUMAN_GATE_KINDS:
        authoritative = step_evidence(state, from_step).get("gate_outcome")
        if authoritative is None:
            authoritative = step_evidence(state, from_step).get("gate_decision")
        if authoritative is None:
            raise FoundryError(
                "GATE_UNRESOLVED",
                f"Gate on {from_step!r} has no authoritative outcome. Run `gate resolve` first.",
                required_input="gate",
            )
        if decision is not None and decision != authoritative:
            raise FoundryError(
                "GATE_OUTCOME_MISMATCH",
                f"Transition decision {decision!r} conflicts with resolved outcome {authoritative!r}.",
                extra={"step_id": from_step, "outcome": authoritative, "decision": decision},
            )
        decision = str(authoritative)
    context = build_context(state, config, decision)

    validate_intake_exit(from_step, target, state, config, decision)

    route = resolve_route(flow, from_step, target, context)
    if route is None:
        raise FoundryError(
            "ILLEGAL_TRANSITION",
            f"No edge from {from_step!r} to {target!r} matches the current context.",
            required_input="to",
            extra={
                "fromStep": from_step,
                "requestedStep": target,
                "allowedSteps": reachable_targets(flow, from_step, context),
            },
        )
    edge, skipped_steps = route

    if from_step == "implement.validate" and target == "implement.build" and decision == "critical_findings":
        assert_rework_threshold(
            state,
            config,
            counter="validator_loops",
            threshold_key="validator_loop_threshold",
            from_step=from_step,
        )
    if from_step == "implement.pre_pr_review" and target == "implement.build" and decision == "fix_findings":
        assert_rework_threshold(
            state,
            config,
            counter="builder_to_bugbot_loops",
            threshold_key="builder_to_bugbot_loop_threshold",
            from_step=from_step,
        )

    if target == "implement.build":
        ensure_execution_graph_reference(state_path, state)
        validate_build_entry(state, config, state_path=state_path, graph_path=None)

    assert_open_launches_closed(state)
    assert_gate_presented_before_resolve(
        state_path,
        flow,
        from_step,
        decision,
        rework=bool(edge.get("rework")),
    )
    assert_brief_snapshot_for_graph(state, target)
    assert_validator_transition_allowed(
        state,
        state_path,
        from_step=from_step,
        target=target,
        decision=decision,
    )
    assert_pre_pr_transition_allowed(
        state,
        state_path,
        from_step=from_step,
        target=target,
        decision=decision,
        config=config,
    )
    assert_worker_exit_receipt(
        state_path,
        state,
        step_id=from_step,
        step=from_step_meta,
    )
    assert_intake_exit_receipt(
        state,
        step_id=from_step,
        step=from_step_meta,
    )

    for action in ((from_step_meta.get("actions") or {}).get("on_exit") or []):
        if action == "validate_build_exit":
            evidence_file = Path(evidence) if evidence else None
            validate_build_exit(
                state,
                config,
                state_path=state_path,
                evidence_path=evidence_file,
                require_step_receipt=True,
            )
        else:
            raise FoundryError("UNKNOWN_FLOW_ACTION", f"Unsupported on_exit action {action!r}.")

    assert_no_orchestration_anomaly(state_path, state, config, from_step=from_step)
    # The gate on the step being left is judged before that step is closed out.
    if not edge.get("rework"):
        blockers = gate_blockers(from_step, get_step(flow, from_step), context)
        if blockers:
            raise FoundryError(
                "GATE_UNRESOLVED",
                f"Gate on {from_step!r} is not satisfied: " + "; ".join(blockers),
                extra={"fromStep": from_step, "requestedStep": target, "unresolved": blockers},
            )
        source_gate = get_step(flow, from_step).get("gate")
        source_record = step_evidence(state, from_step)
        approved_digest = source_record.get("approved_digest")
        if (
            isinstance(source_gate, dict)
            and not isinstance(approved_digest, str)
            and source_record.get("gate_decision") in GATE_DECISIONS_SATISFYING
            and foundry_lineage.gate_artifact_available(from_step, state, state_path.parent)
        ):
            approved_digest = foundry_lineage.gate_artifact_digest(
                from_step,
                state,
                state_path.parent,
            )
            source_record["approved_digest"] = approved_digest
        if isinstance(source_gate, dict) and isinstance(approved_digest, str):
            current_digest = foundry_lineage.gate_artifact_digest(
                from_step,
                state,
                state_path.parent,
            )
            if current_digest != approved_digest:
                raise FoundryError(
                    "STALE_GATE_APPROVAL",
                    f"Approval for {from_step!r} does not match the current artifact.",
                    extra={
                        "step_id": from_step,
                        "approved_digest": approved_digest,
                        "current_digest": current_digest,
                    },
                )

    if edge.get("rework"):
        foundry_lineage.invalidate_after(state, target)

    timestamp = now_iso()
    steps = state.setdefault("steps", {})
    source_evidence = steps.setdefault(from_step, {})
    if evidence_refs:
        source_evidence["receipt_id"] = evidence_refs[-1]
    if source_evidence.get("status") not in ("skipped", "failed") and target != from_step:
        source_evidence["status"] = "completed"
        source_evidence["completed_at"] = timestamp

    for skipped_id in skipped_steps:
        skipped_evidence = steps.setdefault(skipped_id, {})
        skipped_evidence["status"] = "skipped"
        skipped_evidence["completed_at"] = timestamp

    bypassed = mark_bypassed_skippable_steps(
        flow,
        from_step=from_step,
        target=target,
        context=context,
        steps=steps,
        timestamp=timestamp,
    )

    # `requires` and delivery evidence describe the state the target starts
    # from, so they are judged after the source step is closed out. Nothing is
    # persisted until every check below passes.
    context = build_context(state, config, decision)
    unmet = unmet_requires(target_step, context)
    if unmet:
        raise FoundryError(
            "STEP_REQUIREMENTS_UNMET",
            f"Step {target!r} cannot start; unmet requirements: " + "; ".join(unmet),
            extra={"fromStep": from_step, "requestedStep": target, "unmetRequires": unmet},
        )

    if target_step.get("require_delivery_check"):
        delivery_check(state, config, state_path=state_path)

    for action in ((target_step.get("actions") or {}).get("on_enter") or []):
        run_on_enter_action(
            str(action),
            state_path=state_path,
            state=state,
            step_id=target,
        )
    target_evidence = steps.setdefault(target, {})
    target_evidence["status"] = "in_progress"
    target_evidence["started_at"] = timestamp
    if target == from_step:
        target_evidence.pop("completed_at", None)
    state["current_step"] = target

    write_state(state_path, state)
    events_path = state_path.parent / "events.jsonl"
    append_event(
        events_path,
        make_event(
            str(state["run_id"]),
            "state_transition",
            "engine",
            step_id=target,
            payload={
                "from_step": from_step,
                "to_step": target,
                "evidence_refs": evidence_refs,
                "rule_id": f"{from_step}->{target}",
            },
        ),
    )
    record_transition_receipt_events(
        state_path,
        state,
        config,
        Path(evidence) if evidence else None,
        evidence_refs,
        from_step,
    )
    rework_result = record_rework_on_transition(
        state_path,
        config,
        from_step=from_step,
        decision=decision,
    )
    response: dict[str, Any] = {
        "from_step": from_step,
        "current_step": target,
        "rework": bool(edge.get("rework")),
        "evidence_refs": evidence_refs,
        "state_path": str(state_path),
    }
    if rework_result is not None:
        response["rework_counters"] = rework_result
    return response


def walk_route(
    flow: dict[str, Any],
    edge: dict[str, Any],
    context: dict[str, Any],
) -> tuple[str, list[str]]:
    """Follow `edge`, stepping over any `when_skip` steps. Returns (landing, skipped)."""
    skipped: list[str] = []
    candidate = str(edge["to"])
    for _ in range(len(flow.get("steps") or {}) + 1):
        step = (flow.get("steps") or {}).get(candidate)
        if not isinstance(step, dict) or not skip_reasons(step, context):
            return candidate, skipped
        skipped.append(candidate)
        onward = [e for e in outgoing_edges(flow, candidate) if edge_matches(e, context)]
        if not onward:
            return candidate, skipped
        candidate = str(onward[0]["to"])
    raise FoundryError("FLOW_CYCLE", "Route resolution exceeded the step count; check when_skip rules.")


def resolve_route(
    flow: dict[str, Any],
    from_step: str,
    target: str,
    context: dict[str, Any],
) -> tuple[dict[str, Any], list[str]] | None:
    """Find the edge that reaches `target`, directly or over skipped steps."""
    for edge in outgoing_edges(flow, from_step):
        if not edge_matches(edge, context):
            continue
        if str(edge["to"]) == target:
            return edge, []
        landing, skipped = walk_route(flow, edge, context)
        if landing == target:
            return edge, skipped
    return None


def reachable_targets(flow: dict[str, Any], from_step: str, context: dict[str, Any]) -> list[str]:
    targets: set[str] = set()
    for edge in outgoing_edges(flow, from_step):
        if not edge_matches(edge, context):
            continue
        targets.add(str(edge["to"]))
        landing, _ = walk_route(flow, edge, context)
        targets.add(landing)
    return sorted(targets)


# --------------------------------------------------------------------------
# delivery-check
# --------------------------------------------------------------------------


def delivery_check(
    state: dict[str, Any],
    config: dict[str, Any],
    *,
    state_path: Path | None = None,
    git_snapshot: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Port of `foundry.py delivery-check` onto dotted step IDs."""
    if state_path is not None:
        assert_run_manifest_current(state_path, state)
    failures: list[str] = []
    checked: list[str] = []

    def require(condition: bool, code: str, message: str) -> None:
        checked.append(code)
        if not condition:
            failures.append(f"{code}: {message}")

    steps = state.get("steps") or {}

    def evidence(step_id: str) -> dict[str, Any]:
        value = steps.get(step_id)
        return value if isinstance(value, dict) else {}

    def gate_ran(step_id: str) -> bool:
        record = evidence(step_id)
        return record.get("report") == "received" and record.get("human_approved") is True

    code_review = evidence("implement.code_review")
    require(
        code_review.get("human_approved") is True,
        "CODE_REVIEW",
        "Human must approve implement.code_review before documentation and ship.",
    )

    documentation = evidence("implement.documentation")
    require(
        documentation.get("report") == "received" and documentation.get("human_approved") is True,
        "DOCUMENTATION",
        "implement.documentation DocChangeReport must be received and human-approved.",
    )

    result = documentation.get("documentation_result")
    publication = result.get("publication") if isinstance(result, dict) else None
    publication = publication if isinstance(publication, dict) else {}
    model = documentation.get("model") or (result.get("model") if isinstance(result, dict) else None)
    requirements = None
    if model:
        try:
            backend = foundry_docs.resolve_documentation_backend(str(model))
            requirements = backend.delivery_requirements({}, documentation)
        except foundry_docs.DocsError:
            requirements = None
    if requirements is None:
        required = bool(publication.get("required")) or bool(documentation.get("prd_created_or_updated"))
        passed = bool(publication.get("passed")) or documentation.get("sync_prd_ok") is True
        if not required:
            passed = True
        requirements = {"required": required, "passed": passed}
    if requirements.get("required"):
        code = "DOCUMENTATION_PUBLICATION"
        if not isinstance(result, dict) and documentation.get("prd_created_or_updated"):
            code = "SYNC_PRD"
        require(
            bool(requirements.get("passed")),
            code,
            "Documentation publication must pass when the selected model requires it.",
        )

    devops = resolve_path(config, ["devops"]) or {}
    if devops.get("enabled") and devops.get("run_before_pr"):
        require(
            gate_ran("implement.devops_review"),
            "DEVOPS_REVIEW",
            "implement.devops_review must complete and be approved.",
        )

    review = resolve_path(config, ["review"]) or {}
    if review.get("enabled") and review.get("run_before_pr"):
        require(
            gate_ran("implement.pre_pr_review"),
            "PRE_PR_REVIEW",
            "implement.pre_pr_review report must be received and approved.",
        )
        if state_path is not None:
            try:
                assert_critic_receipts_for_state(
                    state,
                    config,
                    state_path=state_path,
                    git_snapshot=git_snapshot,
                )
                require(True, "PRE_PR_CRITICS", "Critic receipts must be valid for this run.")
            except FoundryError as exc:
                if exc.error_code in (
                    "CRITIC_RECEIPTS_INVALID",
                    "CRITIC_RECEIPT_MISSING",
                    "CRITIC_RECEIPT_DUPLICATE",
                    "CRITIC_RECEIPT_WRONG_AGENT",
                    "CRITIC_RECEIPT_PARTIAL",
                    "CRITIC_RECEIPT_STALE_HEAD",
                    "CRITIC_LAUNCH_REQUIRED",
                    "RECEIPT_RUN_MISMATCH",
                    "RECEIPT_PROVENANCE_INVALID",
                    "INVALID_RECEIPTS_DIR",
                    "MISSING_CRITICS",
                ):
                    require(False, "PRE_PR_CRITICS", exc.message)
                else:
                    raise

    if post_repair_gate_needed(state, state_path):
        try:
            assert_post_repair_satisfied(
                state,
                state_path=state_path,
                git_snapshot=git_snapshot,
            )
            require(True, "POST_REPAIR", "Post-repair verification must match the current HEAD.")
        except FoundryError as exc:
            if exc.error_code in ("POST_REPAIR_NOT_RUN", "COMMAND_FAILED"):
                require(False, "POST_REPAIR", exc.message)
            else:
                raise

    feature_branch = state.get("feature_branch")
    default_branch = state.get("default_branch")
    require(
        bool(feature_branch) and feature_branch != default_branch,
        "FEATURE_BRANCH",
        "Feature branch must be checked out (not the default branch).",
    )

    require(
        isinstance(state.get("pr_extras_register"), list),
        "PR_EXTRAS",
        "pr_extras_register must be an array (empty allowed).",
    )

    if failures:
        raise FoundryError(
            "DELIVERY_GATES_FAILED",
            "Delivery gates failed: " + "; ".join(failures),
            required_input="state",
            extra={"failures": failures, "gates": checked},
        )
    return {"passed": True, "gates": checked}


# --------------------------------------------------------------------------
# flow validate
# --------------------------------------------------------------------------


def parse_frontmatter(text: str) -> dict[str, Any]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return {}
    require_yaml()
    data = yaml.safe_load(match.group(1))
    return data if isinstance(data, dict) else {}


def validate_registry(flow_path: str | None) -> dict[str, Any]:
    require_jsonschema()
    registry = load_registry(flow_path)
    source = registry.pop("_path")
    errors: list[str] = []
    warnings: list[str] = []

    schema = read_json(SCHEMAS_DIR / "factory-flow.schema.json", "MISSING_SCHEMA")
    for error in sorted(Draft202012Validator(schema).iter_errors(registry), key=str):
        errors.append(f"schema: {'/'.join(str(p) for p in error.absolute_path) or '<root>'}: {error.message}")

    state_schema = registry.get("state_schema")
    if state_schema and not (FOUNDRY_ROOT / state_schema).is_file():
        errors.append(f"state_schema: {state_schema} does not exist")

    gates = registry.get("gates") or {}
    try:
        agent_registry = foundry_protocol.load_agent_registry()
    except foundry_protocol.ProtocolError as exc:
        errors.append(f"contracts: {exc.message}")
        agent_registry = {"agents": {}}
    step_count = 0
    unit_paths: set[str] = set()

    for flow_name, flow in (registry.get("flows") or {}).items():
        steps = flow.get("steps") or {}
        edges = flow.get("edges") or []
        step_count += len(steps)

        entry = flow.get("entry")
        if entry not in steps:
            errors.append(f"{flow_name}: entry {entry!r} is not a step in this flow")

        for step_id, step in steps.items():
            if not STEP_ID_RE.match(step_id):
                errors.append(f"{flow_name}.{step_id}: step ID does not match ^[a-z]+\\.[a-z_]+$")
            instructions_rel = step_instructions(step)
            instructions_file = FOUNDRY_ROOT / instructions_rel if instructions_rel else None
            if not instructions_file or not instructions_file.is_file():
                errors.append(
                    f"{flow_name}.{step_id}: instructions file {instructions_rel!r} does not exist"
                )
            else:
                unit_paths.add(instructions_rel)
                frontmatter = parse_frontmatter(instructions_file.read_text(encoding="utf-8"))
                if frontmatter.get("step_id") != step_id:
                    errors.append(
                        f"{flow_name}.{step_id}: instructions frontmatter step_id is "
                        f"{frontmatter.get('step_id')!r}"
                    )
                if bool(frontmatter.get("delivery_gate")) != bool(step.get("delivery_gate")):
                    errors.append(
                        f"{flow_name}.{step_id}: instructions delivery_gate disagrees with the registry"
                    )
                registry_agent = step_worker_agent(step)
                if frontmatter.get("subagent") != registry_agent:
                    errors.append(
                        f"{flow_name}.{step_id}: instructions subagent "
                        f"{frontmatter.get('subagent')!r} != registry worker {registry_agent!r}"
                    )
                unit_owns = frontmatter.get("state_keys") or []
                registry_owns = step_state_json_permissions(step)
                if sorted(unit_owns) != sorted(registry_owns):
                    errors.append(
                        f"{flow_name}.{step_id}: unit state_keys disagree with registry state_json.permissions"
                    )
                instructions_text = instructions_file.read_text(encoding="utf-8")
                errors.extend(
                    foundry_invoke.validate_markdown(
                        instructions_text,
                        source=str(instructions_rel),
                    )
                )

            run_modes = step.get("run_modes") or []
            if run_modes and flow_name not in run_modes:
                errors.append(f"{flow_name}.{step_id}: run_modes {run_modes} does not include {flow_name}")

            for field in ("when_skip", "requires"):
                for expr in step.get(field) or []:
                    try:
                        parse_expression(str(expr))
                    except FoundryError as exc:
                        errors.append(f"{flow_name}.{step_id}.{field}: {exc.message}")

            gate = step.get("gate")
            if isinstance(gate, dict):
                prompt_key = gate.get("prompt_key")
                if prompt_key and prompt_key not in gates:
                    errors.append(f"{flow_name}.{step_id}: gate prompt_key {prompt_key!r} is not in gates")
                options = ((gates.get(prompt_key) or {}).get("options") or []) if prompt_key else []
                outcomes = gate.get("outcomes") or {}
                if gate.get("kind") in HUMAN_GATE_KINDS and options and set(outcomes) != set(options):
                    errors.append(
                        f"{flow_name}.{step_id}: gate outcomes must exactly cover options {options}"
                    )
                for option, destination in outcomes.items():
                    if isinstance(destination, dict) and destination.get("terminal") is True:
                        if any(edge.get("from") == step_id for edge in edges):
                            errors.append(
                                f"{flow_name}.{step_id}: outcome {option!r} is terminal but step has outgoing edges"
                            )
                        continue
                    if destination == "$forward":
                        expected_fragment = f"decision == '{option}'"
                        if not any(
                            edge.get("from") == step_id
                            and expected_fragment in str(edge.get("when") or "")
                            for edge in edges
                        ):
                            errors.append(
                                f"{flow_name}.{step_id}: outcome {option!r} lacks an explicit forward edge"
                            )
                        continue
                    if destination not in steps:
                        errors.append(
                            f"{flow_name}.{step_id}: outcome {option!r} targets unknown step {destination!r}"
                        )
                        continue
                    expected_expr = f"decision == '{option}'"
                    if not any(
                        edge.get("from") == step_id
                        and edge.get("to") == destination
                        and edge.get("when") == expected_expr
                        for edge in edges
                    ):
                        errors.append(
                            f"{flow_name}.{step_id}: outcome {option!r} lacks explicit edge to {destination!r}"
                        )
                for blocked in gate.get("blocks") or []:
                    if blocked not in steps:
                        warnings.append(
                            f"{flow_name}.{step_id}: gate blocks {blocked!r}, which is not in this flow"
                        )
                for expr in gate.get("require") or []:
                    try:
                        parse_expression(str(expr))
                    except FoundryError as exc:
                        errors.append(f"{flow_name}.{step_id}.gate.require: {exc.message}")

            worker = step_worker(step)
            if worker:
                agent = worker["agent"]
                mode = worker["mode"]
                prompt_rel = worker["prompt"]
                contract_rel = worker["contract"]
                prompt_path = foundry_protocol.resolve_foundry_relative_path(prompt_rel)
                contract_path = foundry_protocol.resolve_foundry_relative_path(contract_rel)
                if not prompt_path.is_file():
                    errors.append(
                        f"{flow_name}.{step_id}: worker prompt file {prompt_rel!r} does not exist"
                    )
                if not contract_path.is_file():
                    errors.append(
                        f"{flow_name}.{step_id}: worker contract file {contract_rel!r} does not exist"
                    )
                try:
                    contract = foundry_protocol.worker_contract(contract_rel, mode)
                    contract_targets: set[str] = set()
                    frontier = [step_id]
                    while frontier:
                        source_step = frontier.pop()
                        for edge in edges:
                            if edge.get("from") != source_step:
                                continue
                            destination = str(edge.get("to"))
                            if destination not in contract_targets:
                                contract_targets.add(destination)
                                frontier.append(destination)
                    for next_state in contract.get("valid_next_states") or []:
                        if next_state not in contract_targets:
                            errors.append(
                                f"{flow_name}.{step_id}: worker contract next state "
                                f"{next_state!r} is unreachable in the flow"
                            )
                except foundry_protocol.ProtocolError as exc:
                    errors.append(f"{flow_name}.{step_id}: {exc.message}")
                legacy_contract = step.get("worker_contract")
                if isinstance(legacy_contract, str) and legacy_contract != f"{agent}/{mode}":
                    errors.append(
                        f"{flow_name}.{step_id}: worker_contract {legacy_contract!r} "
                        f"does not match worker {agent!r}/{mode!r}"
                    )
                if not isinstance(step.get("context_budget"), dict) and step_has_worker(step):
                    pass
                if not step_message(step, "outro"):
                    errors.append(f"{flow_name}.{step_id}: worker step requires outro.message")
            receipts = step.get("receipts")
            if receipts is not None and not isinstance(receipts, (str, list)):
                errors.append(f"{flow_name}.{step_id}: receipts must be a schema path or list of paths")
            elif isinstance(receipts, list) and not receipts:
                errors.append(f"{flow_name}.{step_id}: receipts must not be an empty list")
            for receipt_schema in step_receipt_schemas(step):
                schema_path = FOUNDRY_ROOT / receipt_schema
                if not schema_path.is_file():
                    errors.append(
                        f"{flow_name}.{step_id}: receipt schema {receipt_schema!r} does not exist"
                    )
            if intake_receipt_required(step) and not worker:
                errors.append(
                    f"{flow_name}.{step_id}: receipts includes intake receipt schema but step has no worker"
                )
            if intake_receipt_required(step):
                permission_key = f"steps.{step_id}.intake_receipt_id"
                if permission_key not in step_state_json_permissions(step):
                    errors.append(
                        f"{flow_name}.{step_id}: intake receipt required but "
                        f"{permission_key!r} is not in state_json.permissions"
                    )

        for index, edge in enumerate(edges):
            source_step, dest = edge.get("from"), edge.get("to")
            if source_step not in steps:
                errors.append(f"{flow_name}.edges[{index}]: from {source_step!r} is not a step")
            if dest not in steps:
                errors.append(f"{flow_name}.edges[{index}]: to {dest!r} is not a step")
            when = edge.get("when")
            if when not in (None, "", "always"):
                try:
                    parse_expression(str(when))
                except FoundryError as exc:
                    errors.append(f"{flow_name}.edges[{index}].when: {exc.message}")

        reachable = {entry}
        frontier = [entry]
        while frontier:
            node = frontier.pop()
            for edge in edges:
                if edge.get("from") == node and edge.get("to") not in reachable:
                    reachable.add(str(edge["to"]))
                    frontier.append(str(edge["to"]))
        for orphan in sorted(set(steps) - reachable):
            errors.append(f"{flow_name}.{orphan}: orphan step — unreachable from {entry!r}")

        terminals = sorted(step_id for step_id in steps if not any(e.get("from") == step_id for e in edges))
        if not terminals:
            errors.append(f"{flow_name}: no terminal step — every step has an outgoing edge")

    for unused in sorted(set(gates) - _referenced_gate_keys(registry)):
        warnings.append(f"gates.{unused}: defined but never referenced by a step")

    if errors:
        raise FoundryError(
            "FLOW_INVALID",
            f"{len(errors)} problem(s) in {source}",
            extra={"errors": errors, "warnings": warnings, "source": source},
        )
    return {
        "source": source,
        "flows": sorted((registry.get("flows") or {}).keys()),
        "step_definitions": step_count,
        "unit_files": len(unit_paths),
        "gates": len(gates),
        "warnings": warnings,
    }


def _referenced_gate_keys(registry: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for flow in (registry.get("flows") or {}).values():
        for step in (flow.get("steps") or {}).values():
            gate = step.get("gate")
            if isinstance(gate, dict) and gate.get("prompt_key"):
                keys.add(str(gate["prompt_key"]))
    return keys


# --------------------------------------------------------------------------
# flow diagram
# --------------------------------------------------------------------------

OPERATOR_WORDS = [
    ("&&", " and "),
    ("||", " or "),
    ("==", " is "),
    ("!=", " is not "),
    ("!(", "not ("),
    ("!", "not "),
]


def humanize(expression: str) -> str:
    text = str(expression)
    for symbol, word in OPERATOR_WORDS:
        text = text.replace(symbol, word)
    text = text.replace("'", "").replace('"', "")
    return re.sub(r"\s+", " ", text).strip()


def node_id(flow_name: str, step_id: str) -> str:
    return f"{flow_name}__{step_id.replace('.', '_')}"


def render_diagram(registry: dict[str, Any]) -> str:
    lines = [
        "%% GENERATED FILE - do not edit by hand.",
        "%% Source: .cursor/foundry/flows/factory-flow.yaml",
        "%% Regenerate: python .cursor/foundry/cli/foundry.py flow diagram",
        "flowchart TD",
    ]
    for flow_name in sorted((registry.get("flows") or {}).keys()):
        flow = registry["flows"][flow_name]
        steps = flow.get("steps") or {}
        lines.append(f'  subgraph {flow_name}["{flow_name} flow"]')
        lines.append("    direction TB")
        for step_id in sorted(steps):
            step = steps[step_id]
            label = [step_id, str(step_title(step) or "")]
            gate = step.get("gate")
            if isinstance(gate, dict):
                label.append(f"gate: {gate.get('kind')}")
            if step.get("delivery_gate"):
                label.append("delivery gate")
            if step.get("when_skip"):
                label.append("skippable")
            lines.append(f'    {node_id(flow_name, step_id)}["{"<br/>".join(p for p in label if p)}"]')
        lines.append("  end")
        entry = flow.get("entry")
        lines.append(f'  {flow_name}__entry(["{flow_name} entry"]) --> {node_id(flow_name, entry)}')
        for edge in flow.get("edges") or []:
            source = node_id(flow_name, str(edge["from"]))
            dest = node_id(flow_name, str(edge["to"]))
            when = edge.get("when")
            label = humanize(when) if when not in (None, "", "always") else ""
            if edge.get("rework"):
                connector = f'-. "{label}" .->' if label else "-.->"
            else:
                connector = f'-- "{label}" -->' if label else "-->"
            lines.append(f"  {source} {connector} {dest}")
    return "\n".join(lines) + "\n"


def flow_diagram(flow_path: str | None, out_path: str | None, check: bool) -> dict[str, Any]:
    registry = load_registry(flow_path)
    registry.pop("_path", None)
    rendered = render_diagram(registry)
    destination = Path(out_path) if out_path else DEFAULT_DIAGRAM_PATH
    existing = destination.read_text(encoding="utf-8") if destination.is_file() else None
    if check:
        if existing != rendered:
            raise FoundryError(
                "DIAGRAM_STALE",
                f"{destination} is out of date. Run `foundry.py flow diagram`.",
                extra={"path": str(destination), "exists": existing is not None},
            )
        return {"path": str(destination), "checked": True, "stale": False}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(rendered, encoding="utf-8")
    return {"path": str(destination), "written": True, "changed": existing != rendered}


# --------------------------------------------------------------------------
# schema validate
# --------------------------------------------------------------------------


def schema_validate(file_path: str, schema_name: str) -> dict[str, Any]:
    require_jsonschema()
    filename = SCHEMA_ALIASES.get(schema_name, schema_name)
    schema_path = SCHEMAS_DIR / filename
    if not schema_path.is_file():
        raise FoundryError(
            "UNKNOWN_SCHEMA",
            f"No schema named {schema_name!r}.",
            required_input="schema",
            extra={"knownSchemas": sorted(SCHEMA_ALIASES)},
        )
    document = read_json(Path(file_path), "INVALID_DOCUMENT")
    schema = read_json(schema_path, "MISSING_SCHEMA")
    errors = [
        f"{'/'.join(str(p) for p in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(Draft202012Validator(schema).iter_errors(document), key=str)
    ]
    if errors:
        raise FoundryError(
            "SCHEMA_INVALID",
            f"{file_path} failed {filename}: {len(errors)} error(s)",
            extra={"errors": errors},
        )
    return {"file": file_path, "schema": filename, "valid": True}


def schema_validate_examples() -> dict[str, Any]:
    return call_eval(
        "validate_schema_examples",
        SCHEMAS_DIR,
        SCHEMAS_DIR / "examples",
        validate_document=lambda path, schema: schema_validate(str(path), schema),
    )


# --------------------------------------------------------------------------
# Execution graph (Phase 5)
# --------------------------------------------------------------------------


def ac_ids_from_items(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    ids: list[str] = []
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            ids.append(item["id"])
    return ids


def planner_required(config: dict[str, Any], risk_tier: str | None) -> bool:
    foundry_cfg = resolve_path(config, ["foundry"]) or {}
    planner_cfg = foundry_cfg.get("planner") or {}
    required_risks = planner_cfg.get("required_when_risk") or ["medium", "high"]
    tier = risk_tier or "medium"
    return tier in required_risks


def resolve_graph_path(state_path: Path | None, explicit: str | None = None) -> Path | None:
    if explicit:
        return Path(explicit)
    if state_path is not None:
        candidate = state_path.parent / "execution-graph.json"
        if candidate.is_file():
            return candidate
    return None


def load_execution_graph(file_path: str | Path) -> dict[str, Any]:
    graph = read_json(Path(file_path), "INVALID_GRAPH")
    if not isinstance(graph, dict):
        raise FoundryError("INVALID_GRAPH", f"{file_path} must contain a JSON object.")
    if graph.get("schema_version") != SCHEMA_VERSION:
        raise FoundryError(
            "UNSUPPORTED_PROTOCOL_VERSION",
            f"Execution graph must use Foundry protocol {SCHEMA_VERSION}.",
            recoverable=False,
        )
    return graph


def validate_execution_graph_semantics(
    graph: dict[str, Any],
    *,
    approved_ac_ids: list[str] | None = None,
    min_work_items: int = 1,
    require_docs_after_human_approval: bool = True,
) -> list[str]:
    """Semantic checks beyond JSON Schema: DAG, AC coverage, verification ordering."""
    errors: list[str] = []
    work_items = graph.get("work_items") or []
    if not isinstance(work_items, list) or not work_items:
        errors.append("work_items: at least one work item is required")
        return errors

    ids: list[str] = []
    id_set: set[str] = set()
    covered_ac_refs: set[str] = set()

    for index, item in enumerate(work_items):
        if not isinstance(item, dict):
            errors.append(f"work_items[{index}]: must be an object")
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str):
            errors.append(f"work_items[{index}]: missing id")
            continue
        if item_id in id_set:
            errors.append(f"work_items[{index}]: duplicate id {item_id!r}")
        id_set.add(item_id)
        ids.append(item_id)
        for ac_ref in item.get("ac_refs") or []:
            if isinstance(ac_ref, str):
                covered_ac_refs.add(ac_ref)

    for index, item in enumerate(work_items):
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        for dep in item.get("depends_on") or []:
            if not isinstance(dep, str):
                continue
            if dep not in id_set:
                errors.append(f"work_items[{item_id}].depends_on: unknown dependency {dep!r}")

    # Cycle detection via Kahn topological sort.
    indegree = {item_id: 0 for item_id in ids}
    adjacency: dict[str, list[str]] = {item_id: [] for item_id in ids}
    for item in work_items:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id"))
        for dep in item.get("depends_on") or []:
            if isinstance(dep, str) and dep in indegree:
                indegree[item_id] += 1
                adjacency[dep].append(item_id)
    queue = [item_id for item_id, degree in indegree.items() if degree == 0]
    visited = 0
    while queue:
        current = queue.pop(0)
        visited += 1
        for neighbor in adjacency[current]:
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)
    if visited != len(ids):
        errors.append("depends_on: dependency graph contains a cycle")

    if len(ids) < min_work_items:
        errors.append(
            f"work_items: expected at least {min_work_items} item(s), found {len(ids)}"
        )

    if approved_ac_ids:
        missing = sorted(set(approved_ac_ids) - covered_ac_refs)
        if missing:
            errors.append(f"ac_refs: orphan acceptance criteria not covered by any work item: {missing}")

    if require_docs_after_human_approval:
        verification_plan = graph.get("verification_plan") or []
        doc_steps = [
            entry
            for entry in verification_plan
            if isinstance(entry, dict) and entry.get("step") == "documentation-writer"
        ]
        if not doc_steps:
            errors.append(
                "verification_plan: documentation-writer step is required and must run after step6_human_approval"
            )
        else:
            for entry in doc_steps:
                after = entry.get("after") or []
                if "step6_human_approval" not in after:
                    errors.append(
                        "verification_plan: documentation-writer must list step6_human_approval in after"
                    )

    return errors


def graph_validate(
    file_path: str,
    *,
    state_path: str | None = None,
    approved_ac: str | None = None,
    config_path: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    require_jsonschema()
    graph = load_execution_graph(file_path)
    schema = read_json(SCHEMAS_DIR / "execution-graph.schema.json", "MISSING_SCHEMA")
    schema_errors = [
        f"{'/'.join(str(p) for p in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(Draft202012Validator(schema).iter_errors(graph), key=str)
    ]
    if schema_errors:
        raise FoundryError(
            "SCHEMA_INVALID",
            f"{file_path} failed execution-graph.schema.json: {len(schema_errors)} error(s)",
            extra={"errors": schema_errors},
        )

    approved_ac_ids: list[str] | None = None
    state: dict[str, Any] | None = None
    snapshot: dict[str, Any] | None = None
    if approved_ac:
        payload = coerce_scalar(approved_ac) if approved_ac.strip().startswith(("[", "{")) else approved_ac
        if isinstance(payload, str):
            approved_ac_ids = [part.strip() for part in payload.split(",") if part.strip()]
        elif isinstance(payload, list):
            approved_ac_ids = ac_ids_from_items(payload)
        else:
            raise FoundryError(
                "INVALID_APPROVED_AC",
                "--approved-ac must be a JSON array or comma-separated AC ids.",
                required_input="approved-ac",
            )
    if state_path:
        state, snapshot = load_run_manifest(Path(state_path))
        if approved_ac_ids is None:
            approved_ac_ids = ac_ids_from_items(state.get("approved_ac"))

    resolved_config = config or load_config(config_path)
    foundry_cfg = resolve_path(resolved_config, ["foundry"]) or {}
    planner_cfg = foundry_cfg.get("planner") or {}
    min_work_items = int(planner_cfg.get("min_work_items") or 1)

    semantic_errors = validate_execution_graph_semantics(
        graph,
        approved_ac_ids=approved_ac_ids,
        min_work_items=min_work_items,
    )
    for item in graph.get("work_items") or []:
        if not isinstance(item, dict):
            continue
        owner = str(item.get("owner") or "")
        try:
            foundry_protocol.assert_agent_capability(owner, "work_item")
        except foundry_protocol.ProtocolError as exc:
            semantic_errors.append(f"{item.get('id')}: {exc.message}")
        if snapshot is not None:
            try:
                foundry_app.assert_work_item_owner(snapshot, item)
            except foundry_app.AppManifestError as exc:
                semantic_errors.append(f"{item.get('id')}: {exc.message}")
    if semantic_errors:
        raise FoundryError(
            "GRAPH_INVALID",
            f"{file_path} failed execution graph semantic validation: {len(semantic_errors)} error(s)",
            extra={"errors": semantic_errors},
        )
    if state is not None:
        try:
            foundry_lineage.assert_graph_current(graph, state)
        except foundry_lineage.LineageError as exc:
            raise FoundryError(exc.error_code, exc.message, extra=exc.extra) from exc

    return {
        "file": file_path,
        "schema": "execution-graph.schema.json",
        "valid": True,
        "work_item_count": len(graph.get("work_items") or []),
        "topology": graph.get("topology"),
    }


def graph_ready(file_path: str, completed: Iterable[str] | None = None) -> dict[str, Any]:
    graph = load_execution_graph(file_path)
    work_items = graph.get("work_items") or []
    if not isinstance(work_items, list):
        raise FoundryError("INVALID_GRAPH", "work_items must be an array.")

    completed_ids: set[str] = set(completed or [])
    for item in work_items:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        if item.get("status") == "completed" and isinstance(item_id, str):
            completed_ids.add(item_id)

    ready: list[str] = []
    for item in work_items:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str):
            continue
        if item_id in completed_ids:
            continue
        status = item.get("status", "pending")
        if status in ("failed", "blocked", "in_progress"):
            continue
        dependencies = [dep for dep in (item.get("depends_on") or []) if isinstance(dep, str)]
        if all(dep in completed_ids for dep in dependencies):
            ready.append(item_id)

    return {
        "file": file_path,
        "ready": ready,
        "completed": sorted(completed_ids),
        "all_complete": len(ready) == 0 and all(
            isinstance(item, dict) and item.get("status") == "completed" for item in work_items
        ),
    }


def ensure_plan_stability(graph: dict[str, Any]) -> dict[str, Any]:
    stability = graph.get("plan_stability")
    if not isinstance(stability, dict):
        stability = {}
        graph["plan_stability"] = stability
    stability.setdefault("changes_after_build_started", 0)
    return stability


def graph_record_change(file_path: str, *, after_build_started: bool = False) -> dict[str, Any]:
    path = Path(file_path)
    graph = load_execution_graph(path)
    stability = ensure_plan_stability(graph)
    if after_build_started:
        stability["changes_after_build_started"] = int(stability.get("changes_after_build_started") or 0) + 1
    stability["last_modified_at"] = now_iso()
    path.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    return {
        "file": str(path),
        "changes_after_build_started": stability["changes_after_build_started"],
        "last_modified_at": stability["last_modified_at"],
    }


def graph_add_repair_item(
    file_path: str,
    *,
    state_path: Path | None,
    item_id: str,
    reason: str,
) -> dict[str, Any]:
    if not re.match(r"^[a-z0-9][a-z0-9_-]*$", item_id):
        raise FoundryError(
            "INVALID_WORK_ITEM_ID",
            f"Repair work item id {item_id!r} must match ^[a-z0-9][a-z0-9_-]*$.",
            required_input="id",
        )
    path = Path(file_path)
    graph = load_execution_graph(path)
    if item_id in work_item_index(graph):
        raise FoundryError(
            "WORK_ITEM_DUPLICATE",
            f"Work item {item_id!r} already exists in the execution graph.",
            extra={"work_item_id": item_id},
        )
    item = {
        "id": item_id,
        "description": reason,
        "owner": "repairer",
        "kind": "repair",
        "depends_on": [],
        "ac_refs": [],
        "files_hint": [],
        "evidence_required": ["build-pass"],
        "status": "ready",
    }
    work_items = graph.setdefault("work_items", [])
    if not isinstance(work_items, list):
        raise FoundryError("INVALID_GRAPH", "work_items must be an array.")
    work_items.append(item)
    path.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    stability = graph_record_change(str(path), after_build_started=True)
    if state_path is not None:
        state = load_state(state_path)
        append_event(
            state_path.parent / "events.jsonl",
            make_event(
                str(state["run_id"]),
                "evidence_recorded",
                "engine",
                step_id=str(state.get("current_step")),
                payload={"work_item_id": item_id, "kind": "repair", "reason": reason},
            ),
        )
        mark_post_repair_required_on_state(state)
        write_state(state_path, state)
    return {
        "file": str(path),
        "work_item_id": item_id,
        "owner": "repairer",
        "kind": "repair",
        "status": "ready",
        "reason": reason,
        "plan_stability": stability,
    }


def validate_low_risk_graph(graph: dict[str, Any]) -> None:
    topology = graph.get("topology")
    work_items = graph.get("work_items") or []
    if topology != "single_worker" or len(work_items) != 1:
        raise FoundryError(
            "GRAPH_LOW_RISK_INVALID",
            "Low-risk runs with an execution graph must use topology single_worker and exactly one work item.",
            extra={"topology": topology, "work_item_count": len(work_items)},
        )


def validate_build_entry(
    state: dict[str, Any],
    config: dict[str, Any],
    *,
    state_path: Path | None = None,
    graph_path: str | None = None,
) -> None:
    risk_tier = str(state.get("risk_tier") or "medium")
    resolved_graph_path = resolve_graph_path(state_path, graph_path)
    if state.get("feature_branch_head"):
        snapshot = call_shared("git_snapshot", Path(str(state.get("app_folder"))))
        drift = []
        if snapshot["branch"] != state.get("feature_branch"):
            drift.append("branch")
        if snapshot["head"] != state.get("feature_branch_head"):
            drift.append("head")
        if drift:
            raise FoundryError(
                "FEATURE_BRANCH_DRIFT",
                "The checked-out branch no longer matches the implement.branch checkpoint.",
                extra={"mismatches": drift},
            )

    graph_id = state.get("execution_graph_id")
    graph_step = step_evidence(state, "plan.graph")
    if not graph_id or not graph_step.get("human_approved"):
        raise FoundryError(
            "EXECUTION_GRAPH_REQUIRED",
            "implement.build requires an approved execution graph for every risk tier.",
            required_input="execution_graph_id",
            extra={
                "risk_tier": risk_tier,
                "execution_graph_id": graph_id,
                "plan_graph_human_approved": graph_step.get("human_approved"),
            },
        )
    if resolved_graph_path is None:
        raise FoundryError(
            "GRAPH_FILE_MISSING",
            "execution-graph.json was not found beside state.json and --graph was not provided.",
            required_input="graph",
        )
    graph_validate(
        str(resolved_graph_path),
        state_path=str(state_path) if state_path is not None else None,
        config=config,
    )
    if risk_tier == "low":
        validate_low_risk_graph(load_execution_graph(resolved_graph_path))


BUILDER_AGENTS = frozenset({"backend-builder", "client-builder", "feature-builder", "repairer"})
CRITIC_LAUNCH_AGENTS = frozenset({"bugbot", "security-review"})
POST_REPAIR_TRIGGER_AGENTS = frozenset(
    {"repairer", "backend-builder", "client-builder", "feature-builder"}
)
POST_REPAIR_SKIP_AGENTS = frozenset(
    {
        "implementation-validator",
        "bugbot",
        "security-review",
        "documentation-writer",
        "planner",
        "devops-builder",
        "story-writer",
        "codebase-researcher",
        "grilling",
    }
)
PRE_PR_REVIEW_STEP_ID = "implement.pre_pr_review"


def assert_open_launches_closed(state: dict[str, Any]) -> None:
    launches = state.get("open_subagent_launches") or []
    if not launches:
        return
    raise FoundryError(
        "OPEN_SUBAGENT_LAUNCH",
        "One or more subagent launches are still open; complete them before transitioning.",
        extra={"open_launches": launches},
    )


def receipt_has_builder_evidence(receipt: dict[str, Any]) -> bool:
    outputs = receipt.get("outputs") if isinstance(receipt.get("outputs"), dict) else {}
    files_changed = outputs.get("files_changed") if isinstance(outputs.get("files_changed"), list) else []
    if files_changed:
        return True
    commands = receipt.get("commands") if isinstance(receipt.get("commands"), list) else []
    return any(isinstance(item, dict) and item.get("exit_code") == 0 for item in commands)


def work_item_delegation_proven(
    events_path: Path,
    work_item_id: str,
    *,
    step_id: str = ORCHESTRATION_STEP_ID,
) -> bool:
    events = call_observability("load_events", events_path)
    launched = False
    completed = False
    for event in events:
        if event.get("step_id") != step_id:
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if payload.get("work_item_id") != work_item_id:
            continue
        if event.get("event_type") == "subagent_launched":
            launched = True
        if event.get("event_type") == "subagent_completed":
            completed = True
    return launched and completed


def validate_work_item_receipt(
    receipt: dict[str, Any],
    *,
    work_item_id: str,
    owner: str,
) -> None:
    if receipt.get("work_item_id") != work_item_id:
        raise FoundryError(
            "BUILD_RECEIPT_INVALID",
            f"Receipt work_item_id does not match {work_item_id!r}.",
            extra={"expected": work_item_id, "actual": receipt.get("work_item_id")},
        )
    agent = receipt.get("agent") if isinstance(receipt.get("agent"), dict) else {}
    if agent.get("name") != owner:
        raise FoundryError(
            "BUILD_RECEIPT_INVALID",
            f"Receipt agent {agent.get('name')!r} does not match work item owner {owner!r}.",
            extra={"work_item_id": work_item_id, "owner": owner},
        )
    if not receipt_has_builder_evidence(receipt):
        raise FoundryError(
            "BUILD_RECEIPT_THIN",
            f"Work item {work_item_id!r} receipt lacks files_changed or successful commands.",
            extra={"receipt_id": receipt.get("receipt_id")},
        )


def validate_step_build_receipt(
    receipt: dict[str, Any],
    *,
    child_receipt_ids: list[str],
    work_item_count: int,
    run_id: str | None = None,
    expected_receipt_id: str | None = None,
) -> None:
    outputs = receipt.get("outputs") if isinstance(receipt.get("outputs"), dict) else {}
    if outputs.get("work_items_completed"):
        raise FoundryError(
            "BUILD_STEP_RECEIPT_INVALID",
            "Step receipt must not aggregate work_items_completed; use child_receipt_ids.",
            extra={"receipt_id": receipt.get("receipt_id")},
        )
    agent = receipt.get("agent") if isinstance(receipt.get("agent"), dict) else {}
    if agent.get("name") == "feature-builder" and agent.get("mode") == "implement":
        raise FoundryError(
            "BUILD_STEP_RECEIPT_INVALID",
            "feature-builder/implement is not valid as the implement.build step receipt.",
            extra={"receipt_id": receipt.get("receipt_id")},
        )
    children = receipt.get("child_receipt_ids") if isinstance(receipt.get("child_receipt_ids"), list) else []
    if len(children) != work_item_count:
        raise FoundryError(
            "BUILD_STEP_RECEIPT_INVALID",
            "Step receipt child_receipt_ids must list every work item receipt.",
            extra={
                "expected_count": work_item_count,
                "actual_count": len(children),
                "child_receipt_ids": children,
            },
        )
    if sorted(str(item) for item in children) != sorted(child_receipt_ids):
        raise FoundryError(
            "BUILD_STEP_RECEIPT_INVALID",
            "Step receipt child_receipt_ids do not match execution graph receipts.",
            extra={"expected": child_receipt_ids, "actual": children},
        )
    commands = receipt.get("commands") if isinstance(receipt.get("commands"), list) else []
    successful = [item for item in commands if isinstance(item, dict) and item.get("exit_code") == 0]
    if len(successful) < 2:
        raise FoundryError(
            "BUILD_VERIFY_MISSING",
            "Step receipt must include successful build and test commands.",
            extra={"receipt_id": receipt.get("receipt_id")},
        )
    provenance = receipt.get("provenance") if isinstance(receipt.get("provenance"), dict) else {}
    provenance_ok = (
        provenance.get("source") == "build_step_verify"
        and provenance.get("cli_command") == BUILD_STEP_VERIFY_COMMAND
        and (run_id is None or provenance.get("run_id") == run_id)
    )
    if agent.get("name") == "feature-builder" and agent.get("mode") == "orchestrate" and not provenance_ok:
        raise FoundryError(
            "BUILD_VERIFY_RECEIPT_FORGED",
            "feature-builder/orchestrate step receipts must carry CLI provenance from build-step verify.",
            extra={"receipt_id": receipt.get("receipt_id"), "provenance": provenance},
        )
    if not provenance_ok:
        raise FoundryError(
            "BUILD_VERIFY_RECEIPT_FORGED",
            "implement.build step receipt must be produced by build-step verify.",
            extra={"receipt_id": receipt.get("receipt_id"), "provenance": provenance},
        )
    if expected_receipt_id and receipt.get("receipt_id") != expected_receipt_id:
        raise FoundryError(
            "BUILD_VERIFY_RECEIPT_FORGED",
            "Evidence receipt_id does not match the CLI-recorded build-step verify receipt.",
            extra={
                "expected": expected_receipt_id,
                "actual": receipt.get("receipt_id"),
            },
        )


def assert_build_step_verify_cli_evidence(
    state: dict[str, Any],
    *,
    state_path: Path,
    step_receipt: dict[str, Any],
) -> None:
    events = call_observability("load_events", state_path.parent / "events.jsonl")
    started_at = None
    evidence = (state.get("steps") or {}).get(ORCHESTRATION_STEP_ID)
    if isinstance(evidence, dict):
        started_at = evidence.get("started_at")
        if not isinstance(started_at, str):
            started_at = None
    match = latest_successful_build_step_verify_event(
        events,
        step_id=ORCHESTRATION_STEP_ID,
        started_at=started_at,
    )
    if match is None:
        raise FoundryError(
            "CLI_EVIDENCE_MISSING",
            "implement.build cannot advance without a successful cli_invoked event for build-step verify.",
            extra={"step_id": ORCHESTRATION_STEP_ID},
        )
    recorded_id = None
    if isinstance(evidence, dict):
        recorded_id = evidence.get("build_step_verify_receipt_id")
    if not recorded_id:
        raise FoundryError(
            "BUILD_VERIFY_NOT_RUN",
            "state.steps.implement.build.build_step_verify_receipt_id is missing. Run build-step verify.",
        )
    if step_receipt.get("receipt_id") != recorded_id:
        raise FoundryError(
            "BUILD_VERIFY_RECEIPT_FORGED",
            "Transition evidence is not the receipt written by build-step verify.",
            extra={"expected": recorded_id, "actual": step_receipt.get("receipt_id")},
        )
    payload = match.get("payload") if isinstance(match.get("payload"), dict) else {}
    event_receipt_id = payload.get("receipt_id")
    if isinstance(event_receipt_id, str) and event_receipt_id != recorded_id:
        raise FoundryError(
            "BUILD_VERIFY_RECEIPT_FORGED",
            "cli_invoked receipt_id does not match the recorded build-step verify receipt.",
            extra={"event_receipt_id": event_receipt_id, "recorded": recorded_id},
        )


def validate_build_exit(
    state: dict[str, Any],
    config: dict[str, Any],
    *,
    state_path: Path,
    evidence_path: Path | None = None,
    require_step_receipt: bool = True,
) -> None:
    assert_open_launches_closed(state)
    resolved_graph_path = resolve_graph_path(state_path, None)
    if resolved_graph_path is None or not resolved_graph_path.is_file():
        raise FoundryError(
            "GRAPH_FILE_MISSING",
            "execution-graph.json was not found beside state.json.",
            required_input="graph",
        )

    graph = load_execution_graph(resolved_graph_path)
    work_items = graph.get("work_items") or []
    if not work_items:
        return

    ready = graph_ready(str(resolved_graph_path))
    if not ready["all_complete"]:
        raise FoundryError(
            "BUILD_GRAPH_INCOMPLETE",
            "Every execution graph work item must be completed before leaving implement.build.",
            extra=ready,
        )

    events_path = state_path.parent / "events.jsonl"
    receipts_dir = state_path.parent / "receipts"
    child_receipt_ids: list[str] = []

    for item in work_items:
        if not isinstance(item, dict):
            continue
        work_item_id = str(item.get("id"))
        owner = str(item.get("owner"))
        receipt_id = item.get("receipt_id")
        if not isinstance(receipt_id, str):
            raise FoundryError(
                "BUILD_ITEM_INCOMPLETE",
                f"Work item {work_item_id!r} is missing receipt_id.",
                extra={"work_item_id": work_item_id},
            )
        child_receipt_ids.append(receipt_id)
        if not work_item_delegation_proven(events_path, work_item_id):
            raise FoundryError(
                "BUILD_DELEGATION_UNPROVEN",
                f"Work item {work_item_id!r} lacks matching subagent launch and completion events.",
                extra={"work_item_id": work_item_id},
            )
        receipt = load_receipt(receipts_dir, receipt_id)
        validate_work_item_receipt(receipt, work_item_id=work_item_id, owner=owner)

    if require_step_receipt:
        if evidence_path is None or not evidence_path.is_file():
            raise FoundryError(
                "BUILD_STEP_RECEIPT_INVALID",
                "implement.build requires an orchestrator step receipt as transition evidence.",
                required_input="evidence",
            )
        step_receipt = read_json(evidence_path, "INVALID_RECEIPT")
        if not isinstance(step_receipt, dict):
            raise FoundryError("INVALID_RECEIPT", "Step evidence must be a receipt JSON object.")
        build_evidence = (state.get("steps") or {}).get(ORCHESTRATION_STEP_ID)
        expected_receipt_id = None
        if isinstance(build_evidence, dict):
            expected_receipt_id = build_evidence.get("build_step_verify_receipt_id")
        validate_step_build_receipt(
            step_receipt,
            child_receipt_ids=child_receipt_ids,
            work_item_count=len(work_items),
            run_id=str(state.get("run_id")) if state.get("run_id") else None,
            expected_receipt_id=str(expected_receipt_id) if expected_receipt_id else None,
        )
        assert_build_step_verify_cli_evidence(
            state,
            state_path=state_path,
            step_receipt=step_receipt,
        )
        # TODO: optionally require cli_invoked test evidence when leaving implement.documentation.


def worker_next_builder(
    *,
    state_path: Path,
    graph_path: str,
    config_path: str | None,
) -> dict[str, Any]:
    ready = graph_ready(graph_path)
    if ready["all_complete"]:
        return {
            "done": True,
            "file": graph_path,
            "completed": ready["completed"],
        }
    if not ready["ready"]:
        raise FoundryError(
            "BUILD_BLOCKED",
            "No work items are ready; resolve in-progress or failed items first.",
            extra=ready,
        )
    work_item_id = ready["ready"][0]
    packet = builder_packet(
        state_path=state_path,
        graph_path=graph_path,
        work_item_id=work_item_id,
        receipts_dir=None,
        config_path=config_path,
    )
    return {
        "done": False,
        "file": graph_path,
        "work_item_id": work_item_id,
        "packet": packet,
        "launch": {
            "agent": packet["subagent"],
            "mode": packet["subagent_mode"],
            "work_item": work_item_id,
        },
    }


def build_step_verify(
    state_path: Path,
    *,
    graph_path: str | None,
    config_path: str | None,
    runner: Any | None = None,
) -> dict[str, Any]:
    state = load_state(state_path)
    config = load_run_config(state_path, state, config_path)
    resolved_graph = graph_path or str(resolve_graph_path(state_path, None) or "")
    validate_build_exit(
        state,
        config,
        state_path=state_path,
        evidence_path=None,
        require_step_receipt=False,
    )

    try:
        verification_results = run_manifest_verification(
            state_path,
            "implementation",
            runner=runner,
        )
    except FoundryError as exc:
        log_step_cli(
            state_path,
            state,
            config,
            command=BUILD_STEP_VERIFY_COMMAND,
            argv=["build-step", "verify"],
            exit_code=1,
        )
        maybe_auto_block_on_failure(
            state_path,
            command=BUILD_STEP_VERIFY_COMMAND,
            error_code=exc.error_code,
            message=exc.message,
            config=config,
        )
        raise

    graph = load_execution_graph(resolved_graph)
    child_receipt_ids = [
        str(item["receipt_id"])
        for item in (graph.get("work_items") or [])
        if isinstance(item, dict) and isinstance(item.get("receipt_id"), str)
    ]
    receipt_id = str(uuid.uuid4())
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "receipt_id": receipt_id,
        "run_id": str(state["run_id"]),
        "timestamp": now_iso(),
        "agent": {"name": "feature-builder", "mode": "orchestrate"},
        "status": "completed",
        "recommended_next_state": "implement.validate",
        "child_receipt_ids": child_receipt_ids,
        "commands": [
            result["receipt_command"]
            for result in verification_results
        ],
        "summary": "Manifest implementation verification passed for all work items.",
        "provenance": {
            "source": "build_step_verify",
            "cli_command": BUILD_STEP_VERIFY_COMMAND,
            "run_id": str(state["run_id"]),
        },
    }
    receipts_dir = state_path.parent / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipts_dir / f"{receipt_id}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    build_evidence = state.setdefault("steps", {}).setdefault(ORCHESTRATION_STEP_ID, {})
    build_evidence["build_step_verify_receipt_id"] = receipt_id
    build_evidence["build_step_verify_at"] = now_iso()
    write_state(state_path, state)
    log_step_cli(
        state_path,
        state,
        config,
        command=BUILD_STEP_VERIFY_COMMAND,
        argv=["build-step", "verify"],
        exit_code=0,
        extra={"receipt_id": receipt_id},
    )
    return {
        "receipt_id": receipt_id,
        "receipt_path": str(receipt_path),
        "child_receipt_ids": child_receipt_ids,
        "verification": verification_results,
    }


# --------------------------------------------------------------------------
# Worker runtime and build (Phase 6)
# --------------------------------------------------------------------------

DEFAULT_DEPENDENCY_SUMMARY_TOKEN_BUDGET = 500
DEFAULT_RECEIPT_FILES_CHANGED_LIMIT = 25
DEFAULT_VALIDATOR_LOOP_THRESHOLD = 5
DEFAULT_BUILDER_TO_BUGBOT_LOOP_THRESHOLD = 3


def worker_config(config: dict[str, Any]) -> dict[str, Any]:
    foundry_cfg = resolve_path(config, ["foundry"]) or {}
    worker_cfg = foundry_cfg.get("worker") or {}
    return {
        "dependency_summary_token_budget": int(
            worker_cfg.get("dependency_summary_token_budget") or DEFAULT_DEPENDENCY_SUMMARY_TOKEN_BUDGET
        ),
        "validator_loop_threshold": int(
            worker_cfg.get("validator_loop_threshold") or DEFAULT_VALIDATOR_LOOP_THRESHOLD
        ),
        "builder_to_bugbot_loop_threshold": int(
            worker_cfg.get("builder_to_bugbot_loop_threshold") or DEFAULT_BUILDER_TO_BUGBOT_LOOP_THRESHOLD
        ),
    }


def ensure_rework(state: dict[str, Any]) -> dict[str, Any]:
    rework = state.setdefault("rework", {})
    rework.setdefault("validator_loops", 0)
    rework.setdefault("builder_to_bugbot_loops", 0)
    return rework


def dependency_summary_char_budget(config: dict[str, Any]) -> int:
    tokens = worker_config(config)["dependency_summary_token_budget"]
    return max(tokens * 4, 1)


def truncate_summary(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def bound_files_changed(
    paths: list[str],
    *,
    max_files: int = DEFAULT_RECEIPT_FILES_CHANGED_LIMIT,
) -> tuple[list[str], int]:
    if len(paths) <= max_files:
        return paths, 0
    return paths[:max_files], len(paths) - max_files


def slim_builder_packet_for_launch(packet: dict[str, Any]) -> dict[str, Any]:
    """Drop fields duplicated by the outer worker launch packet."""
    return {key: value for key, value in packet.items() if key not in ("factory_config", "prompt")}


def load_receipt(receipts_dir: Path, receipt_id: str) -> dict[str, Any]:
    path = receipts_dir / f"{receipt_id}.json"
    if not path.is_file():
        raise FoundryError(
            "MISSING_RECEIPT",
            f"Receipt not found: {path}",
            required_input="receipts_dir",
            extra={"receipt_id": receipt_id},
        )
    receipt = read_json(path, "INVALID_RECEIPT")
    if not isinstance(receipt, dict):
        raise FoundryError("INVALID_RECEIPT", f"Receipt at {path} must be a JSON object.")
    return receipt


def work_item_index(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in graph.get("work_items") or []:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            indexed[item["id"]] = item
    return indexed


def work_item_by_id(graph: dict[str, Any], work_item_id: str) -> dict[str, Any]:
    item = work_item_index(graph).get(work_item_id)
    if item is None:
        raise FoundryError(
            "UNKNOWN_WORK_ITEM",
            f"Work item {work_item_id!r} is not in the execution graph.",
            required_input="work_item",
            extra={"knownWorkItems": sorted(work_item_index(graph))},
        )
    return item


def work_item_slice(item: dict[str, Any]) -> dict[str, Any]:
    """Minimal work-item packet — excludes sibling work-item prose."""
    return {
        "id": item.get("id"),
        "description": item.get("description"),
        "owner": item.get("owner"),
        "kind": item.get("kind") or "feature",
        "ac_refs": item.get("ac_refs") or [],
        "files_hint": item.get("files_hint") or [],
        "depends_on": item.get("depends_on") or [],
        "evidence_required": item.get("evidence_required") or [],
    }


def filter_approved_ac(state: dict[str, Any], ac_refs: Iterable[str]) -> list[dict[str, Any]]:
    ref_set = set(ac_refs)
    approved = state.get("approved_ac") or []
    if not isinstance(approved, list):
        return []
    return [
        item
        for item in approved
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"] in ref_set
    ]


def summarize_receipt(receipt: dict[str, Any], *, max_chars: int) -> dict[str, Any]:
    outputs = receipt.get("outputs") if isinstance(receipt.get("outputs"), dict) else {}
    summary = outputs.get("summary_markdown") if isinstance(outputs.get("summary_markdown"), str) else ""
    raw_files = outputs.get("files_changed") if isinstance(outputs.get("files_changed"), list) else []
    files_changed, omitted = bound_files_changed([str(path) for path in raw_files])
    payload: dict[str, Any] = {
        "receipt_id": receipt.get("receipt_id"),
        "work_item_id": receipt.get("work_item_id"),
        "status": receipt.get("status"),
        "summary": truncate_summary(summary, max_chars),
        "files_changed": files_changed,
    }
    if omitted:
        payload["files_changed_omitted"] = omitted
    return payload


def dependency_receipt_summaries(
    graph: dict[str, Any],
    work_item: dict[str, Any],
    receipts_dir: Path,
    *,
    max_chars: int,
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for dep_id in work_item.get("depends_on") or []:
        if not isinstance(dep_id, str):
            continue
        dep_item = work_item_by_id(graph, dep_id)
        receipt_id = dep_item.get("receipt_id")
        if not isinstance(receipt_id, str):
            continue
        summaries.append(summarize_receipt(load_receipt(receipts_dir, receipt_id), max_chars=max_chars))
    return summaries


def format_builder_prompt(
    work_item: dict[str, Any],
    approved_ac: list[dict[str, Any]],
    dependency_summaries: list[dict[str, Any]],
    factory_config: dict[str, Any],
    *,
    mode: str = "implement",
) -> str:
    templates = factory_config.get("templates") or {}
    lines = [
        f"Mode: {mode}",
        f"Work item: {work_item.get('id')} — {work_item.get('description')}",
        f"Acceptance criteria refs: {', '.join(work_item.get('ac_refs') or [])}",
        f"Files in scope: {', '.join(work_item.get('files_hint') or [])}",
        f"Templates: {templates.get('implement')}, {templates.get('add_tests')}, {templates.get('run_tests')}",
        "Scope files from the run snapshot builder routes in project_context; unmatched paths use default_owner.",
        "Return: files changed, tests added, commands run with exit codes, blockers.",
        "If craft_staging_path is provided, follow .cursor/foundry/docs/worker-launch-contract.md.",
    ]
    if approved_ac:
        lines.append("Approved acceptance criteria:")
        for item in approved_ac:
            lines.append(f"- {item.get('id')}: {item.get('text')}")
    if dependency_summaries:
        lines.append("Dependency receipt summaries:")
        for summary in dependency_summaries:
            lines.append(
                f"- {summary.get('work_item_id')} ({summary.get('receipt_id')}): {summary.get('summary')}"
            )
    return "\n".join(lines)


def builder_packet(
    *,
    state_path: Path,
    graph_path: str,
    work_item_id: str,
    receipts_dir: str | None,
    config_path: str | None,
) -> dict[str, Any]:
    state, snapshot = load_run_manifest(state_path)
    config = load_run_config(state_path, state, config_path)
    graph = load_execution_graph(graph_path)
    work_item = work_item_by_id(graph, work_item_id)
    owner = str(work_item.get("owner"))
    kind = str(work_item.get("kind") or "feature")
    subagent_mode = "repair" if owner == "repairer" or kind == "repair" else "implement"
    config_role = owner if owner in CONFIG_ROLES else "backend-builder"
    resolved_owner = call_app("assert_work_item_owner", snapshot, work_item)
    max_chars = dependency_summary_char_budget(config)
    resolved_receipts = Path(receipts_dir) if receipts_dir else state_path.parent / "receipts"
    dependency_summaries = dependency_receipt_summaries(
        graph,
        work_item,
        resolved_receipts,
        max_chars=max_chars,
    )
    approved_ac = filter_approved_ac(state, work_item.get("ac_refs") or [])
    factory_config = slice_config(
        config,
        config_role,
        app_folder=str(state.get("app_folder")),
        factory_root=str(state.get("factory_root")),
    )
    factory_config["resolved_profile_hash"] = state.get("resolved_profile_hash") or profile_hash(config)
    project_ctx = call_app("manifest_project_context", state, snapshot)
    packet = {
        "work_item": work_item_slice(work_item),
        "approved_ac": approved_ac,
        "dependency_summaries": dependency_summaries,
        "factory_config": factory_config,
        "project_context": project_ctx,
        "builder_routing": {
            "resolved_owner": resolved_owner,
            "default_owner": (snapshot.get("builders") or {}).get("default_owner"),
            "files_hint": list(work_item.get("files_hint") or []),
        },
        "subagent": owner,
        "subagent_mode": subagent_mode,
        "prompt": format_builder_prompt(
            work_item,
            approved_ac,
            dependency_summaries,
            factory_config,
            mode=subagent_mode,
        ),
    }
    return packet


def validator_ready_check(graph_path: str) -> dict[str, Any]:
    graph = load_execution_graph(graph_path)
    work_items = graph.get("work_items") or []
    incomplete = [
        str(item.get("id"))
        for item in work_items
        if isinstance(item, dict) and item.get("status") != "completed"
    ]
    return {
        "file": graph_path,
        "ready": len(incomplete) == 0 and bool(work_items),
        "incomplete": incomplete,
        "all_complete": len(incomplete) == 0 and bool(work_items),
    }


def builder_receipt_summaries(
    graph: dict[str, Any],
    receipts_dir: Path,
    *,
    max_chars: int,
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for item in graph.get("work_items") or []:
        if not isinstance(item, dict):
            continue
        receipt_id = item.get("receipt_id")
        if not isinstance(receipt_id, str):
            continue
        receipt = load_receipt(receipts_dir, receipt_id)
        summary = summarize_receipt(receipt, max_chars=max_chars)
        summary["work_item_id"] = item.get("id")
        summaries.append(summary)
    return summaries


def validator_packet(
    *,
    state_path: Path,
    graph_path: str,
    receipts_dir: str | None,
    config_path: str | None,
) -> dict[str, Any]:
    state = load_state(state_path)
    config = load_run_config(state_path, state, config_path)
    graph = load_execution_graph(graph_path)
    readiness = validator_ready_check(graph_path)
    if not readiness["ready"]:
        raise FoundryError(
            "VALIDATOR_NOT_READY",
            "implementation-validator requires every work item to be completed.",
            extra=readiness,
        )
    max_chars = dependency_summary_char_budget(config)
    resolved_receipts = Path(receipts_dir) if receipts_dir else state_path.parent / "receipts"
    return {
        "graph_path": graph_path,
        "execution_graph": graph,
        "approved_ac": state.get("approved_ac") or [],
        "builder_receipt_summaries": builder_receipt_summaries(graph, resolved_receipts, max_chars=max_chars),
        "subagent": "implementation-validator",
        "subagent_mode": "validate",
        "app_folder": state.get("app_folder"),
    }


def parse_findings_json(raw: str) -> list[dict[str, Any]]:
    payload = coerce_scalar(raw) if raw.strip().startswith(("[", "{")) else raw
    if isinstance(payload, str):
        raise FoundryError(
            "INVALID_FINDINGS",
            "--findings must be a JSON array of finding objects.",
            required_input="findings",
        )
    if isinstance(payload, dict) and isinstance(payload.get("findings"), list):
        findings = payload["findings"]
    elif isinstance(payload, list):
        findings = payload
    else:
        raise FoundryError(
            "INVALID_FINDINGS",
            "--findings must be a JSON array or {findings:[...]}.",
            required_input="findings",
        )
    return [item for item in findings if isinstance(item, dict)]


def route_critical_findings(graph_path: str, findings_raw: str) -> dict[str, Any]:
    graph = load_execution_graph(graph_path)
    findings = parse_findings_json(findings_raw)
    items = work_item_index(graph)
    ac_to_items: dict[str, list[str]] = {}
    for item_id, item in items.items():
        for ac_ref in item.get("ac_refs") or []:
            if isinstance(ac_ref, str):
                ac_to_items.setdefault(ac_ref, []).append(item_id)

    routes: list[dict[str, Any]] = []
    for finding in findings:
        severity = str(finding.get("severity") or finding.get("grade") or "").lower()
        if severity != "critical":
            continue
        work_item_id = finding.get("work_item_id")
        candidate_ids: list[str] = []
        if isinstance(work_item_id, str) and work_item_id in items:
            candidate_ids = [work_item_id]
        else:
            ac_ref = finding.get("ac_ref")
            if isinstance(ac_ref, str):
                candidate_ids = [item_id for item_id in ac_to_items.get(ac_ref, []) if item_id in items]
        for candidate_id in candidate_ids:
            item = items[candidate_id]
            routes.append(
                {
                    "work_item_id": candidate_id,
                    "owner": item.get("owner"),
                    "finding": finding,
                }
            )
    return {"routes": routes, "route_count": len(routes)}


def graph_complete_item(
    graph_path: str,
    work_item_id: str,
    receipt_id: str,
    *,
    state_path: Path | None = None,
) -> dict[str, Any]:
    path = Path(graph_path)
    graph = load_execution_graph(path)
    item = work_item_by_id(graph, work_item_id)
    if state_path is not None:
        events_path = state_path.parent / "events.jsonl"
        if not work_item_delegation_proven(events_path, work_item_id):
            raise FoundryError(
                "BUILD_DELEGATION_UNPROVEN",
                f"Work item {work_item_id!r} lacks matching subagent launch and completion events.",
                extra={"work_item_id": work_item_id},
            )
        receipt = load_receipt(state_path.parent / "receipts", receipt_id)
        validate_work_item_receipt(
            receipt,
            work_item_id=work_item_id,
            owner=str(item.get("owner")),
        )
    item["status"] = "completed"
    item["receipt_id"] = receipt_id
    path.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    if state_path is not None and item.get("kind") == "repair":
        state = load_state(state_path)
        rework = state.get("rework") if isinstance(state.get("rework"), dict) else {}
        if rework.get("post_repair_ok") is not True:
            run_post_repair_verification(state_path)
    return {
        "file": str(path),
        "work_item_id": work_item_id,
        "status": "completed",
        "receipt_id": receipt_id,
    }


def command_receipt_entry(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "command": result.get("command"),
        "exit_code": result.get("exitCode"),
        "duration_ms": result.get("durationMilliseconds"),
    }


def load_run_manifest(state_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    state = load_state(state_path)
    snapshot = call_app(
        "assert_run_manifest_current",
        state,
        state_path.parent,
        check_live=False,
    )
    return state, snapshot


def assert_run_manifest_current(
    state_path: Path,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_state = state or load_state(state_path)
    return call_app(
        "assert_run_manifest_current",
        resolved_state,
        state_path.parent,
    )


def run_manifest_command(
    state_path: Path,
    command_name: str,
    runner: Any | None = None,
) -> dict[str, Any]:
    state, snapshot = load_run_manifest(state_path)
    command = (snapshot.get("commands") or {}).get(command_name)
    if not isinstance(command, dict):
        raise FoundryError(
            "APP_MANIFEST_COMMAND_NOT_SNAPSHOTTED",
            f"Command {command_name!r} is not available in this run snapshot.",
            extra={"available": sorted((snapshot.get("commands") or {}).keys())},
        )
    result = call_shared(
        "run_manifest_command",
        Path(str(state["app_folder"])),
        command_name,
        command,
        runner=runner,
    )
    return {**result, "receipt_command": command_receipt_entry(result)}


def run_manifest_verification(
    state_path: Path,
    policy: str,
    runner: Any | None = None,
) -> list[dict[str, Any]]:
    _, snapshot = load_run_manifest(state_path)
    command_names = (snapshot.get("verification") or {}).get(policy)
    if not isinstance(command_names, list):
        raise FoundryError(
            "APP_MANIFEST_VERIFICATION_POLICY_MISSING",
            f"Verification policy {policy!r} is not available in this run snapshot.",
        )
    return [
        run_manifest_command(state_path, str(command_name), runner=runner)
        for command_name in command_names
    ]


def mark_post_repair_required_on_state(state: dict[str, Any]) -> dict[str, Any]:
    rework = ensure_rework(state)
    rework["post_repair_required"] = True
    rework["post_repair_ok"] = False
    return rework


def mark_post_repair_required(state_path: Path) -> dict[str, Any]:
    state = load_state(state_path)
    rework = mark_post_repair_required_on_state(state)
    write_state(state_path, state)
    return rework


def resolve_git_head_sha(
    state: dict[str, Any],
    *,
    state_path: Path | None,
    git_snapshot: dict[str, str] | None = None,
    required: bool = False,
) -> str | None:
    if git_snapshot is not None:
        head = git_snapshot.get("head")
        return str(head) if head else None
    if state_path is None:
        return None
    app_folder = state.get("app_folder")
    if not app_folder:
        if required:
            raise FoundryError(
                "GIT_SNAPSHOT_FAILED",
                "Cannot snapshot git HEAD because app_folder is missing.",
            )
        return None
    try:
        snapshot = call_shared("git_snapshot", Path(str(app_folder)))
    except FoundryError as exc:
        if required:
            raise FoundryError(
                "GIT_SNAPSHOT_FAILED",
                exc.message,
                extra=exc.extra,
            ) from exc
        return None
    head = snapshot.get("head") if isinstance(snapshot, dict) else None
    return str(head) if head else None


def lookup_critic_launch_ids(
    state_path: Path,
    critics: list[str],
    step_id: str,
) -> dict[str, str]:
    found: dict[str, str] = {}
    events = call_observability("load_events", state_path.parent / "events.jsonl")
    for event in events:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        agent = payload.get("agent")
        launch_id = payload.get("launch_id")
        if agent not in critics or not launch_id:
            continue
        if event.get("step_id") not in (step_id, None):
            continue
        if event.get("event_type") in ("subagent_launched", "subagent_completed"):
            found[str(agent)] = str(launch_id)
    staging = state_path.parent / "staging"
    if staging.is_dir():
        for meta_path in staging.glob("*.meta.json"):
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(meta, dict):
                continue
            agent = (meta.get("agent") or {}).get("name")
            launch_id = meta.get("launch_id")
            if agent in critics and launch_id and meta.get("step_id") in (step_id, None):
                found.setdefault(str(agent), str(launch_id))
    return found


def review_critics_for_config(
    config: dict[str, Any],
    selected: list[str] | None = None,
) -> list[str]:
    review = resolve_path(config, ["review"]) or {}
    mode = str(review.get("mode") or "both")
    payload = call_review("review_critics", mode, selected=selected)
    return list(payload.get("critics") or [])


def assert_critic_receipts_for_state(
    state: dict[str, Any],
    config: dict[str, Any],
    *,
    state_path: Path,
    git_snapshot: dict[str, str] | None = None,
    critics: list[str] | None = None,
    receipt_paths: list[str] | None = None,
) -> dict[str, Any]:
    resolved = critics or review_critics_for_config(config)
    head = resolve_git_head_sha(state, state_path=state_path, git_snapshot=git_snapshot)
    launch_ids = lookup_critic_launch_ids(state_path, resolved, PRE_PR_REVIEW_STEP_ID)
    return call_review(
        "assert_critic_receipts_valid",
        str(state_path.parent / "receipts"),
        resolved,
        receipt_paths=receipt_paths,
        expected_run_id=str(state["run_id"]),
        expected_step_id=PRE_PR_REVIEW_STEP_ID,
        expected_head_sha=head,
        expected_branch_point=state.get("default_branch"),
        require_launch_ids=launch_ids or None,
    )


def completed_repair_items(state_path: Path | None) -> list[dict[str, Any]]:
    if state_path is None:
        return []
    graph_path = resolve_graph_path(state_path, None)
    if graph_path is None or not graph_path.is_file():
        return []
    graph = load_execution_graph(graph_path)
    return [
        item
        for item in (graph.get("work_items") or [])
        if isinstance(item, dict)
        and item.get("kind") == "repair"
        and item.get("status") == "completed"
    ]


def post_repair_gate_needed(state: dict[str, Any], state_path: Path | None) -> bool:
    rework = state.get("rework") if isinstance(state.get("rework"), dict) else {}
    if rework.get("post_repair_required") is True:
        return True
    if rework.get("post_repair_ok") is False:
        return True
    return bool(completed_repair_items(state_path))


def assert_post_repair_satisfied(
    state: dict[str, Any],
    *,
    state_path: Path | None,
    git_snapshot: dict[str, str] | None = None,
) -> None:
    if not post_repair_gate_needed(state, state_path):
        return
    rework = state.get("rework") if isinstance(state.get("rework"), dict) else {}
    if rework.get("post_repair_ok") is not True:
        if rework.get("post_repair_at") and rework.get("post_repair_ok") is False:
            raise FoundryError(
                "COMMAND_FAILED",
                "Post-repair verification failed. Re-run after mutating repair.",
                extra={"rework": rework},
            )
        raise FoundryError(
            "POST_REPAIR_NOT_RUN",
            "Mutating repair requires post-repair verification before review or delivery.",
            extra={"rework": rework},
        )
    head = resolve_git_head_sha(state, state_path=state_path, git_snapshot=git_snapshot)
    recorded = rework.get("post_repair_head")
    if head and recorded and recorded != head:
        raise FoundryError(
            "POST_REPAIR_NOT_RUN",
            "Post-repair evidence is stale relative to the current HEAD.",
            extra={"expected_head": head, "post_repair_head": recorded},
        )


def run_post_repair_verification(
    state_path: Path,
    runner: Any | None = None,
    git_snapshot: dict[str, str] | None = None,
) -> dict[str, Any]:
    state = load_state(state_path)
    rework = ensure_rework(state)
    try:
        results = run_manifest_verification(state_path, "post_repair", runner=runner)
    except FoundryError:
        rework["post_repair_ok"] = False
        rework["post_repair_required"] = True
        rework["post_repair_at"] = now_iso()
        write_state(state_path, state)
        raise
    rework["post_repair_ok"] = True
    rework["post_repair_required"] = False
    rework["post_repair_at"] = now_iso()
    snapshot = git_snapshot
    if snapshot is None:
        try:
            snapshot = call_shared("git_snapshot", Path(str(state["app_folder"])))
        except FoundryError:
            snapshot = None
    if isinstance(snapshot, dict) and snapshot.get("head"):
        rework["post_repair_head"] = snapshot["head"]
    write_state(state_path, state)
    return {"ok": True, "verification": results, "rework": rework}


def work_item_kind_from_graph(state_path: Path, work_item_id: str | None) -> str | None:
    if not work_item_id:
        return None
    graph_path = state_path.parent / "execution-graph.json"
    if not graph_path.is_file():
        return None
    try:
        item = work_item_by_id(load_execution_graph(graph_path), work_item_id)
    except FoundryError:
        return None
    kind = item.get("kind")
    return str(kind) if kind else None


def should_run_post_repair_after_complete(
    state: dict[str, Any],
    *,
    agent: str | None,
    work_item_kind: str | None,
) -> bool:
    if not agent or agent in POST_REPAIR_SKIP_AGENTS:
        return False
    rework = state.get("rework") if isinstance(state.get("rework"), dict) else {}
    required = bool(rework.get("post_repair_required"))
    if agent == "repairer" or work_item_kind == "repair":
        return True
    return required and agent in POST_REPAIR_TRIGGER_AGENTS


def review_validate_receipts_command(args: Any) -> dict[str, Any]:
    state_path = Path(args.state) if getattr(args, "state", None) else None
    critics = list(getattr(args, "critics", None) or [])
    receipt_paths = getattr(args, "receipt_paths", None) or None
    if state_path is not None:
        state = load_state(state_path)
        config = load_run_config(state_path, state, getattr(args, "config", None))
        if not critics:
            critics = review_critics_for_config(config)
        return assert_critic_receipts_for_state(
            state,
            config,
            state_path=state_path,
            critics=critics,
            receipt_paths=receipt_paths,
        )
    receipts_dir = getattr(args, "receipts_dir", None)
    if not receipts_dir:
        raise FoundryError(
            "MISSING_RECEIPTS_DIR",
            "Pass --receipts-dir or --state to validate critic receipts.",
            required_input="receipts-dir",
        )
    return call_review(
        "assert_critic_receipts_valid",
        receipts_dir,
        critics,
        receipt_paths=receipt_paths,
    )


def run_build(
    state_path: Path,
    runner: Any | None = None,
) -> dict[str, Any]:
    return run_manifest_command(state_path, "build", runner=runner)


def run_test(
    state_path: Path,
    runner: Any | None = None,
) -> dict[str, Any]:
    return run_manifest_command(state_path, "test", runner=runner)


def increment_rework_counter(
    state: dict[str, Any],
    counter: str,
    *,
    config: dict[str, Any],
    state_path: Path,
    from_step: str,
) -> dict[str, Any]:
    if counter not in ("validator_loops", "builder_to_bugbot_loops"):
        raise FoundryError(
            "INVALID_REWORK_COUNTER",
            f"Unknown rework counter: {counter!r}.",
            required_input="counter",
        )
    rework = ensure_rework(state)
    rework[counter] = int(rework.get(counter) or 0) + 1
    thresholds = worker_config(config)
    threshold_key = (
        "validator_loop_threshold"
        if counter == "validator_loops"
        else "builder_to_bugbot_loop_threshold"
    )
    threshold = thresholds[threshold_key]
    blocked = rework[counter] >= threshold
    events_path = state_path.parent / "events.jsonl"
    if blocked:
        state["blocked"] = {
            "reason": f"{counter} threshold exceeded ({rework[counter]} >= {threshold})",
            "step_id": from_step,
            "since": now_iso(),
        }
        append_event(
            events_path,
            make_event(
                str(state["run_id"]),
                "failure_classified",
                "engine",
                step_id=from_step,
                payload={
                    "failure_class": "implementation_mistake",
                    "source_step_id": from_step,
                    "notes": state["blocked"]["reason"],
                },
            ),
        )
        append_event(
            events_path,
            make_event(
                str(state["run_id"]),
                "blocked",
                "engine",
                step_id=from_step,
                payload={"reason": state["blocked"]["reason"], "rework": rework},
            ),
        )
    write_state(state_path, state)
    return {
        "counter": counter,
        "value": rework[counter],
        "threshold": threshold,
        "blocked": blocked,
        "rework": rework,
    }


def assert_rework_threshold(
    state: dict[str, Any],
    config: dict[str, Any],
    *,
    counter: str,
    threshold_key: str,
    from_step: str,
) -> None:
    rework = ensure_rework(state)
    thresholds = worker_config(config)
    next_count = int(rework.get(counter) or 0) + 1
    threshold = thresholds[threshold_key]
    if next_count >= threshold:
        raise FoundryError(
            "REWORK_THRESHOLD_EXCEEDED",
            (
                f"{counter} threshold exceeded "
                f"({next_count} >= {threshold})."
            ),
            extra={
                "counter": counter,
                "value": next_count,
                "threshold": threshold,
                "from_step": from_step,
            },
        )


def record_rework_on_transition(
    state_path: Path,
    config: dict[str, Any],
    *,
    from_step: str,
    decision: str | None,
) -> dict[str, Any] | None:
    if from_step == "implement.validate" and decision == "critical_findings":
        state = load_state(state_path)
        mark_post_repair_required_on_state(state)
        return increment_rework_counter(
            state,
            "validator_loops",
            config=config,
            state_path=state_path,
            from_step=from_step,
        )
    if from_step == "implement.pre_pr_review" and decision == "fix_findings":
        state = load_state(state_path)
        mark_post_repair_required_on_state(state)
        return increment_rework_counter(
            state,
            "builder_to_bugbot_loops",
            config=config,
            state_path=state_path,
            from_step=from_step,
        )
    return None


# --------------------------------------------------------------------------
# Intake, risk tier, Jira board (Phase 4)
# --------------------------------------------------------------------------


def ac_item_texts(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    texts: list[str] = []
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("text"), str):
            texts.append(item["text"])
    return texts


def intake_validate_ac(state: dict[str, Any]) -> dict[str, Any]:
    presented = ac_item_texts(state.get("presented_ac"))
    approved = ac_item_texts(state.get("approved_ac"))
    if not presented:
        raise FoundryError(
            "AC_MISSING_PRESENTED",
            "presented_ac is empty; run intake.present_ac before approving.",
            required_input="presented_ac",
        )
    if not approved:
        raise FoundryError(
            "AC_MISSING_APPROVED",
            "approved_ac is empty; record approval at intake.approve_ac.",
            required_input="approved_ac",
        )
    if presented != approved:
        raise FoundryError(
            "AC_MISMATCH",
            "approved_ac must match presented_ac verbatim (same texts in order).",
            extra={"presented_count": len(presented), "approved_count": len(approved)},
        )
    return {"valid": True, "criterion_count": len(presented)}


def require_step_receipt(state: dict[str, Any], step_id: str, config: dict[str, Any]) -> None:
    foundry_cfg = resolve_path(config, ["foundry"]) or {}
    observability = foundry_cfg.get("observability") or {}
    if not observability.get("emit_receipts", True):
        return
    evidence = step_evidence(state, step_id)
    if evidence.get("status") == "skipped":
        return
    if not evidence.get("receipt_id"):
        raise FoundryError(
            "RECEIPT_MISSING",
            f"Step {step_id!r} requires a subagent receipt (--evidence).",
            required_input="evidence",
            extra={"stepId": step_id},
        )


def validate_grill_exit(state: dict[str, Any], decision: str | None) -> None:
    grill = step_evidence(state, "intake.grill")
    if grill.get("status") == "skipped":
        return
    unresolved = state.get("grilling_unresolved_count")
    if unresolved is None:
        unresolved = 0
    try:
        unresolved = int(unresolved)
    except (TypeError, ValueError):
        unresolved = 0
    if unresolved <= 0:
        return
    if decision == "accept_risk":
        assumptions = state.get("assumptions") or []
        if not assumptions:
            raise FoundryError(
                "GRILL_ASSUMPTIONS_REQUIRED",
                f"{unresolved} grilling question(s) remain; record assumptions before accept_risk.",
                required_input="assumptions",
                extra={"grilling_unresolved_count": unresolved},
            )
        return
    raise FoundryError(
        "GRILL_UNRESOLVED",
        f"{unresolved} grilling question(s) remain; answer them, record assumptions with accept_risk, "
        "or revise_ac.",
        required_input="decision",
        extra={"grilling_unresolved_count": unresolved},
    )


def validate_intake_exit(
    from_step: str,
    target: str,
    state: dict[str, Any],
    config: dict[str, Any],
    decision: str | None,
) -> None:
    if from_step == "intake.refine" and target != from_step:
        require_step_receipt(state, "intake.refine", config)
    if from_step == "intake.grill" and target == "intake.present_ac":
        require_step_receipt(state, "intake.grill", config)
        validate_grill_exit(state, decision)
    if from_step == "intake.approve_ac" and target not in (from_step, "intake.present_ac", "intake.refine"):
        intake_validate_ac(state)


def suggest_risk_tier(*, ac_count: int, issue_type: str, config_path: str | None) -> dict[str, Any]:
    config = load_config(config_path)
    foundry_cfg = resolve_path(config, ["foundry"]) or {}
    rules = foundry_cfg.get("default_risk_tier_rules") or []
    context = build_context({}, config, None, ac_count=ac_count, issue_type=issue_type)
    matched_rule: dict[str, Any] | None = None
    tier = "low"
    for rule in rules:
        when = str(rule.get("when", ""))
        if when and truthy(when, context):
            tier = str(rule["tier"])
            matched_rule = rule
            break
    return {
        "risk_tier": tier,
        "ac_count": ac_count,
        "issue_type": issue_type,
        "matched_rule": matched_rule,
    }


def _issue_get(issue: dict[str, Any], *path: str, default: Any = "") -> Any:
    current: Any = issue
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return current if current is not None else default


def _issue_status_name(issue: dict[str, Any]) -> str:
    fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else issue
    status = fields.get("status")
    if isinstance(status, dict):
        return str(status.get("name") or status.get("statusCategory", {}).get("name") or "")
    return str(fields.get("status") or "")


def _issue_summary(issue: dict[str, Any]) -> str:
    fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else issue
    return str(fields.get("summary") or issue.get("summary") or "(no summary)")


def _issue_key(issue: dict[str, Any]) -> str:
    return str(issue.get("key") or _issue_get(issue, "fields", "key", default="UNKNOWN"))


def _issue_type_name(issue: dict[str, Any]) -> str:
    fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else issue
    issue_type = fields.get("issuetype")
    if isinstance(issue_type, dict):
        return str(issue_type.get("name") or "Issue")
    return str(fields.get("issuetype") or "Issue")


def _issue_priority_name(issue: dict[str, Any]) -> str:
    fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else issue
    priority = fields.get("priority")
    if isinstance(priority, dict):
        return str(priority.get("name") or "")
    return str(fields.get("priority") or "")


def _issue_assignee(issue: dict[str, Any]) -> str:
    fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else issue
    assignee = fields.get("assignee")
    if isinstance(assignee, dict):
        return str(assignee.get("displayName") or assignee.get("name") or "")
    return str(fields.get("assignee") or "")


def _normalize_status_bucket(status_name: str) -> str:
    lowered = status_name.lower()
    if "progress" in lowered:
        return "in_progress"
    if "done" in lowered or "closed" in lowered or "resolved" in lowered:
        return "done"
    return "to_do"


def jira_format_board(
    issues: list[Any],
    *,
    project_key: str,
    developer_first_name: str | None,
) -> dict[str, Any]:
    if not isinstance(issues, list):
        raise FoundryError("INVALID_ISSUES", "issues must be a JSON array.", required_input="issues")

    buckets: dict[str, list[dict[str, Any]]] = {"to_do": [], "in_progress": [], "other": []}
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        key = _issue_key(issue)
        if project_key and not key.startswith(f"{project_key}-"):
            continue
        status_name = _issue_status_name(issue)
        bucket = _normalize_status_bucket(status_name)
        if bucket == "done":
            continue
        entry = {
            "key": key,
            "summary": _issue_summary(issue),
            "issue_type": _issue_type_name(issue),
            "priority": _issue_priority_name(issue),
            "status": status_name,
            "assignee": _issue_assignee(issue),
        }
        if bucket == "in_progress":
            buckets["in_progress"].append(entry)
        elif bucket == "to_do":
            buckets["to_do"].append(entry)
        else:
            buckets["other"].append(entry)

    lines: list[str] = []
    greeting = developer_first_name or "there"
    lines.append(f"Hi {greeting}! Tickets on the current board ({project_key}):")
    lines.append("")

    index = 1
    numbered: list[dict[str, Any]] = []

    def append_section(title: str, items: list[dict[str, Any]]) -> None:
        nonlocal index
        if not items:
            return
        lines.append(f"### {title}")
        for item in items:
            priority = f", {item['priority']}" if item.get("priority") else ""
            lines.append(
                f"{index}. {item['key']} - {item['summary']} "
                f"({item['issue_type']}{priority})"
            )
            numbered.append({"index": index, **item})
            index += 1
        lines.append("")

    append_section("To Do", buckets["to_do"])
    append_section("In Progress", buckets["in_progress"])
    append_section("Other", buckets["other"])

    lines.append("Reply with the **number** or **issue key** (e.g. TICKET-101).")
    markdown = "\n".join(lines).rstrip() + "\n"
    return {
        "markdown": markdown,
        "numbered_issues": numbered,
        "counts": {
            "to_do": len(buckets["to_do"]),
            "in_progress": len(buckets["in_progress"]),
            "other": len(buckets["other"]),
            "total": len(numbered),
        },
    }


def parse_issues_json(raw: str) -> list[Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FoundryError("INVALID_ISSUES", f"Could not parse issues JSON: {exc}") from exc
    if isinstance(payload, dict) and isinstance(payload.get("issues"), list):
        return payload["issues"]
    if isinstance(payload, list):
        return payload
    raise FoundryError("INVALID_ISSUES", "issues JSON must be an array or {issues: [...]}.")


def issue_key_parse(text: str, pattern: str | None) -> dict[str, Any]:
    return {"issue_key": call_shared("parse_issue_key", text, pattern)}


def pr_title(
    issue_key: str | None,
    summary: str,
    pattern: str | None,
    jira_enabled: bool,
    *,
    state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_issue_key = issue_key
    resolved_pattern = pattern
    resolved_jira_enabled = jira_enabled
    if state is not None:
        if resolved_issue_key is None:
            resolved_issue_key = state.get("issue_key")
        if config is not None:
            if resolved_pattern is None:
                resolved_pattern = foundry_deliver.pr_title_pattern(config)
            jira = config.get("jira") or {}
            if issue_key is None:
                resolved_jira_enabled = bool(jira.get("enabled", True))
    return {
        "title": call_shared(
            "build_pr_title",
            issue_key=resolved_issue_key,
            summary=summary,
            pattern=resolved_pattern,
            jira_enabled=resolved_jira_enabled,
        ),
        "pattern": resolved_pattern,
        "issue_key": resolved_issue_key,
    }


def record_external_operation(
    state_path: Path,
    *,
    integration: str,
    operation: str,
    target: str,
    status: str,
    evidence_json: str | None,
    operation_id: str | None = None,
    request_json: str | None = None,
    remote_id: str | None = None,
) -> dict[str, Any]:
    if integration not in ("github", "jira", "confluence"):
        raise FoundryError("INVALID_INTEGRATION", f"Unsupported integration {integration!r}.")
    if integration == "github" and operation == "pr_verify":
        raise FoundryError(
            "ENGINE_OWNED_EVIDENCE_REQUIRED",
            "GitHub PR verification is engine-owned. Run `deliver pr-verify`.",
            required_input="deliver pr-verify",
        )
    if status not in ("prepared", "succeeded", "failed", "skipped", "reconciled"):
        raise FoundryError("INVALID_OPERATION_STATUS", f"Unsupported operation status {status!r}.")
    evidence = json.loads(evidence_json) if evidence_json else {}
    if not isinstance(evidence, dict):
        raise FoundryError("INVALID_OPERATION_EVIDENCE", "--evidence-json must be a JSON object.")
    request = json.loads(request_json) if request_json else {}
    if not isinstance(request, dict):
        raise FoundryError("INVALID_OPERATION_REQUEST", "--request-json must be a JSON object.")
    state = load_state(state_path)
    events_path = state_path.parent / "events.jsonl"
    events = call_observability("load_events", events_path)
    resolved_operation_id = operation_id or foundry_integrations.operation_id(
        run_id=str(state["run_id"]),
        integration=integration,
        operation=operation,
        target=target,
        request=request,
    )
    prior_success = foundry_integrations.latest_success(events, resolved_operation_id)
    if prior_success is not None and status in ("prepared", "succeeded"):
        return {
            "event_id": prior_success.get("event_id"),
            "payload": prior_success.get("payload"),
            "idempotent": True,
        }
    attempt = foundry_integrations.next_attempt(events, resolved_operation_id)
    event = make_event(
        str(state["run_id"]),
        "external_operation",
        "parent",
        step_id=str(state.get("current_step")),
        payload={
            "integration": integration,
            "operation": operation,
            "target": target,
            "status": status,
            "operation_id": resolved_operation_id,
            "request_digest": foundry_integrations.request_digest(request),
            "attempt": attempt,
            "remote_id": remote_id,
            "evidence": evidence,
        },
    )
    try:
        foundry_protocol.validate_schema(event, "factory-event.schema.json", artifact="external operation event")
    except foundry_protocol.ProtocolError as exc:
        raise FoundryError(exc.error_code, exc.message, extra={"errors": exc.errors}) from exc
    append_event(events_path, event)
    return {"event_id": event["event_id"], "payload": event["payload"], "idempotent": False}


def default_gh_runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def run_gh_json(
    argv: list[str],
    cwd: Path,
    *,
    runner: Any,
) -> Any:
    try:
        result = runner(argv, cwd)
    except FileNotFoundError as exc:
        raise FoundryError(
            "PR_VERIFICATION_LOOKUP_FAILED",
            "GitHub CLI (`gh`) was not found.",
            required_input="gh auth login",
        ) from exc
    if result.returncode != 0:
        raise FoundryError(
            "PR_VERIFICATION_LOOKUP_FAILED",
            "Authenticated GitHub PR lookup failed.",
            required_input="gh auth login",
            extra={"command": argv, "stderr": str(result.stderr or "").strip()},
        )
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        raise FoundryError(
            "PR_VERIFICATION_RESPONSE_INVALID",
            "GitHub CLI returned invalid JSON for PR verification.",
            extra={"command": argv},
        ) from exc


def github_pr_coordinates(pr_url: str) -> tuple[str, str]:
    parsed = urlparse(pr_url)
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com" or len(parts) != 4:
        raise FoundryError(
            "INVALID_PR_URL",
            "PR URL must be https://github.com/{owner}/{repo}/pull/{number}.",
            required_input="pr-url",
        )
    owner, repo, pull_segment, number = parts
    if pull_segment != "pull" or not number.isdigit():
        raise FoundryError(
            "INVALID_PR_URL",
            "PR URL must be https://github.com/{owner}/{repo}/pull/{number}.",
            required_input="pr-url",
        )
    return owner, repo


def verify_github_pr(
    state_path: Path,
    *,
    pr_url: str,
    resolved_pr_title: str | None,
    runner: Any = default_gh_runner,
) -> dict[str, Any]:
    state = load_state(state_path)
    if state.get("current_step") != "deliver.ship":
        raise FoundryError(
            "PR_VERIFICATION_WRONG_STEP",
            "GitHub PR verification can only run at 'deliver.ship'.",
            extra={"current_step": state.get("current_step")},
        )
    owner, repo = github_pr_coordinates(pr_url)
    snapshot = validate_delivery_seal(state)
    expected_title = resolved_pr_title or state.get("resolved_pr_title")
    if not expected_title:
        raise FoundryError(
            "PR_TITLE_REQUIRED",
            "Resolved PR title is required for authenticated verification.",
            required_input="pr-title",
        )
    pr_data = run_gh_json(
        [
            "gh",
            "pr",
            "view",
            pr_url,
            "--json",
            "url,title,headRefName,headRefOid,commits",
        ],
        Path(str(state["app_folder"])),
        runner=runner,
    )
    if not isinstance(pr_data, dict):
        raise FoundryError(
            "PR_VERIFICATION_RESPONSE_INVALID",
            "GitHub CLI PR response must be a JSON object.",
        )
    head_sha = str(pr_data.get("headRefOid") or "")
    if not head_sha:
        raise FoundryError(
            "PR_VERIFICATION_RESPONSE_INVALID",
            "GitHub CLI PR response did not include headRefOid.",
        )
    commit_data = run_gh_json(
        ["gh", "api", f"repos/{owner}/{repo}/git/commits/{head_sha}"],
        Path(str(state["app_folder"])),
        runner=runner,
    )
    tree_data = commit_data.get("tree") if isinstance(commit_data, dict) else None
    remote_tree = tree_data.get("sha") if isinstance(tree_data, dict) else None
    commit_oids = [
        str(item.get("oid"))
        for item in (pr_data.get("commits") or [])
        if isinstance(item, dict) and item.get("oid")
    ]
    seal = state.get("delivery_seal") or {}
    expected = {
        "url": pr_url.rstrip("/"),
        "title": str(expected_title),
        "branch": state.get("feature_branch"),
        "head_sha": snapshot.get("head"),
        "tree": seal.get("index_tree"),
    }
    actual = {
        "url": str(pr_data.get("url") or "").rstrip("/"),
        "title": pr_data.get("title"),
        "branch": pr_data.get("headRefName"),
        "head_sha": head_sha,
        "tree": remote_tree,
    }
    mismatches = [key for key, value in expected.items() if actual.get(key) != value]
    if head_sha not in commit_oids:
        mismatches.append("commits")
    if mismatches:
        raise FoundryError(
            "PR_VERIFICATION_MISMATCH",
            "Authenticated GitHub PR data does not match the sealed local delivery.",
            extra={
                "mismatches": list(dict.fromkeys(mismatches)),
                "expected": expected,
                "actual": {**actual, "commit_oids": commit_oids},
            },
        )
    evidence = {**actual, "commit_oids": commit_oids, "verifier": "authenticated_gh"}
    event = make_event(
        str(state["run_id"]),
        "external_operation",
        "engine",
        step_id="deliver.ship",
        payload={
            "integration": "github",
            "operation": "pr_verify",
            "target": actual["url"],
            "status": "succeeded",
            "evidence": evidence,
        },
    )
    try:
        foundry_protocol.validate_schema(
            event,
            "factory-event.schema.json",
            artifact="authenticated PR verification event",
        )
    except foundry_protocol.ProtocolError as exc:
        raise FoundryError(exc.error_code, exc.message, extra={"errors": exc.errors}) from exc
    append_event(state_path.parent / "events.jsonl", event)
    return {"event_id": event["event_id"], "pr_url": actual["url"], "evidence": evidence}


def assert_pr_operation_evidence(
    state_path: Path,
    state: dict[str, Any],
    *,
    pr_url: str,
    resolved_pr_title: str,
    snapshot: dict[str, Any],
) -> None:
    events = call_observability("load_events", state_path.parent / "events.jsonl")
    matches = [
        event
        for event in events
        if event.get("event_type") == "external_operation"
        and event.get("actor") == "engine"
        and (event.get("payload") or {}).get("integration") == "github"
        and (event.get("payload") or {}).get("operation") == "pr_verify"
        and (event.get("payload") or {}).get("target") == pr_url
        and (event.get("payload") or {}).get("status") == "succeeded"
    ]
    if not matches:
        raise FoundryError(
            "PR_VERIFICATION_REQUIRED",
            "Record a successful github/pr_verify external operation for the supplied PR URL.",
            required_input="external_operation",
        )
    evidence = (matches[-1].get("payload") or {}).get("evidence") or {}
    if evidence.get("verifier") != "authenticated_gh":
        raise FoundryError(
            "PR_VERIFICATION_REQUIRED",
            "Run `deliver pr-verify`; parent-recorded PR evidence is not accepted.",
            required_input="deliver pr-verify",
        )
    seal = state.get("delivery_seal") or {}
    expected = {
        "branch": state.get("feature_branch"),
        "head_sha": snapshot.get("head"),
        "tree": seal.get("index_tree"),
        "title": resolved_pr_title,
    }
    mismatches = [key for key, value in expected.items() if evidence.get(key) != value]
    if mismatches:
        raise FoundryError(
            "PR_VERIFICATION_MISMATCH",
            "GitHub PR evidence does not match the sealed local delivery.",
            extra={"mismatches": mismatches, "expected": expected, "actual": evidence},
        )


def run_complete(
    state_path: Path,
    *,
    pr_url: str | None,
    config_path: str | None,
    resolved_pr_title: str | None = None,
) -> dict[str, Any]:
    state = load_state(state_path)
    assert_run_manifest_current(state_path, state)
    config = load_run_config(state_path, state, config_path)
    open_launches = state.get("open_subagent_launches") or []
    if open_launches:
        raise FoundryError(
            "OPEN_WORK_REMAINS",
            "Run completion is blocked while delegated worker launches remain open.",
            required_input="observability subagent complete or run block",
            extra={"open_subagent_launches": open_launches},
        )
    if orchestrator_settings(config).get("require_integrity_check"):
        import foundry_integrity  # noqa: PLC0415

        integrity = foundry_integrity.run_integrity_check(state_path)
        if not integrity.get("ok"):
            raise FoundryError(
                "INTEGRITY_CHECK_FAILED",
                "Run integrity check failed at completion.",
                extra={"issues": integrity.get("issues") or []},
            )
    obligation = state.get("session_stop_obligation")
    if isinstance(obligation, dict):
        raise FoundryError(
            "SESSION_HANDOFF_REQUIRED",
            "Run `run handoff` after the hard gate before completing the run.",
            required_input="handoff",
            extra={"obligation": obligation},
        )
    if state.get("run_mode") == "analysis":
        if state.get("current_step") != "analysis.deliver":
            raise FoundryError(
                "INVALID_STEP",
                "Analysis runs can only complete from 'analysis.deliver'.",
                extra={"current_step": state.get("current_step")},
            )
        deliver = step_evidence(state, "analysis.deliver")
        if deliver.get("gate_decision") != "approve":
            raise FoundryError(
                "GATE_UNRESOLVED",
                "analysis.deliver requires gate_decision=approve before completion.",
            )
        timestamp = now_iso()
        state["outcome_status"] = "completed"
        deliver["status"] = "completed"
        deliver["completed_at"] = timestamp
        write_state(state_path, state)
        append_event(
            state_path.parent / "events.jsonl",
            make_event(
                str(state["run_id"]),
                "run_completed",
                "engine",
                step_id="analysis.deliver",
                payload={"issue_key": state.get("issue_key"), "run_mode": "analysis"},
            ),
        )
        learning = run_finalize_learning(state_path, outcome_status="completed")
        return {
            "run_id": state.get("run_id"),
            "current_step": state.get("current_step"),
            "completed_at": timestamp,
            "learning_record": learning.get("learning_record"),
            "learning_review": learning.get("learning_review"),
        }
    if not pr_url:
        raise FoundryError(
            "MISSING_PR_URL",
            "Implementation run completion requires --pr-url.",
            required_input="prUrl",
        )
    result = call_deliver(
        "validate_run_complete",
        state,
        pr_url=pr_url,
        resolved_pr_title=resolved_pr_title,
    )
    snapshot = validate_delivery_seal(state)
    delivery_config = ((config.get("foundry") or {}).get("delivery") or {})
    if delivery_config.get("require_pr_verification", False):
        assert_pr_operation_evidence(
            state_path,
            state,
            pr_url=result["pr_url"],
            resolved_pr_title=result["resolved_pr_title"],
            snapshot=snapshot,
        )
    timestamp = now_iso()
    state["pr_url"] = result["pr_url"]
    state["resolved_pr_title"] = result["resolved_pr_title"]
    state["outcome_status"] = "completed"
    ship = state.setdefault("steps", {}).setdefault("deliver.ship", {})
    ship["status"] = "completed"
    ship["completed_at"] = timestamp
    write_state(state_path, state)
    append_event(
        state_path.parent / "events.jsonl",
        make_event(
            str(state["run_id"]),
            "run_completed",
            "engine",
            step_id="deliver.ship",
            payload={
                "pr_url": result["pr_url"],
                "resolved_pr_title": result["resolved_pr_title"],
                "issue_key": state.get("issue_key"),
                "feature_branch": state.get("feature_branch"),
            },
        ),
    )
    learning = run_finalize_learning(state_path, outcome_status="completed")
    return {
        "run_id": state.get("run_id"),
        "current_step": state.get("current_step"),
        "pr_url": result["pr_url"],
        "resolved_pr_title": result["resolved_pr_title"],
        "completed_at": timestamp,
        "learning_record": learning.get("learning_record"),
        "learning_review": learning.get("learning_review"),
    }


def git_default_branch(repo: str) -> dict[str, Any]:
    return {"default_branch": call_shared("git_default_branch", Path(repo))}


def create_feature_branch(
    state_path: Path,
    repo: str,
    name: str,
    start_point: str | None = None,
) -> dict[str, Any]:
    state = load_state(state_path)
    if state.get("current_step") != "implement.branch":
        raise FoundryError(
            "BRANCH_WRONG_STEP",
            "Feature branches can only be created at 'implement.branch'.",
            extra={"current_step": state.get("current_step")},
        )
    resolved_start_point = (start_point or state.get("start_point") or "").strip() or None
    result = call_shared("branch_create", Path(repo), name, start_point=resolved_start_point)
    state["default_branch"] = result["default_branch"]
    state["feature_branch"] = result["branch"]
    state["feature_branch_head"] = result["head"]
    if resolved_start_point:
        state["start_point"] = resolved_start_point
    write_state(state_path, state)
    return result


def prepare_delivery_seal(state_path: Path, factory_root: str) -> dict[str, Any]:
    state = load_state(state_path)
    config = load_run_config(state_path, state, None)
    if state.get("current_step") != "deliver.ship":
        raise FoundryError(
            "DELIVERY_PREPARE_WRONG_STEP",
            "Delivery can only be prepared at 'deliver.ship'.",
            extra={"current_step": state.get("current_step")},
        )
    delivery_check(state, config, state_path=state_path)
    if orchestrator_settings(config).get("require_integrity_check"):
        import foundry_integrity  # noqa: PLC0415

        integrity = foundry_integrity.run_integrity_check(state_path)
        if not integrity.get("ok"):
            raise FoundryError(
                "INTEGRITY_CHECK_FAILED",
                "Run integrity check failed during delivery preparation.",
                extra={"issues": integrity.get("issues") or []},
            )
    repo = Path(str(state["app_folder"]))
    secrets = call_shared("git_staged_secrets_check", repo, Path(factory_root))
    snapshot = call_shared("git_snapshot", repo)
    if snapshot["branch"] != state.get("feature_branch"):
        raise FoundryError(
            "FEATURE_BRANCH_DRIFT",
            "Current Git branch does not match the recorded feature branch.",
            extra={"expected": state.get("feature_branch"), "actual": snapshot["branch"]},
        )
    seal = {
        "branch": snapshot["branch"],
        "base_head": snapshot["head"],
        "index_tree": snapshot["index_tree"],
        "prepared_at": now_iso(),
        "staged_secrets_passed": bool(secrets.get("passed")),
    }
    state["delivery_seal"] = seal
    write_state(state_path, state)
    append_event(
        state_path.parent / "events.jsonl",
        make_event(
            str(state["run_id"]),
            "evidence_recorded",
            "engine",
            step_id="deliver.ship",
            payload={"kind": "delivery_seal", **seal},
        ),
    )
    return {"passed": True, "delivery_seal": seal, "staged_secrets": secrets}


def validate_delivery_seal(state: dict[str, Any]) -> dict[str, Any]:
    seal = state.get("delivery_seal")
    if not isinstance(seal, dict) or not seal.get("staged_secrets_passed"):
        raise FoundryError(
            "DELIVERY_SEAL_REQUIRED",
            "Run `deliver prepare` after staging and before commit/PR creation.",
            required_input="delivery_seal",
        )
    snapshot = call_shared("git_snapshot", Path(str(state["app_folder"])))
    failures = []
    if snapshot["branch"] != seal.get("branch"):
        failures.append("branch")
    if snapshot["index_tree"] != seal.get("index_tree"):
        failures.append("index_tree")
    if failures:
        raise FoundryError(
            "DELIVERY_SEAL_STALE",
            "The branch or committed tree changed after delivery preparation.",
            extra={"mismatches": failures},
        )
    return snapshot


def branch_name(pattern: str, developer: str, issue_key: str) -> dict[str, Any]:
    return {
        "branch": call_shared(
            "expand_branch_name",
            pattern,
            developer_first_name=developer,
            issue_key=issue_key,
        )
    }


def project_context(state_path: Path) -> dict[str, Any]:
    state, snapshot = load_run_manifest(state_path)
    return call_app("manifest_project_context", state, snapshot)


# --------------------------------------------------------------------------
# Documentation, PRD, and knowledge (Phase 7)
# --------------------------------------------------------------------------

import foundry_deliver  # noqa: E402
import foundry_docs  # noqa: E402
import foundry_devops  # noqa: E402
import foundry_eval  # noqa: E402
import foundry_cursor_telemetry  # noqa: E402
import foundry_observability  # noqa: E402
import foundry_review  # noqa: E402

DEFAULT_THRESHOLDS_PATH = FOUNDRY_ROOT / "eval" / "thresholds.yaml"


def call_deliver(function_name: str, *args: Any, **kwargs: Any) -> Any:
    try:
        return getattr(foundry_deliver, function_name)(*args, **kwargs)
    except foundry_deliver.DeliverError as exc:
        raise FoundryError(
            exc.error_code,
            exc.message,
            required_input=exc.required_input,
            extra=exc.extra,
        ) from exc


def call_docs(function_name: str, *args: Any, **kwargs: Any) -> Any:
    try:
        return getattr(foundry_docs, function_name)(*args, **kwargs)
    except foundry_docs.DocsError as exc:
        raise FoundryError(exc.error_code, exc.message, extra=exc.extra) from exc


def call_app(function_name: str, *args: Any, **kwargs: Any) -> Any:
    try:
        return getattr(foundry_app, function_name)(*args, **kwargs)
    except foundry_app.AppManifestError as exc:
        extra = {"errors": exc.errors} if exc.errors else None
        raise FoundryError(
            exc.error_code,
            exc.message,
            required_input=exc.required_input,
            extra=extra,
        ) from exc


def call_devops(function_name: str, *args: Any, **kwargs: Any) -> Any:
    try:
        return getattr(foundry_devops, function_name)(*args, **kwargs)
    except foundry_devops.DevOpsError as exc:
        raise FoundryError(exc.error_code, exc.message, extra=exc.extra) from exc


def call_review(function_name: str, *args: Any, **kwargs: Any) -> Any:
    try:
        return getattr(foundry_review, function_name)(*args, **kwargs)
    except foundry_review.ReviewError as exc:
        raise FoundryError(exc.error_code, exc.message, extra=exc.extra) from exc


def call_observability(function_name: str, *args: Any, **kwargs: Any) -> Any:
    try:
        return getattr(foundry_observability, function_name)(*args, **kwargs)
    except foundry_observability.ObservabilityError as exc:
        raise FoundryError(
            exc.error_code,
            exc.message,
            required_input=exc.required_input,
            extra=exc.extra,
        ) from exc


def call_eval(function_name: str, *args: Any, **kwargs: Any) -> Any:
    try:
        return getattr(foundry_eval, function_name)(*args, **kwargs)
    except foundry_eval.EvalError as exc:
        raise FoundryError(
            exc.error_code,
            exc.message,
            required_input=exc.required_input,
            extra=exc.extra,
        ) from exc


def observability_settings(config: dict[str, Any]) -> dict[str, bool]:
    foundry_cfg = resolve_path(config, ["foundry"]) or {}
    observability = foundry_cfg.get("observability") or {}
    return {
        "emit_receipts": bool(observability.get("emit_receipts", True)),
        "emit_events": bool(observability.get("emit_events", True)),
    }


def record_transition_receipt_events(
    state_path: Path,
    state: dict[str, Any],
    config: dict[str, Any],
    evidence_path: Path | None,
    evidence_refs: list[str],
    step_id: str | None,
) -> None:
    if not evidence_path or not evidence_refs:
        return
    settings = observability_settings(config)
    if not settings["emit_events"]:
        return
    events_path = state_path.parent / "events.jsonl"
    receipts_dir = state_path.parent / "receipts"
    run_id = str(state["run_id"])
    try:
        receipt, _ = call_observability(
            "ensure_receipt_in_run",
            evidence_path,
            receipts_dir,
            run_id,
        )
    except FoundryError:
        return
    receipt_id = str(receipt["receipt_id"])
    existing = {
        (event.get("payload") or {}).get("receipt_id")
        for event in call_observability("load_events", events_path)
        if event.get("event_type") in ("evidence_recorded", "subagent_completed", "subagent_failed")
    }
    if receipt_id in existing:
        return
    agent_info = receipt.get("agent") if isinstance(receipt.get("agent"), dict) else {}
    agent = agent_info.get("name")
    status = receipt.get("status")
    provenance = receipt.get("provenance") if isinstance(receipt.get("provenance"), dict) else {}
    cli_owned_step_receipt = (
        provenance.get("source") == "build_step_verify"
        or agent_info.get("mode") == "orchestrate"
    )
    if agent and not cli_owned_step_receipt:
        event_type = "subagent_failed" if status == "failed" else "subagent_completed"
        append_event(
            events_path,
            make_event(
                run_id,
                event_type,
                "subagent",
                step_id=step_id,
                payload={
                    "receipt_id": receipt_id,
                    "agent": agent,
                    "status": status,
                    "work_item_id": receipt.get("work_item_id"),
                },
            ),
        )
    append_event(
        events_path,
        make_event(
            run_id,
            "evidence_recorded",
            "parent",
            step_id=step_id,
            payload={"receipt_id": receipt_id, "receipt_path": str(receipts_dir / f"{receipt_id}.json")},
        ),
    )


def resolve_cli_run_context(args: argparse.Namespace) -> tuple[Path | None, dict[str, Any] | None, str | None]:
    state_path: Path | None = None
    if getattr(args, "state", None):
        state_path = Path(args.state)
    elif getattr(args, "app_folder", None) and getattr(args, "run_id", None):
        state_path = run_dir(Path(args.app_folder).resolve(), args.run_id) / "state.json"
    if state_path is None or not state_path.is_file():
        return None, None, None
    state = load_state(state_path)
    try:
        config = load_run_config(state_path, state, getattr(args, "config", None))
    except FoundryError:
        config = None
    return state_path, config, str(state.get("current_step"))


def observability_status(
    state_path: Path,
    *,
    config_path: str | None,
    flow_path: str | None,
    recent_event_count: int = 5,
) -> dict[str, Any]:
    state = load_state(state_path)
    config = load_run_config(state_path, state, config_path)
    registry = load_registry(flow_path)
    flow = get_flow(registry, str(state.get("run_mode")))
    return call_observability(
        "build_status_payload",
        state,
        state_path.parent / "events.jsonl",
        recent_event_count=recent_event_count,
        flow=flow,
        compute_next=flow_next,
        config=config,
        state_path=state_path,
    )


def observability_status_markdown(
    state_path: Path,
    *,
    config_path: str | None,
    flow_path: str | None,
    write_file: bool = True,
) -> dict[str, Any]:
    state = load_state(state_path)
    config = load_run_config(state_path, state, config_path)
    registry = load_registry(flow_path)
    flow = get_flow(registry, str(state.get("run_mode")))
    markdown = call_observability(
        "render_status_markdown",
        state,
        flow,
        state_path.parent,
        compute_next=flow_next,
        config=config,
        state_path=state_path,
    )
    status_path = state_path.parent / "status.md"
    written = call_observability("write_status_markdown", status_path, markdown) if write_file else None
    return {"markdown": markdown, "status_path": written}


def observability_receipt_show(
    *,
    receipt_id: str,
    state_path: Path | None,
    receipts_dir: str | None,
) -> dict[str, Any]:
    directory = Path(receipts_dir) if receipts_dir else (state_path.parent / "receipts" if state_path else None)
    if directory is None:
        raise FoundryError(
            "MISSING_RECEIPTS_DIR",
            "Pass --state or --receipts-dir.",
            required_input="receipts_dir",
        )
    receipt_path = call_observability("find_receipt_path", directory, receipt_id)
    receipt = call_observability("load_receipt_file", directory, receipt_id)
    durable_issues = call_observability("validate_receipt_durable", receipt, path=str(receipt_path))
    semantic_issues = call_observability("validate_receipt_semantic", receipt, path=str(receipt_path))
    issues = durable_issues + semantic_issues
    return {
        "receipt_id": receipt_id,
        "receipt_path": str(receipt_path),
        "formatted": call_observability("receipt_summary_markdown", receipt),
        "telemetry_issues": durable_issues,
        "semantic_issues": semantic_issues,
        "valid": not issues,
    }


def observability_receipt_validate(
    receipt_path: Path,
    *,
    run_id: str | None = None,
    state_path: Path | None = None,
) -> dict[str, Any]:
    receipt = read_json(receipt_path, "INVALID_RECEIPT")
    if not isinstance(receipt, dict):
        raise FoundryError("INVALID_RECEIPT", "Receipt must be a JSON object.")
    if run_id and receipt.get("run_id") and receipt.get("run_id") != run_id:
        raise FoundryError(
            "RECEIPT_RUN_MISMATCH",
            f"Receipt run_id {receipt.get('run_id')!r} does not match {run_id!r}.",
        )
    durable_issues = call_observability("validate_receipt_durable", receipt, path=str(receipt_path))
    semantic_issues = call_observability("validate_receipt_semantic", receipt, path=str(receipt_path))
    issues = durable_issues + semantic_issues
    if state_path is not None:
        state = load_state(state_path)
        config = load_run_config(state_path, state, None)
        settings = orchestrator_settings(config)
        if settings["strict_receipts"]:
            assert_receipt_cli_provenance(receipt_path, receipt, state_path)
    return {
        "receipt_id": receipt.get("receipt_id"),
        "receipt_path": str(receipt_path),
        "issues": issues,
        "valid": not issues,
    }


def assert_receipt_cli_provenance(
    receipt_path: Path,
    receipt: dict[str, Any],
    state_path: Path,
) -> None:
    events = call_observability("load_events", state_path.parent / "events.jsonl")
    receipt_id = receipt.get("receipt_id")
    provenance = receipt.get("provenance") if isinstance(receipt.get("provenance"), dict) else {}
    if provenance.get("source") == "build_step_verify":
        matching = [
            event
            for event in events
            if event.get("event_type") == "cli_invoked" and is_build_step_verify_event(event)
        ]
        if matching:
            return
        raise FoundryError(
            "RECEIPT_PROVENANCE_INVALID",
            "Build-step receipt has no matching cli_invoked event.",
            extra={"receipt_id": receipt_id, "receipt_path": str(receipt_path)},
        )
    if receipt.get("work_item_id"):
        for event in events:
            if event.get("event_type") != "subagent_completed":
                continue
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            if payload.get("receipt_id") == receipt_id:
                return
        raise FoundryError(
            "RECEIPT_PROVENANCE_INVALID",
            "Work-item receipt has no matching subagent_completed event.",
            extra={"receipt_id": receipt_id, "receipt_path": str(receipt_path)},
        )
    raise FoundryError(
        "RECEIPT_PROVENANCE_INVALID",
        "Receipt file has no matching CLI provenance event.",
        extra={"receipt_id": receipt_id, "receipt_path": str(receipt_path)},
    )


def observability_gate_present(
    state_path: Path,
    *,
    config_path: str | None,
    prompt_key: str | None = None,
) -> dict[str, Any]:
    state = load_state(state_path)
    config = load_run_config(state_path, state, config_path)
    step_id = str(state.get("current_step"))
    registry = load_registry(None)
    flow = get_flow(registry, str(state.get("run_mode")))
    step = get_step(flow, step_id)
    gate = step.get("gate")
    if not isinstance(gate, dict) or gate.get("kind") not in HUMAN_GATE_KINDS:
        raise FoundryError(
            "GATE_NOT_APPLICABLE",
            f"Step {step_id!r} does not have a human gate to present.",
            extra={"step_id": step_id},
        )
    settings = observability_settings(config)
    events_path = state_path.parent / "events.jsonl"
    if settings["emit_events"]:
        append_event(
            events_path,
            make_event(
                str(state["run_id"]),
                "gate_presented",
                "parent",
                step_id=step_id,
                payload={
                    "gate_kind": gate.get("kind"),
                    "prompt_key": prompt_key or gate.get("prompt_key"),
                },
            ),
        )
    timestamp = now_iso()
    evidence = state.setdefault("steps", {}).setdefault(step_id, {})
    evidence["gate_presented"] = True
    evidence["gate_presented_at"] = timestamp
    write_state(state_path, state)
    return {"step_id": step_id, "gate_presented_at": timestamp}


def plan_record_brief(
    state_path: Path,
    *,
    brief_file: str,
) -> dict[str, Any]:
    import hashlib
    import shutil

    source = Path(brief_file)
    if not source.is_file():
        raise FoundryError("BRIEF_FILE_MISSING", f"Brief file not found: {source}", required_input="brief_file")
    text = source.read_text(encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    state = load_state(state_path)
    version = int(state.get("brief_version") or 0) + 1
    destination = state_path.parent / f"brief-v{version}.md"
    shutil.copy2(source, destination)
    snapshot = {
        "version": version,
        "hash": digest,
        "path": str(destination),
        "captured_at": now_iso(),
        "source_path": str(source),
    }
    state["brief_version"] = version
    state["brief_snapshot"] = snapshot
    write_state(state_path, state)
    return {"brief_snapshot": snapshot}


def observability_events_tail(
    state_path: Path,
    *,
    count: int,
) -> dict[str, Any]:
    events = call_observability("tail_events", state_path.parent / "events.jsonl", count)
    return {"run_id": load_state(state_path).get("run_id"), "count": len(events), "events": events}


def cursor_session_record(
    state_path: Path,
    *,
    conversation_id: str,
    email: str | None = None,
) -> dict[str, Any]:
    run_dir = state_path.parent
    extra = {"email": email} if email else None
    result = foundry_cursor_telemetry.write_cursor_session(
        run_dir,
        conversation_id=conversation_id,
        extra=extra,
    )
    state = load_state(state_path)
    obligation = state.get("session_stop_obligation")
    fulfilled = None
    fresh_conversation_proven = False
    if isinstance(obligation, dict) and obligation.get("handoff_written_at"):
        source_id = obligation.get("source_conversation_id")
        source_identity_known = isinstance(source_id, str) and bool(source_id)
        if (not source_identity_known) or conversation_id != source_id:
            fulfilled = dict(obligation)
            fulfilled["fulfillment_semantics"] = (
                "first_host_identity_after_handoff"
                if not source_identity_known
                else "different_host_identity"
            )
            fresh_conversation_proven = source_identity_known
            state.pop("session_stop_obligation", None)
    state["active_conversation_id"] = conversation_id
    write_state(state_path, state)
    append_event(
        run_dir / "events.jsonl",
        make_event(
            str(state["run_id"]),
            "session_started",
            "engine",
            step_id=str(state.get("current_step")),
            payload={
                "session_id": conversation_id,
                "fresh_conversation_proven": fresh_conversation_proven,
                "fulfilled_obligation": fulfilled,
            },
        ),
    )
    return result


def cursor_usage_enrich(
    state_path: Path,
    *,
    api_key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    email: str | None = None,
) -> dict[str, Any]:
    try:
        return foundry_cursor_telemetry.enrich_cursor_usage(
            state_path.parent,
            api_key=api_key,
            start_date=start_date,
            end_date=end_date,
            email=email,
        )
    except foundry_cursor_telemetry.CursorTelemetryError as exc:
        raise FoundryError(exc.error_code, exc.message, extra=exc.extra) from exc


def observability_metrics_summarize(
    state_path: Path,
    *,
    transcript_path: str | None = None,
) -> dict[str, Any]:
    state = load_state(state_path)
    metrics = call_observability(
        "summarize_metrics",
        state,
        state_path.parent / "events.jsonl",
        state_path.parent,
    )
    return call_eval(
        "enrich_metrics_for_eval",
        metrics,
        state,
        state_path.parent / "events.jsonl",
        transcript_path=Path(transcript_path) if transcript_path else None,
    )


def observability_metrics_export(
    state_path: Path,
    output: str | None,
    *,
    transcript_path: str | None = None,
) -> dict[str, Any]:
    state = load_state(state_path)
    metrics = call_eval(
        "enrich_metrics_for_eval",
        call_observability(
            "summarize_metrics",
            state,
            state_path.parent / "events.jsonl",
            state_path.parent,
        ),
        state,
        state_path.parent / "events.jsonl",
        transcript_path=Path(transcript_path) if transcript_path else None,
    )
    payload = call_observability(
        "export_metrics",
        state,
        state_path.parent / "events.jsonl",
        state_path.parent,
    )
    payload["metrics"] = metrics
    if output:
        Path(output).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        payload["output_path"] = output
    return payload


def metrics_classify(
    state_path: Path,
    *,
    failure_class: str,
    source_step: str | None,
    notes: str | None,
    receipt_id: str | None,
    actor: str,
) -> dict[str, Any]:
    state = load_state(state_path)
    run_dir = state_path.parent
    return call_eval(
        "classify_failure",
        run_id=str(state["run_id"]),
        events_path=run_dir / "events.jsonl",
        failure_class=failure_class,
        source_step_id=source_step,
        notes=notes,
        actor=actor,
        append_event=append_event,
        make_event=make_event,
        receipts_dir=run_dir / "receipts",
        receipt_id=receipt_id,
    )


def metrics_suggest(
    state_path: Path,
    *,
    source_step: str | None,
) -> dict[str, Any]:
    state = load_state(state_path)
    run_dir = state_path.parent
    return call_eval(
        "suggest_failure_class",
        events=call_eval("load_events", run_dir / "events.jsonl"),
        receipts=call_eval("load_receipts", run_dir / "receipts"),
        source_step_id=source_step or str(state.get("current_step") or ""),
    )


def metrics_compare_runs(
    baseline_path: str,
    candidate_path: str,
    *,
    scorecard_baseline: str | None = None,
    scorecard_candidate: str | None = None,
) -> dict[str, Any]:
    baseline_scorecard = json.loads(Path(scorecard_baseline).read_text(encoding="utf-8")) if scorecard_baseline else None
    candidate_scorecard = json.loads(Path(scorecard_candidate).read_text(encoding="utf-8")) if scorecard_candidate else None
    return call_eval(
        "compare_runs",
        Path(baseline_path),
        Path(candidate_path),
        scorecard_baseline=baseline_scorecard,
        scorecard_candidate=candidate_scorecard,
    )


def metrics_check_thresholds(
    *,
    candidate_path: str | None,
    state_path: Path | None,
    baseline_path: str | None,
    packet: str,
    thresholds_path: str | None,
    transcript_path: str | None,
    scorecard_baseline: str | None,
    scorecard_candidate: str | None,
) -> dict[str, Any]:
    thresholds_bundle = call_eval(
        "load_thresholds",
        Path(thresholds_path) if thresholds_path else DEFAULT_THRESHOLDS_PATH,
        packet,
    )
    thresholds = thresholds_bundle.get("packet") if isinstance(thresholds_bundle, dict) else thresholds_bundle
    integrity_thresholds = (
        thresholds_bundle.get("integrity") if isinstance(thresholds_bundle, dict) else None
    )
    baseline_metrics = None
    if baseline_path:
        baseline_metrics = call_eval("load_metrics_export", Path(baseline_path))["metrics"]
    if state_path is not None:
        export = observability_metrics_export(
            state_path,
            None,
            transcript_path=transcript_path,
        )
        candidate_metrics = export["metrics"]
    elif candidate_path:
        candidate_metrics = call_eval("load_metrics_export", Path(candidate_path))["metrics"]
    else:
        raise FoundryError(
            "MISSING_CANDIDATE",
            "Pass --candidate or --state for threshold checks.",
            required_input="candidate",
        )
    baseline_scorecard = json.loads(Path(scorecard_baseline).read_text(encoding="utf-8")) if scorecard_baseline else None
    candidate_scorecard = json.loads(Path(scorecard_candidate).read_text(encoding="utf-8")) if scorecard_candidate else None
    return call_eval(
        "check_thresholds",
        candidate_metrics,
        thresholds,
        baseline_metrics=baseline_metrics,
        scorecard_baseline=baseline_scorecard,
        scorecard_candidate=candidate_scorecard,
        integrity_thresholds=integrity_thresholds,
    )


def observability_subagent_launch(
    state_path: Path,
    *,
    agent: str,
    mode: str,
    work_item: str | None,
    config_path: str | None,
    launch_id: str | None = None,
    receipt_id: str | None = None,
    git_snapshot: dict[str, str] | None = None,
) -> dict[str, Any]:
    state = load_state(state_path)
    if isinstance(state.get("session_stop_obligation"), dict):
        raise FoundryError(
            "SESSION_HANDOFF_REQUIRED",
            "A prior worker or hard-gate checkpoint must be resumed in a proven new host conversation before another worker launch.",
            required_input="handoff",
            extra={"obligation": state.get("session_stop_obligation")},
        )
    config = load_run_config(state_path, state, config_path)
    step_id = str(state.get("current_step"))
    try:
        foundry_protocol.agent_contract(agent, mode)
    except foundry_protocol.ProtocolError as exc:
        raise FoundryError(exc.error_code, exc.message, extra={"errors": exc.errors}) from exc
    if step_id == ORCHESTRATION_STEP_ID:
        if not work_item:
            raise FoundryError(
                "WORK_ITEM_REQUIRED",
                "implement.build subagent launches require --work-item.",
                required_input="work-item",
            )
        graph_path = state_path.parent / "execution-graph.json"
        if not graph_path.is_file():
            raise FoundryError(
                "GRAPH_FILE_MISSING",
                "execution-graph.json was not found beside state.json.",
                required_input="graph",
            )
        graph = load_execution_graph(graph_path)
        item = work_item_by_id(graph, work_item)
        if item.get("status") == "completed":
            raise FoundryError(
                "WORK_ITEM_ALREADY_COMPLETED",
                f"Work item {work_item!r} is already completed.",
                extra={"work_item_id": work_item},
            )
        owner = str(item.get("owner"))
        if agent != owner:
            raise FoundryError(
                "AGENT_OWNER_MISMATCH",
                f"Launch agent {agent!r} does not match work item owner {owner!r}.",
                extra={"work_item_id": work_item, "owner": owner, "agent": agent},
            )
        _, snapshot = load_run_manifest(state_path)
        call_app("assert_work_item_owner", snapshot, item)
    settings = observability_settings(config)
    snapshot = git_snapshot
    branch_point = None
    reviewed_head_sha = None
    if agent in CRITIC_LAUNCH_AGENTS:
        if snapshot is None:
            snapshot = call_shared("git_snapshot", Path(str(state.get("app_folder"))))
        reviewed_head_sha = snapshot.get("head") if isinstance(snapshot, dict) else None
        if not reviewed_head_sha:
            raise FoundryError(
                "GIT_SNAPSHOT_FAILED",
                "Critic launches require a git HEAD snapshot.",
                extra={"agent": agent},
            )
        branch_point = state.get("default_branch")
    result = call_observability(
        "subagent_launch",
        run_id=str(state["run_id"]),
        run_dir=state_path.parent,
        events_path=state_path.parent / "events.jsonl",
        step_id=step_id,
        agent=agent,
        mode=mode,
        work_item_id=work_item,
        append_event=append_event,
        make_event=make_event,
        emit_events=settings["emit_events"],
        launch_id=launch_id,
        receipt_id=receipt_id,
        branch_point=branch_point,
        reviewed_head_sha=reviewed_head_sha,
    )
    launches = state.setdefault("open_subagent_launches", [])
    launches.append(
        {
            "launch_id": result["launch_id"],
            "step_id": step_id,
            "agent": agent,
            "mode": mode,
            "work_item_id": work_item,
            "craft_staging_path": result["craft_staging_path"],
            "started_at": now_iso(),
        }
    )
    write_state(state_path, state)
    return result


def worker_launch_packet(
    state_path: Path,
    *,
    agent: str | None,
    mode: str | None,
    work_item: str | None,
    config_path: str | None,
    flow_path: str | None,
) -> dict[str, Any]:
    """Open one worker launch and emit its complete, bounded Task packet."""
    state = load_state(state_path)
    config = load_run_config(state_path, state, config_path)
    registry = load_registry(flow_path)
    flow = get_flow(registry, str(state.get("run_mode")))
    step_id = str(state.get("current_step"))
    step = get_step(flow, step_id)

    worker_binding = step_worker(step)
    resolved_agent = agent or step_worker_agent(step)
    resolved_mode = mode or step_worker_mode(step)
    resolved_prompt = step_worker_prompt(step) if worker_binding else None
    resolved_contract = step_worker_contract(step) if worker_binding else None
    if step_id == ORCHESTRATION_STEP_ID and work_item:
        graph = load_execution_graph(state_path.parent / "execution-graph.json")
        item = work_item_by_id(graph, work_item)
        resolved_agent = agent or item.get("owner")
        resolved_mode = mode or ("repair" if resolved_agent == "repairer" else "implement")
    if not resolved_agent or not resolved_mode:
        raise FoundryError(
            "WORKER_CONTRACT_MISSING",
            f"Step {step_id!r} does not identify a worker agent and mode.",
            required_input="agent",
        )
    try:
        if resolved_contract:
            contract = foundry_protocol.worker_contract(str(resolved_contract), str(resolved_mode))
        else:
            contract = foundry_protocol.agent_contract(str(resolved_agent), str(resolved_mode))
    except foundry_protocol.ProtocolError as exc:
        raise FoundryError(exc.error_code, exc.message, extra={"errors": exc.errors}) from exc

    budget = step.get("context_budget") if isinstance(step.get("context_budget"), dict) else {
        "max_input_chars": 16000,
        "max_summary_chars": 4000,
    }
    inputs = foundry_handoff.step_inputs(step_id, state, state_path.parent)
    if step_id == ORCHESTRATION_STEP_ID and work_item:
        inputs["builder_packet"] = slim_builder_packet_for_launch(
            builder_packet(
                state_path=state_path,
                graph_path=str(state_path.parent / "execution-graph.json"),
                work_item_id=work_item,
                receipts_dir=None,
                config_path=config_path,
            )
        )
    role = str(resolved_agent) if str(resolved_agent) in CONFIG_ROLES else "parent"
    config_slice = slice_config(
        config,
        role,
        app_folder=str(state.get("app_folder") or ""),
        factory_root=str(state.get("factory_root") or REPO_ROOT),
    )
    config_slice, config_redactions = foundry_context.redact(config_slice)
    inputs, input_redactions = foundry_context.redact(inputs)
    launch_id = str(uuid.uuid4())
    receipt_id = str(uuid.uuid4())
    craft_staging_path = str(
        call_observability("receipt_craft_path", state_path.parent, launch_id)
    )
    named_artifact = None
    if step_id == "plan.brief":
        named_artifact = str(state_path.parent / "brief.md")
    elif step_id == "plan.graph":
        named_artifact = str(state_path.parent / "execution-graph.json")

    allowed_writes: list[str] = [craft_staging_path]
    for scope in contract.get("write_scopes") or []:
        if scope in ("app_folder", "app_folder_docs", "workflow_files"):
            allowed_writes.append(str(state.get("app_folder")))
        elif scope == "named_artifact_path" and named_artifact:
            allowed_writes.append(named_artifact)
    allowed_writes = list(dict.fromkeys(allowed_writes))
    prompt_ref = (
        f".cursor/{resolved_prompt}"
        if resolved_prompt and not resolved_prompt.startswith(".cursor/")
        else (resolved_prompt or f".cursor/agents/{resolved_agent}.md")
    )
    contract_ref = (
        f".cursor/foundry/{resolved_contract}"
        if resolved_contract and not resolved_contract.startswith(".cursor/")
        else (resolved_contract or f".cursor/foundry/contracts/{resolved_agent}.yaml")
    )
    contract_refs = [
        ".cursor/foundry/docs/worker-launch-contract.md",
        contract_ref,
        prompt_ref,
    ]
    prompt = "\n".join(
        [
            f"Run {resolved_agent} in {resolved_mode} mode for Foundry step {step_id}.",
            f"Run ID: {state['run_id']}",
            f"Launch ID: {launch_id}",
            f"Work item: {work_item or 'none'}",
            f"Read contract refs: {', '.join(contract_refs)}",
            f"Allowed writes: {json.dumps(allowed_writes)}",
            f"Write craft-only protocol {SCHEMA_VERSION} JSON to: {craft_staging_path}",
            "Use only the bounded config and inputs in this launch packet; final reply is the craft path.",
        ]
    )
    packet = {
        "schema_version": SCHEMA_VERSION,
        "run_id": state["run_id"],
        "launch_id": launch_id,
        "receipt_id": receipt_id,
        "step_id": step_id,
        "work_item_id": work_item,
        "agent": str(resolved_agent),
        "mode": str(resolved_mode),
        "config": config_slice,
        "inputs": inputs,
        "allowed_writes": allowed_writes,
        "craft_staging_path": craft_staging_path,
        "named_artifact_path": named_artifact,
        "contract_refs": contract_refs,
        "context_budget": budget,
        "input_digests": foundry_lineage.current_digests(state, state_path.parent),
        "prompt": prompt,
    }
    try:
        context_usage = foundry_context.enforce_packet(packet, budget)
    except foundry_context.ContextError as exc:
        raise FoundryError(
            exc.error_code,
            exc.message,
            extra={"step_id": step_id, **exc.extra},
        ) from exc
    packet["context_usage"] = context_usage
    packet["redacted_paths"] = config_redactions + input_redactions
    try:
        foundry_protocol.validate_schema(
            packet,
            "packets/worker-launch-packet.schema.json",
            artifact="worker launch packet",
        )
    except foundry_protocol.ProtocolError as exc:
        raise FoundryError(exc.error_code, exc.message, extra={"errors": exc.errors}) from exc
    launch_result = observability_subagent_launch(
        state_path,
        agent=str(resolved_agent),
        mode=str(resolved_mode),
        work_item=work_item,
        config_path=config_path,
        launch_id=launch_id,
        receipt_id=receipt_id,
    )
    meta_path = Path(str(launch_result["receipt_meta_path"]))
    meta = read_json(meta_path, "INVALID_RECEIPT")
    if isinstance(meta, dict):
        meta["input_digests"] = packet["input_digests"]
        meta["context_usage"] = context_usage
        foundry_store.atomic_write_text(meta_path, json.dumps(meta, indent=2) + "\n")
    return packet


def resolve_open_subagent_launch(
    state: dict[str, Any],
    launch_id: str | None,
    *,
    step_id: str,
) -> dict[str, Any]:
    if not launch_id:
        raise FoundryError(
            "LAUNCH_ID_REQUIRED",
            "Subagent completion requires --launch-id from worker launch-packet.",
            required_input="launch-id",
        )
    launches = state.get("open_subagent_launches") or []
    match = next(
        (item for item in launches if isinstance(item, dict) and item.get("launch_id") == launch_id),
        None,
    )
    if match is None:
        raise FoundryError(
            "LAUNCH_ID_UNKNOWN",
            f"No open launch matches launch_id {launch_id!r}.",
            extra={"launch_id": launch_id},
        )
    if match.get("step_id") != step_id:
        raise FoundryError(
            "LAUNCH_STEP_MISMATCH",
            f"Launch {launch_id!r} belongs to step {match.get('step_id')!r}, not {step_id!r}.",
            extra={"launch_id": launch_id, "expected_step": step_id, "launch_step": match.get("step_id")},
        )
    return match


def observability_subagent_complete(
    state_path: Path,
    *,
    receipt: str,
    launch_id: str | None,
    config_path: str | None,
) -> dict[str, Any]:
    state = load_state(state_path)
    config = load_run_config(state_path, state, config_path)
    step_id = str(state.get("current_step"))
    receipt_path = Path(receipt)
    match = resolve_open_subagent_launch(state, launch_id, step_id=step_id)
    staging_path = Path(str(match.get("craft_staging_path") or ""))
    call_observability(
        "assert_receipt_staging_path",
        receipt_path,
        state_path.parent / "receipts",
        staging_path,
    )
    receipt_data = read_json(receipt_path, "INVALID_RECEIPT")
    if not isinstance(receipt_data, dict):
        raise FoundryError("INVALID_RECEIPT", "Receipt must be a JSON object.")
    flow = get_flow(load_registry(None), str(state.get("run_mode")))
    step_meta = get_step(flow, step_id)
    budget = step_meta.get("context_budget") or {
        "max_input_chars": 16000,
        "max_summary_chars": 4000,
    }
    try:
        foundry_context.enforce_summary(receipt_data, budget)
    except foundry_context.ContextError as exc:
        raise FoundryError(exc.error_code, exc.message, extra=exc.extra) from exc
    if step_id == ORCHESTRATION_STEP_ID:
        work_item_id = match.get("work_item_id")
        # Prefer craft overlay for builder evidence when present
        craft_candidate = Path(str(match.get("craft_staging_path") or ""))
        evidence_blob = receipt_data
        if craft_candidate.is_file():
            craft_data = read_json(craft_candidate, "INVALID_RECEIPT")
            if isinstance(craft_data, dict):
                evidence_blob = {**receipt_data, **craft_data}
        if evidence_blob.get("work_item_id") not in (work_item_id, None) and evidence_blob.get("work_item_id") != work_item_id:
            # Allow missing work_item_id on craft — launch meta supplies it
            if evidence_blob.get("work_item_id") is not None:
                raise FoundryError(
                    "BUILD_RECEIPT_INVALID",
                    "Receipt work_item_id does not match the open launch.",
                    extra={
                        "launch_work_item_id": work_item_id,
                        "receipt_work_item_id": evidence_blob.get("work_item_id"),
                    },
                )
        if not receipt_has_builder_evidence(evidence_blob):
            raise FoundryError(
                "BUILD_RECEIPT_THIN",
                "Builder receipt must include files_changed or successful commands.",
                extra={"receipt_id": receipt_data.get("receipt_id") or match.get("launch_id")},
            )
    settings = observability_settings(config)
    result = call_observability(
        "subagent_complete",
        run_id=str(state["run_id"]),
        events_path=state_path.parent / "events.jsonl",
        receipts_dir=state_path.parent / "receipts",
        receipt_path=receipt_path,
        launch_id=launch_id,
        step_id=step_id,
        state=state,
        append_event=append_event,
        make_event=make_event,
        emit_events=settings["emit_events"],
    )
    durable_receipt = load_receipt(state_path.parent / "receipts", str(result["receipt_id"]))
    patch = durable_receipt.get("state_patch")
    if isinstance(patch, dict):
        for dotted, value in assert_state_patch_owned(
            step_id,
            step_meta,
            flatten_patch(patch),
            source=f"launch:{launch_id}",
        ):
            nested_set(state, dotted, value)
    step_record = state.setdefault("steps", {}).setdefault(step_id, {})
    step_record["receipt_id"] = result["receipt_id"]
    step_record["launch_id"] = launch_id
    if step_id == "implement.documentation":
        step_record["report"] = "received"
    if step_id == PRE_PR_REVIEW_STEP_ID:
        receipt_ids = step_record.setdefault("critic_receipt_ids", [])
        if isinstance(receipt_ids, list) and result["receipt_id"] not in receipt_ids:
            receipt_ids.append(result["receipt_id"])
    if launch_id:
        launches = state.get("open_subagent_launches") or []
        state["open_subagent_launches"] = [
            item
            for item in launches
            if not (isinstance(item, dict) and item.get("launch_id") == launch_id)
        ]
    state["session_stop_obligation"] = {
        "reason": "stop_after_worker",
        "step_id": step_id,
        "created_at": now_iso(),
        "launch_id": launch_id,
    }
    write_state(state_path, state)
    agent_name = str(match.get("agent") or "")
    item_kind = work_item_kind_from_graph(state_path, match.get("work_item_id"))
    if should_run_post_repair_after_complete(
        state,
        agent=agent_name,
        work_item_kind=item_kind,
    ):
        result["post_repair"] = run_post_repair_verification(state_path)
    return result


def prd_sync_validate(repo: str, factory_root: str) -> dict[str, Any]:
    return call_shared("prd_sync_validate", Path(repo), Path(factory_root))


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="foundry.py", description="Foundry v2 state engine")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run")
    run_sub = run.add_subparsers(dest="run_command", required=True)
    run_init_p = run_sub.add_parser("init")
    run_init_p.add_argument("--app-folder", required=True)
    run_init_p.add_argument("--issue-key", default=None)
    run_init_p.add_argument(
        "--run-mode", required=True, choices=("implementation", "analysis")
    )
    run_init_p.add_argument("--factory-root", default=None)
    run_init_p.add_argument("--config", default=None)
    run_init_p.add_argument("--developer-first-name", default=None)
    run_init_p.add_argument("--risk-tier", default="medium", choices=("low", "medium", "high"))
    run_init_p.add_argument(
        "--interaction-mode",
        default=None,
        choices=("interactive", "drive_to_pr", "plan_control"),
    )
    run_init_p.add_argument("--flow", default=None)
    run_init_p.add_argument("--run-id", default=None)
    run_init_p.add_argument("--ticket-file", default=None, help="Seal local markdown ticket into run ticket.json")
    run_init_p.add_argument(
        "--ticket-stdin",
        action="store_true",
        help="Read pasted ticket markdown from stdin and seal as source=paste",
    )
    run_init_p.add_argument(
        "--ticket-text",
        default=None,
        help="Pasted ticket markdown text to seal (alternative to --ticket-stdin)",
    )
    run_init_p.add_argument(
        "--start-point",
        default=None,
        help="Git ref to create the feature branch from instead of the detected default branch",
    )

    run_show_p = run_sub.add_parser("show")
    run_show_p.add_argument("--state", default=None)
    run_show_p.add_argument("--app-folder", default=None)
    run_show_p.add_argument("--run-id", default=None)

    run_list_p = run_sub.add_parser("list")
    run_list_p.add_argument("--app-folder", required=True)

    run_latest_p = run_sub.add_parser("latest")
    run_latest_p.add_argument("--app-folder", required=True)
    run_latest_p.add_argument("--issue-key", default=None)

    run_handoff_p = run_sub.add_parser("handoff")
    run_handoff_p.add_argument("--state", required=True)
    run_handoff_p.add_argument("--config", default=None)
    run_handoff_p.add_argument("--flow", default=None)
    run_handoff_p.add_argument("--what-happened", default=None)
    run_handoff_p.add_argument("--what-next", default=None)

    run_finalize_p = run_sub.add_parser("finalize-learning")
    run_finalize_p.add_argument("--state", required=True)
    run_finalize_p.add_argument(
        "--outcome",
        default="completed",
        choices=("completed", "abandoned", "blocked"),
    )
    run_finalize_p.add_argument("--abandon-reason", default=None)

    run_abandon_p = run_sub.add_parser("abandon")
    run_abandon_p.add_argument("--state", required=True)
    run_abandon_p.add_argument("--reason", required=True)

    run_recover_p = run_sub.add_parser("recover")
    run_recover_p.add_argument("--state", required=True)

    run_complete_p = run_sub.add_parser("complete")
    run_complete_p.add_argument("--state", required=True)
    run_complete_p.add_argument("--pr-url", default=None)
    run_complete_p.add_argument("--config", default=None)
    run_complete_p.add_argument("--pr-title", default=None, dest="resolved_pr_title")

    run_block_p = run_sub.add_parser("block")
    run_block_p.add_argument("--state", required=True)
    run_block_p.add_argument("--reason", required=True)
    run_block_p.add_argument("--step-id", default=None)

    run_unblock_p = run_sub.add_parser("unblock")
    run_unblock_p.add_argument("--state", required=True)
    run_unblock_p.add_argument("--decision", required=True)

    run_context_p = run_sub.add_parser("context")
    run_context_p.add_argument("--state", required=True)

    run_integrity_p = run_sub.add_parser("integrity-check")
    run_integrity_p.add_argument("--state", required=True)
    run_integrity_p.add_argument("--transcript", default=None)

    cli = sub.add_parser("cli")
    cli_sub = cli.add_subparsers(dest="cli_command", required=True)
    cli_resolve_p = cli_sub.add_parser("resolve")
    cli_resolve_p.add_argument("--factory-root", default=None)

    invoke = sub.add_parser("invoke")
    invoke_sub = invoke.add_subparsers(dest="invoke_command", required=True)
    invoke_render_p = invoke_sub.add_parser("render")
    invoke_render_p.add_argument("--tail", required=True, help="foundry-invoke argv tail")
    invoke_render_p.add_argument("--state", default=None)
    invoke_render_p.add_argument("--factory-root", default=None)
    invoke_render_p.add_argument("--foundry-cli", default=None, dest="foundry_cli_override")

    cfg = sub.add_parser("config")
    cfg_sub = cfg.add_subparsers(dest="config_command", required=True)
    cfg_get = cfg_sub.add_parser("get")
    cfg_get.add_argument("--factory-root", required=True)
    cfg_get.add_argument("--role", required=True, choices=CONFIG_ROLES)
    cfg_get.add_argument("--app-folder", default=None)
    cfg_get.add_argument("--profile", default=None)

    app = sub.add_parser("app")
    app_sub = app.add_subparsers(dest="app_command", required=True)
    app_discover = app_sub.add_parser("discover")
    app_discover.add_argument("--app-folder", required=True)
    app_init = app_sub.add_parser("init")
    app_init.add_argument("--app-folder", required=True)
    app_init.add_argument("--manifest-file", required=True)
    app_init.add_argument(
        "--run-mode",
        choices=("implementation", "analysis"),
        required=True,
    )
    app_init.add_argument("--dry-run", action="store_true")
    app_init.add_argument("--force", action="store_true")
    app_validate = app_sub.add_parser("validate")
    app_validate.add_argument("--app-folder", required=True)
    app_validate.add_argument(
        "--run-mode",
        choices=("implementation", "analysis"),
        required=True,
    )
    app_context = app_sub.add_parser("print-context")
    app_context.add_argument("--app-folder", required=True)
    app_context.add_argument(
        "--run-mode",
        choices=("implementation", "analysis"),
        required=True,
    )

    issue = sub.add_parser("issue-key")
    issue_sub = issue.add_subparsers(dest="issue_command", required=True)
    issue_parse = issue_sub.add_parser("parse")
    issue_parse.add_argument("--text", required=True)
    issue_parse.add_argument("--pattern", default=None)

    title = sub.add_parser("pr-title")
    title.add_argument("--issue-key", default=None)
    title.add_argument("--summary", required=True)
    title.add_argument("--pattern", default=None)
    title.add_argument("--jira-enabled", default="true", choices=("true", "false"))
    title.add_argument("--state", default=None)
    title.add_argument("--config", default=None)

    git = sub.add_parser("git")
    git_sub = git.add_subparsers(dest="git_command", required=True)
    git_branch = git_sub.add_parser("default-branch")
    git_branch.add_argument("--repo", required=True)
    git_secrets = git_sub.add_parser("staged-secrets-check")
    git_secrets.add_argument("--repo", required=True)
    git_secrets.add_argument("--factory-root", required=True)
    git_secrets.add_argument(
        "--pattern",
        default=None,
        help="Replace team-variables patterns (tests/debug only)",
    )

    branch = sub.add_parser("branch")
    branch_sub = branch.add_subparsers(dest="branch_command", required=True)
    branch_create_p = branch_sub.add_parser("create")
    branch_create_p.add_argument("--repo", required=True)
    branch_create_p.add_argument("--name", required=True)
    branch_create_p.add_argument("--state", required=True)
    branch_create_p.add_argument(
        "--start-point",
        default=None,
        help="Create the feature branch from this ref instead of the detected default branch",
    )

    branch_name = sub.add_parser("branch-name")
    branch_name.add_argument("--pattern", required=True)
    branch_name.add_argument("--developer", "--developer-first-name", required=True, dest="developer")
    branch_name.add_argument("--issue-key", required=True)

    context = sub.add_parser("project-context")
    context.add_argument("--state", required=True)

    build_cmd = sub.add_parser("build")
    build_cmd.add_argument("--state", required=True)

    test_cmd = sub.add_parser("test")
    test_cmd.add_argument("--state", required=True)

    worker = sub.add_parser("worker")
    worker_sub = worker.add_subparsers(dest="worker_command", required=True)
    worker_launch_packet_p = worker_sub.add_parser("launch-packet")
    worker_launch_packet_p.add_argument("--state", required=True)
    worker_launch_packet_p.add_argument("--agent", default=None)
    worker_launch_packet_p.add_argument("--mode", default=None)
    worker_launch_packet_p.add_argument("--work-item", default=None)
    worker_launch_packet_p.add_argument("--config", default=None)
    worker_launch_packet_p.add_argument("--flow", default=None)
    worker_builder = worker_sub.add_parser("builder-packet")
    worker_builder.add_argument("--state", required=True)
    worker_builder.add_argument("--graph", required=True)
    worker_builder.add_argument("--work-item", required=True)
    worker_builder.add_argument("--receipts-dir", default=None)
    worker_builder.add_argument("--config", default=None)
    worker_validator_ready = worker_sub.add_parser("validator-ready")
    worker_validator_ready.add_argument("--file", required=True)
    worker_validator_packet = worker_sub.add_parser("validator-packet")
    worker_validator_packet.add_argument("--state", required=True)
    worker_validator_packet.add_argument("--graph", required=True)
    worker_validator_packet.add_argument("--receipts-dir", default=None)
    worker_validator_packet.add_argument("--config", default=None)
    worker_route = worker_sub.add_parser("route-critical")
    worker_route.add_argument("--graph", required=True)
    worker_route.add_argument("--findings", required=True)
    worker_complete = worker_sub.add_parser("complete-item")
    worker_complete.add_argument("--file", required=True)
    worker_complete.add_argument("--work-item", required=True)
    worker_complete.add_argument("--receipt", required=True)
    worker_complete.add_argument("--state", default=None)
    worker_next = worker_sub.add_parser("next-builder")
    worker_next.add_argument("--state", required=True)
    worker_next.add_argument("--graph", required=True)
    worker_next.add_argument("--config", default=None)

    build_step = sub.add_parser("build-step")
    build_step_sub = build_step.add_subparsers(dest="build_step_command", required=True)
    build_step_verify_p = build_step_sub.add_parser("verify")
    build_step_verify_p.add_argument("--state", required=True)
    build_step_verify_p.add_argument("--graph", default=None)
    build_step_verify_p.add_argument("--config", default=None)
    worker_rework = worker_sub.add_parser("rework")
    worker_rework.add_argument("--state", required=True)
    worker_rework.add_argument(
        "--counter",
        required=True,
        choices=("validator_loops", "builder_to_bugbot_loops"),
    )
    worker_rework.add_argument("--config", default=None)

    risk = sub.add_parser("risk-tier")
    risk_sub = risk.add_subparsers(dest="risk_command", required=True)
    risk_suggest = risk_sub.add_parser("suggest")
    risk_suggest.add_argument("--ac-count", type=int, required=True)
    risk_suggest.add_argument("--issue-type", required=True)
    risk_suggest.add_argument("--config", default=None)

    jira = sub.add_parser("jira")
    jira_sub = jira.add_subparsers(dest="jira_command", required=True)
    jira_board = jira_sub.add_parser("format-board")
    jira_board.add_argument("--issues", required=True, help="JSON array or {issues:[...]} from MCP search")
    jira_board.add_argument("--project-key", required=True)
    jira_board.add_argument("--developer-first-name", default=None)
    jira_comment = jira_sub.add_parser("format-comment")
    jira_comment.add_argument("--state", required=True)
    jira_comment.add_argument("--config", default=None)
    jira_comment.add_argument("--body", default=None, help="Comment body; defaults to draft-scope-comment output")

    deliver = sub.add_parser("deliver")
    deliver_sub = deliver.add_subparsers(dest="deliver_command", required=True)
    deliver_scope = deliver_sub.add_parser("draft-scope-comment")
    deliver_scope.add_argument("--state", required=True)
    deliver_scope.add_argument("--config", default=None)
    deliver_scope.add_argument("--in-scope-summary", default=None)
    deliver_prepare = deliver_sub.add_parser("prepare")
    deliver_prepare.add_argument("--state", required=True)
    deliver_prepare.add_argument("--factory-root", required=True)
    deliver_pr_verify = deliver_sub.add_parser("pr-verify")
    deliver_pr_verify.add_argument("--state", required=True)
    deliver_pr_verify.add_argument("--pr-url", required=True)
    deliver_pr_verify.add_argument("--pr-title", default=None)

    intake = sub.add_parser("intake")
    intake_sub = intake.add_subparsers(dest="intake_command", required=True)
    intake_ac = intake_sub.add_parser("validate-ac")
    intake_ac.add_argument("--state", required=True)

    flow = sub.add_parser("flow")
    flow_sub = flow.add_subparsers(dest="flow_command", required=True)

    flow_current_p = flow_sub.add_parser("current")
    flow_current_p.add_argument("--state", required=True)
    flow_current_p.add_argument("--config", default=None)
    flow_current_p.add_argument("--flow", default=None)

    flow_next_p = flow_sub.add_parser("next")
    flow_next_p.add_argument("--state", required=True)
    flow_next_p.add_argument("--config", default=None)
    flow_next_p.add_argument("--flow", default=None)
    flow_next_p.add_argument("--decision", default=None)

    flow_packet_p = flow_sub.add_parser("orchestrator-packet")
    flow_packet_p.add_argument("--state", required=True)
    flow_packet_p.add_argument("--config", default=None)
    flow_packet_p.add_argument("--flow", default=None)

    flow_resume_p = flow_sub.add_parser("resume-packet")
    flow_resume_p.add_argument("--state", required=True)
    flow_resume_p.add_argument("--config", default=None)
    flow_resume_p.add_argument("--flow", default=None)

    gate = sub.add_parser("gate")
    gate_sub = gate.add_subparsers(dest="gate_command", required=True)
    gate_resolve_p = gate_sub.add_parser("resolve")
    gate_resolve_p.add_argument("--state", required=True)
    gate_resolve_p.add_argument("--decision", required=True)
    gate_resolve_p.add_argument("--source", default="human", choices=("human", "auto"))
    gate_resolve_p.add_argument("--config", default=None)
    gate_resolve_p.add_argument("--flow", default=None)
    gate_resolve_p.add_argument("--devops-empty", action="store_true")
    gate_resolve_p.add_argument("--graph-validated", action="store_true")

    flow_validate_p = flow_sub.add_parser("validate")
    flow_validate_p.add_argument("--flow", default=None)

    flow_diagram_p = flow_sub.add_parser("diagram")
    flow_diagram_p.add_argument("--flow", default=None)
    flow_diagram_p.add_argument("--out", default=None)
    flow_diagram_p.add_argument("--check", action="store_true")

    trans = sub.add_parser("transition")
    trans.add_argument("--state", required=True)
    trans.add_argument("--to", required=True, dest="to_step")
    trans.add_argument("--evidence", default=None)
    trans.add_argument("--config", default=None)
    trans.add_argument("--flow", default=None)
    trans.add_argument("--decision", default=None)
    trans.add_argument("--force", action="store_true")
    trans.add_argument(
        "--set",
        action="append",
        default=[],
        dest="assignments",
        metavar="KEY=JSON",
        help="Record evidence before validating, e.g. steps.implement.code_review.approved=true",
    )

    delivery = sub.add_parser("delivery-check")
    delivery.add_argument("--state", required=True)
    delivery.add_argument("--config", default=None)

    external = sub.add_parser("external-operation")
    external_sub = external.add_subparsers(dest="external_command", required=True)
    external_record = external_sub.add_parser("record")
    external_record.add_argument("--state", required=True)
    external_record.add_argument("--integration", required=True, choices=("github", "jira", "confluence"))
    external_record.add_argument("--operation", required=True)
    external_record.add_argument("--target", required=True)
    external_record.add_argument("--status", required=True, choices=("succeeded", "failed", "skipped"))
    external_record.add_argument("--evidence-json", default=None)
    external_record.add_argument("--operation-id", default=None)
    external_record.add_argument("--request-json", default=None)
    external_record.add_argument("--remote-id", default=None)
    for external_name, external_status in (("prepare", "prepared"), ("reconcile", "reconciled")):
        external_phase = external_sub.add_parser(external_name)
        external_phase.add_argument("--state", required=True)
        external_phase.add_argument("--integration", required=True, choices=("github", "jira", "confluence"))
        external_phase.add_argument("--operation", required=True)
        external_phase.add_argument("--target", required=True)
        external_phase.add_argument("--operation-id", default=None)
        external_phase.add_argument("--request-json", default=None)
        external_phase.add_argument("--evidence-json", default=None)
        external_phase.add_argument("--remote-id", default=None)
        external_phase.set_defaults(external_status=external_status)

    outcome = sub.add_parser("outcome")
    outcome_sub = outcome.add_subparsers(dest="outcome_command", required=True)
    outcome_observe = outcome_sub.add_parser("observe")
    outcome_observe.add_argument("--state", required=True)
    outcome_observe.add_argument("--pr-url", default=None)

    schema = sub.add_parser("schema")
    schema_sub = schema.add_subparsers(dest="schema_command", required=True)
    schema_val = schema_sub.add_parser("validate")
    schema_val.add_argument("--file", required=True)
    schema_val.add_argument("--schema", required=True)
    schema_sub.add_parser("validate-examples")

    metrics = sub.add_parser("metrics")
    metrics_sub = metrics.add_subparsers(dest="metrics_command", required=True)
    metrics_classify_p = metrics_sub.add_parser("classify")
    metrics_classify_p.add_argument("--state", default=None)
    metrics_classify_p.add_argument("--app-folder", default=None)
    metrics_classify_p.add_argument("--run-id", default=None)
    metrics_classify_p.add_argument("--failure-class", "--code", dest="failure_class", required=True)
    metrics_classify_p.add_argument("--source-step", default=None)
    metrics_classify_p.add_argument("--notes", default=None)
    metrics_classify_p.add_argument("--receipt-id", default=None)
    metrics_classify_p.add_argument("--actor", default="human", choices=("human", "parent", "engine"))
    metrics_suggest_p = metrics_sub.add_parser("suggest")
    metrics_suggest_p.add_argument("--state", default=None)
    metrics_suggest_p.add_argument("--app-folder", default=None)
    metrics_suggest_p.add_argument("--run-id", default=None)
    metrics_suggest_p.add_argument("--source-step", default=None)
    metrics_compare_p = metrics_sub.add_parser("compare-runs")
    metrics_compare_p.add_argument("--baseline", required=True)
    metrics_compare_p.add_argument("--candidate", required=True)
    metrics_compare_p.add_argument("--scorecard-baseline", default=None)
    metrics_compare_p.add_argument("--scorecard-candidate", default=None)
    metrics_thresholds_p = metrics_sub.add_parser("check-thresholds")
    metrics_thresholds_p.add_argument("--candidate", default=None)
    metrics_thresholds_p.add_argument("--baseline", default=None)
    metrics_thresholds_p.add_argument("--state", default=None)
    metrics_thresholds_p.add_argument("--app-folder", default=None)
    metrics_thresholds_p.add_argument("--run-id", default=None)
    metrics_thresholds_p.add_argument("--packet", default="iris-eval-001")
    metrics_thresholds_p.add_argument("--thresholds", default=None)
    metrics_thresholds_p.add_argument("--transcript", default=None)
    metrics_thresholds_p.add_argument("--scorecard-baseline", default=None)
    metrics_thresholds_p.add_argument("--scorecard-candidate", default=None)

    graph = sub.add_parser("graph")
    graph_sub = graph.add_subparsers(dest="graph_command", required=True)
    graph_validate_p = graph_sub.add_parser("validate")
    graph_validate_p.add_argument("--file", required=True)
    graph_validate_p.add_argument("--state", default=None)
    graph_validate_p.add_argument("--approved-ac", default=None)
    graph_validate_p.add_argument("--config", default=None)
    graph_ready_p = graph_sub.add_parser("ready")
    graph_ready_p.add_argument("--file", required=True)
    graph_ready_p.add_argument(
        "--completed",
        action="append",
        default=[],
        help="Work item IDs already completed (repeatable).",
    )
    graph_record_p = graph_sub.add_parser("record-change")
    graph_record_p.add_argument("--file", required=True)
    graph_record_p.add_argument(
        "--after-build-started",
        action="store_true",
        help="Increment plan_stability.changes_after_build_started.",
    )
    graph_repair_p = graph_sub.add_parser("add-repair-item")
    graph_repair_p.add_argument("--file", required=True)
    graph_repair_p.add_argument("--state", default=None)
    graph_repair_p.add_argument("--id", required=True, dest="repair_id")
    graph_repair_p.add_argument("--reason", required=True)

    docs = sub.add_parser("docs")
    docs_sub = docs.add_subparsers(dest="docs_command", required=True)
    docs_discover_p = docs_sub.add_parser("discover")
    docs_discover_p.add_argument("--app-folder", required=True)
    docs_audit_p = docs_sub.add_parser("audit")
    docs_audit_p.add_argument("--app-folder", required=True)
    docs_pipeline_p = docs_sub.add_parser("pipeline")
    docs_pipeline_p.add_argument("--state", required=True)
    docs_pipeline_p.add_argument("--since", required=True)
    docs_validate_invokes_p = docs_sub.add_parser("validate-invokes")
    docs_validate_invokes_p.add_argument(
        "--steps-dir",
        default=None,
        help="Defaults to .cursor/foundry/steps under factory root",
    )

    prd = sub.add_parser("prd")
    prd_sub = prd.add_subparsers(dest="prd_command", required=True)
    prd_generate_p = prd_sub.add_parser("generate")
    prd_generate_p.add_argument("--app-folder", required=True)
    prd_generate_p.add_argument("--since", default=None)
    prd_validate_p = prd_sub.add_parser("validate")
    prd_validate_p.add_argument("--app-folder", required=True)

    prd_sync = sub.add_parser("prd-sync")
    prd_sync_sub = prd_sync.add_subparsers(dest="prd_sync_command", required=True)
    prd_sync_validate_p = prd_sync_sub.add_parser("validate")
    prd_sync_validate_p.add_argument("--repo", required=True)
    prd_sync_validate_p.add_argument("--factory-root", required=True)

    knowledge = sub.add_parser("knowledge")
    knowledge_sub = knowledge.add_subparsers(dest="knowledge_command", required=True)
    knowledge_suggest_p = knowledge_sub.add_parser("suggest")
    knowledge_suggest_p.add_argument("--receipt", required=True)
    knowledge_suggest_p.add_argument("--factory-root", default=None)

    devops = sub.add_parser("devops")
    devops_sub = devops.add_subparsers(dest="devops_command", required=True)
    devops_scan_p = devops_sub.add_parser("scan")
    devops_scan_p.add_argument("--app-folder", required=True)
    devops_scan_p.add_argument("--config", default=None)
    devops_pin_report_p = devops_sub.add_parser("pin-report")
    devops_pin_report_p.add_argument("--app-folder", required=True)
    devops_pin_report_p.add_argument("--config", default=None)
    devops_apply_pin_p = devops_sub.add_parser("apply-pin")
    devops_apply_pin_p.add_argument("--workflow", required=True)
    devops_apply_pin_p.add_argument("--action", required=True)
    devops_apply_pin_p.add_argument("--sha", required=True)
    devops_apply_pin_p.add_argument("--app-folder", default=None)
    devops_apply_pin_p.add_argument("--tag", default=None)
    devops_apply_pin_p.add_argument("--line", type=int, default=None)

    review = sub.add_parser("review")
    review_sub = review.add_subparsers(dest="review_command", required=True)
    review_bundle_p = review_sub.add_parser("bundle")
    review_bundle_p.add_argument("--app-folder", required=True)
    review_bundle_p.add_argument("--since", required=True)
    review_critics_p = review_sub.add_parser("critics")
    review_critics_p.add_argument("--mode", default="both")
    review_critics_p.add_argument(
        "--selected",
        action="append",
        default=[],
        help="When mode is ask, the critics the human chose.",
    )
    review_validate_p = review_sub.add_parser("validate-receipts")
    review_validate_p.add_argument("--receipts-dir", default=None)
    review_validate_p.add_argument("--state", default=None)
    review_validate_p.add_argument("--config", default=None)
    review_validate_p.add_argument(
        "--critic",
        action="append",
        dest="critics",
        default=[],
        help="Expected critic agent (repeatable).",
    )
    review_validate_p.add_argument(
        "--receipt",
        action="append",
        dest="receipt_paths",
        default=[],
        help="Receipt file path relative to receipts-dir (repeatable).",
    )

    status = sub.add_parser("status")
    status.add_argument("--state", default=None)
    status.add_argument("--app-folder", default=None)
    status.add_argument("--run-id", default=None)
    status.add_argument("--config", default=None)
    status.add_argument("--flow", default=None)

    observability = sub.add_parser("observability")
    observability_sub = observability.add_subparsers(dest="observability_command", required=True)

    observability_status_p = observability_sub.add_parser("status")
    observability_status_p.add_argument("--state", default=None)
    observability_status_p.add_argument("--app-folder", default=None)
    observability_status_p.add_argument("--run-id", default=None)
    observability_status_p.add_argument("--config", default=None)
    observability_status_p.add_argument("--flow", default=None)

    observability_status_md = observability_sub.add_parser("status-markdown")
    observability_status_md.add_argument("--state", default=None)
    observability_status_md.add_argument("--app-folder", default=None)
    observability_status_md.add_argument("--run-id", default=None)
    observability_status_md.add_argument("--config", default=None)
    observability_status_md.add_argument("--flow", default=None)
    observability_status_md.add_argument(
        "--no-write",
        action="store_true",
        help="Return markdown only; do not write status.md.",
    )

    observability_receipt = observability_sub.add_parser("receipt")
    observability_receipt_sub = observability_receipt.add_subparsers(dest="receipt_command", required=True)
    observability_receipt_show = observability_receipt_sub.add_parser("show")
    observability_receipt_show.add_argument("--id", required=True, dest="receipt_id")
    observability_receipt_show.add_argument("--state", default=None)
    observability_receipt_show.add_argument("--app-folder", default=None)
    observability_receipt_show.add_argument("--run-id", default=None)
    observability_receipt_show.add_argument("--receipts-dir", default=None)
    observability_receipt_validate_p = observability_receipt_sub.add_parser("validate")
    observability_receipt_validate_p.add_argument("--receipt", required=True)
    observability_receipt_validate_p.add_argument("--run-id", default=None)
    observability_receipt_validate_p.add_argument("--state", default=None)

    observability_gate = observability_sub.add_parser("gate")
    observability_gate_sub = observability_gate.add_subparsers(dest="gate_command", required=True)
    observability_gate_present_p = observability_gate_sub.add_parser("present")
    observability_gate_present_p.add_argument("--state", required=True)
    observability_gate_present_p.add_argument("--config", default=None)
    observability_gate_present_p.add_argument("--prompt-key", default=None)

    observability_events = observability_sub.add_parser("events")
    observability_events_sub = observability_events.add_subparsers(dest="events_command", required=True)
    observability_events_tail_p = observability_events_sub.add_parser("tail")
    observability_events_tail_p.add_argument("--state", default=None)
    observability_events_tail_p.add_argument("--app-folder", default=None)
    observability_events_tail_p.add_argument("--run-id", default=None)
    observability_events_tail_p.add_argument("-n", "--count", type=int, default=20)

    observability_metrics = observability_sub.add_parser("metrics")
    observability_metrics_sub = observability_metrics.add_subparsers(dest="metrics_command", required=True)
    observability_metrics_summarize_p = observability_metrics_sub.add_parser("summarize")
    observability_metrics_summarize_p.add_argument("--state", default=None)
    observability_metrics_summarize_p.add_argument("--app-folder", default=None)
    observability_metrics_summarize_p.add_argument("--run-id", default=None)
    observability_metrics_summarize_p.add_argument("--transcript", default=None)
    observability_metrics_export_p = observability_metrics_sub.add_parser("export")
    observability_metrics_export_p.add_argument("--state", default=None)
    observability_metrics_export_p.add_argument("--app-folder", default=None)
    observability_metrics_export_p.add_argument("--run-id", default=None)
    observability_metrics_export_p.add_argument("--output", default=None)
    observability_metrics_export_p.add_argument("--transcript", default=None)

    observability_subagent = observability_sub.add_parser("subagent")
    observability_subagent_sub = observability_subagent.add_subparsers(dest="subagent_command", required=True)
    observability_subagent_launch_p = observability_subagent_sub.add_parser("launch")
    observability_subagent_launch_p.add_argument("--state", required=True)
    observability_subagent_launch_p.add_argument("--agent", required=True)
    observability_subagent_launch_p.add_argument("--mode", required=True)
    observability_subagent_launch_p.add_argument("--work-item", default=None)
    observability_subagent_launch_p.add_argument("--config", default=None)
    observability_subagent_complete_p = observability_subagent_sub.add_parser("complete")
    observability_subagent_complete_p.add_argument("--state", required=True)
    observability_subagent_complete_p.add_argument("--receipt", required=True)
    observability_subagent_complete_p.add_argument("--launch-id", default=None)
    observability_subagent_complete_p.add_argument("--config", default=None)

    plan = sub.add_parser("plan")
    plan_sub = plan.add_subparsers(dest="plan_command", required=True)
    plan_record_brief_p = plan_sub.add_parser("record-brief")
    plan_record_brief_p.add_argument("--state", required=True)
    plan_record_brief_p.add_argument("--brief-file", required=True)

    cursor = sub.add_parser("cursor")
    cursor_sub = cursor.add_subparsers(dest="cursor_command", required=True)
    cursor_session_p = cursor_sub.add_parser("session-record")
    cursor_session_p.add_argument("--state", required=True)
    cursor_session_p.add_argument("--conversation-id", required=True)
    cursor_session_p.add_argument("--email", default=None)
    cursor_usage_p = cursor_sub.add_parser("usage-enrich")
    cursor_usage_p.add_argument("--state", required=True)
    cursor_usage_p.add_argument("--api-key", default=None)
    cursor_usage_p.add_argument("--start-date", default=None)
    cursor_usage_p.add_argument("--end-date", default=None)
    cursor_usage_p.add_argument("--email", default=None)

    ticket = sub.add_parser("ticket")
    ticket_sub = ticket.add_subparsers(dest="ticket_command", required=True)
    ticket_list_p = ticket_sub.add_parser("list")
    ticket_list_p.add_argument("--app-folder", default=None)
    ticket_list_p.add_argument("--factory-root", default=None)
    ticket_list_p.add_argument("--tickets-root", default=None)
    ticket_load_p = ticket_sub.add_parser("load")
    ticket_load_p.add_argument("--file", required=True)
    ticket_pick_p = ticket_sub.add_parser("pick")
    ticket_pick_p.add_argument("--app-folder", default=None)
    ticket_pick_p.add_argument("--factory-root", default=None)
    ticket_pick_p.add_argument("--tickets-root", default=None)
    ticket_pick_p.add_argument("--selection", default=None)
    ticket_ingest_p = ticket_sub.add_parser("ingest")
    ticket_ingest_p.add_argument("--file", default=None)
    ticket_ingest_p.add_argument("--text", default=None)
    ticket_ingest_p.add_argument("--stdin", action="store_true")
    ticket_ingest_p.add_argument("--issue-key", default=None)
    ticket_ingest_p.add_argument("--source", default=None, choices=("local_file", "paste", "jira"))
    ticket_save_p = ticket_sub.add_parser("save")
    ticket_save_p.add_argument("--tickets-root", required=True)
    ticket_save_p.add_argument("--file", default=None, help="Existing markdown to copy/normalize into tickets root")
    ticket_save_p.add_argument("--text", default=None)
    ticket_save_p.add_argument("--stdin", action="store_true")
    ticket_save_p.add_argument("--issue-key", default=None)

    return parser


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "run" and args.run_command == "init":
        ticket_text = getattr(args, "ticket_text", None)
        if getattr(args, "ticket_stdin", False):
            ticket_text = sys.stdin.read()
        return run_init(
            app_folder=args.app_folder,
            issue_key=args.issue_key,
            run_mode=args.run_mode,
            factory_root=args.factory_root,
            config_path=args.config,
            developer_first_name=args.developer_first_name,
            risk_tier=args.risk_tier,
            flow_path=args.flow,
            run_id=args.run_id,
            interaction_mode=getattr(args, "interaction_mode", None),
            ticket_file=getattr(args, "ticket_file", None),
            ticket_text=ticket_text,
            start_point=getattr(args, "start_point", None),
        )
    if args.command == "run" and args.run_command == "show":
        return run_show(resolve_state_path(args.state, args.app_folder, args.run_id))
    if args.command == "run" and args.run_command == "list":
        return run_list(args.app_folder)
    if args.command == "run" and args.run_command == "latest":
        return run_latest(args.app_folder, issue_key=args.issue_key)
    if args.command == "run" and args.run_command == "handoff":
        return run_handoff(
            Path(args.state),
            config_path=args.config,
            flow_path=args.flow,
            what_happened=args.what_happened,
            what_next=args.what_next,
        )
    if args.command == "run" and args.run_command == "finalize-learning":
        return run_finalize_learning(
            Path(args.state),
            outcome_status=args.outcome,
            abandon_reason=args.abandon_reason,
        )
    if args.command == "run" and args.run_command == "abandon":
        return run_abandon(Path(args.state), reason=args.reason)
    if args.command == "run" and args.run_command == "recover":
        try:
            return foundry_store.recover_run(Path(args.state).parent)
        except foundry_store.StoreError as exc:
            raise FoundryError(exc.error_code, exc.message, extra=exc.extra) from exc
    if args.command == "run" and args.run_command == "sync":
        return run_sync(Path(args.state), push=bool(args.push))
    if args.command == "run" and args.run_command == "complete":
        return run_complete(
            Path(args.state),
            pr_url=args.pr_url,
            config_path=args.config,
            resolved_pr_title=args.resolved_pr_title,
        )
    if args.command == "run" and args.run_command == "block":
        return run_block(Path(args.state), reason=args.reason, step_id=args.step_id)
    if args.command == "run" and args.run_command == "unblock":
        return run_unblock(Path(args.state), decision=args.decision)
    if args.command == "run" and args.run_command == "context":
        return run_context(Path(args.state))
    if args.command == "run" and args.run_command == "integrity-check":
        import foundry_integrity  # noqa: PLC0415

        findings = None
        if args.transcript:
            metrics = observability_metrics_summarize(
                Path(args.state),
                transcript_path=args.transcript,
            )
            raw = metrics.get("transcript_findings")
            findings = raw if isinstance(raw, dict) else None
        result = foundry_integrity.run_integrity_check(
            Path(args.state),
            transcript_findings=findings,
        )
        if not result.get("ok"):
            raise FoundryError(
                "INTEGRITY_CHECK_FAILED",
                "Run integrity check failed.",
                extra={"issues": result.get("issues")},
            )
        return result
    if args.command == "cli" and args.cli_command == "resolve":
        return cli_resolve(args.factory_root)
    if args.command == "invoke" and args.invoke_command == "render":
        if args.state:
            context = run_context(Path(args.state))
            foundry_cli = args.foundry_cli_override or str(context["foundry_cli"])
        else:
            resolved_factory_root = (
                str(Path(args.factory_root).resolve()) if args.factory_root else str(REPO_ROOT)
            )
            context = {"factory_root": resolved_factory_root}
            foundry_cli = args.foundry_cli_override or resolve_foundry_cli(resolved_factory_root)
        return foundry_invoke.render_foundry_invoke(args.tail, foundry_cli, context)
    if args.command == "docs" and args.docs_command == "validate-invokes":
        steps_dir = (
            Path(args.steps_dir)
            if args.steps_dir
            else FOUNDRY_ROOT / "steps"
        )
        step_result = foundry_invoke.validate_step_units(steps_dir)
        steward_templates = [
            FOUNDRY_ROOT / "templates" / name
            for name in (
                "create-pr-step.md",
                "delivery-steps.md",
                "factory-run-state.md",
                "factory-config-packet.md",
                "command-bootstrap.md",
                "post-build-steps.md",
                "pre-pr-review-step.md",
                "sync-prd-step.md",
            )
        ]
        template_result = foundry_invoke.validate_steward_docs(steward_templates)
        errors = list(step_result.get("errors") or []) + list(template_result.get("errors") or [])
        return {
            "valid": not errors,
            "checked": int(step_result.get("checked") or 0) + int(template_result.get("checked") or 0),
            "errors": errors,
            "steps": step_result,
            "templates": template_result,
        }
    if args.command == "config" and args.config_command == "get":
        return config_get(
            factory_root=args.factory_root,
            role=args.role,
            app_folder=args.app_folder,
            profile_path=args.profile,
        )
    if args.command == "app" and args.app_command == "discover":
        return call_app("discover_app", args.app_folder)
    if args.command == "app" and args.app_command == "init":
        return call_app(
            "init_app_manifest",
            args.app_folder,
            args.manifest_file,
            run_mode=args.run_mode,
            dry_run=args.dry_run,
            force=args.force,
        )
    if args.command == "app" and args.app_command in ("validate", "print-context"):
        context = call_app(
            "validate_app_manifest",
            args.app_folder,
            run_mode=args.run_mode,
        )
        if args.app_command == "print-context":
            return context
        return {
            key: value
            for key, value in context.items()
            if key != "manifest"
        } | {"valid": True}
    if args.command == "issue-key" and args.issue_command == "parse":
        return issue_key_parse(args.text, args.pattern)
    if args.command == "pr-title":
        state = None
        config = None
        if args.state:
            state_path = Path(args.state)
            state = load_state(state_path)
            config = load_run_config(state_path, state, args.config)
        return pr_title(
            args.issue_key,
            args.summary,
            args.pattern,
            args.jira_enabled == "true",
            state=state,
            config=config,
        )
    if args.command == "git" and args.git_command == "default-branch":
        return git_default_branch(args.repo)
    if args.command == "git" and args.git_command == "staged-secrets-check":
        return call_shared(
            "git_staged_secrets_check",
            Path(args.repo),
            Path(args.factory_root),
            pattern_override=args.pattern,
        )
    if args.command == "branch" and args.branch_command == "create":
        return create_feature_branch(
            Path(args.state),
            args.repo,
            args.name,
            start_point=getattr(args, "start_point", None),
        )
    if args.command == "branch-name":
        return branch_name(args.pattern, args.developer, args.issue_key)
    if args.command == "project-context":
        return project_context(Path(args.state))
    if args.command == "build":
        return run_build(Path(args.state))
    if args.command == "test":
        return run_test(Path(args.state))
    if args.command == "worker" and args.worker_command == "builder-packet":
        return builder_packet(
            state_path=Path(args.state),
            graph_path=args.graph,
            work_item_id=args.work_item,
            receipts_dir=args.receipts_dir,
            config_path=args.config,
        )
    if args.command == "worker" and args.worker_command == "launch-packet":
        return worker_launch_packet(
            Path(args.state),
            agent=args.agent,
            mode=args.mode,
            work_item=args.work_item,
            config_path=args.config,
            flow_path=args.flow,
        )
    if args.command == "worker" and args.worker_command == "validator-ready":
        return validator_ready_check(args.file)
    if args.command == "worker" and args.worker_command == "validator-packet":
        return validator_packet(
            state_path=Path(args.state),
            graph_path=args.graph,
            receipts_dir=args.receipts_dir,
            config_path=args.config,
        )
    if args.command == "worker" and args.worker_command == "route-critical":
        return route_critical_findings(args.graph, args.findings)
    if args.command == "worker" and args.worker_command == "complete-item":
        return graph_complete_item(
            args.file,
            args.work_item,
            args.receipt,
            state_path=Path(args.state) if args.state else None,
        )
    if args.command == "worker" and args.worker_command == "next-builder":
        return worker_next_builder(
            state_path=Path(args.state),
            graph_path=args.graph,
            config_path=args.config,
        )
    if args.command == "build-step" and args.build_step_command == "verify":
        return build_step_verify(
            Path(args.state),
            graph_path=args.graph,
            config_path=args.config,
        )
    if args.command == "worker" and args.worker_command == "rework":
        state_path = Path(args.state)
        state = load_state(state_path)
        config = load_run_config(state_path, state, args.config)
        return increment_rework_counter(
            state,
            args.counter,
            config=config,
            state_path=state_path,
            from_step=str(state.get("current_step") or "implement.build"),
        )
    if args.command == "risk-tier" and args.risk_command == "suggest":
        return suggest_risk_tier(
            ac_count=args.ac_count,
            issue_type=args.issue_type,
            config_path=args.config,
        )
    if args.command == "jira" and args.jira_command == "format-board":
        return jira_format_board(
            parse_issues_json(args.issues),
            project_key=args.project_key,
            developer_first_name=args.developer_first_name,
        )
    if args.command == "jira" and args.jira_command == "format-comment":
        state_path = Path(args.state)
        state = load_state(state_path)
        config = load_run_config(state_path, state, args.config)
        body = args.body
        if body is None:
            draft = call_deliver("draft_scope_comment", state, config)
            body = draft.get("markdown") or ""
        return call_deliver("jira_format_comment", state, config, body)
    if args.command == "deliver" and args.deliver_command == "draft-scope-comment":
        state_path = Path(args.state)
        state = load_state(state_path)
        config = load_run_config(state_path, state, args.config)
        return call_deliver(
            "draft_scope_comment",
            state,
            config,
            in_scope_summary=args.in_scope_summary,
        )
    if args.command == "deliver" and args.deliver_command == "prepare":
        return prepare_delivery_seal(Path(args.state), args.factory_root)
    if args.command == "deliver" and args.deliver_command == "pr-verify":
        return verify_github_pr(
            Path(args.state),
            pr_url=args.pr_url,
            resolved_pr_title=args.pr_title,
        )
    if args.command == "intake" and args.intake_command == "validate-ac":
        return intake_validate_ac(load_state(Path(args.state)))
    if args.command == "flow" and args.flow_command == "current":
        return flow_current(Path(args.state), args.config, args.flow)
    if args.command == "flow" and args.flow_command == "next":
        return flow_next(Path(args.state), args.config, args.flow, args.decision)
    if args.command == "flow" and args.flow_command == "orchestrator-packet":
        return flow_orchestrator_packet(Path(args.state), args.config, args.flow)
    if args.command == "flow" and args.flow_command == "resume-packet":
        return flow_resume_packet(Path(args.state), args.config, args.flow)
    if args.command == "gate" and args.gate_command == "resolve":
        extras = {}
        if getattr(args, "devops_empty", False):
            extras["devops_empty"] = True
        if getattr(args, "graph_validated", False):
            extras["graph_validated"] = True
        return gate_resolve(
            Path(args.state),
            decision=args.decision,
            source=args.source,
            config_path=args.config,
            flow_path=args.flow,
            extras=extras or None,
        )
    if args.command == "flow" and args.flow_command == "validate":
        return validate_registry(args.flow)
    if args.command == "flow" and args.flow_command == "diagram":
        return flow_diagram(args.flow, args.out, args.check)
    if args.command == "transition":
        return transition(
            Path(args.state),
            args.to_step,
            config_path=args.config,
            flow_path=args.flow,
            evidence=args.evidence,
            decision=args.decision,
            assignments=args.assignments,
            force=bool(getattr(args, "force", False)),
        )
    if args.command == "delivery-check":
        state_path = Path(args.state)
        state = load_state(state_path)
        return delivery_check(
            state,
            load_run_config(state_path, state, args.config),
            state_path=state_path,
        )
    if args.command == "external-operation" and args.external_command in ("record", "prepare", "reconcile"):
        return record_external_operation(
            Path(args.state),
            integration=args.integration,
            operation=args.operation,
            target=args.target,
            status=getattr(args, "status", None) or args.external_status,
            evidence_json=args.evidence_json,
            operation_id=args.operation_id,
            request_json=args.request_json,
            remote_id=args.remote_id,
        )
    if args.command == "outcome" and args.outcome_command == "observe":
        try:
            return foundry_outcome.observe(Path(args.state), pr_url=args.pr_url)
        except foundry_outcome.OutcomeError as exc:
            raise FoundryError(exc.error_code, exc.message, extra=exc.extra) from exc
    if args.command == "schema" and args.schema_command == "validate":
        return schema_validate(args.file, args.schema)
    if args.command == "schema" and args.schema_command == "validate-examples":
        return schema_validate_examples()
    if args.command == "metrics" and args.metrics_command == "classify":
        state_path = resolve_state_path(args.state, args.app_folder, args.run_id)
        return metrics_classify(
            state_path,
            failure_class=args.failure_class,
            source_step=args.source_step,
            notes=args.notes,
            receipt_id=args.receipt_id,
            actor=args.actor,
        )
    if args.command == "metrics" and args.metrics_command == "suggest":
        state_path = resolve_state_path(args.state, args.app_folder, args.run_id)
        return metrics_suggest(state_path, source_step=args.source_step)
    if args.command == "metrics" and args.metrics_command == "compare-runs":
        return metrics_compare_runs(
            args.baseline,
            args.candidate,
            scorecard_baseline=args.scorecard_baseline,
            scorecard_candidate=args.scorecard_candidate,
        )
    if args.command == "metrics" and args.metrics_command == "check-thresholds":
        state_path = None
        if args.state or (args.app_folder and args.run_id):
            state_path = resolve_state_path(args.state, args.app_folder, args.run_id)
        return metrics_check_thresholds(
            candidate_path=args.candidate,
            state_path=state_path,
            baseline_path=args.baseline,
            packet=args.packet,
            thresholds_path=args.thresholds,
            transcript_path=args.transcript,
            scorecard_baseline=args.scorecard_baseline,
            scorecard_candidate=args.scorecard_candidate,
        )
    if args.command == "graph" and args.graph_command == "validate":
        return graph_validate(
            args.file,
            state_path=args.state,
            approved_ac=args.approved_ac,
            config_path=args.config,
        )
    if args.command == "graph" and args.graph_command == "ready":
        return graph_ready(args.file, completed=args.completed)
    if args.command == "graph" and args.graph_command == "record-change":
        return graph_record_change(args.file, after_build_started=args.after_build_started)
    if args.command == "graph" and args.graph_command == "add-repair-item":
        return graph_add_repair_item(
            args.file,
            state_path=Path(args.state) if args.state else None,
            item_id=args.repair_id,
            reason=args.reason,
        )
    if args.command == "docs" and args.docs_command == "discover":
        return call_docs("docs_discover", args.app_folder)
    if args.command == "docs" and args.docs_command == "audit":
        return call_docs("docs_audit", args.app_folder)
    if args.command == "docs" and args.docs_command == "pipeline":
        return call_docs("docs_pipeline", args.state, args.since)
    if args.command == "prd" and args.prd_command == "generate":
        return call_docs("prd_generate", args.app_folder, args.since)
    if args.command == "prd" and args.prd_command == "validate":
        return call_docs("prd_validate", args.app_folder)
    if args.command == "prd-sync" and args.prd_sync_command == "validate":
        return prd_sync_validate(args.repo, args.factory_root)
    if args.command == "knowledge" and args.knowledge_command == "suggest":
        return call_docs("knowledge_suggest", args.receipt, args.factory_root)
    if args.command == "devops" and args.devops_command == "scan":
        config = load_config(args.config) if args.config else None
        return call_devops("devops_scan", args.app_folder, config)
    if args.command == "devops" and args.devops_command == "pin-report":
        config = load_config(args.config) if args.config else None
        return call_devops("devops_pin_report", args.app_folder, config)
    if args.command == "devops" and args.devops_command == "apply-pin":
        return call_devops(
            "devops_apply_pin",
            args.workflow,
            args.action,
            args.sha,
            app_folder=args.app_folder,
            tag=args.tag,
            line=args.line,
        )
    if args.command == "review" and args.review_command == "bundle":
        return call_review("review_bundle", args.app_folder, args.since)
    if args.command == "review" and args.review_command == "critics":
        return call_review(
            "review_critics",
            args.mode,
            selected=args.selected or None,
        )
    if args.command == "review" and args.review_command == "validate-receipts":
        return review_validate_receipts_command(args)
    if args.command == "status":
        state_path = resolve_state_path(args.state, args.app_folder, args.run_id)
        return observability_status(
            state_path,
            config_path=args.config,
            flow_path=args.flow,
        )
    if args.command == "observability" and args.observability_command == "status":
        state_path = resolve_state_path(args.state, args.app_folder, args.run_id)
        return observability_status(
            state_path,
            config_path=args.config,
            flow_path=args.flow,
        )
    if args.command == "observability" and args.observability_command == "status-markdown":
        state_path = resolve_state_path(args.state, args.app_folder, args.run_id)
        return observability_status_markdown(
            state_path,
            config_path=args.config,
            flow_path=args.flow,
            write_file=not args.no_write,
        )
    if args.command == "observability" and args.observability_command == "receipt":
        if args.receipt_command == "validate":
            return observability_receipt_validate(
                Path(args.receipt),
                run_id=args.run_id,
                state_path=Path(args.state) if args.state else None,
            )
        state_path = Path(args.state) if args.state else None
        if state_path is None and args.app_folder and args.run_id:
            state_path = resolve_state_path(None, args.app_folder, args.run_id)
        return observability_receipt_show(
            receipt_id=args.receipt_id,
            state_path=state_path,
            receipts_dir=args.receipts_dir,
        )
    if args.command == "observability" and args.observability_command == "gate":
        if args.gate_command == "present":
            return observability_gate_present(
                Path(args.state),
                config_path=args.config,
                prompt_key=args.prompt_key,
            )
    if args.command == "plan" and args.plan_command == "record-brief":
        return plan_record_brief(Path(args.state), brief_file=args.brief_file)
    if args.command == "cursor" and args.cursor_command == "session-record":
        return cursor_session_record(
            Path(args.state),
            conversation_id=args.conversation_id,
            email=args.email,
        )
    if args.command == "cursor" and args.cursor_command == "usage-enrich":
        return cursor_usage_enrich(
            Path(args.state),
            api_key=args.api_key,
            start_date=args.start_date,
            end_date=args.end_date,
            email=args.email,
        )
    if args.command == "ticket":
        try:
            if args.ticket_command == "list":
                root = foundry_tickets.resolve_tickets_root(
                    app_folder=args.app_folder,
                    factory_root=args.factory_root,
                    tickets_root=args.tickets_root,
                )
                return foundry_tickets.list_tickets(root)
            if args.ticket_command == "load":
                return foundry_tickets.load_ticket_file(Path(args.file))
            if args.ticket_command == "pick":
                root = foundry_tickets.resolve_tickets_root(
                    app_folder=args.app_folder,
                    factory_root=args.factory_root,
                    tickets_root=args.tickets_root,
                )
                return foundry_tickets.pick_ticket(root, selection=args.selection)
            if args.ticket_command == "ingest":
                text = args.text
                if args.stdin:
                    text = sys.stdin.read()
                return foundry_tickets.ingest_ticket(
                    file=Path(args.file) if args.file else None,
                    text=text,
                    issue_key=args.issue_key,
                    source=args.source,
                )
            if args.ticket_command == "save":
                text = args.text
                if args.stdin:
                    text = sys.stdin.read()
                if args.file:
                    sealed = foundry_tickets.ingest_ticket(file=Path(args.file), source="local_file")
                else:
                    sealed = foundry_tickets.ingest_ticket(
                        text=text,
                        issue_key=args.issue_key,
                        source="paste",
                    )
                return foundry_tickets.save_ticket(
                    sealed,
                    tickets_root=Path(args.tickets_root),
                )
        except foundry_tickets.TicketError as exc:
            raise FoundryError(
                exc.error_code,
                exc.message,
                required_input=exc.required_input,
            ) from exc
    if args.command == "observability" and args.observability_command == "events":
        state_path = resolve_state_path(args.state, args.app_folder, args.run_id)
        return observability_events_tail(state_path, count=args.count)
    if args.command == "observability" and args.observability_command == "metrics":
        state_path = resolve_state_path(args.state, args.app_folder, args.run_id)
        if args.metrics_command == "summarize":
            return observability_metrics_summarize(state_path, transcript_path=args.transcript)
        if args.metrics_command == "export":
            return observability_metrics_export(
                state_path,
                args.output,
                transcript_path=args.transcript,
            )
    if args.command == "observability" and args.observability_command == "subagent":
        state_path = Path(args.state)
        if args.subagent_command == "launch":
            return observability_subagent_launch(
                state_path,
                agent=args.agent,
                mode=args.mode,
                work_item=args.work_item,
                config_path=args.config,
            )
        if args.subagent_command == "complete":
            return observability_subagent_complete(
                state_path,
                receipt=args.receipt,
                launch_id=args.launch_id,
                config_path=args.config,
            )
    raise FoundryError("UNKNOWN_COMMAND", f"Unhandled command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if argv[:2] == ["run", "sync"] or (
        argv[:2] == ["run", "init"]
        and "--run-mode" in argv
        and argv[argv.index("--run-mode") + 1 : argv.index("--run-mode") + 2] == ["bug_squash"]
    ):
        return emit_error(
            FoundryError(
                "UNSUPPORTED_MODE",
                "Foundry no longer exposes distributed sync or bug_squash run mode.",
            )
        )
    args = build_parser().parse_args(argv)
    state_path, config, step_id = resolve_cli_run_context(args)
    emit_events = True
    if config is not None:
        emit_events = observability_settings(config)["emit_events"]
    try:
        result = dispatch(args)
        exit_code = 0
        if args.command == "metrics" and getattr(args, "metrics_command", None) == "check-thresholds":
            if not result.get("passed", True):
                exit_code = 2
        if args.command == "run" and getattr(args, "run_command", None) == "init":
            call_observability(
                "log_cli_invoked",
                run_id=str(result["run_id"]),
                events_path=Path(result["events_path"]),
                command="run init",
                argv=argv,
                append_event=append_event,
                make_event=make_event,
                emit_events=True,
                step_id=result.get("current_step"),
                exit_code=0,
            )
        elif state_path is not None:
            state = load_state(state_path)
            call_observability(
                "log_cli_invoked",
                run_id=str(state["run_id"]),
                events_path=state_path.parent / "events.jsonl",
                command=args.command,
                argv=argv,
                append_event=append_event,
                make_event=make_event,
                emit_events=emit_events,
                step_id=step_id,
                exit_code=0,
            )
        emit_success(result)
        return exit_code
    except FoundryError as exc:
        command_label = args.command
        if args.command == "build-step" and getattr(args, "build_step_command", None) == "verify":
            command_label = BUILD_STEP_VERIFY_COMMAND
        if not (args.command == "run" and getattr(args, "run_command", None) in ("block", "unblock")):
            maybe_auto_block_on_failure(
                state_path,
                command=command_label,
                error_code=exc.error_code,
                message=exc.message,
                config=config,
            )
        if state_path is not None:
            try:
                state = load_state(state_path)
                call_observability(
                    "log_cli_invoked",
                    run_id=str(state["run_id"]),
                    events_path=state_path.parent / "events.jsonl",
                    command=command_label,
                    argv=argv,
                    append_event=append_event,
                    make_event=make_event,
                    emit_events=emit_events,
                    step_id=step_id,
                    exit_code=1,
                )
            except FoundryError:
                pass
        return emit_error(exc)


if __name__ == "__main__":
    sys.exit(main())
