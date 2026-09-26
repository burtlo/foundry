"""Workflow engine: hooks, checks, admission, and transition."""

from foundry_cli.engine.gates import decide_gate
from foundry_cli.engine.hooks import run_hook, run_on_close
from foundry_cli.engine.lifecycle import (
    RUN_UUID_KEY,
    active_visit,
    admit_visit,
    generate_run_slug,
    next_visit_id,
    now_iso,
    run_uuid,
    transition_visit,
    update_active_visit,
)
from foundry_cli.engine.receipts import (
    fill_receipt_provenance,
    find_artifact_declaration,
    resolve_source_path,
    schema_name_from_registry,
    seal_receipt_path,
    sha256_digest,
)
from foundry_cli.engine.routing import evaluate_when_expression, select_connection
from foundry_cli.engine.state import patch_allowed

__all__ = [
    "RUN_UUID_KEY",
    "active_visit",
    "admit_visit",
    "decide_gate",
    "evaluate_when_expression",
    "fill_receipt_provenance",
    "find_artifact_declaration",
    "generate_run_slug",
    "next_visit_id",
    "now_iso",
    "patch_allowed",
    "resolve_source_path",
    "run_hook",
    "run_on_close",
    "run_uuid",
    "schema_name_from_registry",
    "seal_receipt_path",
    "select_connection",
    "sha256_digest",
    "transition_visit",
    "update_active_visit",
]
