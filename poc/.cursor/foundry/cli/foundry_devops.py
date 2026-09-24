"""Deterministic DevOps workflow helpers for Foundry v2 Phase 8."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

SHA_RE = re.compile(r"^[a-f0-9]{40}$", re.IGNORECASE)
USES_LINE_RE = re.compile(
    r"^(?P<indent>\s*)(?:-\s+)?uses:\s*(?P<value>.+?)\s*(?:#\s*(?P<comment>.*))?\s*$"
)
ACTION_REF_RE = re.compile(
    r"^(?P<owner>[^/]+)/(?P<repo>[^@]+)@(?P<ref>.+)$",
    re.IGNORECASE,
)
DEFAULT_EXCLUDE_OWNERS = ("actions", "github")
MUTABLE_REF_RE = re.compile(r"^(v\d|latest|main|master|HEAD)$", re.IGNORECASE)


class DevOpsError(Exception):
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
        raise DevOpsError("INVALID_APP_FOLDER", f"App folder does not exist: {app_folder}")
    return root


def workflow_files(app_folder: Path) -> list[Path]:
    workflows_dir = app_folder / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return []
    files: list[Path] = []
    for pattern in ("*.yml", "*.yaml"):
        files.extend(sorted(workflows_dir.rglob(pattern)))
    return files


def normalize_uses_value(raw: str) -> tuple[str, str | None]:
    value = raw.strip()
    comment: str | None = None
    if "#" in value and not value.startswith('"') and not value.startswith("'"):
        value, _, inline = value.partition("#")
        value = value.strip()
        comment = inline.strip() or None
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]
    return value, comment


def classify_action(
    uses_value: str,
    *,
    exclude_owners: tuple[str, ...] = DEFAULT_EXCLUDE_OWNERS,
) -> dict[str, Any]:
    if uses_value.startswith("./") or uses_value.startswith("../"):
        return {
            "class": "local_reusable",
            "action": uses_value,
            "owner": None,
            "repo": None,
            "ref": None,
            "pinned": None,
        }

    match = ACTION_REF_RE.match(uses_value)
    if not match:
        return {
            "class": "unknown",
            "action": uses_value,
            "owner": None,
            "repo": None,
            "ref": None,
            "pinned": None,
        }

    owner = match.group("owner")
    repo = match.group("repo")
    ref = match.group("ref")
    action = f"{owner}/{repo}"
    pinned = bool(SHA_RE.match(ref))

    if owner in exclude_owners:
        if owner in ("actions", "github"):
            action_class = "github_owned"
        else:
            action_class = "org_shared"
    else:
        action_class = "third_party"

    return {
        "class": action_class,
        "action": action,
        "owner": owner,
        "repo": repo,
        "ref": ref,
        "pinned": pinned,
    }


def parse_comment_tag(comment: str | None, action: str) -> str | None:
    if not comment:
        return None
    cleaned = comment.strip()
    if cleaned.startswith(action):
        return cleaned.split("@", 1)[-1] if "@" in cleaned else cleaned
    if "@" in cleaned:
        return cleaned.split("@", 1)[-1]
    return cleaned or None


def inventory_entry(
    *,
    file_path: Path,
    app_folder: Path,
    line_no: int,
    uses_value: str,
    inline_comment: str | None,
    exclude_owners: tuple[str, ...],
) -> dict[str, Any]:
    classification = classify_action(uses_value, exclude_owners=exclude_owners)
    comment_tag = parse_comment_tag(inline_comment, str(classification["action"]))
    return {
        "file": str(file_path.relative_to(app_folder)).replace("\\", "/"),
        "line": line_no,
        "uses": uses_value,
        "action": classification["action"],
        "class": classification["class"],
        "ref": classification["ref"],
        "pinned": classification["pinned"],
        "comment_tag": comment_tag,
    }


def scan_inventory(app_folder: Path, exclude_owners: tuple[str, ...]) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for workflow in workflow_files(app_folder):
        text = workflow.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            match = USES_LINE_RE.match(line)
            if not match:
                continue
            uses_value, inline_comment = normalize_uses_value(match.group("value"))
            inventory.append(
                inventory_entry(
                    file_path=workflow,
                    app_folder=app_folder,
                    line_no=line_no,
                    uses_value=uses_value,
                    inline_comment=inline_comment or match.group("comment"),
                    exclude_owners=exclude_owners,
                )
            )
    return inventory


def devops_config_slice(config: dict[str, Any] | None) -> dict[str, Any]:
    devops = (config or {}).get("devops") or {}
    exclude = devops.get("third_party_owners_exclude") or list(DEFAULT_EXCLUDE_OWNERS)
    return {
        "exclude_owners": tuple(str(owner) for owner in exclude),
        "auto_refresh_same_tag": bool(devops.get("auto_refresh_same_tag", True)),
    }


def devops_scan(app_folder: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    root = resolve_app_folder(app_folder)
    cfg = devops_config_slice(config)
    workflows = workflow_files(root)
    inventory = scan_inventory(root, cfg["exclude_owners"])
    by_class: dict[str, int] = {}
    for item in inventory:
        by_class[item["class"]] = by_class.get(item["class"], 0) + 1
    return {
        "app_folder": str(root),
        "workflow_count": len(workflows),
        "workflows": [str(path.relative_to(root)).replace("\\", "/") for path in workflows],
        "inventory": inventory,
        "inventory_count": len(inventory),
        "summary": {"by_class": by_class},
    }


def is_mutable_third_party_ref(item: dict[str, Any]) -> bool:
    if item.get("class") != "third_party":
        return False
    ref = str(item.get("ref") or "")
    if SHA_RE.match(ref):
        return False
    return True


def devops_pin_report(app_folder: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    scan = devops_scan(app_folder, config)
    cfg = devops_config_slice(config)
    inventory = scan["inventory"]

    unpinned_third_party: list[dict[str, Any]] = []
    missing_pin_comments: list[dict[str, Any]] = []
    malformed_pins: list[dict[str, Any]] = []
    same_tag_refresh_candidates: list[dict[str, Any]] = []
    major_bump_candidates: list[dict[str, Any]] = []
    same_tag_drift: list[dict[str, Any]] = []

    for item in inventory:
        if item["class"] != "third_party":
            continue
        if is_mutable_third_party_ref(item):
            candidate = {**item, "reason": "mutable_ref_requires_pin"}
            unpinned_third_party.append(candidate)
            if item.get("ref") and not str(item["ref"]).startswith("v"):
                major_bump_candidates.append({**item, "reason": "non_semver_ref_requires_human"})
            continue
        if item.get("pinned") is True and not item.get("comment_tag"):
            missing_pin_comments.append({**item, "reason": "pinned_without_tag_comment"})
        if item.get("pinned") is True and item.get("comment_tag"):
            refresh = {**item, "reason": "verify_current_commit_via_gh_api"}
            same_tag_refresh_candidates.append(refresh)
            if not cfg["auto_refresh_same_tag"]:
                same_tag_drift.append({**item, "reason": "same_tag_drift_requires_human_when_auto_refresh_disabled"})
        if item.get("pinned") is False and item.get("ref") and SHA_RE.match(str(item["ref"])) is None:
            malformed_pins.append({**item, "reason": "invalid_sha_format"})

    return {
        **scan,
        "unpinned_third_party": unpinned_third_party,
        "missing_pin_comments": missing_pin_comments,
        "malformed_pins": malformed_pins,
        "same_tag_refresh_candidates": same_tag_refresh_candidates,
        "major_bump_candidates": major_bump_candidates,
        "same_tag_drift": same_tag_drift,
        "policy": {
            "major_bump_requires_human": True,
            "auto_refresh_same_tag": cfg["auto_refresh_same_tag"],
        },
        "summary": {
            **scan["summary"],
            "unpinned_third_party": len(unpinned_third_party),
            "missing_pin_comments": len(missing_pin_comments),
            "same_tag_refresh_candidates": len(same_tag_refresh_candidates),
            "major_bump_candidates": len(major_bump_candidates),
            "same_tag_drift": len(same_tag_drift),
        },
    }


def find_action_lines(text: str, action: str, *, line: int | None = None) -> list[int]:
    matches: list[int] = []
    for line_no, row in enumerate(text.splitlines(), start=1):
        if line is not None and line_no != line:
            continue
        parsed = USES_LINE_RE.match(row)
        if not parsed:
            continue
        uses_value, _ = normalize_uses_value(parsed.group("value"))
        classification = classify_action(uses_value)
        if classification["action"] == action:
            matches.append(line_no)
    return matches


def devops_apply_pin(
    workflow: str,
    action: str,
    sha: str,
    *,
    app_folder: str | None = None,
    tag: str | None = None,
    line: int | None = None,
) -> dict[str, Any]:
    if not SHA_RE.match(sha):
        raise DevOpsError(
            "INVALID_SHA",
            "SHA must be exactly 40 hexadecimal characters.",
            extra={"sha": sha},
        )

    workflow_path = Path(workflow)
    if app_folder and not workflow_path.is_absolute():
        workflow_path = resolve_app_folder(app_folder) / workflow
    if not workflow_path.is_file():
        raise DevOpsError("WORKFLOW_NOT_FOUND", f"Workflow file not found: {workflow_path}")

    text = workflow_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    target_lines = find_action_lines(text, action, line=line)
    if not target_lines:
        raise DevOpsError(
            "ACTION_NOT_FOUND",
            f"No uses: line for action {action!r} in {workflow_path}.",
            extra={"action": action, "workflow": str(workflow_path)},
        )
    if len(target_lines) > 1 and line is None:
        raise DevOpsError(
            "AMBIGUOUS_ACTION",
            f"Action {action!r} appears on multiple lines; pass --line.",
            extra={"lines": target_lines},
        )

    target_line = target_lines[0]
    original = lines[target_line - 1]
    parsed = USES_LINE_RE.match(original)
    if not parsed:
        raise DevOpsError("INVALID_WORKFLOW_LINE", f"Could not parse line {target_line}.")

    indent = parsed.group("indent")
    comment_tag = tag or parse_comment_tag(parsed.group("comment"), action) or "unknown"
    dash_prefix = "- " if original.lstrip().startswith("- uses:") else ""
    replacement = f"{indent}{dash_prefix}uses: {action}@{sha.lower()} # {action}@{comment_tag}"
    lines[target_line - 1] = replacement
    workflow_path.write_text("\n".join(lines) + ("\n" if text.endswith("\n") else ""), encoding="utf-8")

    return {
        "workflow": str(workflow_path),
        "action": action,
        "line": target_line,
        "sha": sha.lower(),
        "tag": comment_tag,
        "before": original.strip(),
        "after": replacement.strip(),
        "applied": True,
    }
