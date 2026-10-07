"""Task-bound advance metadata and ActionRegistry wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

from foundry_cli.engine.actions import default_action_registry
from foundry_cli.engine.task_bound_advance import task_advance_metadata
from tests.conftest import FOUNDRY_ROOT

BUNDLE = FOUNDRY_ROOT

_JUDGMENT_TASK_IDS = (
    "shape.examine",
    "shape.present",
    "shape.record",
    "execute.plan",
    "verify.acceptance",
)


@pytest.mark.parametrize("task_id", _JUDGMENT_TASK_IDS)
def test_judgment_tasks_declare_registered_complete_action(task_id: str) -> None:
    meta = task_advance_metadata(task_id, BUNDLE)
    action = meta["complete_action"]
    assert action
    registry = default_action_registry()
    assert registry.has(action), f"{task_id} complete_action {action!r} not registered"
