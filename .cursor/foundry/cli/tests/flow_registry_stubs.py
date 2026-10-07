"""Minimal flow registry files for unit tests."""

from __future__ import annotations

from pathlib import Path

from tests.unit.constants import IMPLEMENTATION_FLOW

STUB_REGISTRY_YAML = """\
version: 2
state_schema: registry:schemas/factory-run-state.schema.json
flow:
  id: implementation
  entry: shape.intake
  checks: {}
  nodes: []
  connections: []
"""


def write_stub_flow_registry(bundle: Path, flow_id: str = IMPLEMENTATION_FLOW) -> Path:
    path = bundle / "flows" / flow_id / "registry.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(STUB_REGISTRY_YAML, encoding="utf-8")
    return path
