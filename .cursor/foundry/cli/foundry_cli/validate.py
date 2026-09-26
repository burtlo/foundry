"""Validate JSON payloads against registry schemas."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


@lru_cache(maxsize=32)
def _validator(schema_path: Path) -> Draft202012Validator:
    with schema_path.open(encoding="utf-8") as handle:
        schema = json.load(handle)
    return Draft202012Validator(schema)


def validate_payload(payload: Any, schema_name: str, foundry_bundle: Path) -> list[str]:
    schema_path = foundry_bundle / "schemas" / schema_name
    if not schema_path.is_file():
        return [f"Missing schema file: {schema_path}"]
    validator = _validator(schema_path)
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.path))
    return [f"{list(error.path)}: {error.message}" for error in errors]
