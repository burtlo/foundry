"""Pre-PR review helpers for Foundry v2 Phase 8."""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Callable

CRITIC_AGENTS = {
    "bugbot": "bugbot",
    "security": "security-review",
    "security-review": "security-review",
}


class ReviewError(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.extra = extra or {}


def resolve_app_folder(app_folder: str) -> Path:
    root = Path(app_folder)
    if not root.is_dir():
        raise ReviewError("INVALID_APP_FOLDER", f"App folder does not exist: {app_folder}")
    return root


def review_critics(
    mode: str,
    *,
    selected: list[str] | None = None,
) -> dict[str, Any]:
    normalized = (mode or "both").strip().lower()
    if normalized == "ask":
        critics = [CRITIC_AGENTS.get(name, name) for name in (selected or [])]
        return {
            "mode": "ask",
            "critics": critics,
            "sequential": len(critics) > 1,
            "requires_human_selection": not critics,
        }
    if normalized == "both":
        return {
            "mode": "both",
            "critics": ["bugbot", "security-review"],
            "sequential": True,
            "requires_human_selection": False,
        }
    if normalized == "bugbot":
        return {
            "mode": "bugbot",
            "critics": ["bugbot"],
            "sequential": False,
            "requires_human_selection": False,
        }
    if normalized == "security":
        return {
            "mode": "security",
            "critics": ["security-review"],
            "sequential": False,
            "requires_human_selection": False,
        }
    raise ReviewError(
        "INVALID_REVIEW_MODE",
        f"Unsupported review mode: {mode!r}.",
        extra={"allowed": ["both", "bugbot", "security", "ask"]},
    )


def git_command(
    app_folder: Path,
    args: list[str],
    *,
    runner: Callable[..., Any] | None = None,
) -> str:
    command = ["git", "-C", str(app_folder), *args]
    if runner is not None:
        result = runner(command, app_folder)
        return result.stdout or ""
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise ReviewError(
            "GIT_COMMAND_FAILED",
            (completed.stderr or completed.stdout or "git command failed").strip(),
            extra={"exitCode": completed.returncode, "command": command},
        )
    return completed.stdout or ""


def git_changed_files(
    app_folder: Path,
    since: str,
    *,
    runner: Callable[..., Any] | None = None,
) -> list[str]:
    output = git_command(app_folder, ["diff", "--name-only", f"{since}..HEAD"], runner=runner)
    return [line.strip() for line in output.splitlines() if line.strip()]


def git_numstat(
    app_folder: Path,
    since: str,
    *,
    runner: Callable[..., Any] | None = None,
) -> tuple[int, int]:
    output = git_command(app_folder, ["diff", "--numstat", f"{since}..HEAD"], runner=runner)
    insertions = 0
    deletions = 0
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        if parts[0] == "-" and parts[1] == "-":
            continue
        insertions += int(parts[0])
        deletions += int(parts[1])
    return insertions, deletions


def extension_counts(changed_files: list[str]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for path in changed_files:
        suffix = Path(path).suffix.lower() or "(no_ext)"
        counts[suffix] += 1
    return dict(sorted(counts.items()))


def review_bundle(
    app_folder: str,
    since: str,
    *,
    git_runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    root = resolve_app_folder(app_folder)
    if not since:
        raise ReviewError("MISSING_SINCE", "Branch point (--since) is required for review bundle.")
    changed_files = git_changed_files(root, since, runner=git_runner)
    insertions, deletions = git_numstat(root, since, runner=git_runner)
    workflow_files = [path for path in changed_files if path.replace("\\", "/").startswith(".github/workflows/")]
    return {
        "app_folder": str(root),
        "since": since,
        "changed_files": changed_files,
        "file_count": len(changed_files),
        "extensions": extension_counts(changed_files),
        "insertions": insertions,
        "deletions": deletions,
        "workflow_files": workflow_files,
        "subagent_launch": {
            "full_repository_path": str(root.resolve()),
            "diff": "branch changes",
        },
    }


def load_receipt(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewError("INVALID_RECEIPT", f"Could not read receipt at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ReviewError("INVALID_RECEIPT", "Receipt file must contain a JSON object.")
    return data


def _receipt_agent_name(receipt: dict[str, Any]) -> str | None:
    agent = receipt.get("agent") if isinstance(receipt.get("agent"), dict) else {}
    name = agent.get("name")
    return str(name) if isinstance(name, str) else None


def _provenance(receipt: dict[str, Any]) -> dict[str, Any]:
    value = receipt.get("provenance")
    return value if isinstance(value, dict) else {}


def _result_item(
    *,
    agent: str,
    receipt_id: Any = None,
    status: Any = None,
    issues: list[str],
    error_code: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "agent": agent,
        "receipt_id": receipt_id,
        "status": status,
        "valid": not issues,
        "issues": issues,
    }
    if error_code:
        payload["error_code"] = error_code
    return payload


def validate_critic_receipt(
    receipt: dict[str, Any],
    expected_agent: str,
    *,
    expected_run_id: str | None = None,
    expected_step_id: str | None = None,
    expected_head_sha: str | None = None,
    expected_branch_point: str | None = None,
    expected_launch_id: str | None = None,
    require_launch_id: bool = False,
) -> dict[str, Any]:
    agent_name = _receipt_agent_name(receipt)
    provenance = _provenance(receipt)
    provenance_agent = provenance.get("agent")
    receipt_id = receipt.get("receipt_id")
    status = receipt.get("status")
    issues: list[str] = []
    error_code: str | None = None

    def fail(code: str, issue: str) -> None:
        nonlocal error_code
        issues.append(issue)
        if error_code is None:
            error_code = code

    if not receipt_id:
        fail("INVALID_RECEIPT", "missing receipt_id")
    if agent_name != expected_agent or (
        provenance_agent is not None and provenance_agent != expected_agent
    ):
        fail(
            "CRITIC_RECEIPT_WRONG_AGENT",
            f"expected agent.name {expected_agent!r}, got {agent_name!r}",
        )
    if status == "partial" or status != "completed":
        fail("CRITIC_RECEIPT_PARTIAL", f"unexpected status {status!r}")
    if expected_run_id is not None and receipt.get("run_id") != expected_run_id:
        fail(
            "RECEIPT_RUN_MISMATCH",
            f"receipt.run_id {receipt.get('run_id')!r} != {expected_run_id!r}",
        )
    launch_id = provenance.get("launch_id")
    if require_launch_id and not launch_id:
        fail("CRITIC_LAUNCH_REQUIRED", "provenance.launch_id is required")
    elif expected_launch_id is not None and launch_id != expected_launch_id:
        fail(
            "RECEIPT_PROVENANCE_INVALID",
            f"provenance.launch_id {launch_id!r} != {expected_launch_id!r}",
        )
    if expected_step_id is not None and provenance.get("step_id") != expected_step_id:
        fail(
            "RECEIPT_PROVENANCE_INVALID",
            f"provenance.step_id {provenance.get('step_id')!r} != {expected_step_id!r}",
        )
    if expected_branch_point is not None and provenance.get("branch_point") != expected_branch_point:
        fail(
            "RECEIPT_PROVENANCE_INVALID",
            (
                f"provenance.branch_point {provenance.get('branch_point')!r} "
                f"!= {expected_branch_point!r}"
            ),
        )
    if expected_head_sha is not None and provenance.get("reviewed_head_sha") != expected_head_sha:
        fail(
            "CRITIC_RECEIPT_STALE_HEAD",
            (
                f"provenance.reviewed_head_sha {provenance.get('reviewed_head_sha')!r} "
                f"!= {expected_head_sha!r}"
            ),
        )
    return _result_item(
        agent=expected_agent,
        receipt_id=receipt_id,
        status=status,
        issues=issues,
        error_code=error_code,
    )


def review_validate_receipts(
    receipts_dir: str,
    critics: list[str],
    *,
    receipt_paths: list[str] | None = None,
    expected_run_id: str | None = None,
    expected_step_id: str | None = None,
    expected_head_sha: str | None = None,
    expected_branch_point: str | None = None,
    require_launch_ids: dict[str, str] | None = None,
) -> dict[str, Any]:
    if not critics:
        raise ReviewError("MISSING_CRITICS", "At least one critic agent is required.")
    resolved_critics = [CRITIC_AGENTS.get(name, name) for name in critics]
    directory = Path(receipts_dir)
    if not directory.is_dir():
        raise ReviewError("INVALID_RECEIPTS_DIR", f"Receipts directory not found: {receipts_dir}")

    explicit_paths = bool(receipt_paths)
    if receipt_paths:
        paths = [Path(path) if Path(path).is_absolute() else directory / path for path in receipt_paths]
    else:
        paths = sorted(directory.glob("*.json"))

    receipts = [load_receipt(path) for path in paths]
    results: list[dict[str, Any]] = []
    critic_counts = Counter(resolved_critics)

    def binding_kwargs(agent: str) -> dict[str, Any]:
        expected_launch = None
        require_launch = False
        if require_launch_ids is not None:
            if agent in require_launch_ids:
                expected_launch = require_launch_ids[agent]
                require_launch = True
            elif require_launch_ids:
                require_launch = True
        return {
            "expected_run_id": expected_run_id,
            "expected_step_id": expected_step_id,
            "expected_head_sha": expected_head_sha,
            "expected_branch_point": expected_branch_point,
            "expected_launch_id": expected_launch,
            "require_launch_id": require_launch,
        }

    if explicit_paths:
        seen: dict[str, int] = {}
        for index, agent in enumerate(resolved_critics):
            if critic_counts[agent] > 1 and seen.get(agent, 0) == 0:
                seen[agent] = 1
                results.append(
                    _result_item(
                        agent=agent,
                        issues=["multiple receipts for critic"],
                        error_code="CRITIC_RECEIPT_DUPLICATE",
                    )
                )
                continue
            if critic_counts[agent] > 1:
                continue
            if index >= len(receipts):
                results.append(
                    _result_item(
                        agent=agent,
                        issues=["missing receipt"],
                        error_code="CRITIC_RECEIPT_MISSING",
                    )
                )
                continue
            results.append(
                validate_critic_receipt(
                    receipts[index],
                    agent,
                    **binding_kwargs(agent),
                )
            )
    else:
        by_agent: dict[str, list[dict[str, Any]]] = {agent: [] for agent in resolved_critics}
        for receipt in receipts:
            agent = _receipt_agent_name(receipt)
            if agent in by_agent:
                by_agent[agent].append(receipt)
        for agent in resolved_critics:
            matches = by_agent.get(agent) or []
            if not matches:
                results.append(
                    _result_item(
                        agent=agent,
                        issues=["missing receipt"],
                        error_code="CRITIC_RECEIPT_MISSING",
                    )
                )
                continue
            if len(matches) > 1:
                results.append(
                    _result_item(
                        agent=agent,
                        issues=["multiple receipts for critic"],
                        error_code="CRITIC_RECEIPT_DUPLICATE",
                    )
                )
                continue
            results.append(
                validate_critic_receipt(
                    matches[0],
                    agent,
                    **binding_kwargs(agent),
                )
            )

    return {
        "receipts_dir": str(directory),
        "critics": resolved_critics,
        "results": results,
        "valid": all(item["valid"] for item in results),
        "receipt_ids": [item["receipt_id"] for item in results if item.get("receipt_id")],
    }


def assert_critic_receipts_valid(
    receipts_dir: str,
    critics: list[str],
    **kwargs: Any,
) -> dict[str, Any]:
    directory = Path(receipts_dir)
    if not directory.is_dir():
        results = [
            _result_item(
                agent=CRITIC_AGENTS.get(name, name),
                issues=["missing receipt"],
                error_code="CRITIC_RECEIPT_MISSING",
            )
            for name in critics
        ]
        raise ReviewError(
            "CRITIC_RECEIPTS_INVALID",
            "Critic receipts are missing or invalid.",
            extra={"results": results},
        )
    payload = review_validate_receipts(receipts_dir, critics, **kwargs)
    if not payload.get("valid"):
        raise ReviewError(
            "CRITIC_RECEIPTS_INVALID",
            "Critic receipts are missing or invalid.",
            extra={"results": payload.get("results") or []},
        )
    return payload
