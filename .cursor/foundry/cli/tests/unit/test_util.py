"""Unit tests for foundry_cli.util."""

from __future__ import annotations

import pytest

from foundry_cli.util import list_or_empty, now_iso


def test_list_or_empty_returns_empty_for_none() -> None:
    assert list_or_empty(None) == []


def test_list_or_empty_coerces_list_items_to_strings() -> None:
    assert list_or_empty(["a", 1, True]) == ["a", "1", "True"]


def test_list_or_empty_rejects_non_list() -> None:
    with pytest.raises(ValueError, match="Expected list"):
        list_or_empty("not-a-list")


def test_now_iso_returns_utc_z_suffix() -> None:
    value = now_iso()
    assert value.endswith("Z")
    assert "T" in value
