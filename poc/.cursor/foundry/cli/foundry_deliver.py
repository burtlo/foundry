"""Phase 9 delivery helpers: scope comments, PR title, and run completion."""

from __future__ import annotations

from typing import Any

SCOPE_COMMENT_STEP = "deliver.scope_comment"
SHIP_STEP = "deliver.ship"


class DeliverError(Exception):
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


def require_scope_comment_step(state: dict[str, Any]) -> None:
    if state.get("run_mode") != "implementation":
        raise DeliverError(
            "JIRA_COMMENT_FORBIDDEN",
            "Jira comments are only allowed in implementation runs.",
        )
    current = state.get("current_step")
    if current != SCOPE_COMMENT_STEP:
        raise DeliverError(
            "JIRA_COMMENT_WRONG_STEP",
            f"Jira comments are only allowed at {SCOPE_COMMENT_STEP!r}, not {current!r}.",
            extra={"current_step": current, "allowed_step": SCOPE_COMMENT_STEP},
        )


def scope_comment_skip_reason(state: dict[str, Any], config: dict[str, Any]) -> str | None:
    register = state.get("pr_extras_register")
    if not isinstance(register, list) or not register:
        return "pr_extras_register is empty"
    if not state.get("issue_key"):
        return "issue_key is null"
    jira = config.get("jira") or {}
    if not jira.get("enabled"):
        return "jira.enabled is false"
    scope_comments = jira.get("scope_comments")
    if isinstance(scope_comments, dict) and scope_comments.get("enabled") is False:
        return "jira.scope_comments.enabled is false"
    return None


def scope_comment_should_skip(state: dict[str, Any], config: dict[str, Any]) -> bool:
    return scope_comment_skip_reason(state, config) is not None


def extras_table_rows(register: list[Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for entry in register:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or "").strip()
        reason = str(entry.get("reason") or "").strip()
        step_id = str(entry.get("step_id") or "").strip()
        if not path:
            continue
        rows.append({"path": path, "purpose": reason, "notes": step_id})
    return rows


def render_extras_table(rows: list[dict[str, str]]) -> str:
    lines = [
        "| File / area | Purpose | Notes |",
        "|-------------|---------|-------|",
    ]
    for row in rows:
        notes = row["notes"] or "—"
        lines.append(f"| `{row['path']}` | {row['purpose']} | {notes} |")
    return "\n".join(lines)


def draft_scope_comment(
    state: dict[str, Any],
    config: dict[str, Any],
    *,
    in_scope_summary: str | None = None,
) -> dict[str, Any]:
    require_scope_comment_step(state)
    skip_reason = scope_comment_skip_reason(state, config)
    if skip_reason:
        return {
            "skip": True,
            "reason": skip_reason,
            "markdown": "",
            "table": "",
            "table_rows": [],
            "issue_key": state.get("issue_key"),
        }

    register = state.get("pr_extras_register") or []
    rows = extras_table_rows(register)
    issue_key = str(state["issue_key"])
    branch = state.get("feature_branch") or "(branch not set)"
    developer = (
        state.get("developer_first_name")
        or (config.get("org") or {}).get("display_name")
        or "the engineer"
    )
    in_scope = in_scope_summary or "See ticket acceptance criteria."
    table = render_extras_table(rows)

    markdown = (
        "## PR includes work not called out in this ticket\n\n"
        f"**Ticket:** {issue_key}\n"
        f"**Branch:** {branch}\n"
        "**PR:** Pending — commit/PR will follow this comment\n\n"
        "The upcoming PR includes the following changes that were **not** in the "
        "ticket description or acceptance criteria:\n\n"
        f"{table}\n\n"
        f"**In scope for this ticket (also in PR):** {in_scope}\n\n"
        "These additions are intentional (org Foundry / team policy). "
        "Reviewers: please treat the table above as scope documentation, not scope "
        "creep to revert without discussion.\n\n"
        f"— Posted via Foundry on behalf of {developer}\n"
    )
    return {
        "skip": False,
        "reason": None,
        "markdown": markdown,
        "table": table,
        "table_rows": rows,
        "issue_key": issue_key,
        "step_id": SCOPE_COMMENT_STEP,
    }


def jira_format_comment(
    state: dict[str, Any],
    config: dict[str, Any],
    body: str,
) -> dict[str, Any]:
    require_scope_comment_step(state)
    skip_reason = scope_comment_skip_reason(state, config)
    if skip_reason:
        raise DeliverError(
            "SCOPE_COMMENT_SKIP",
            f"Scope comment should be skipped: {skip_reason}",
            extra={"reason": skip_reason},
        )

    issue_key = state.get("issue_key")
    if not issue_key:
        raise DeliverError(
            "MISSING_ISSUE_KEY",
            "issue_key is required for Jira comment.",
            required_input="issueKey",
        )

    jira = config.get("jira") or {}
    cloud_id = jira.get("cloud_id")
    if not cloud_id:
        raise DeliverError(
            "MISSING_CLOUD_ID",
            "jira.cloud_id is required in the resolved team profile.",
            required_input="cloudId",
        )

    comment_body = body.strip()
    if not comment_body:
        raise DeliverError(
            "MISSING_COMMENT_BODY",
            "Comment body is required.",
            required_input="body",
        )

    return {
        "mcp_tool": "addCommentToJiraIssue",
        "mcp_namespace": "plugin-atlassian-atlassian",
        "arguments": {
            "cloudId": cloud_id,
            "issueIdOrKey": issue_key,
            "commentBody": comment_body,
            "contentFormat": "markdown",
        },
        "issue_key": issue_key,
        "allowed_step": SCOPE_COMMENT_STEP,
    }


def pr_title_pattern(config: dict[str, Any]) -> str | None:
    git = config.get("git") or {}
    pattern = git.get("pr_title_pattern")
    return str(pattern) if pattern else None


def validate_run_complete(
    state: dict[str, Any],
    *,
    pr_url: str,
    resolved_pr_title: str | None = None,
) -> dict[str, Any]:
    if state.get("run_mode") != "implementation":
        raise DeliverError(
            "INVALID_RUN_MODE",
            "run complete with a PR URL is only valid for implementation runs.",
        )
    current = state.get("current_step")
    if current != SHIP_STEP:
        raise DeliverError(
            "INVALID_STEP",
            f"Run can only complete from {SHIP_STEP!r}.",
            extra={"current_step": current, "required_step": SHIP_STEP},
        )

    ship = ((state.get("steps") or {}).get(SHIP_STEP)) or {}
    if ship.get("gate_decision") != "approve":
        raise DeliverError(
            "GATE_UNRESOLVED",
            f"{SHIP_STEP} requires gate_decision=approve before run completion.",
            extra={"gate_decision": ship.get("gate_decision")},
        )

    url = pr_url.strip()
    if not url.startswith("http"):
        raise DeliverError(
            "INVALID_PR_URL",
            "PR URL must be an http(s) URL.",
            required_input="prUrl",
        )

    title = resolved_pr_title or state.get("resolved_pr_title")
    if not title:
        raise DeliverError(
            "MISSING_PR_TITLE",
            "resolved_pr_title must be set before run completion.",
            required_input="resolvedPrTitle",
        )

    return {
        "pr_url": url,
        "resolved_pr_title": title,
        "current_step": current,
    }
