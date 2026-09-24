"""Documentation-model kernel: registry, pipeline, and generic knowledge helpers."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

import foundry_store


class DocsError(Exception):
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


DRIVE_PATH_RE = re.compile(r"^[A-Za-z]:")
KNOWLEDGE_CATEGORIES = ("gotchas", "patterns", "conventions")
DOCUMENTATION_STEP_ID = "implement.documentation"
COMMON_RESULT_KEYS = (
    "model",
    "status",
    "artifacts",
    "changed",
    "validation",
    "publication",
    "blockers",
    "workflow",
)
_IOT_EXPORTS = {
    "ENTRY_POINT_SUFFIXES",
    "TEST_SUFFIXES",
    "SLN_PROJECT_RE",
    "ROOT_AGENTS_AUDIT_FIELDS",
    "PRD_VALIDATION_CHECKS",
    "IotAgentsPrdBackend",
    "agents_content_hash",
    "audit_agents_file",
    "canonical_audit_fields",
    "classify_project",
    "compile_prd_markdown",
    "default_prd_path",
    "docs_audit",
    "docs_discover",
    "extract_table_field",
    "find_prd_path",
    "find_solution",
    "is_narrow_agents_diff",
    "list_agents_files",
    "normalize_text",
    "parse_sln_projects",
    "prd_generate",
    "prd_validate",
    "section_present",
    "value_in_prd",
}

_BACKENDS: dict[str, Any] | None = None


def unsafe_relative_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return (
        not normalized
        or normalized.startswith("/")
        or bool(DRIVE_PATH_RE.match(normalized))
        or ".." in normalized.split("/")
    )


def git_changed_files(
    app_folder: Path,
    since: str,
    runner: Callable[..., Any] | None = None,
) -> list[str]:
    command = ["git", "-C", str(app_folder), "diff", "--name-only", f"{since}..HEAD"]
    if runner is not None:
        result = runner(command, app_folder)
        output = result.stdout or ""
    else:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise DocsError(
                "GIT_DIFF_FAILED",
                (completed.stderr or completed.stdout or "git diff failed").strip(),
                extra={"exitCode": completed.returncode, "command": command},
            )
        output = completed.stdout or ""
    return [line.strip() for line in output.splitlines() if line.strip()]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "finding"


def common_result(
    *,
    model: str,
    workflow: str,
    status: str,
    artifacts: list[str],
    changed: bool,
    validation_passed: bool,
    checks: list[str],
    publication_required: bool,
    publication_passed: bool,
    blockers: list[str],
) -> dict[str, Any]:
    if status not in {"completed", "failed"}:
        raise DocsError("INVALID_DOCUMENTATION_RESULT", f"Unsupported documentation status: {status!r}.")
    return {
        "model": model,
        "status": status,
        "artifacts": list(artifacts),
        "changed": bool(changed),
        "validation": {"passed": bool(validation_passed), "checks": list(checks)},
        "publication": {
            "required": bool(publication_required),
            "passed": bool(publication_passed),
        },
        "blockers": list(blockers),
        "workflow": workflow,
    }


def validate_common_result(
    receipt: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    expected_model: str | None = None,
) -> dict[str, Any]:
    result = receipt.get("documentation_result") if isinstance(receipt, dict) else None
    if not isinstance(result, dict):
        result = receipt if isinstance(receipt, dict) else {}
    checks: list[str] = []
    blockers: list[str] = []
    for key in COMMON_RESULT_KEYS:
        if key in result:
            checks.append(key)
        else:
            blockers.append(f"missing {key}")
    model = result.get("model")
    expected = expected_model or ((snapshot or {}).get("documentation") or {}).get("model")
    if expected and model != expected:
        blockers.append(f"model mismatch: expected {expected!r}, got {model!r}")
    else:
        checks.append("model_matches_snapshot")
    validation = result.get("validation") if isinstance(result.get("validation"), dict) else {}
    publication = result.get("publication") if isinstance(result.get("publication"), dict) else {}
    if "passed" in validation:
        checks.append("validation.passed")
    else:
        blockers.append("missing validation.passed")
    if "required" in publication and "passed" in publication:
        checks.append("publication")
    else:
        blockers.append("missing publication.required or publication.passed")
    passed = not blockers
    return common_result(
        model=str(model or expected or ""),
        workflow=str(result.get("workflow") or ""),
        status="completed" if passed else "failed",
        artifacts=list(result.get("artifacts") or []),
        changed=bool(result.get("changed")),
        validation_passed=passed and bool(validation.get("passed", True)),
        checks=checks,
        publication_required=bool(publication.get("required")),
        publication_passed=bool(publication.get("passed")),
        blockers=blockers,
    )


def documentation_backends() -> dict[str, Any]:
    global _BACKENDS
    if _BACKENDS is None:
        from foundry_docs_feature_records import FeatureRecordsBackend
        from foundry_docs_iot import IotAgentsPrdBackend

        _BACKENDS = {
            "iot-agents-prd": IotAgentsPrdBackend(),
            "feature-records": FeatureRecordsBackend(),
        }
    return _BACKENDS


def resolve_documentation_backend(model: str) -> Any:
    if not model or model not in documentation_backends():
        registered = ", ".join(sorted(documentation_backends()))
        raise DocsError(
            "APP_MANIFEST_DOCUMENTATION_MODEL_UNKNOWN",
            f"Unknown documentation.model {model!r}. Registered models: {registered}.",
            extra={"model": model, "registered": sorted(documentation_backends())},
        )
    return documentation_backends()[model]


def persist_documentation_result(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    step = state.setdefault("steps", {}).setdefault(DOCUMENTATION_STEP_ID, {})
    if not isinstance(step, dict):
        step = {}
        state.setdefault("steps", {})[DOCUMENTATION_STEP_ID] = step
    step["model"] = result["model"]
    step["documentation_result"] = result
    if result.get("model") == "iot-agents-prd":
        step["prd_created_or_updated"] = bool((result.get("publication") or {}).get("required"))
    return step


def docs_pipeline(
    state_path: str,
    since: str | None,
    *,
    git_runner: Callable[..., Any] | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    import foundry_app

    path = Path(state_path)
    if not path.is_file():
        raise DocsError("MISSING_STATE", f"Run state not found: {state_path}")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DocsError("INVALID_STATE", f"Run state is not valid JSON: {path}") from exc
    if not isinstance(state, dict):
        raise DocsError("INVALID_STATE", "Run state must be a JSON object.")
    try:
        snapshot = foundry_app.load_run_manifest_snapshot(path.parent)
    except foundry_app.AppManifestError as exc:
        raise DocsError(exc.error_code, exc.message, extra={"errors": exc.errors}) from exc
    documentation = snapshot.get("documentation") if isinstance(snapshot.get("documentation"), dict) else {}
    model = str(documentation.get("model") or "")
    backend = resolve_documentation_backend(model)
    app_folder = str(state.get("app_folder") or "")
    if not app_folder:
        raise DocsError("INVALID_APP_FOLDER", "Run state is missing app_folder.")
    result = backend.execute(snapshot, app_folder, since, git_runner=git_runner)
    if persist:
        expected_revision = int(state.get("state_revision") or 0)
        persist_documentation_result(state, result)
        try:
            foundry_store.write_state_cas(path, state, expected_revision=expected_revision)
        except foundry_store.StoreError as exc:
            raise DocsError(exc.error_code, exc.message, extra=exc.extra) from exc
    return result


def knowledge_suggest(receipt_path: str, factory_root: str | None = None) -> dict[str, Any]:
    path = Path(receipt_path)
    if not path.is_file():
        raise DocsError("MISSING_RECEIPT", f"Receipt not found: {receipt_path}")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(receipt, dict):
        raise DocsError("INVALID_RECEIPT", "Receipt must be a JSON object.")

    suggestions: list[dict[str, Any]] = []
    receipt_id = str(receipt.get("receipt_id") or path.stem)

    exploration = receipt.get("exploration") or {}
    for hypothesis in exploration.get("hypotheses") or []:
        if not isinstance(hypothesis, dict):
            continue
        if hypothesis.get("status") != "accepted":
            continue
        text = str(hypothesis.get("text") or "").strip()
        if not text:
            continue
        category = "gotchas" if "must" in text.lower() or "after" in text.lower() else "patterns"
        suggestions.append(
            {
                "category": category,
                "proposed_path": f".cursor/foundry/knowledge/{category}/{slugify(text)}.md",
                "title": text[:120],
                "content_preview": text,
                "source_receipt_id": receipt_id,
                "requires_human_promotion": True,
                "auto_commit": False,
            }
        )

    for decision in receipt.get("decisions") or []:
        if not isinstance(decision, dict):
            continue
        text = str(decision.get("text") or "").strip()
        if not text:
            continue
        category = "conventions" if decision.get("confidence") == "high" else "patterns"
        suggestions.append(
            {
                "category": category,
                "proposed_path": f".cursor/foundry/knowledge/{category}/{slugify(text)}.md",
                "title": text[:120],
                "content_preview": text,
                "source_receipt_id": receipt_id,
                "requires_human_promotion": True,
                "auto_commit": False,
            }
        )

    summary = str((receipt.get("outputs") or {}).get("summary_markdown") or "").strip()
    if summary and not suggestions:
        suggestions.append(
            {
                "category": "patterns",
                "proposed_path": f".cursor/foundry/knowledge/patterns/{slugify(summary[:60])}.md",
                "title": summary.splitlines()[0][:120],
                "content_preview": summary[:500],
                "source_receipt_id": receipt_id,
                "requires_human_promotion": True,
                "auto_commit": False,
            }
        )

    knowledge_root = None
    if factory_root:
        knowledge_root = Path(factory_root) / ".cursor" / "foundry" / "knowledge"
    return {
        "receipt_path": str(path),
        "suggestion_count": len(suggestions),
        "suggestions": suggestions,
        "requires_human_promotion": True,
        "knowledge_root": str(knowledge_root) if knowledge_root else None,
        "note": "Suggestions are proposals only; nothing is written until a human approves promotion in implement.documentation.",
    }


def __getattr__(name: str) -> Any:
    if name == "FeatureRecordsBackend":
        from foundry_docs_feature_records import FeatureRecordsBackend

        return FeatureRecordsBackend
    if name in _IOT_EXPORTS:
        import foundry_docs_iot as iot

        return getattr(iot, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
