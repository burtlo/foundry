"""Offline GitHub PR outcome observation for completed Foundry runs."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import foundry_store


class OutcomeError(Exception):
    def __init__(self, error_code: str, message: str, *, extra: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.extra = extra or {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def observe(
    state_path: Path,
    *,
    pr_url: str | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    resolved_url = pr_url or state.get("pr_url")
    if not isinstance(resolved_url, str) or not resolved_url:
        raise OutcomeError("MISSING_PR_URL", "Outcome observation requires a PR URL.")
    if state.get("pr_url") and resolved_url != state["pr_url"]:
        raise OutcomeError(
            "PR_URL_MISMATCH",
            "Observed PR URL does not match the completed run.",
            extra={"expected": state["pr_url"], "actual": resolved_url},
        )
    completed = runner(
        [
            "gh",
            "pr",
            "view",
            resolved_url,
            "--json",
            "url,state,mergedAt,closedAt,title,headRefName,headRefOid,statusCheckRollup,reviews",
        ],
        cwd=str(Path(state.get("app_folder") or state_path.parent)),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise OutcomeError(
            "GH_PR_OBSERVE_FAILED",
            completed.stderr.strip() or "gh pr view failed.",
        )
    remote = json.loads(completed.stdout)
    snapshot_digest = _digest(remote)
    outcomes_path = state_path.parent / "outcomes.jsonl"
    prior: list[dict[str, Any]] = []
    if outcomes_path.is_file():
        prior = [
            json.loads(line)
            for line in outcomes_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    for item in reversed(prior):
        if item.get("snapshot_digest") == snapshot_digest:
            return {**item, "idempotent": True, "path": str(outcomes_path)}
    checks = remote.get("statusCheckRollup") if isinstance(remote.get("statusCheckRollup"), list) else []
    failed_checks = [
        check.get("name") or check.get("context")
        for check in checks
        if str(check.get("conclusion") or check.get("state") or "").upper()
        not in ("SUCCESS", "NEUTRAL", "SKIPPED", "EXPECTED")
    ]
    outcome = {
        "schema_version": "1.0.0",
        "run_id": state.get("run_id"),
        "observed_at": _now_iso(),
        "pr_url": resolved_url,
        "state": remote.get("state"),
        "merged_at": remote.get("mergedAt"),
        "closed_at": remote.get("closedAt"),
        "head_sha": remote.get("headRefOid"),
        "checks_total": len(checks),
        "failed_checks": failed_checks,
        "review_count": len(remote.get("reviews") or []),
        "snapshot_digest": snapshot_digest,
    }
    foundry_store.append_jsonl(outcomes_path, outcome)
    learning_path = state_path.parent / "learning_record.json"
    if learning_path.is_file():
        learning = json.loads(learning_path.read_text(encoding="utf-8"))
        learning["observed_outcome"] = outcome
        foundry_store.atomic_write_text(
            state_path.parent / "learning_record.observed.json",
            json.dumps(learning, indent=2) + "\n",
        )
    return {**outcome, "idempotent": False, "path": str(outcomes_path)}
