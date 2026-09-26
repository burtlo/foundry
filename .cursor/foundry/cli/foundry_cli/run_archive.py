"""Archive application runs into the Foundry repo runs/ store."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from foundry_cli.app_manifest import load_manifest
from foundry_cli.paths import repo_root_from_bundle, workspace_from_run_dir

ARCHIVE_MANIFEST_VERSION = "1.0.0"
ARCHIVE_SUBDIR = "archive"


def archive_root_for_bundle(foundry_bundle: Path, override: Path | None = None) -> Path:
    if override is not None:
        return override.resolve()
    return repo_root_from_bundle(foundry_bundle) / "runs"


def allocate_archive_slug(archive_root: Path, app_id: str) -> str:
    archive_root.mkdir(parents=True, exist_ok=True)
    max_num = 0
    pattern = re.compile(rf"^{re.escape(app_id)}-(\d+)$")
    for child in archive_root.iterdir():
        if child.is_dir():
            match = pattern.match(child.name)
            if match:
                max_num = max(max_num, int(match.group(1)))
    return f"{app_id}-{max_num + 1:04d}"


def _git_head(repo: Path) -> dict[str, str | None]:
    if not (repo / ".git").exists():
        return {"commit_sha": None, "commit_subject": None}
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        subject = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return {"commit_sha": sha, "commit_subject": subject}
    except (subprocess.CalledProcessError, OSError):
        return {"commit_sha": None, "commit_subject": None}


def _visit_summary(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for visit in snapshot.get("visits") or []:
        if not isinstance(visit, dict):
            continue
        row: dict[str, Any] = {
            "id": visit.get("id"),
            "node_id": visit.get("node_id"),
            "kind": visit.get("kind"),
            "outcome": visit.get("outcome"),
        }
        if visit.get("decision") is not None:
            row["decision"] = visit.get("decision")
        if visit.get("lifecycle") is not None and visit.get("outcome") is None:
            row["lifecycle"] = visit.get("lifecycle")
        rows.append(row)
    return rows


def _work_request_from_run(source_run_dir: Path, snapshot: dict[str, Any]) -> str | None:
    state = snapshot.get("state") or {}
    ticket = state.get("ticket") or {}
    if isinstance(ticket, dict) and ticket.get("raw_input"):
        return str(ticket["raw_input"])
    ticket_path = source_run_dir / "ticket.json"
    if ticket_path.is_file():
        try:
            ticket_file = json.loads(ticket_path.read_text(encoding="utf-8"))
            if isinstance(ticket_file, dict) and ticket_file.get("raw_input"):
                return str(ticket_file["raw_input"])
        except json.JSONDecodeError:
            pass
    return None


def build_archive_manifest(
    *,
    archive_slug: str,
    snapshot: dict[str, Any],
    workspace: Path,
    foundry_repo: Path,
    app_id: str,
    work_request: str | None,
    transcript_rel: str | None,
    review_rel: str | None,
    workspace_plan_rel: str | None,
) -> dict[str, Any]:
    active = snapshot.get("active_visit") or {}
    state = snapshot.get("state") or {}
    app_git = _git_head(workspace)
    foundry_git = _git_head(foundry_repo)
    manifest: dict[str, Any] = {
        "schema_version": ARCHIVE_MANIFEST_VERSION,
        "archived_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "archive_slug": archive_slug,
        "run_id": snapshot.get("run_id"),
        "run_uuid": snapshot.get("run_uuid"),
        "flow_id": snapshot.get("flow_id"),
        "application": {
            "id": app_id,
            "workspace": str(workspace.resolve()),
            **app_git,
        },
        "foundry": foundry_git,
        "active_visit_at_archive": {
            "id": active.get("id"),
            "node_id": active.get("node_id"),
            "kind": active.get("kind"),
            "lifecycle": active.get("lifecycle"),
            "decision": active.get("decision"),
        },
        "work_request": work_request,
        "approved_ac_digest": state.get("approved_ac_digest"),
        "artifacts": {
            "run_snapshot": "snapshot.json",
            "presentation": _artifact_path(snapshot, "shape.present.presentation"),
            "plan": _artifact_path(snapshot, "shape.record.plan"),
        },
        "visits": _visit_summary(snapshot),
    }
    if transcript_rel:
        manifest["artifacts"]["transcript"] = transcript_rel
    if review_rel:
        manifest["artifacts"]["review"] = review_rel
    if workspace_plan_rel:
        manifest["artifacts"]["workspace_plan_copy"] = workspace_plan_rel
    return manifest


def _artifact_path(snapshot: dict[str, Any], artifact_id: str) -> str | None:
    for visit in snapshot.get("visits") or []:
        if not isinstance(visit, dict):
            continue
        for artifact in visit.get("artifacts") or []:
            if isinstance(artifact, dict) and artifact.get("artifact") == artifact_id:
                path = artifact.get("path")
                if path:
                    return str(path).removeprefix("run:")
    return None


def archive_run(
    *,
    source_run_dir: Path,
    foundry_bundle: Path,
    archive_root: Path | None = None,
    archive_slug: str | None = None,
    transcript_path: Path | None = None,
    review_path: Path | None = None,
    dry_run: bool = False,
    remove_source: bool = True,
) -> dict[str, Any]:
    source_run_dir = source_run_dir.resolve()
    if not (source_run_dir / "snapshot.json").is_file():
        raise FileNotFoundError(f"Run directory missing snapshot.json: {source_run_dir}")

    workspace = workspace_from_run_dir(source_run_dir)
    _, manifest = load_manifest(workspace)
    app_id = str(manifest.get("id") or "run")

    snapshot = json.loads((source_run_dir / "snapshot.json").read_text(encoding="utf-8"))
    run_id = str(snapshot.get("run_id") or source_run_dir.name)

    root = archive_root_for_bundle(foundry_bundle, archive_root)
    slug = archive_slug or allocate_archive_slug(root, app_id)
    dest_run_dir = root / slug

    if dest_run_dir.exists():
        raise FileExistsError(f"Archive destination already exists: {dest_run_dir}")

    archive_meta_dir = dest_run_dir / ARCHIVE_SUBDIR
    transcript_rel: str | None = None
    review_rel: str | None = None
    workspace_plan_rel: str | None = None

    work_request = _work_request_from_run(source_run_dir, snapshot)

    if dry_run:
        foundry_repo = repo_root_from_bundle(foundry_bundle)
        manifest_doc = build_archive_manifest(
            archive_slug=slug,
            snapshot=snapshot,
            workspace=workspace,
            foundry_repo=foundry_repo,
            app_id=app_id,
            work_request=work_request,
            transcript_rel=f"{ARCHIVE_SUBDIR}/transcript.jsonl" if transcript_path else None,
            review_rel=f"{ARCHIVE_SUBDIR}/review.md" if review_path else None,
            workspace_plan_rel=f"{ARCHIVE_SUBDIR}/workspace-plan.md"
            if (workspace / "plan.md").is_file()
            else None,
        )
        return {
            "dry_run": True,
            "archive_slug": slug,
            "archive_path": str(dest_run_dir),
            "source_run_dir": str(source_run_dir),
            "run_id": run_id,
            "app_id": app_id,
            "manifest": manifest_doc,
            "removed_source": False,
        }

    if remove_source:
        shutil.move(str(source_run_dir), str(dest_run_dir))
    else:
        shutil.copytree(source_run_dir, dest_run_dir)

    archive_meta_dir.mkdir(parents=True, exist_ok=True)

    if transcript_path is not None:
        transcript_path = transcript_path.resolve()
        if not transcript_path.is_file():
            raise FileNotFoundError(f"Transcript not found: {transcript_path}")
        dest_transcript = archive_meta_dir / "transcript.jsonl"
        shutil.copy2(transcript_path, dest_transcript)
        transcript_rel = f"{ARCHIVE_SUBDIR}/transcript.jsonl"

    if review_path is not None:
        review_path = review_path.resolve()
        if not review_path.is_file():
            raise FileNotFoundError(f"Review file not found: {review_path}")
        dest_review = archive_meta_dir / "review.md"
        shutil.copy2(review_path, dest_review)
        review_rel = f"{ARCHIVE_SUBDIR}/review.md"

    workspace_plan = workspace / "plan.md"
    if workspace_plan.is_file():
        dest_plan = archive_meta_dir / "workspace-plan.md"
        shutil.copy2(workspace_plan, dest_plan)
        workspace_plan_rel = f"{ARCHIVE_SUBDIR}/workspace-plan.md"

    foundry_repo = repo_root_from_bundle(foundry_bundle)
    manifest_doc = build_archive_manifest(
        archive_slug=slug,
        snapshot=snapshot,
        workspace=workspace,
        foundry_repo=foundry_repo,
        app_id=app_id,
        work_request=work_request,
        transcript_rel=transcript_rel,
        review_rel=review_rel,
        workspace_plan_rel=workspace_plan_rel,
    )
    (archive_meta_dir / "manifest.json").write_text(
        json.dumps(manifest_doc, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "dry_run": False,
        "archive_slug": slug,
        "archive_path": str(dest_run_dir),
        "source_run_dir": str(source_run_dir),
        "run_id": run_id,
        "app_id": app_id,
        "manifest_path": str(archive_meta_dir / "manifest.json"),
        "removed_source": remove_source and not source_run_dir.exists(),
    }
