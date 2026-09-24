"""Foundry 2.2 protocol constants, schemas, and worker contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    Draft202012Validator = None

PROTOCOL_VERSION = "2.2.0"
FOUNDRY_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = FOUNDRY_ROOT / "schemas"
CONTRACTS_DIR = FOUNDRY_ROOT / "contracts"
LEGACY_CONTRACTS_DIR = FOUNDRY_ROOT / "agents"
CONTRACT_REGISTRY_PATH = CONTRACTS_DIR / "registry.yaml"
CONTRACT_PROTOCOL_PATH = CONTRACTS_DIR / "_protocol.yaml"
CONTRACT_REGISTRY_SKIP_NAMES = frozenset({"registry", "_protocol"})

# Backward-compatible aliases
AGENTS_DIR = CONTRACTS_DIR
AGENT_REGISTRY_PATH = CONTRACT_REGISTRY_PATH
AGENT_PROTOCOL_PATH = CONTRACT_PROTOCOL_PATH
AGENT_REGISTRY_SKIP_NAMES = CONTRACT_REGISTRY_SKIP_NAMES


class ProtocolError(Exception):
    def __init__(self, error_code: str, message: str, *, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.errors = errors or []


def contracts_dir() -> Path:
    if CONTRACTS_DIR.is_dir():
        return CONTRACTS_DIR
    if LEGACY_CONTRACTS_DIR.is_dir():
        return LEGACY_CONTRACTS_DIR
    return CONTRACTS_DIR


def resolve_foundry_relative_path(relative: str) -> Path:
    """Resolve a flow-relative path under .cursor/foundry or .cursor for agent prompts."""
    rel = str(relative or "").strip().replace("\\", "/")
    if not rel:
        raise ProtocolError("INVALID_PATH", "Path must be a non-empty string.")
    if rel.startswith("agents/"):
        return FOUNDRY_ROOT.parent / rel
    return FOUNDRY_ROOT / rel


def contract_id_from_path(contract_relative: str) -> str:
    return Path(str(contract_relative or "").replace("\\", "/")).stem


def _validate_worker_contracts(contracts: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for name, contract in contracts.items():
        if not isinstance(contract, dict):
            errors.append(f"{name}: contract must be an object")
            continue
        capabilities = contract.get("capabilities")
        if not isinstance(capabilities, list) or not capabilities or not all(
            isinstance(item, str) and item for item in capabilities
        ):
            errors.append(f"{name}: capabilities must be a non-empty string list")
        if not isinstance(contract.get("modes"), dict) or not contract["modes"]:
            errors.append(f"{name}: modes must be a non-empty object")
    return errors


def _load_monolithic_contract_registry(source: Path) -> dict[str, Any]:
    value = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("protocol_version") != PROTOCOL_VERSION:
        raise ProtocolError(
            "INVALID_CONTRACT_REGISTRY",
            f"Contract registry must declare protocol_version {PROTOCOL_VERSION}.",
        )
    agents = value.get("agents")
    if not isinstance(agents, dict) or not agents:
        raise ProtocolError("INVALID_CONTRACT_REGISTRY", "Contract registry must define agents.")
    errors = _validate_worker_contracts(agents)
    if errors:
        raise ProtocolError(
            "INVALID_CONTRACT_REGISTRY",
            "Worker capability contracts are invalid.",
            errors=errors,
        )
    return value


def _load_contract_directory(contracts_root: Path) -> dict[str, Any]:
    protocol_path = contracts_root / "_protocol.yaml"
    if protocol_path.is_file():
        protocol = yaml.safe_load(protocol_path.read_text(encoding="utf-8"))
        if not isinstance(protocol, dict) or protocol.get("protocol_version") != PROTOCOL_VERSION:
            raise ProtocolError(
                "INVALID_CONTRACT_REGISTRY",
                f"{protocol_path} must declare protocol_version {PROTOCOL_VERSION}.",
            )
    else:
        legacy = contracts_root / "registry.yaml"
        if legacy.is_file():
            monolith = yaml.safe_load(legacy.read_text(encoding="utf-8"))
            if not (isinstance(monolith, dict) and monolith.get("protocol_version") == PROTOCOL_VERSION):
                raise ProtocolError(
                    "INVALID_CONTRACT_REGISTRY",
                    f"Contract directory {contracts_root} requires _protocol.yaml or a legacy registry.yaml.",
                )
        else:
            raise ProtocolError(
                "INVALID_CONTRACT_REGISTRY",
                f"Contract directory {contracts_root} requires _protocol.yaml.",
            )

    agents: dict[str, Any] = {}
    for contract_path in sorted(contracts_root.glob("*.yaml")):
        contract_name = contract_path.stem
        if contract_name in CONTRACT_REGISTRY_SKIP_NAMES:
            continue
        contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
        if not isinstance(contract, dict):
            raise ProtocolError(
                "INVALID_CONTRACT_REGISTRY",
                f"Worker contract at {contract_path} must be a mapping.",
            )
        agents[contract_name] = contract

    if not agents:
        raise ProtocolError(
            "INVALID_CONTRACT_REGISTRY",
            f"No worker contracts found in {contracts_root}.",
        )
    errors = _validate_worker_contracts(agents)
    if errors:
        raise ProtocolError(
            "INVALID_CONTRACT_REGISTRY",
            "Worker capability contracts are invalid.",
            errors=errors,
        )
    return {"protocol_version": PROTOCOL_VERSION, "agents": agents}


def load_agent_registry(path: Path | None = None) -> dict[str, Any]:
    """Load all worker contracts from a directory or legacy monolithic registry."""
    if yaml is None:
        raise ProtocolError("MISSING_DEPENDENCY", "PyYAML is required for the worker contract registry.")
    if path is not None:
        if path.is_dir():
            return _load_contract_directory(path)
        if path.is_file():
            return _load_monolithic_contract_registry(path)
        raise ProtocolError("MISSING_CONTRACT_REGISTRY", f"Contract registry not found: {path}")

    root = contracts_dir()
    if root.is_dir() and any(
        p.stem not in CONTRACT_REGISTRY_SKIP_NAMES for p in root.glob("*.yaml")
    ):
        return _load_contract_directory(root)
    if CONTRACT_REGISTRY_PATH.is_file():
        monolith = _load_monolithic_contract_registry(CONTRACT_REGISTRY_PATH)
        nested = monolith.get("agents") or {}
        if isinstance(nested, dict) and nested:
            return monolith
    raise ProtocolError("MISSING_CONTRACT_REGISTRY", f"Contract registry not found under {root}")


load_contract_registry = load_agent_registry


def agents_for_capability(capability: str, path: Path | None = None) -> list[str]:
    registry = load_agent_registry(path)
    return sorted(
        name
        for name, contract in registry["agents"].items()
        if capability in (contract.get("capabilities") or [])
    )


def assert_agent_capability(agent: str, capability: str, path: Path | None = None) -> None:
    registry = load_agent_registry(path)
    contract = registry["agents"].get(agent)
    if not isinstance(contract, dict) or capability not in (contract.get("capabilities") or []):
        raise ProtocolError(
            "AGENT_CAPABILITY_MISMATCH",
            f"Agent {agent!r} does not provide capability {capability!r}.",
            errors=[f"available: {', '.join(agents_for_capability(capability, path))}"],
        )


def agent_contract(agent: str, mode: str, path: Path | None = None) -> dict[str, Any]:
    registry = load_agent_registry(path)
    contract = (registry.get("agents") or {}).get(agent)
    if not isinstance(contract, dict):
        raise ProtocolError("UNKNOWN_AGENT", f"Worker contract {agent!r} is not registered.")
    modes = contract.get("modes") or {}
    mode_contract = modes.get(mode) if isinstance(modes, dict) else None
    if not isinstance(mode_contract, dict):
        raise ProtocolError(
            "INVALID_AGENT_MODE",
            f"Worker contract {agent!r} does not support mode {mode!r}.",
        )
    merged = dict(contract)
    merged.pop("modes", None)
    merged.update(mode_contract)
    merged["agent"] = agent
    merged["mode"] = mode
    return merged


def worker_contract(contract_relative: str, mode: str, path: Path | None = None) -> dict[str, Any]:
    contract_relative = str(contract_relative or "").strip().replace("\\", "/")
    contract_path = resolve_foundry_relative_path(contract_relative)
    if not contract_path.is_file():
        raise ProtocolError(
            "MISSING_WORKER_CONTRACT",
            f"Worker contract file not found: {contract_relative}",
        )
    agent = contract_id_from_path(contract_relative)
    return agent_contract(agent, mode, path)


worker_contract_from_path = worker_contract


def validate_schema(instance: Any, schema_relative: str, *, artifact: str) -> None:
    if Draft202012Validator is None:
        raise ProtocolError("MISSING_DEPENDENCY", "jsonschema is required for protocol validation.")
    schema_path = SCHEMAS_DIR / schema_relative
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=str)
    if errors:
        rendered = [
            f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
            for error in errors
        ]
        raise ProtocolError(
            "PROTOCOL_SCHEMA_INVALID",
            f"{artifact} failed {schema_relative}.",
            errors=rendered,
        )


def validate_receipt_contract(
    receipt: dict[str, Any],
    *,
    expected_run_id: str,
    expected_launch_id: str,
    expected_step_id: str,
    expected_agent: str,
    expected_mode: str,
    contract_relative: str | None = None,
) -> dict[str, Any]:
    if receipt.get("schema_version") != PROTOCOL_VERSION:
        raise ProtocolError("RECEIPT_VERSION_MISMATCH", "Receipt is not Foundry protocol 2.2.0.")
    provenance = receipt.get("provenance")
    expected = {
        "run_id": expected_run_id,
        "launch_id": expected_launch_id,
        "step_id": expected_step_id,
        "agent": expected_agent,
        "mode": expected_mode,
    }
    actual = {
        "run_id": receipt.get("run_id"),
        "launch_id": provenance.get("launch_id") if isinstance(provenance, dict) else None,
        "step_id": provenance.get("step_id") if isinstance(provenance, dict) else None,
        "agent": (receipt.get("agent") or {}).get("name"),
        "mode": (receipt.get("agent") or {}).get("mode"),
    }
    mismatches = [key for key, value in expected.items() if actual.get(key) != value]
    if mismatches:
        raise ProtocolError(
            "RECEIPT_PROVENANCE_INVALID",
            "Receipt provenance does not match its launch.",
            errors=[f"{key}: expected {expected[key]!r}, got {actual.get(key)!r}" for key in mismatches],
        )
    if contract_relative:
        contract = worker_contract(contract_relative, expected_mode)
    else:
        contract = agent_contract(expected_agent, expected_mode)
    required = contract.get("required_output_fields") or []
    missing = [path for path in required if _resolve(receipt, str(path)) is None]
    if missing:
        raise ProtocolError(
            "RECEIPT_OUTPUTS_MISSING",
            "Receipt is missing fields required by the worker contract.",
            errors=missing,
        )
    next_state = receipt.get("recommended_next_state")
    valid_next = contract.get("valid_next_states") or []
    if next_state not in valid_next and not str(next_state).startswith("BLOCKED_"):
        raise ProtocolError(
            "RECEIPT_NEXT_STATE_INVALID",
            f"Receipt next state {next_state!r} is not valid for {expected_agent}/{expected_mode}.",
        )
    return contract


def _resolve(value: Any, dotted: str) -> Any:
    current = value
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current
