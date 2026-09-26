"""Step definitions for catalog_build.feature."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pytest_bdd import given, parsers, then, when

from tests.acceptance.helpers import (
    collect_index_field_failures,
    default_catalog_index_path,
    invoke_foundry,
)


@given("catalog output directory is a temporary directory")
def catalog_output_dir(acceptance, tmp_path) -> None:
    output_dir = tmp_path / "catalog" / "nodes"
    output_dir.mkdir(parents=True)
    acceptance["output_dir"] = output_dir


@when(parsers.parse('I invoke "catalog build" with json output'))
def invoke_catalog_build(acceptance) -> None:
    acceptance["command"] = "catalog build"
    acceptance["node_id"] = None
    acceptance["json_output"] = True
    invoke_foundry(acceptance)


@when(parsers.parse('I invoke "catalog build" with output directory'))
def invoke_catalog_build_to_output(acceptance) -> None:
    acceptance["command"] = "catalog build"
    acceptance["node_id"] = None
    acceptance["json_output"] = False
    invoke_foundry(acceptance)


@when(parsers.parse('I invoke "catalog build" for node "{node_id}" with json output'))
def invoke_catalog_build_for_node(acceptance, node_id: str) -> None:
    acceptance["command"] = "catalog build"
    acceptance["node_id"] = node_id
    acceptance["json_output"] = True
    path = default_catalog_index_path(node_id)
    acceptance["catalog_index_before"] = path.stat().st_mtime if path.is_file() else None
    invoke_foundry(acceptance)


@when(parsers.parse('I invoke "catalog build" for node "{node_id}" with output directory'))
def invoke_catalog_build_for_node_to_output(acceptance, node_id: str) -> None:
    acceptance["command"] = "catalog build"
    acceptance["node_id"] = node_id
    acceptance["json_output"] = False
    invoke_foundry(acceptance)


@then(parsers.parse("catalog summary node count equals {count:d}"))
def assert_catalog_node_count(acceptance, count: int) -> None:
    payload = acceptance.get("payload")
    if payload is not None and payload.get("ok") is True:
        assert payload.get("node_count") == count, payload
        return
    stdout = acceptance.get("stdout") or ""
    assert f"nodes={count}" in stdout, stdout


@then(parsers.parse('catalog index file exists for node "{node_id}"'))
def assert_catalog_index_file_exists(acceptance, node_id: str) -> None:
    output_dir = acceptance.get("output_dir")
    if output_dir is not None:
        path = Path(output_dir) / f"{node_id}.index.yaml"
    else:
        path = default_catalog_index_path(node_id)
    assert path.is_file(), f"expected index file at {path}"


@then(parsers.parse('catalog index file does not exist for node "{node_id}"'))
def assert_catalog_index_file_missing(acceptance, node_id: str) -> None:
    output_dir = acceptance.get("output_dir")
    if output_dir is not None:
        path = Path(output_dir) / f"{node_id}.index.yaml"
    else:
        path = default_catalog_index_path(node_id)
    assert not path.exists(), f"expected no index file at {path}"


@then(parsers.parse('default catalog index file does not exist for node "{node_id}"'))
def assert_default_catalog_index_missing(acceptance, node_id: str) -> None:
    path = default_catalog_index_path(node_id)
    before = acceptance.get("catalog_index_before")
    if before is None:
        assert not path.exists(), f"expected json mode to skip writing {path}"
        return
    assert path.is_file(), f"expected existing catalog index at {path}"
    assert path.stat().st_mtime == before, f"expected json mode to skip rewriting {path}"


@then(parsers.parse('response catalog index for node "{node_id}" is present'))
def assert_response_catalog_index(acceptance, node_id: str) -> None:
    payload = acceptance["payload"]
    assert payload is not None and payload.get("ok") is True
    indexes = payload.get("indexes") or {}
    assert node_id in indexes, payload
    assert indexes[node_id]["node_id"] == node_id


@then(parsers.parse('catalog index for node "{node_id}" fields match:'))
def assert_catalog_index_fields(acceptance, node_id: str, datatable) -> None:
    output_dir = acceptance.get("output_dir")
    if output_dir is not None:
        path = Path(output_dir) / f"{node_id}.index.yaml"
    else:
        indexes = acceptance["payload"].get("indexes") or {}
        index = indexes.get(node_id)
        if index is None:
            pytest.fail(f"missing index for {node_id!r} in response payload")
        failures = collect_index_field_failures(index, datatable)
        if failures:
            message = "catalog index field expectation failures:\n" + "\n".join(
                f"  - {item}" for item in failures
            )
            pytest.fail(message)
        return

    index = yaml.safe_load(path.read_text(encoding="utf-8"))
    failures = collect_index_field_failures(index, datatable)
    if failures:
        message = "catalog index field expectation failures:\n" + "\n".join(
            f"  - {item}" for item in failures
        )
        pytest.fail(message)


@then(parsers.parse('catalog index for node "{node_id}" tests include "{feature_path}"'))
def assert_catalog_index_tests_include(acceptance, node_id: str, feature_path: str) -> None:
    output_dir = acceptance.get("output_dir")
    if output_dir is not None:
        path = Path(output_dir) / f"{node_id}.index.yaml"
        index = yaml.safe_load(path.read_text(encoding="utf-8"))
    else:
        index = acceptance["payload"]["indexes"][node_id]
    tests = index.get("tests") or []
    assert feature_path in tests, f"{feature_path!r} not in {tests!r}"
