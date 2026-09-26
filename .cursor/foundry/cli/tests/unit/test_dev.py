"""Unit tests for foundry_cli.dev shortcuts."""

from __future__ import annotations

from unittest.mock import patch

from foundry_cli.dev import (
    ACCEPTANCE_TESTS,
    CLI_DIR,
    UNIT_TESTS,
    run_acceptance_tests,
    run_all_tests,
    run_dev_docs,
    run_unit_tests,
)
from tests.conftest import FOUNDRY_ROOT, REPO_ROOT
from tests.unit.constants import IMPLEMENTATION_FLOW, NODE_SHAPE_INTAKE


def test_unit_and_acceptance_paths_exist() -> None:
    assert UNIT_TESTS.is_dir()
    assert ACCEPTANCE_TESTS.is_dir()
    assert CLI_DIR.name == "cli"


def test_run_unit_tests_success_when_pytest_passes() -> None:
    with patch("foundry_cli.dev.run_pytest") as mock_run:
        mock_run.return_value = {"ok": True, "exit_code": 0, "stdout": "", "stderr": ""}
        result = run_unit_tests()
    assert result["ok"] is True
    assert result["suite"] == "unit"
    mock_run.assert_called_once_with(UNIT_TESTS, quiet=False, extra_argv=None)


def test_run_all_tests_reports_suites_passed() -> None:
    with patch("foundry_cli.dev.run_unit_tests") as mock_unit, patch(
        "foundry_cli.dev.run_acceptance_tests"
    ) as mock_acceptance:
        mock_unit.return_value = {"ok": True, "suite": "unit"}
        mock_acceptance.return_value = {"ok": True, "suite": "acceptance"}
        result = run_all_tests()
    assert result["ok"] is True
    assert result["suite"] == "all"
    assert result["suites_passed"] == ["unit", "acceptance"]


def test_run_dev_docs_writes_index(tmp_path) -> None:
    output_dir = tmp_path / "generated"
    result = run_dev_docs(
        workspace=REPO_ROOT,
        foundry_bundle=FOUNDRY_ROOT,
        flow_id=IMPLEMENTATION_FLOW,
        output_dir=output_dir,
    )
    assert result["ok"] is True
    assert (output_dir / "nodes" / f"{NODE_SHAPE_INTAKE}.md").is_file()
