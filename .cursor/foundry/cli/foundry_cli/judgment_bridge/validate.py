"""Validate bridge results against registry task schemas."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from foundry_cli.engine.agent.submit import _validate_verify_acceptance_semantics
from foundry_cli.engine.agent.tasks import VERIFY_ACCEPTANCE_TASK_ID, output_schema_file
from foundry_cli.validate import validate_payload


def validate_task_result(
    request: dict[str, Any],
    result: dict[str, Any],
    *,
    foundry_bundle: Path,
) -> None:
    schema_file = output_schema_file(request, foundry_bundle)
    errors = validate_payload(result, schema_file, foundry_bundle)
    if errors:
        raise ValueError("Schema validation failed: " + "; ".join(errors[:5]))
    task_id = str(request.get("task_id") or "")
    if task_id == VERIFY_ACCEPTANCE_TASK_ID:
        semantic = _validate_verify_acceptance_semantics(result)
        if semantic:
            raise ValueError(semantic)
