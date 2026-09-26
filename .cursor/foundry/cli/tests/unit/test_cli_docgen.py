"""Unit tests for foundry_cli.cli_docgen."""

from __future__ import annotations

from pathlib import Path

import pytest

from foundry_cli.cli_docgen import (
    CLI_CAPABILITIES,
    build_cli_command_doc,
    build_cli_index,
    collect_command_specs,
    write_cli_docs,
)
from foundry_cli.parser import build_parser

CLI_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = CLI_DIR.parents[2]


@pytest.fixture
def parser():
    return build_parser()


def test_collect_command_specs_includes_implemented_commands(parser) -> None:
    specs = collect_command_specs(parser)
    capability_ids = {spec.capability_id for spec in specs}
    assert "run.context" in capability_ids
    assert "catalog.build" in capability_ids
    assert "doc.build" in capability_ids
    assert "dev.docs" in capability_ids
    assert capability_ids.issubset(CLI_CAPABILITIES.keys())


def test_build_cli_index_lists_commands(parser) -> None:
    specs = collect_command_specs(parser)
    doc = build_cli_index(
        specs,
        repo_root=REPO_ROOT,
        output_dir=REPO_ROOT / "docs",
        root_parser=parser,
    )
    assert "# Foundry CLI reference" in doc
    assert "`run.context`" in doc
    assert "## Global flags" in doc
    assert "`--workspace`" in doc


def test_build_cli_command_doc_run_context(parser) -> None:
    spec = next(item for item in collect_command_specs(parser) if item.capability_id == "run.context")
    doc = build_cli_command_doc(
        spec,
        repo_root=REPO_ROOT,
        from_file=REPO_ROOT / "docs" / "cli" / "run-context.md",
        root_parser=parser,
    )
    assert "# `run context`" in doc
    assert "context-packet.schema.json" in doc
    assert "run_context.feature" in doc
    assert "## Command flags" in doc
    assert "`--run`" in doc
    assert "`--markdown`" in doc
    assert "## Output modes" in doc
    assert "## Sample markdown output (abbreviated)" in doc
    assert "Steward context — shape.intake" in doc


def test_write_cli_docs_creates_index_and_command_pages(parser, tmp_path) -> None:
    output_dir = tmp_path / "docs"
    written = write_cli_docs(parser=parser, repo_root=REPO_ROOT, output_dir=output_dir)
    paths = {path.name for path in written}
    assert "index.md" in paths
    assert "run-context.md" in paths
    assert "dev-docs.md" in paths
    index = (output_dir / "cli" / "index.md").read_text(encoding="utf-8")
    assert "CLI reference" in index or "Foundry CLI reference" in index
