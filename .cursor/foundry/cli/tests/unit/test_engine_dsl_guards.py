"""Architecture grep guards for engine DSL hardening."""

from __future__ import annotations

from pathlib import Path

from tests.conftest import FOUNDRY_ROOT

_ENGINE = FOUNDRY_ROOT / "cli" / "foundry_cli" / "engine"


def test_advance_classifier_has_no_legacy_handler_frozensets() -> None:
    text = (_ENGINE / "advance_classifier.py").read_text(encoding="utf-8")
    assert "_HOST_ADVANCE" not in text
    assert "_TASK_BOUND_COMPLETE" not in text


def test_task_bound_advance_has_no_handler_map() -> None:
    text = (_ENGINE / "task_bound_advance.py").read_text(encoding="utf-8")
    assert "_TASK_COMPLETE_HANDLERS" not in text


def test_advance_py_has_no_flow_node_id_literals() -> None:
    text = (_ENGINE / "advance.py").read_text(encoding="utf-8")
    for prefix in ("shape.", "execute.", "verify."):
        assert prefix not in text
