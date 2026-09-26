"""Step definitions specific to dev_commands.feature."""

from __future__ import annotations

from pytest_bdd import given


@given("dev docs output directory is a temporary directory")
def dev_docs_output_dir(acceptance, tmp_path) -> None:
    output_dir = tmp_path / "generated"
    output_dir.mkdir(parents=True)
    acceptance["output_dir"] = output_dir
