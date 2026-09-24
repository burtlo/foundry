"""Evidence digests and stale-artifact checks for Foundry."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class LineageError(Exception):
    def __init__(self, error_code: str, message: str, *, extra: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.extra = extra or {}


def digest_value(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def digest_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest_text_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def approved_ac_digest(state: dict[str, Any]) -> str:
    return digest_value(
        {
            "version": int(state.get("approved_ac_version") or 0),
            "items": state.get("approved_ac") or [],
        }
    )


def current_digests(state: dict[str, Any], run_dir: Path) -> dict[str, str]:
    digests = {"approved_ac": approved_ac_digest(state)}
    brief = state.get("brief_snapshot")
    if isinstance(brief, dict) and isinstance(brief.get("hash"), str):
        digests["brief"] = brief["hash"]
    graph_digest = digest_file(run_dir / "execution-graph.json")
    if graph_digest:
        digests["execution_graph"] = graph_digest
    seal = state.get("delivery_seal")
    if isinstance(seal, dict) and isinstance(seal.get("index_tree"), str):
        digests["reviewed_tree"] = seal["index_tree"]
    return digests


def gate_artifact_digest(step_id: str, state: dict[str, Any], run_dir: Path) -> str:
    digests = current_digests(state, run_dir)
    if step_id in ("intake.present_ac", "intake.approve_ac"):
        return digest_value(state.get("presented_ac") or state.get("approved_ac") or [])
    if step_id == "plan.brief":
        return digests.get("brief") or digest_text_file(run_dir / "brief.md") or digest_value(None)
    if step_id == "plan.graph":
        return digests.get("execution_graph") or digest_value(None)
    if step_id.startswith("implement.") or step_id.startswith("deliver."):
        return digest_value(digests)
    return digest_value({"step_id": step_id, "digests": digests})


def gate_artifact_available(step_id: str, state: dict[str, Any], run_dir: Path) -> bool:
    if step_id in ("intake.present_ac", "intake.approve_ac"):
        return bool(state.get("presented_ac") or state.get("approved_ac"))
    if step_id == "plan.brief":
        return isinstance(state.get("brief_snapshot"), dict) or (run_dir / "brief.md").is_file()
    if step_id == "plan.graph":
        return (run_dir / "execution-graph.json").is_file()
    return True


def stamp_graph(graph: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    graph["approved_ac_version"] = int(state.get("approved_ac_version") or 0)
    graph["approved_ac_digest"] = approved_ac_digest(state)
    brief = state.get("brief_snapshot")
    if isinstance(brief, dict) and isinstance(brief.get("hash"), str):
        graph["brief_hash"] = brief["hash"]
    return graph


def assert_graph_current(graph: dict[str, Any], state: dict[str, Any]) -> None:
    expected_version = int(state.get("approved_ac_version") or 0)
    expected_ac_digest = approved_ac_digest(state)
    expected_brief = (state.get("brief_snapshot") or {}).get("hash")
    mismatches: list[str] = []
    if expected_version and int(graph.get("approved_ac_version") or 0) != expected_version:
        mismatches.append("approved_ac_version")
    if expected_version and graph.get("approved_ac_digest") not in (None, expected_ac_digest):
        mismatches.append("approved_ac_digest")
    if expected_brief and graph.get("brief_hash") not in (None, expected_brief):
        mismatches.append("brief_hash")
    if mismatches:
        raise LineageError(
            "STALE_EXECUTION_GRAPH",
            "Execution graph was derived from stale acceptance criteria or brief evidence.",
            extra={"mismatches": mismatches},
        )


def invalidate_after(state: dict[str, Any], source_step: str) -> list[str]:
    """Clear descendant evidence after an upstream rework decision."""
    order = [
        "intake.refine",
        "intake.grill",
        "intake.present_ac",
        "intake.approve_ac",
        "plan.research",
        "plan.brief",
        "plan.graph",
        "implement.branch",
        "implement.build",
        "implement.validate",
        "implement.code_review",
        "implement.devops_review",
        "implement.pre_pr_review",
        "implement.documentation",
        "deliver.gate",
        "deliver.scope_comment",
        "deliver.ship",
    ]
    if source_step not in order:
        return []
    invalidated: list[str] = []
    steps = state.get("steps") if isinstance(state.get("steps"), dict) else {}
    for step_id in order[order.index(source_step) + 1 :]:
        if step_id in steps:
            steps.pop(step_id, None)
            invalidated.append(step_id)
    for key in ("delivery_seal", "pr_url", "resolved_pr_title"):
        state.pop(key, None)
    if source_step.startswith("intake.") or source_step in ("plan.research", "plan.brief"):
        state.pop("execution_graph_id", None)
    return invalidated
