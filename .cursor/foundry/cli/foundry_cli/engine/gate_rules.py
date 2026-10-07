"""Declarative engine gate rules (``nodes/<gate>/gate.rules.yaml``)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from foundry_cli.engine.evidence import gate_evidence
from foundry_cli.engine.expressions import evaluate_condition, evaluate_expression

GATE_RULES_FILENAME = "gate.rules.yaml"
ENGINE_BUNDLE = Path(__file__).resolve().parents[3]


def _bundle(foundry_bundle: Path | None) -> Path:
    return foundry_bundle if foundry_bundle is not None else ENGINE_BUNDLE


def gate_rules_path(gate_node_id: str, foundry_bundle: Path | None = None) -> Path:
    return _bundle(foundry_bundle) / "nodes" / gate_node_id / GATE_RULES_FILENAME


def gate_rules_ref(gate_node_id: str) -> str:
    return f"registry:nodes/{gate_node_id}/{GATE_RULES_FILENAME}"


def has_gate_rules(gate_node_id: str, foundry_bundle: Path | None = None) -> bool:
    return gate_rules_path(gate_node_id, foundry_bundle).is_file()


def load_gate_rules(gate_node_id: str, foundry_bundle: Path | None = None) -> dict[str, Any] | None:
    path = gate_rules_path(gate_node_id, foundry_bundle)
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("rules"), list):
        raise ValueError(f"Gate rules must be a mapping with a rules list: {path}")
    return data


def examine_check_ids(gate_node_id: str, foundry_bundle: Path | None = None) -> tuple[str, ...]:
    """``lifecycle.on_examine`` check ids from the gate's ``node.yaml``."""
    path = _bundle(foundry_bundle) / "nodes" / gate_node_id / "node.yaml"
    if not path.is_file():
        return ()
    node = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    lifecycle = node.get("lifecycle") if isinstance(node, dict) else None
    hooks = lifecycle.get("on_examine") if isinstance(lifecycle, dict) else None
    if not isinstance(hooks, list):
        return ()
    return tuple(str(item["check"]) for item in hooks if isinstance(item, dict) and item.get("check"))


def examine_fail_codes(rules: dict[str, Any]) -> dict[str, str]:
    examine = rules.get("examine")
    codes = examine.get("fail_codes") if isinstance(examine, dict) else None
    return {str(k): str(v) for k, v in codes.items()} if isinstance(codes, dict) else {}


class _AttrView:
    """Attribute access over nested dicts for ``str.format`` message templates."""

    def __init__(self, data: Any) -> None:
        self._data = data

    def __getattr__(self, name: str) -> Any:
        value = self._data.get(name) if isinstance(self._data, dict) else None
        return _AttrView(value) if isinstance(value, dict) else value


def _render(template: str, names: dict[str, Any]) -> str:
    view = {key: _AttrView(value) if isinstance(value, dict) else value for key, value in names.items()}
    return template.format_map(view)


def _when(snapshot: dict[str, Any], visit: dict[str, Any], when: Any, names: dict[str, Any]) -> bool:
    if when is None:
        return True
    if isinstance(when, bool):
        return when
    return evaluate_condition(snapshot, visit, str(when), names=names)


def evaluate_gate_rules(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    rules: dict[str, Any],
    *,
    run_dir: Path,
) -> dict[str, Any]:
    """First matching rule wins: ``decision``/``decision_from`` → ok; ``reject`` → fail-closed code."""
    gate_node_id = str(visit["node_id"])
    evidence, refs = gate_evidence(snapshot, rules.get("evidence") or {}, run_dir)
    names: dict[str, Any] = {"evidence": evidence, "derived": {}}
    for name, expr in (rules.get("derive") or {}).items():
        names["derived"][str(name)] = _when(snapshot, visit, expr, names)

    for rule in rules["rules"]:
        if not _when(snapshot, visit, rule.get("when"), names):
            continue
        rule_name = str(rule["id"])
        evidence_refs = list(refs) if rule.get("evidence_refs", True) is not False else []
        if "reject" in rule:
            outcome: dict[str, Any] = {
                "ok": False,
                "code": str(rule["reject"]),
                "message": _render(str(rule.get("message") or rule_name), names),
                "rule_id": f"{gate_node_id}/{rule_name}",
            }
            if evidence_refs:
                outcome["evidence_refs"] = evidence_refs
            return outcome
        if "decision_from" in rule:
            decision = evaluate_expression(snapshot, visit, str(rule["decision_from"]), names=names)
        else:
            decision = rule["decision"]
        decision = str(decision)
        template = str(rule.get("rule_id") or f"{gate_node_id}/{rule_name}")
        return {
            "ok": True,
            "decision": decision,
            "rule_id": _render(template, {**names, "decision": decision}),
            "evidence_refs": evidence_refs,
        }
    return {
        "ok": False,
        "code": "EVIDENCE_MISSING",
        "message": f"No gate rule matched for {gate_node_id!r}",
    }
