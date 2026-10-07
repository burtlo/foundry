"""Step definitions for app_bootstrap.feature."""

from __future__ import annotations

from pathlib import Path

import yaml
from pytest_bdd import given, parsers, then, when

from tests.acceptance.acceptance_invoke import invoke_acceptance_command



def _sample_manifest(manifest_id: str = "sample-app") -> dict:
    return {
        "schema_version": 1,
        "id": manifest_id,
        "commands": {
            "build": {
                "default": {
                    "argv": ["python", "-m", "build"],
                    "cwd": ".",
                    "timeout_seconds": 900,
                }
            },
            "test": {
                "default": {
                    "argv": ["python", "-m", "unittest"],
                    "cwd": ".",
                    "timeout_seconds": 1200,
                }
            },
        },
        "verification": {
            "implementation": ["build", "test"],
            "post_repair": ["build", "test"],
        },
        "builders": {
            "default_owner": "general-builder",
            "routes": [
                {
                    "id": "default",
                    "owner": "general-builder",
                    "priority": 0,
                    "globs": ["**/*"],
                }
            ],
        },
    }


@given("a temporary bootstrap workspace with Makefile and go.mod")
def bootstrap_workspace_make_go(acceptance, tmp_path) -> None:
    workspace = tmp_path / "bootstrap-app"
    workspace.mkdir(parents=True)
    (workspace / "Makefile").write_text("build:\n\techo build\n\ntest:\n\techo test\n", encoding="utf-8")
    (workspace / "go.mod").write_text("module example.com/bootstrap\n\ngo 1.22\n", encoding="utf-8")
    acceptance["workspace"] = workspace
    acceptance["fixture_name"] = None
    acceptance["run_id"] = None


@given("a temporary bootstrap workspace without manifest")
def bootstrap_workspace_bare(acceptance, tmp_path) -> None:
    workspace = tmp_path / "bootstrap-bare"
    workspace.mkdir(parents=True)
    acceptance["workspace"] = workspace
    acceptance["fixture_name"] = None
    acceptance["run_id"] = None
    acceptance.pop("manifest_input", None)


@given("a manifest input file with sample bootstrap manifest")
def manifest_input_sample(acceptance, tmp_path) -> None:
    manifest = _sample_manifest("sample-app")
    path = tmp_path / "manifest-input.yaml"
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    acceptance["manifest_input"] = str(path)


@given(parsers.parse('a manifest input file with alternate bootstrap manifest id "{manifest_id}"'))
def manifest_input_alternate(acceptance, tmp_path, manifest_id: str) -> None:
    manifest = _sample_manifest(manifest_id)
    path = tmp_path / f"manifest-input-{manifest_id}.yaml"
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    acceptance["manifest_input"] = str(path)


def _app_init_argv(acceptance, *, extra_flags: list[str] | None = None) -> list[str]:
    manifest_input = acceptance.get("manifest_input")
    assert manifest_input, "manifest_input not set in acceptance state"
    argv = ["--manifest-file", str(manifest_input)]
    argv.extend(extra_flags or [])
    return argv


@when(parsers.parse('I invoke "app init"'))
def invoke_app_init(acceptance) -> None:
    invoke_acceptance_command(acceptance, "app init", extra_argv=_app_init_argv(acceptance))


@when(parsers.parse('I invoke "app init" with flag "{flag}"'))
def invoke_app_init_with_flag(acceptance, flag: str) -> None:
    invoke_acceptance_command(
        acceptance,
        "app init",
        extra_argv=_app_init_argv(acceptance, extra_flags=[flag]),
    )


@then("workspace manifest file does not exist")
def assert_manifest_missing(acceptance) -> None:
    path = Path(acceptance["workspace"]) / ".foundry" / "app.yaml"
    assert not path.is_file(), f"expected no manifest at {path}"


@then(parsers.parse('workspace manifest file exists with id "{manifest_id}"'))
def assert_manifest_exists_with_id(acceptance, manifest_id: str) -> None:
    path = Path(acceptance["workspace"]) / ".foundry" / "app.yaml"
    assert path.is_file(), f"expected manifest at {path}"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data.get("id") == manifest_id
