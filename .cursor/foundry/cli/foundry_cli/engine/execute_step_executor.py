"""Host-owned deterministic Execute steps (intake through commit) — workflow-02 slices 2A–2C."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from foundry_cli.app_manifest import load_manifest
from foundry_cli.engine.intake_executor import (
    AGENT_RECEIPT_SCHEMA,
    INTAKE_RECEIPT_SCHEMA,
    _ledger_checks_for_visit,
    _seal_receipt_file,
    _write_assessment,
)
from foundry_cli.engine.lifecycle import transition_visit
from foundry_cli.constants import EVENT_ARTIFACT_LINKED
from foundry_cli.engine.agent.tasks import EXECUTE_PLAN_TASK_ID
from foundry_cli.engine.shape_step_executor import (
    _accepted_agent_result,
    _publish_document_artifact,
)
from foundry_cli.engine.state import patch_allowed
from foundry_cli.paths import resolve_run_uri
from foundry_cli.engine.receipts import find_artifact_declaration
from foundry_cli.ledger import append_event, count_events
from foundry_cli.registry import get_node

EXECUTE_INTAKE_NODE = "execute.intake"
EXECUTE_BRANCH_NODE = "execute.branch"
EXECUTE_PLAN_NODE = "execute.plan"
EXECUTE_BUILD_NODE = "execute.build"
EXECUTE_TEST_NODE = "execute.test"
EXECUTE_COMMIT_NODE = "execute.commit"
EXECUTE_BUILD_PARKED_VISIT_STATE_KEY = "execute_build_parked_visit_id"
EXECUTE_PLAN_TO_BUILD_CONNECTION = "execute.plan-to-execute.build"
INTAKE_AGENT_NAME = "intake-checker"
COMMIT_AGENT_NAME = "commit-agent"
PLANNER_AGENT_NAME = "planner"
FEATURE_BUILDER_AGENT_NAME = "feature-builder"
REPAIRER_AGENT_NAME = "repairer"

_BRANCH_NAME_RE = re.compile(r"^foundry/[a-z0-9][a-z0-9._/-]*$")


def _snapshot_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    state = snapshot.get("state")
    return state if isinstance(state, dict) else {}


def _visit_id_from_run_uri(uri: str) -> str:
    match = re.search(r"/(v-\d+)/", uri)
    return match.group(1) if match else ""


def _shape_plan_path(snapshot: dict[str, Any], run_dir: Path) -> tuple[Path | None, str | None]:
    state = _snapshot_state(snapshot)
    plan_uri = state.get("plan_path")
    if not isinstance(plan_uri, str) or not plan_uri.strip():
        return None, "PLAN_PATH_MISSING"
    visit_id = _visit_id_from_run_uri(plan_uri)
    path = resolve_run_uri(plan_uri, run_dir, visit_id)
    if not path.is_file():
        return None, "PLAN_ARTIFACT_MISSING"
    return path, None


def _validate_frozen_shape(snapshot: dict[str, Any], run_dir: Path) -> list[str]:
    findings: list[str] = []
    state = _snapshot_state(snapshot)
    approved_ac = str(state.get("approved_ac") or "").strip()
    if not approved_ac:
        findings.append("approved_ac missing from shape.record")
    if not state.get("approved_ac_version"):
        findings.append("approved_ac_version not recorded")
    if not str(state.get("approved_ac_digest") or "").strip():
        findings.append("approved_ac_digest missing")
    plan_path, plan_err = _shape_plan_path(snapshot, run_dir)
    if plan_err:
        findings.append(plan_err)
    elif plan_path is not None:
        text = plan_path.read_text(encoding="utf-8", errors="replace")
        ac_probe = approved_ac.rstrip(".")
        if approved_ac and ac_probe and ac_probe not in text:
            findings.append("plan.md does not contain approved acceptance criteria text")
    return findings


def _run_slug(snapshot: dict[str, Any]) -> str:
    state = _snapshot_state(snapshot)
    slug = state.get("run_slug")
    if isinstance(slug, str) and slug.strip():
        return slug.strip()
    run_id = str(snapshot.get("run_id") or "run")
    return run_id


def _sanitize_slug(slug: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", slug).strip("-").lower()
    return cleaned or "run"


def _expected_feature_branch(snapshot: dict[str, Any]) -> str:
    state = _snapshot_state(snapshot)
    existing = state.get("feature_branch")
    if isinstance(existing, str) and existing.strip() and _BRANCH_NAME_RE.match(existing.strip()):
        return existing.strip()
    slug = _sanitize_slug(_run_slug(snapshot))
    dev = state.get("developer_first_name")
    if isinstance(dev, str) and dev.strip():
        dev_part = re.sub(r"[^a-z0-9]+", "", dev.strip().lower())[:24]
        if dev_part:
            return f"foundry/{dev_part}/{slug}"
    return f"foundry/{slug}"


def _git_run(workspace: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )


def _git_default_branch(workspace: Path) -> str:
    probe = _git_run(workspace, "symbolic-ref", "--short", "HEAD")
    if probe.returncode == 0 and probe.stdout.strip():
        return probe.stdout.strip()
    probe = _git_run(workspace, "rev-parse", "--abbrev-ref", "HEAD")
    if probe.returncode == 0 and probe.stdout.strip() and probe.stdout.strip() != "HEAD":
        return probe.stdout.strip()
    return "main"


def _git_current_branch(workspace: Path) -> str | None:
    probe = _git_run(workspace, "rev-parse", "--abbrev-ref", "HEAD")
    if probe.returncode != 0:
        return None
    branch = probe.stdout.strip()
    return branch if branch and branch != "HEAD" else None


def _git_branch_exists(workspace: Path, branch_name: str) -> bool:
    probe = _git_run(workspace, "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}")
    return probe.returncode == 0


def _git_head_sha(workspace: Path) -> str | None:
    probe = _git_run(workspace, "rev-parse", "HEAD")
    if probe.returncode != 0:
        return None
    return probe.stdout.strip()


def _visit_admission_source(snapshot: dict[str, Any], visit_id: str) -> str | None:
    for event in snapshot.get("ledger") or []:
        if not isinstance(event, dict) or event.get("type") != "visit.admitted":
            continue
        if str(event.get("visit_id")) != visit_id:
            continue
        payload = event.get("payload") or {}
        source = payload.get("source")
        if isinstance(source, str) and source.strip():
            return source.strip()
        return None
    return None


def _connection_taken_payload(snapshot: dict[str, Any], connection_id: str) -> dict[str, Any] | None:
    for event in reversed(snapshot.get("ledger") or []):
        if not isinstance(event, dict) or event.get("type") != "connection.taken":
            continue
        payload = event.get("payload") or {}
        if str(payload.get("connection_id")) == connection_id:
            return payload
    return None


def _execute_build_boundary_parked(snapshot: dict[str, Any], visit_id: str) -> bool:
    state = _snapshot_state(snapshot)
    return str(state.get(EXECUTE_BUILD_PARKED_VISIT_STATE_KEY) or "") == visit_id


def _park_execute_build_boundary(snapshot: dict[str, Any], visit_id: str) -> None:
    state = snapshot.setdefault("state", {})
    if isinstance(state, dict):
        state[EXECUTE_BUILD_PARKED_VISIT_STATE_KEY] = visit_id


def _clear_execute_build_park(snapshot: dict[str, Any]) -> None:
    state = snapshot.get("state")
    if isinstance(state, dict):
        state.pop(EXECUTE_BUILD_PARKED_VISIT_STATE_KEY, None)


def _should_park_at_execute_build_boundary(snapshot: dict[str, Any], visit_id: str) -> str | None:
    if _execute_build_boundary_parked(snapshot, visit_id):
        return None
    source = _visit_admission_source(snapshot, visit_id)
    if not source:
        return None
    if source == EXECUTE_PLAN_TO_BUILD_CONNECTION:
        return "execute_build_boundary"
    payload = _connection_taken_payload(snapshot, source)
    if payload and str(payload.get("loop") or "").strip() == "repair":
        return "repair_reentry_boundary"
    return None


def run_execute_build_boundary_park(snapshot: dict[str, Any], visit: dict[str, Any]) -> dict[str, Any]:
    node_id = str(visit.get("node_id", ""))
    if node_id != EXECUTE_BUILD_NODE:
        return {"ok": False, "code": "WRONG_NODE", "message": f"expected execute.build, got {node_id!r}"}
    if str(visit.get("lifecycle")) != "opened":
        return {"ok": True}

    visit_id = str(visit.get("id", ""))
    if _execute_build_boundary_parked(snapshot, visit_id):
        _clear_execute_build_park(snapshot)
        return {"ok": True, "park_cleared": True}

    park_reason = _should_park_at_execute_build_boundary(snapshot, visit_id)
    if park_reason is None:
        return {"ok": True}

    _park_execute_build_boundary(snapshot, visit_id)
    return {
        "ok": True,
        "boundary_reason": park_reason,
        "wait": {
            "kind": "boundary",
            "summary": "Paused at execute.build boundary",
            "request_ref": park_reason,
        },
    }


def _ensure_feature_branch(workspace: Path, branch_name: str, default_branch: str) -> dict[str, Any]:
    if not _BRANCH_NAME_RE.match(branch_name):
        return {
            "ok": False,
            "code": "BRANCH_NAME_INVALID",
            "message": f"Feature branch {branch_name!r} does not match foundry/* naming rules",
        }
    current = _git_current_branch(workspace)
    if current == branch_name:
        head = _git_head_sha(workspace)
        return {"ok": True, "feature_branch": branch_name, "feature_branch_head": head, "created": False}

    if _git_branch_exists(workspace, branch_name):
        checkout = _git_run(workspace, "checkout", branch_name)
        if checkout.returncode != 0:
            return {
                "ok": False,
                "code": "BRANCH_CHECKOUT_FAILED",
                "message": checkout.stderr.strip() or checkout.stdout.strip() or "checkout failed",
            }
        head = _git_head_sha(workspace)
        return {"ok": True, "feature_branch": branch_name, "feature_branch_head": head, "created": False}

    base = default_branch
    if current != base:
        co_base = _git_run(workspace, "checkout", base)
        if co_base.returncode != 0:
            co_base = _git_run(workspace, "checkout", "-B", base)
        if co_base.returncode != 0:
            return {
                "ok": False,
                "code": "DEFAULT_BRANCH_CHECKOUT_FAILED",
                "message": co_base.stderr.strip() or "could not checkout default branch",
            }
    create = _git_run(workspace, "checkout", "-b", branch_name)
    if create.returncode != 0:
        return {
            "ok": False,
            "code": "BRANCH_CREATE_FAILED",
            "message": create.stderr.strip() or create.stdout.strip() or "branch create failed",
        }
    head = _git_head_sha(workspace)
    return {"ok": True, "feature_branch": branch_name, "feature_branch_head": head, "created": True}


def run_execute_intake_complete(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
    summary: str | None = None,
) -> dict[str, Any]:
    node_id = str(visit.get("node_id", ""))
    if node_id != EXECUTE_INTAKE_NODE:
        return {"ok": False, "code": "WRONG_NODE", "message": f"expected execute.intake, got {node_id!r}"}

    visit_id = str(visit["id"])
    state = snapshot.setdefault("state", {})
    if not isinstance(state, dict):
        state = {}
        snapshot["state"] = state

    if not state.get("run_slug"):
        patch_allowed(snapshot, get_node(flow, node_id), node_id, {"run_slug": _run_slug(snapshot)})

    from foundry_cli.engine.blocked_intake import visit_has_blocked_intake_receipt

    findings = _validate_frozen_shape(snapshot, run_dir)
    if visit_has_blocked_intake_receipt(snapshot, visit_id) and findings:
        return {
            "ok": True,
            "intake_status": "blocked",
            "transitioned": False,
            "visit_id": visit_id,
            "node_id": node_id,
            "findings": findings,
        }
    checks = _ledger_checks_for_visit(snapshot, visit_id)
    if not checks:
        checks = [{"id": "validate-manifest", "status": "pass"}]

    receipts_dir = run_dir / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    assessment_path = receipts_dir / "assessment.md"

    passed = not findings
    if passed:
        _write_assessment(
            assessment_path,
            verdict="PROCEED",
            raw_input=None,
            summary="Execute intake: frozen shape artifacts validated.",
            findings=["approved_ac and plan.md present.", "Git cleanliness enforced on admit."],
        )
        intake_status = "passed"
        summary_md = "PROCEED: execute intake checks passed (host)."
    else:
        _write_assessment(
            assessment_path,
            verdict="BLOCKED",
            raw_input=None,
            summary="Execute intake blocked: shape artifacts incomplete.",
            findings=findings,
        )
        intake_status = "blocked"
        summary_md = "BLOCKED: frozen shape validation failed."

    intake_draft = {
        "schema_version": "2.2.0",
        "step_id": node_id,
        "status": intake_status,
        "checks": checks,
        "agent_assessment": {
            "assessment_path": "run:receipts/assessment.md",
            "summary_markdown": summary_md,
        },
    }
    if not passed:
        intake_draft["agent_assessment"]["blocked_reason"] = "SHAPE_ARTIFACTS_INVALID"

    agent_draft = {
        "schema_version": "2.2.0",
        "agent": {"name": INTAKE_AGENT_NAME, "mode": "engine"},
        "status": "completed",
        "recommended_next_state": "execute.intake.gate",
        "outputs": {
            "assessment_path": "run:receipts/assessment.md",
            "summary_markdown": summary_md,
        },
    }

    for schema_ref, draft, file_name in (
        (INTAKE_RECEIPT_SCHEMA, intake_draft, "intake.json"),
        (AGENT_RECEIPT_SCHEMA, agent_draft, "agent.json"),
    ):
        draft_path = receipts_dir / file_name
        draft_path.write_text(json.dumps(draft, indent=2) + "\n", encoding="utf-8")
        seal_result = _seal_receipt_file(
            draft=draft,
            schema_ref=schema_ref,
            snapshot=snapshot,
            visit=visit,
            run_dir=run_dir,
            visit_id=visit_id,
            foundry_bundle=foundry_bundle,
        )
        if not seal_result.get("ok"):
            return seal_result

    if not passed:
        return {
            "ok": True,
            "intake_status": intake_status,
            "transitioned": False,
            "visit_id": visit_id,
            "node_id": node_id,
            "findings": findings,
        }

    patch_allowed(
        snapshot,
        get_node(flow, node_id),
        node_id,
        {"intake_path": "shaped", "entry_reason": state.get("entry_reason") or "execute_start"},
    )

    return transition_visit(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
        summary=summary or "Execute intake complete",
    )


def run_execute_branch_complete(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
    summary: str | None = None,
) -> dict[str, Any]:
    node_id = str(visit.get("node_id", ""))
    if node_id != EXECUTE_BRANCH_NODE:
        return {"ok": False, "code": "WRONG_NODE", "message": f"expected execute.branch, got {node_id!r}"}

    branch_name = _expected_feature_branch(snapshot)
    default_branch = _git_default_branch(workspace)
    branch_result = _ensure_feature_branch(workspace, branch_name, default_branch)
    if not branch_result.get("ok"):
        return branch_result

    graph_id = f"{_run_slug(snapshot)}:execution-graph"
    patch_allowed(
        snapshot,
        get_node(flow, node_id),
        node_id,
        {
            "default_branch": default_branch,
            "feature_branch": branch_result["feature_branch"],
            "feature_branch_head": branch_result.get("feature_branch_head"),
            "execution_graph_id": graph_id,
        },
    )

    return transition_visit(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
        summary=summary or f"Feature branch {branch_name} ready",
    )


def _minimal_execution_graph(snapshot: dict[str, Any], graph_id: str) -> dict[str, Any]:
    state = _snapshot_state(snapshot)
    return {
        "schema_version": "1.0.0",
        "graph_id": graph_id,
        "run_id": str(snapshot.get("run_id") or ""),
        "approved_ac_digest": state.get("approved_ac_digest"),
        "feature_branch": state.get("feature_branch"),
        "work_items": [
            {
                "id": "wi-001",
                "title": "Implement approved acceptance criteria",
                "owner": "feature-builder",
            }
        ],
    }


def _execute_brief_markdown(snapshot: dict[str, Any], graph_id: str) -> str:
    state = _snapshot_state(snapshot)
    ac = str(state.get("approved_ac") or "").strip()
    lines = [
        "# Execute brief",
        "",
        f"**Execution graph:** `{graph_id}`",
        "",
        "## Scope",
        "",
        "Host-generated phase brief from sealed shape plan.",
        "",
        "## Acceptance criteria",
        "",
        ac or "(none recorded)",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def seal_plan_blocked_receipt(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    *,
    result: dict[str, Any],
    run_dir: Path,
    foundry_bundle: Path,
) -> dict[str, Any]:
    visit_id = str(visit["id"])
    blockers = result.get("blockers") or []
    agent_draft = {
        "schema_version": "2.2.0",
        "agent": {"name": PLANNER_AGENT_NAME, "mode": "plan"},
        "status": "completed",
        "recommended_next_state": EXECUTE_PLAN_NODE,
        "outputs": {
            "summary_markdown": str(result.get("summary") or "BLOCKED"),
            "blockers": list(blockers) if isinstance(blockers, list) else [],
        },
    }
    if isinstance(blockers, list) and blockers:
        agent_draft["blockers"] = [str(b) for b in blockers if str(b).strip()]
    draft_path = run_dir / "receipts" / "agent.json"
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(json.dumps(agent_draft, indent=2) + "\n", encoding="utf-8")
    return _seal_receipt_file(
        draft=agent_draft,
        schema_ref=AGENT_RECEIPT_SCHEMA,
        snapshot=snapshot,
        visit=visit,
        run_dir=run_dir,
        visit_id=visit_id,
        foundry_bundle=foundry_bundle,
    )


def run_execute_plan_complete(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
    summary: str | None = None,
) -> dict[str, Any]:
    node_id = str(visit.get("node_id", ""))
    if node_id != EXECUTE_PLAN_NODE:
        return {"ok": False, "code": "WRONG_NODE", "message": f"expected execute.plan, got {node_id!r}"}

    visit_id = str(visit["id"])
    result = _accepted_agent_result(snapshot, visit_id, EXECUTE_PLAN_TASK_ID)
    if result is None:
        return {
            "ok": False,
            "code": "JUDGMENT_MISSING",
            "message": "No accepted plan result for this visit",
        }
    if result.get("verdict") != "PROCEED":
        return {
            "ok": False,
            "code": "PLAN_BLOCKED",
            "message": "Plan judgment is BLOCKED; resolve blockers and submit again",
        }

    graph = result.get("execution_graph")
    if not isinstance(graph, dict):
        return {
            "ok": False,
            "code": "ARTIFACT_INCOMPLETE",
            "message": "execution_graph object is required to complete",
        }
    brief_md = str(result.get("execute_brief_markdown") or "").strip()
    if not brief_md:
        return {
            "ok": False,
            "code": "ARTIFACT_INCOMPLETE",
            "message": "execute_brief_markdown is required to complete",
        }

    state = _snapshot_state(snapshot)
    graph_id = str(graph.get("graph_id") or state.get("execution_graph_id") or f"{_run_slug(snapshot)}:execution-graph")
    graph_publish = _publish_document_artifact(
        snapshot=snapshot,
        visit=visit,
        flow=flow,
        run_dir=run_dir,
        visit_id=visit_id,
        artifact_id="execution-graph",
        content=json.dumps(graph, indent=2) + "\n",
        foundry_bundle=foundry_bundle,
    )
    if not graph_publish.get("ok"):
        return graph_publish

    brief_publish = _publish_document_artifact(
        snapshot=snapshot,
        visit=visit,
        flow=flow,
        run_dir=run_dir,
        visit_id=visit_id,
        artifact_id="execute-brief",
        content=brief_md if brief_md.endswith("\n") else brief_md + "\n",
        foundry_bundle=foundry_bundle,
    )
    if not brief_publish.get("ok"):
        return brief_publish

    brief_uri = f"run:artifacts/{visit_id}/execute-brief.md"
    patch_allowed(
        snapshot,
        get_node(flow, node_id),
        node_id,
        {
            "execution_graph_id": graph_id,
            "execute_brief_path": brief_uri,
        },
    )

    agent_draft = {
        "schema_version": "2.2.0",
        "agent": {"name": PLANNER_AGENT_NAME, "mode": "plan"},
        "status": "completed",
        "recommended_next_state": "execute.build",
        "outputs": {
            "summary_markdown": str(result.get("summary") or "PROCEED: execution graph and brief published."),
            "execution_graph_id": graph_id,
            "artifacts": [
                str(graph_publish.get("uri") or ""),
                brief_uri,
            ],
        },
    }
    draft_path = run_dir / "receipts" / "agent.json"
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(json.dumps(agent_draft, indent=2) + "\n", encoding="utf-8")
    seal_result = _seal_receipt_file(
        draft=agent_draft,
        schema_ref=AGENT_RECEIPT_SCHEMA,
        snapshot=snapshot,
        visit=visit,
        run_dir=run_dir,
        visit_id=visit_id,
        foundry_bundle=foundry_bundle,
    )
    if not seal_result.get("ok"):
        return seal_result

    return transition_visit(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
        summary=summary or "Execute plan recorded",
    )


def _execute_use_stub_commands() -> bool:
    """Return True when FOUNDRY_EXECUTE_STUB is set (test/CI opt-in only).

    Product runs use manifest commands from the app profile; shaped-work enforcement
    belongs at verify acceptance, not execute build/test stubs.
    """
    flag = (os.environ.get("FOUNDRY_EXECUTE_STUB") or "").strip().lower()
    return flag in {"1", "true", "yes"}


def _stub_exit_code(step: str, default: int = 0) -> int:
    key = f"FOUNDRY_EXECUTE_{step.upper()}_EXIT_CODE"
    raw = os.environ.get(key)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        return default


def _repair_loop_count(snapshot: dict[str, Any]) -> int:
    return count_events(snapshot, "connection.taken", loop="repair")


def _verification_policy(snapshot: dict[str, Any]) -> str:
    return "post_repair" if _repair_loop_count(snapshot) > 0 else "implementation"


def _manifest_commands(workspace: Path) -> dict[str, Any]:
    try:
        _, manifest = load_manifest(workspace)
    except (FileNotFoundError, ValueError):
        return {}
    commands = manifest.get("commands")
    return commands if isinstance(commands, dict) else {}


def _verification_command_names(workspace: Path, snapshot: dict[str, Any]) -> list[str]:
    try:
        _, manifest = load_manifest(workspace)
    except (FileNotFoundError, ValueError):
        return ["test"]
    verification = manifest.get("verification")
    if not isinstance(verification, dict):
        return ["test"]
    policy = _verification_policy(snapshot)
    names = verification.get(policy) or verification.get("implementation") or ["test"]
    if not isinstance(names, list):
        return ["test"]
    return [str(name) for name in names if name]


def _run_argv_command(workspace: Path, argv: list[str], *, label: str) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            argv,
            cwd=workspace,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return {
            "command": label,
            "exit_code": 1,
            "stderr": str(exc),
        }
    return {
        "command": label,
        "exit_code": int(completed.returncode),
        "stdout": (completed.stdout or "")[:4000],
        "stderr": (completed.stderr or "")[:4000],
    }


def _run_named_manifest_command(workspace: Path, commands: dict[str, Any], name: str) -> dict[str, Any]:
    entry = commands.get(name)
    if not isinstance(entry, dict):
        return {"command": name, "exit_code": 1, "stderr": "command not defined in app manifest"}
    variant = entry.get("default") if isinstance(entry.get("default"), dict) else entry
    if not isinstance(variant, dict):
        return {"command": name, "exit_code": 1, "stderr": "invalid command definition"}
    argv = variant.get("argv")
    if not isinstance(argv, list) or not argv:
        return {"command": name, "exit_code": 1, "stderr": "command argv missing"}
    argv_str = [str(part) for part in argv]
    cwd_rel = variant.get("cwd")
    cwd = workspace
    if isinstance(cwd_rel, str) and cwd_rel.strip() and cwd_rel.strip() != ".":
        cwd = (workspace / cwd_rel).resolve()
    return _run_argv_command(cwd, argv_str, label=name)


def _commands_for_build(workspace: Path) -> list[dict[str, Any]]:
    if _execute_use_stub_commands():
        exit_code = _stub_exit_code("build")
        return [{"command": "foundry-stub:build", "exit_code": exit_code}]
    commands = _manifest_commands(workspace)
    if "build" in commands:
        return [_run_named_manifest_command(workspace, commands, "build")]
    return [{"command": "foundry-stub:build", "exit_code": 0}]


def _commands_for_test(workspace: Path, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    if _execute_use_stub_commands():
        exit_code = _stub_exit_code("test")
        return [{"command": "foundry-stub:test", "exit_code": exit_code}]
    commands = _manifest_commands(workspace)
    results: list[dict[str, Any]] = []
    for name in _verification_command_names(workspace, snapshot):
        results.append(_run_named_manifest_command(workspace, commands, name))
    return results or [{"command": "foundry-stub:test", "exit_code": 1, "stderr": "no verification commands"}]


def _receipt_status_from_commands(commands: list[dict[str, Any]]) -> str:
    if any(isinstance(item, dict) and item.get("exit_code", 0) != 0 for item in commands):
        return "failed"
    return "completed"


def _seal_execute_agent_receipt(
    *,
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    run_dir: Path,
    foundry_bundle: Path,
    visit_id: str,
    agent_name: str,
    agent_mode: str,
    commands: list[dict[str, Any]],
    recommended_next_state: str,
    summary_markdown: str,
    extra_outputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = _receipt_status_from_commands(commands)
    outputs: dict[str, Any] = {
        "summary_markdown": summary_markdown,
        "commands": commands,
    }
    if extra_outputs:
        outputs.update(extra_outputs)
    agent_draft = {
        "schema_version": "2.2.0",
        "agent": {"name": agent_name, "mode": agent_mode},
        "status": status,
        "recommended_next_state": recommended_next_state,
        "outputs": outputs,
        "commands": commands,
    }
    receipts_dir = run_dir / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    draft_path = receipts_dir / "agent.json"
    draft_path.write_text(json.dumps(agent_draft, indent=2) + "\n", encoding="utf-8")
    return _seal_receipt_file(
        draft=agent_draft,
        schema_ref=AGENT_RECEIPT_SCHEMA,
        snapshot=snapshot,
        visit=visit,
        run_dir=run_dir,
        visit_id=visit_id,
        foundry_bundle=foundry_bundle,
    )


def run_execute_build_complete(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
    summary: str | None = None,
) -> dict[str, Any]:
    node_id = str(visit.get("node_id", ""))
    if node_id != EXECUTE_BUILD_NODE:
        return {"ok": False, "code": "WRONG_NODE", "message": f"expected execute.build, got {node_id!r}"}

    visit_id = str(visit["id"])
    commands = _commands_for_build(workspace)
    seal_result = _seal_execute_agent_receipt(
        snapshot=snapshot,
        visit=visit,
        run_dir=run_dir,
        foundry_bundle=foundry_bundle,
        visit_id=visit_id,
        agent_name=FEATURE_BUILDER_AGENT_NAME,
        agent_mode="engine",
        commands=commands,
        recommended_next_state=EXECUTE_TEST_NODE,
        summary_markdown="PROCEED: host build step recorded.",
        extra_outputs={"execution_graph_id": _snapshot_state(snapshot).get("execution_graph_id")},
    )
    if not seal_result.get("ok"):
        return seal_result

    patch_allowed(
        snapshot,
        get_node(flow, node_id),
        node_id,
        {"last_build_exit_code": commands[-1].get("exit_code") if commands else None},
    )

    return transition_visit(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
        summary=summary or "Execute build recorded",
    )


def run_execute_test_complete(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
    summary: str | None = None,
) -> dict[str, Any]:
    node_id = str(visit.get("node_id", ""))
    if node_id != EXECUTE_TEST_NODE:
        return {"ok": False, "code": "WRONG_NODE", "message": f"expected execute.test, got {node_id!r}"}

    visit_id = str(visit["id"])
    commands = _commands_for_test(workspace, snapshot)
    seal_result = _seal_execute_agent_receipt(
        snapshot=snapshot,
        visit=visit,
        run_dir=run_dir,
        foundry_bundle=foundry_bundle,
        visit_id=visit_id,
        agent_name=REPAIRER_AGENT_NAME,
        agent_mode="repair",
        commands=commands,
        recommended_next_state="execute.test.gate",
        summary_markdown="PROCEED: host verification commands recorded.",
        extra_outputs={"verification_policy": _verification_policy(snapshot)},
    )
    if not seal_result.get("ok"):
        return seal_result

    patch_allowed(
        snapshot,
        get_node(flow, node_id),
        node_id,
        {
            "last_test_exit_code": commands[-1].get("exit_code") if commands else None,
            "repair_loop_count": _repair_loop_count(snapshot),
        },
    )

    return transition_visit(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
        summary=summary or "Execute test recorded",
    )


def _publish_git_commit_artifact(
    *,
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    run_dir: Path,
    visit_id: str,
    commit_sha: str,
) -> dict[str, Any]:
    node = get_node(flow, str(visit["node_id"]))
    artifact_decl = find_artifact_declaration(node, "final-commit")
    if artifact_decl is None:
        return {
            "ok": False,
            "code": "ARTIFACT_NOT_DECLARED",
            "message": "final-commit artifact not declared on execute.commit",
        }
    ref_uri = f"git:commit/{commit_sha}"
    append_event(
        snapshot,
        event_type=EVENT_ARTIFACT_LINKED,
        visit_id=visit_id,
        node_id=str(visit["node_id"]),
        payload={
            "artifact_id": "final-commit",
            "uri": ref_uri,
            "scheme": str(artifact_decl.get("scheme") or "git_commit"),
            "kind": "reference",
        },
    )
    return {"ok": True, "uri": ref_uri}


def _execute_commit_message(snapshot: dict[str, Any]) -> str:
    state = _snapshot_state(snapshot)
    existing = state.get("execute_commit_message")
    if isinstance(existing, str) and existing.strip():
        return existing.strip()
    slug = _run_slug(snapshot)
    return f"foundry: finalize execute for {slug}"


def _record_execute_commit(
    workspace: Path,
    snapshot: dict[str, Any],
    *,
    branch_name: str | None,
    message: str,
) -> dict[str, Any]:
    if _execute_use_stub_commands():
        exit_code = _stub_exit_code("commit")
        if exit_code != 0:
            return {
                "ok": False,
                "code": "COMMIT_FAILED",
                "message": f"Stub commit exit code {exit_code}",
                "command": "foundry-stub:commit",
                "exit_code": exit_code,
            }
        if branch_name:
            checkout = _git_run(workspace, "checkout", branch_name)
            if checkout.returncode != 0:
                return {
                    "ok": False,
                    "code": "BRANCH_CHECKOUT_FAILED",
                    "message": checkout.stderr.strip() or "checkout failed",
                }
        commit = _git_run(workspace, "commit", "--allow-empty", "-m", message)
        if commit.returncode != 0:
            return {
                "ok": False,
                "code": "COMMIT_FAILED",
                "message": commit.stderr.strip() or commit.stdout.strip() or "commit failed",
                "command": "git commit",
                "exit_code": commit.returncode,
            }
        sha = _git_head_sha(workspace)
        if not sha:
            return {"ok": False, "code": "COMMIT_FAILED", "message": "Could not read HEAD after commit"}
        return {
            "ok": True,
            "final_commit_sha": sha,
            "command": "git commit --allow-empty",
            "exit_code": 0,
        }

    if branch_name:
        checkout = _git_run(workspace, "checkout", branch_name)
        if checkout.returncode != 0:
            return {
                "ok": False,
                "code": "BRANCH_CHECKOUT_FAILED",
                "message": checkout.stderr.strip() or "checkout failed",
            }
    status = _git_run(workspace, "status", "--porcelain")
    if status.returncode != 0:
        return {"ok": False, "code": "COMMIT_FAILED", "message": "git status failed"}
    if status.stdout.strip():
        _git_run(workspace, "add", "-A")
    commit = _git_run(workspace, "commit", "--allow-empty", "-m", message)
    if commit.returncode != 0:
        return {
            "ok": False,
            "code": "COMMIT_FAILED",
            "message": commit.stderr.strip() or "commit failed",
            "exit_code": commit.returncode,
        }
    sha = _git_head_sha(workspace)
    if not sha:
        return {"ok": False, "code": "COMMIT_FAILED", "message": "Could not read HEAD after commit"}
    return {"ok": True, "final_commit_sha": sha, "command": "git commit", "exit_code": 0}


def run_execute_commit_complete(
    snapshot: dict[str, Any],
    visit: dict[str, Any],
    flow: dict[str, Any],
    *,
    workspace: Path,
    foundry_bundle: Path,
    run_dir: Path,
    summary: str | None = None,
) -> dict[str, Any]:
    node_id = str(visit.get("node_id", ""))
    if node_id != EXECUTE_COMMIT_NODE:
        return {"ok": False, "code": "WRONG_NODE", "message": f"expected execute.commit, got {node_id!r}"}

    visit_id = str(visit["id"])
    state = _snapshot_state(snapshot)
    branch = state.get("feature_branch")
    branch_name = branch.strip() if isinstance(branch, str) and branch.strip() else None
    message = _execute_commit_message(snapshot)
    commit_result = _record_execute_commit(workspace, snapshot, branch_name=branch_name, message=message)
    if not commit_result.get("ok"):
        return commit_result

    sha = str(commit_result["final_commit_sha"])
    publish = _publish_git_commit_artifact(
        snapshot=snapshot,
        visit=visit,
        flow=flow,
        run_dir=run_dir,
        visit_id=visit_id,
        commit_sha=sha,
    )
    if not publish.get("ok"):
        return publish

    patch_allowed(
        snapshot,
        get_node(flow, node_id),
        node_id,
        {
            "final_commit_sha": sha,
            "execute_commit_message": message,
        },
    )

    agent_draft = {
        "schema_version": "2.2.0",
        "agent": {"name": COMMIT_AGENT_NAME, "mode": "execute"},
        "status": "completed",
        "recommended_next_state": "execute.commit.gate",
        "outputs": {
            "summary_markdown": "PROCEED: final commit recorded (host).",
            "final_commit_sha": sha,
            "execute_commit_message": message,
            "artifacts": [publish.get("uri")],
        },
    }
    receipts_dir = run_dir / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    draft_path = receipts_dir / "agent.json"
    draft_path.write_text(json.dumps(agent_draft, indent=2) + "\n", encoding="utf-8")
    seal_result = _seal_receipt_file(
        draft=agent_draft,
        schema_ref=AGENT_RECEIPT_SCHEMA,
        snapshot=snapshot,
        visit=visit,
        run_dir=run_dir,
        visit_id=visit_id,
        foundry_bundle=foundry_bundle,
    )
    if not seal_result.get("ok"):
        return seal_result

    return transition_visit(
        snapshot,
        visit,
        flow,
        workspace=workspace,
        foundry_bundle=foundry_bundle,
        run_dir=run_dir,
        summary=summary or "Execute commit recorded",
    )
