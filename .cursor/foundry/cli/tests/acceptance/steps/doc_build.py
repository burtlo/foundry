"""Step definitions for doc_build.feature."""

from __future__ import annotations

from pathlib import Path

from pytest_bdd import given, parsers, then, when

from tests.acceptance.helpers import invoke_foundry


@given("doc output directory is a temporary directory")
def doc_output_dir(acceptance, tmp_path) -> None:
    output_dir = tmp_path / "generated"
    output_dir.mkdir(parents=True)
    acceptance["output_dir"] = output_dir


@when(parsers.parse('I invoke "doc build" for node "{node_id}" with output directory'))
def invoke_doc_build_for_node(acceptance, node_id: str) -> None:
    acceptance["command"] = "doc build"
    acceptance["node_id"] = node_id
    acceptance["json_output"] = False
    invoke_foundry(acceptance)


@when('I invoke "doc build" with output directory')
def invoke_doc_build_all(acceptance) -> None:
    acceptance["command"] = "doc build"
    acceptance["node_id"] = None
    acceptance["json_output"] = False
    invoke_foundry(acceptance)


@then(parsers.parse('generated node doc exists for node "{node_id}"'))
def assert_generated_node_doc_exists(acceptance, node_id: str) -> None:
    output_dir = Path(acceptance["output_dir"])
    path = output_dir / "nodes" / f"{node_id}.md"
    assert path.is_file(), f"expected generated doc at {path}"


@then(parsers.parse('generated node doc for node "{node_id}" contains "{text}"'))
def assert_generated_node_doc_contains(acceptance, node_id: str, text: str) -> None:
    output_dir = Path(acceptance["output_dir"])
    path = output_dir / "nodes" / f"{node_id}.md"
    content = path.read_text(encoding="utf-8")
    assert text in content, f"expected {text!r} in {path}"


@then(parsers.parse('generated cli doc exists for command "{slug}"'))
def assert_generated_cli_doc_exists(acceptance, slug: str) -> None:
    output_dir = Path(acceptance["output_dir"])
    path = output_dir / "cli" / f"{slug}.md"
    assert path.is_file(), f"expected generated CLI doc at {path}"


@then(parsers.parse('generated cli index contains "{text}"'))
def assert_generated_cli_index_contains(acceptance, text: str) -> None:
    output_dir = Path(acceptance["output_dir"])
    path = output_dir / "cli" / "index.md"
    content = path.read_text(encoding="utf-8")
    assert text in content, f"expected {text!r} in {path}"


@then("generated flow doc exists")
def assert_generated_flow_doc_exists(acceptance) -> None:
    output_dir = Path(acceptance["output_dir"])
    path = output_dir / "flow.md"
    assert path.is_file(), f"expected generated flow doc at {path}"


@then(parsers.parse('generated flow doc contains "{text}"'))
def assert_generated_flow_doc_contains(acceptance, text: str) -> None:
    output_dir = Path(acceptance["output_dir"])
    path = output_dir / "flow.md"
    content = path.read_text(encoding="utf-8")
    assert text in content, f"expected {text!r} in {path}"


@then("generated index exists")
def assert_generated_index_exists(acceptance) -> None:
    output_dir = Path(acceptance["output_dir"])
    path = output_dir / "index.md"
    assert path.is_file(), f"expected generated index at {path}"


@then(parsers.parse('generated index contains "{text}"'))
def assert_generated_index_contains(acceptance, text: str) -> None:
    output_dir = Path(acceptance["output_dir"])
    path = output_dir / "index.md"
    content = path.read_text(encoding="utf-8")
    assert text in content, f"expected {text!r} in {path}"
