"""Phase 11 eval harness: failure taxonomy, compare-runs, and quality gates."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

FAILURE_CLASS_CODES: dict[str, str] = {
    "A": "ambiguity",
    "B": "missing_knowledge",
    "C": "plan_error",
    "D": "decomposition_error",
    "E": "oversized_context",
    "F": "integration_gap",
    "G": "implementation_mistake",
    "H": "environment_error",
    "I": "process_violation",
}

FAILURE_CLASS_ALIASES: dict[str, str] = {
    **{value: value for value in FAILURE_CLASS_CODES.values()},
    **FAILURE_CLASS_CODES,
    "decomposition": "decomposition_error",
    "implementation": "implementation_mistake",
    "environment": "environment_error",
    "process": "process_violation",
}

SCHEMA_EXAMPLE_FIXTURES: dict[str, str] = {
    "run-state-implementation.example.json": "run-state",
    "execution-graph-iris.example.json": "execution-graph",
    "ticket-auth-001.example.json": "ticket",
    "agent-craft.example.json": "craft",
    "agent-receipt.example.json": "receipt",
    "resume-packet.example.json": "resume",
    "handoff.example.json": "handoff",
    "worker-launch-packet.example.json": "worker-launch",
}

PR_TITLE_VIOLATION_RE = re.compile(r"^(feat|fix|chore|docs|refactor|test|ci|build|perf|style)(\(.+\))?:", re.I)
EVAL_BRANCH_VIOLATION_RE = re.compile(r"^(feat|fix|eval/[^/]+/[^/]+)", re.I)


class EvalError(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        required_input: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.error_code = error_code
        self.message = message
        self.required_input = required_input
        self.extra = extra or {}


def load_thresholds(path: Path, packet: str) -> dict[str, Any]:
    if yaml is None:
        raise EvalError("MISSING_PYYAML", "PyYAML is required to load eval thresholds.")
    if not path.is_file():
        raise EvalError("MISSING_THRESHOLDS", f"Thresholds file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    packets = data.get("packets") if isinstance(data, dict) else None
    if not isinstance(packets, dict) or packet not in packets:
        raise EvalError(
            "UNKNOWN_PACKET",
            f"No thresholds for packet {packet!r}.",
            required_input="packet",
            extra={"known_packets": sorted(packets) if isinstance(packets, dict) else []},
        )
    integrity = data.get("integrity") if isinstance(data.get("integrity"), dict) else {}
    return {"packet": packets[packet], "integrity": integrity}


def normalize_failure_class(raw: str) -> str:
    key = raw.strip()
    normalized = FAILURE_CLASS_ALIASES.get(key) or FAILURE_CLASS_ALIASES.get(key.upper())
    if normalized is None:
        raise EvalError(
            "INVALID_FAILURE_CLASS",
            f"Unknown failure class {raw!r}.",
            required_input="failure_class",
            extra={"known_codes": sorted(FAILURE_CLASS_CODES), "known_classes": sorted(FAILURE_CLASS_CODES.values())},
        )
    return normalized


def load_receipts(receipts_dir: Path) -> list[dict[str, Any]]:
    if not receipts_dir.is_dir():
        return []
    receipts: list[dict[str, Any]] = []
    for path in sorted(receipts_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            receipts.append(payload)
    return receipts


def suggest_failure_class(
    *,
    events: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
    source_step_id: str | None = None,
) -> dict[str, Any]:
    hints: list[dict[str, Any]] = []
    for receipt in receipts:
        failure_class = receipt.get("failure_class")
        if isinstance(failure_class, str):
            hints.append(
                {
                    "failure_class": failure_class,
                    "source": "receipt.failure_class",
                    "receipt_id": receipt.get("receipt_id"),
                }
            )
        blockers = receipt.get("blockers") if isinstance(receipt.get("blockers"), list) else []
        joined = " ".join(str(item) for item in blockers).lower()
        if "agents.md" in joined or "agents md" in joined:
            hints.append(
                {
                    "failure_class": "missing_knowledge",
                    "source": "receipt.blockers",
                    "receipt_id": receipt.get("receipt_id"),
                }
            )

    for event in events:
        if event.get("event_type") != "failure_classified":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        failure_class = payload.get("failure_class")
        if isinstance(failure_class, str):
            hints.append(
                {
                    "failure_class": failure_class,
                    "source": "event.failure_classified",
                    "step_id": event.get("step_id"),
                }
            )

    if source_step_id == "intake.grill" or source_step_id == "intake.present_ac":
        hints.append({"failure_class": "ambiguity", "source": "step.intake"})
    if source_step_id == "plan.graph":
        hints.append({"failure_class": "plan_error", "source": "step.plan.graph"})
    if source_step_id == "implement.build":
        hints.append({"failure_class": "decomposition_error", "source": "step.implement.build"})
    if source_step_id == "implement.pre_pr_review":
        hints.append({"failure_class": "integration_gap", "source": "step.implement.pre_pr_review"})

    ranked: dict[str, int] = {}
    for hint in hints:
        failure_class = hint["failure_class"]
        ranked[failure_class] = ranked.get(failure_class, 0) + 1
    suggested = max(ranked, key=ranked.get) if ranked else None
    return {"suggested": suggested, "hints": hints}


def classify_failure(
    *,
    run_id: str,
    events_path: Path,
    failure_class: str,
    source_step_id: str | None,
    notes: str | None,
    actor: str,
    append_event: Callable[[Path, dict[str, Any]], None],
    make_event: Callable[..., dict[str, Any]],
    receipts_dir: Path | None = None,
    receipt_id: str | None = None,
) -> dict[str, Any]:
    normalized = normalize_failure_class(failure_class)
    receipts: list[dict[str, Any]] = []
    if receipts_dir is not None:
        receipts = load_receipts(receipts_dir)
        if receipt_id:
            receipts = [item for item in receipts if item.get("receipt_id") == receipt_id]
    hints = suggest_failure_class(
        events=load_events(events_path),
        receipts=receipts,
        source_step_id=source_step_id,
    )
    payload: dict[str, Any] = {
        "failure_class": normalized,
        "source_step_id": source_step_id,
    }
    if notes:
        payload["notes"] = notes
    if hints["hints"]:
        payload["hints"] = hints["hints"]
    event = make_event(
        run_id,
        "failure_classified",
        actor,
        step_id=source_step_id,
        payload=payload,
    )
    append_event(events_path, event)
    return {
        "recorded": True,
        "failure_class": normalized,
        "failure_code": next((code for code, value in FAILURE_CLASS_CODES.items() if value == normalized), None),
        "event_id": event["event_id"],
        "suggested": hints["suggested"],
        "hints": hints["hints"],
    }


def load_events(events_path: Path) -> list[dict[str, Any]]:
    if not events_path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        item = json.loads(stripped)
        if isinstance(item, dict):
            events.append(item)
    return events


def agent_launch_counts(events: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        if event.get("event_type") != "subagent_launched":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        agent = payload.get("agent")
        if isinstance(agent, str):
            counts[agent] = counts.get(agent, 0) + 1
    return counts


def builder_launch_metrics(events: list[dict[str, Any]]) -> dict[str, int]:
    launch_ids: set[str] = set()
    completed_launch_ids: set[str] = set()
    with_work_item = 0
    orphan_completions = 0
    for event in events:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if event.get("event_type") == "subagent_launched":
            launch_id = payload.get("launch_id")
            if payload.get("work_item_id"):
                with_work_item += 1
            if isinstance(launch_id, str):
                launch_ids.add(launch_id)
        if event.get("event_type") in ("subagent_completed", "subagent_failed"):
            launch_id = payload.get("launch_id")
            if isinstance(launch_id, str):
                if launch_id not in launch_ids:
                    orphan_completions += 1
                completed_launch_ids.add(launch_id)
            else:
                orphan_completions += 1
    orphan_launches = len(launch_ids - completed_launch_ids)
    return {
        "builder_launches_with_work_item": with_work_item,
        "orphan_launches": orphan_launches,
        "orphan_completions": orphan_completions,
    }


def derive_eval_signals(
    *,
    state: dict[str, Any],
    events: list[dict[str, Any]],
    transcript_findings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    launches = agent_launch_counts(events)
    builder_metrics = builder_launch_metrics(events)
    subagent_launches = sum(launches.values())
    documentation_writer_runs = launches.get("documentation-writer", 0)
    security_loops = int((state.get("rework") or {}).get("builder_to_bugbot_loops") or 0)

    delivery_bypass = 0
    hand_written_receipt = 0
    parent_app_edit = 0
    raw_dotnet = 0
    continued_without_handoff = 0
    auto_grill = 0
    if transcript_findings:
        for finding in transcript_findings.get("findings") or []:
            rule_id = finding.get("rule_id")
            if rule_id == "DELIVERY_CHECK_BYPASS":
                delivery_bypass += 1
            elif rule_id in ("HAND_WRITE_RECEIPT", "RECEIPT_BACKFILL"):
                hand_written_receipt = 1
            elif rule_id == "PARENT_APP_EDIT":
                parent_app_edit = 1
            elif rule_id == "RAW_DOTNET_ORCHESTRATOR":
                raw_dotnet = 1
            elif rule_id == "continued_after_worker_without_handoff":
                continued_without_handoff = 1
            elif rule_id == "auto_grill_with_clarifying_questions":
                auto_grill = 1

    build_step_verify_bypass = 0
    build_evidence = (state.get("steps") or {}).get("implement.build")
    if isinstance(build_evidence, dict) and build_evidence.get("status") == "completed":
        verify_ok = False
        for event in events:
            if event.get("event_type") != "cli_invoked":
                continue
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            command = str(payload.get("command") or "")
            argv = payload.get("argv") if isinstance(payload.get("argv"), list) else []
            haystack = f"{command} {' '.join(str(part) for part in argv)}".lower()
            if "build-step" in haystack and "verify" in haystack and payload.get("exit_code") == 0:
                verify_ok = True
                break
        if not verify_ok:
            build_step_verify_bypass = 1

    missing_handoff = 1 if isinstance(state.get("session_stop_obligation"), dict) else 0
    invalid_delivery_proof = 0
    if state.get("outcome_status") == "completed" and state.get("run_mode") == "implementation":
        seal = state.get("delivery_seal")
        if not isinstance(seal, dict) or not seal.get("staged_secrets_passed"):
            invalid_delivery_proof = 1

    pr_title_violations = 0
    branch_violations = 0
    resolved_title = state.get("resolved_pr_title")
    if isinstance(resolved_title, str) and PR_TITLE_VIOLATION_RE.match(resolved_title.strip()):
        pr_title_violations += 1
    feature_branch = state.get("feature_branch")
    issue_key = state.get("issue_key")
    if isinstance(feature_branch, str):
        branch = feature_branch.strip()
        if PR_TITLE_VIOLATION_RE.match(branch):
            branch_violations += 1
        elif isinstance(issue_key, str) and issue_key and issue_key not in branch:
            branch_violations += 1

    gate_resolved_all = [event for event in events if event.get("event_type") == "gate_resolved"]
    gate_resolved = [
        event
        for event in gate_resolved_all
        if (event.get("payload") or {}).get("gate_source", (event.get("payload") or {}).get("source", "human"))
        == "human"
    ]
    if int(state.get("clarifying_questions_count") or 0) > 0:
        auto_grill = int(
            any(
                event.get("step_id") == "intake.grill"
                and (event.get("payload") or {}).get("source") == "auto"
                and (event.get("payload") or {}).get("decision") == "approve"
                for event in gate_resolved_all
            )
        )
    last_worker = -1
    last_handoff = -1
    transitions_after_worker = 0
    for index, event in enumerate(events):
        if event.get("event_type") in ("subagent_completed", "subagent_failed"):
            last_worker = index
            transitions_after_worker = 0
        elif event.get("event_type") == "handoff_written" and index > last_worker:
            last_handoff = index
        elif event.get("event_type") == "state_transition" and index > last_worker:
            transitions_after_worker += 1
    if last_worker >= 0 and last_handoff < last_worker and transitions_after_worker > 1:
        continued_without_handoff = 1
    material_changes = sum(
        1
        for event in gate_resolved
        if isinstance(event.get("payload"), dict) and event["payload"].get("material_change")
    )
    gate_utility_ratio = (
        round(material_changes / len(gate_resolved), 3) if gate_resolved else None
    )

    return {
        "subagent_invocations": subagent_launches,
        "builder_launches_with_work_item": builder_metrics["builder_launches_with_work_item"],
        "orphan_launches": builder_metrics["orphan_launches"],
        "orphan_completions": builder_metrics["orphan_completions"],
        "agent_launch_counts": launches,
        "documentation_writer_runs": documentation_writer_runs,
        "security_review_loops": security_loops,
        "delivery_check_bypass": delivery_bypass,
        "pr_title_violations": pr_title_violations,
        "branch_violations": branch_violations,
        "pr_title_branch_violations": pr_title_violations + branch_violations,
        "gate_utility_ratio": gate_utility_ratio,
        "gate_resolved_count": len(gate_resolved),
        "gate_resolved_total_count": len(gate_resolved_all),
        "gate_material_change_count": material_changes,
        "build_step_verify_bypass": build_step_verify_bypass,
        "missing_handoff": missing_handoff,
        "invalid_delivery_proof": invalid_delivery_proof,
        "hand_written_receipt_detected": hand_written_receipt,
        "parent_app_edit_detected": parent_app_edit,
        "raw_dotnet_orchestrator": raw_dotnet,
        "auto_grill_with_clarifying_questions": auto_grill,
        "continued_after_worker_without_handoff": continued_without_handoff,
    }


def analyze_transcript_with_rules(text: str, rules_path: Path) -> dict[str, Any]:
    if yaml is None:
        raise EvalError("MISSING_PYYAML", "PyYAML is required for transcript lint.")
    data = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    rules = data.get("rules") if isinstance(data, dict) else None
    if not isinstance(rules, dict):
        raise EvalError("INVALID_RULES", f"Invalid rules file: {rules_path}")
    compiled: list[dict[str, Any]] = []
    for rule_id, body in rules.items():
        if not isinstance(body, dict):
            continue
        patterns = body.get("patterns") or []
        compiled.append(
            {
                "id": rule_id,
                "description": body.get("description", ""),
                "severity": body.get("severity", "process_violation"),
                "patterns": [re.compile(pattern) for pattern in patterns],
            }
        )
    findings: list[dict[str, Any]] = []
    for rule in compiled:
        for pattern in rule["patterns"]:
            for match in pattern.finditer(text):
                findings.append(
                    {
                        "rule_id": rule["id"],
                        "severity": rule["severity"],
                        "description": rule["description"],
                        "match": match.group(0),
                        "offset": match.start(),
                    }
                )
    return {
        "finding_count": len(findings),
        "findings": findings,
        "rules_checked": [rule["id"] for rule in compiled],
    }


def enrich_metrics_for_eval(
    metrics: dict[str, Any],
    state: dict[str, Any],
    events_path: Path,
    *,
    transcript_path: Path | None = None,
    rules_path: Path | None = None,
) -> dict[str, Any]:
    events = load_events(events_path)
    transcript_findings = None
    if transcript_path is not None and transcript_path.is_file():
        resolved_rules = rules_path
        if resolved_rules is None or not resolved_rules.is_file():
            candidate = transcript_path.parent / "transcript-rules.yaml"
            if candidate.is_file():
                resolved_rules = candidate
            else:
                repo_rules = Path(__file__).resolve().parents[3] / "evaluation" / "scripts" / "transcript-rules.yaml"
                resolved_rules = repo_rules if repo_rules.is_file() else None
        if resolved_rules is not None and resolved_rules.is_file():
            if transcript_path.suffix == ".jsonl":
                from foundry_transcript_lint import analyze_transcript_file  # noqa: PLC0415

                rules_data = yaml.safe_load(resolved_rules.read_text(encoding="utf-8"))
                rules_body = rules_data.get("rules") if isinstance(rules_data, dict) else None
                compiled_rules: list[dict[str, Any]] = []
                if isinstance(rules_body, dict):
                    for rule_id, body in rules_body.items():
                        if not isinstance(body, dict):
                            continue
                        compiled_rules.append(
                            {
                                "id": rule_id,
                                "description": body.get("description", ""),
                                "severity": body.get("severity", "process_violation"),
                                "patterns": [re.compile(pattern) for pattern in body.get("patterns") or []],
                            }
                        )
                transcript_findings = analyze_transcript_file(transcript_path, compiled_rules)
            else:
                transcript_findings = analyze_transcript_with_rules(
                    transcript_path.read_text(encoding="utf-8"),
                    resolved_rules,
                )
    if transcript_findings is not None:
        metrics["transcript_findings"] = transcript_findings
    metrics["eval_signals"] = derive_eval_signals(
        state=state,
        events=events,
        transcript_findings=transcript_findings,
    )
    return metrics


def load_metrics_export(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise EvalError("MISSING_METRICS", f"Metrics export not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise EvalError("INVALID_METRICS", f"{path} must contain a JSON object.")
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else payload
    return {
        "path": str(path),
        "artifact": payload.get("artifact"),
        "run_id": payload.get("run_id") or metrics.get("run_id"),
        "factory_version": payload.get("factory_version") or metrics.get("factory_version"),
        "metrics": metrics,
    }


def compare_runs(
    baseline_path: Path,
    candidate_path: Path,
    *,
    scorecard_baseline: dict[str, Any] | None = None,
    scorecard_candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    baseline = load_metrics_export(baseline_path)
    candidate = load_metrics_export(candidate_path)
    base_metrics = baseline["metrics"]
    cand_metrics = candidate["metrics"]
    base_eval = base_metrics.get("eval_signals") or {}
    cand_eval = cand_metrics.get("eval_signals") or {}

    def delta(key: str) -> int | None:
        if key in ("validator_loops", "builder_to_bugbot_loops"):
            left = (base_metrics.get("rework") or {}).get(key)
            right = (cand_metrics.get("rework") or {}).get(key)
            if isinstance(left, int) and isinstance(right, int):
                return right - left
            return None
        if key not in base_eval and key not in cand_eval:
            left = base_metrics.get(key)
            right = cand_metrics.get(key)
            if isinstance(left, dict) or isinstance(right, dict):
                return None
            if isinstance(left, int) and isinstance(right, int):
                return right - left
            return None
        left = base_eval.get(key)
        right = cand_eval.get(key)
        if isinstance(left, int) and isinstance(right, int):
            return right - left
        return None

    scorecard_delta: dict[str, Any] | None = None
    if scorecard_baseline and scorecard_candidate:
        scorecard_delta = {}
        for key in ("pr_score", "docs_score", "trust_score"):
            left = scorecard_baseline.get(key)
            right = scorecard_candidate.get(key)
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                scorecard_delta[key] = right - left

    return {
        "artifact": "foundry-compare-runs",
        "baseline": {
            "path": baseline["path"],
            "run_id": baseline["run_id"],
            "factory_version": baseline["factory_version"],
        },
        "candidate": {
            "path": candidate["path"],
            "run_id": candidate["run_id"],
            "factory_version": candidate["factory_version"],
        },
        "deltas": {
            "subagent_invocations": delta("subagent_invocations"),
            "documentation_writer_runs": delta("documentation_writer_runs"),
            "security_review_loops": delta("security_review_loops"),
            "delivery_check_bypass": delta("delivery_check_bypass"),
            "pr_title_branch_violations": delta("pr_title_branch_violations"),
            "validator_loops": delta("validator_loops"),
            "builder_to_bugbot_loops": delta("builder_to_bugbot_loops"),
        },
        "scorecard_delta": scorecard_delta,
    }


def check_thresholds(
    candidate_metrics: dict[str, Any],
    thresholds: dict[str, Any],
    *,
    baseline_metrics: dict[str, Any] | None = None,
    scorecard_baseline: dict[str, Any] | None = None,
    scorecard_candidate: dict[str, Any] | None = None,
    integrity_thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    eval_signals = candidate_metrics.get("eval_signals") or {}
    checks: list[dict[str, Any]] = []
    required_signals = set(thresholds.get("required_signals") or [])
    required_signals.update((integrity_thresholds or {}).keys())
    for signal_key in sorted(required_signals):
        present = signal_key in eval_signals or signal_key in candidate_metrics
        checks.append(
            {
                "name": f"required_signal.{signal_key}",
                "pass": present,
                "actual": "present" if present else "missing",
            }
        )

    if "subagent_invocations" in thresholds:
        subagent_count = int(eval_signals.get("subagent_invocations") or candidate_metrics.get("subagent_invocations", {}).get("launched") or 0)
        gielinor = int(thresholds.get("subagent_invocations", {}).get("gielinor_baseline", 15))
        fenris = int(thresholds.get("subagent_invocations", {}).get("fenris_baseline", 27))
        security_loops = int(eval_signals.get("security_review_loops") or 0)
        baseline_security = None
        if baseline_metrics:
            baseline_eval = baseline_metrics.get("eval_signals") or {}
            baseline_security = baseline_eval.get("security_review_loops")
        subagent_pass = subagent_count <= gielinor or (
            subagent_count <= fenris
            and (baseline_security is None or security_loops < int(baseline_security))
        )
        checks.append(
            {
                "name": "subagent_invocations",
                "pass": subagent_pass,
                "actual": subagent_count,
                "limits": {"gielinor": gielinor, "fenris": fenris},
                "security_review_loops": security_loops,
            }
        )

    if "documentation_writer_runs_max" in thresholds:
        doc_writer_max = int(thresholds["documentation_writer_runs_max"])
        doc_writer_actual = int(eval_signals.get("documentation_writer_runs") or 0)
        checks.append(
            {
                "name": "documentation_writer_runs",
                "pass": doc_writer_actual <= doc_writer_max,
                "actual": doc_writer_actual,
                "limit": doc_writer_max,
            }
        )

    if "delivery_check_bypass_max" in thresholds:
        bypass_max = int(thresholds["delivery_check_bypass_max"])
        bypass_actual = int(eval_signals.get("delivery_check_bypass") or 0)
        checks.append(
            {
                "name": "delivery_check_bypass",
                "pass": bypass_actual <= bypass_max,
                "actual": bypass_actual,
                "limit": bypass_max,
            }
        )

    if "pr_title_branch_violations_max" in thresholds:
        title_branch_max = int(thresholds["pr_title_branch_violations_max"])
        title_branch_actual = int(eval_signals.get("pr_title_branch_violations") or 0)
        checks.append(
            {
                "name": "pr_title_branch_violations",
                "pass": title_branch_actual <= title_branch_max,
                "actual": title_branch_actual,
                "limit": title_branch_max,
            }
        )

    for signal_key, max_key in (
        ("hand_written_receipt_detected", "hand_written_receipt_detected_max"),
        ("parent_app_edit_detected", "parent_app_edit_detected_max"),
    ):
        if max_key not in thresholds:
            continue
        limit = int(thresholds[max_key])
        actual = int(
            eval_signals.get(signal_key)
            if eval_signals.get(signal_key) is not None
            else candidate_metrics.get(signal_key)
            or 0
        )
        checks.append(
            {
                "name": signal_key,
                "pass": actual <= limit,
                "actual": actual,
                "limit": limit,
            }
        )

    if integrity_thresholds:
        for signal_key, limit_raw in integrity_thresholds.items():
            limit = int(limit_raw)
            actual = int(
                eval_signals.get(signal_key)
                if eval_signals.get(signal_key) is not None
                else candidate_metrics.get(signal_key)
                or 0
            )
            checks.append(
                {
                    "name": f"integrity.{signal_key}",
                    "pass": actual <= limit,
                    "actual": actual,
                    "limit": limit,
                }
            )

    if "min_builder_launches_with_work_item" in thresholds:
        builder_min = int(thresholds["min_builder_launches_with_work_item"])
        builder_actual = int(eval_signals.get("builder_launches_with_work_item") or 0)
        checks.append(
            {
                "name": "builder_launches_with_work_item",
                "pass": builder_actual >= builder_min,
                "actual": builder_actual,
                "limit": builder_min,
            }
        )

    if "orphan_launch_max" in thresholds:
        orphan_max = int(thresholds["orphan_launch_max"])
        orphan_actual = int(eval_signals.get("orphan_launches") or 0)
        checks.append(
            {
                "name": "orphan_launches",
                "pass": orphan_actual <= orphan_max,
                "actual": orphan_actual,
                "limit": orphan_max,
            }
        )

    scorecard_pass = True
    if thresholds.get("eval_scorecard_min_vs_baseline") and scorecard_baseline and scorecard_candidate:
        for key in ("pr_score", "docs_score", "trust_score"):
            left = scorecard_baseline.get(key)
            right = scorecard_candidate.get(key)
            if isinstance(left, (int, float)) and isinstance(right, (int, float)) and right < left:
                scorecard_pass = False
        checks.append(
            {
                "name": "eval_scorecard_vs_baseline",
                "pass": scorecard_pass,
                "baseline": scorecard_baseline,
                "candidate": scorecard_candidate,
            }
        )

    passed = all(item["pass"] for item in checks)
    return {
        "artifact": "foundry-threshold-check",
        "packet": thresholds.get("description"),
        "passed": passed,
        "checks": checks,
    }


def validate_schema_examples(
    schemas_dir: Path,
    examples_dir: Path,
    *,
    validate_document: Callable[[Path, str], dict[str, Any]],
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for fixture_name, schema_name in SCHEMA_EXAMPLE_FIXTURES.items():
        fixture_path = examples_dir / fixture_name
        if not fixture_path.is_file():
            raise EvalError("MISSING_FIXTURE", f"Example fixture not found: {fixture_path}")
        result = validate_document(fixture_path, schema_name)
        results.append({"fixture": fixture_name, "schema": schema_name, "valid": True, **result})
    return {"validated": len(results), "fixtures": results}
