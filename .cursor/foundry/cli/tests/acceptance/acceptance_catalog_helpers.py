"""Catalog index path resolution for acceptance assertions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tests.acceptance.helpers import default_catalog_index_path


def catalog_index_path(acceptance: dict[str, Any], node_id: str) -> Path:
    output_dir = acceptance.get("output_dir")
    if output_dir is not None:
        return Path(output_dir) / f"{node_id}.index.yaml"
    return default_catalog_index_path(node_id)
