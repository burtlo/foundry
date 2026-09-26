"""Discover and initialize workspace .foundry/app.yaml (v1 bootstrap)."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

from foundry_cli.app_manifest import manifest_path, validate_manifest
from foundry_cli.validate import validate_payload

SCHEMA_VERSION = 1
DEFAULT_BUILDER = "general-builder"
DEFAULT_TIMEOUT = 1200
BUILD_TIMEOUT = 900

def _repo_relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _command_entry(argv: list[str], timeout_seconds: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    return {
        "default": {
            "argv": argv,
            "cwd": ".",
            "timeout_seconds": timeout_seconds,
        }
    }


def _kebab_id(name: str) -> str:
    candidate = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return candidate or "app"


def _makefile_targets(root: Path) -> set[str]:
    makefile = next(
        (candidate for candidate in (root / "Makefile", root / "makefile") if candidate.is_file()),
        None,
    )
    if makefile is None:
        return set()
    text = makefile.read_text(encoding="utf-8", errors="replace")
    return {
        match.group(1)
        for match in re.finditer(r"(?m)^([A-Za-z0-9][A-Za-z0-9_.-]*)\s*:(?!=)", text)
    }


def _validate_command_references(manifest: dict[str, Any]) -> list[str]:
    commands = manifest.get("commands")
    if not isinstance(commands, dict):
        return []
    verification = manifest.get("verification")
    if not isinstance(verification, dict):
        return []
    errors: list[str] = []
    for policy_name, references in verification.items():
        if not isinstance(references, list):
            continue
        for name in references:
            if name not in commands:
                errors.append(
                    f"verification.{policy_name} references unknown command: {name!r}"
                )
    return errors


def validate_manifest_data(manifest: dict[str, Any], foundry_bundle: Path) -> list[str]:
    errors = validate_payload(manifest, "app-manifest.schema.json", foundry_bundle)
    errors.extend(_validate_command_references(manifest))
    if "documentation" in manifest:
        errors.append("documentation section is not supported in v1 manifests")
    return errors


def _ordered_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    order = ("schema_version", "id", "tags", "commands", "verification", "builders", "git", "review")
    return {key: manifest[key] for key in order if key in manifest}


def render_manifest(manifest: dict[str, Any]) -> str:
    return yaml.safe_dump(
        _ordered_manifest(manifest),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )


def _load_yaml_mapping(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {label}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label} root must be a mapping")
    return data


def _gitignore_issues(root: Path) -> list[dict[str, str]]:
    gitignore = root / ".gitignore"
    if not gitignore.is_file():
        return []
    issues: list[dict[str, str]] = []
    for line_number, raw_line in enumerate(
        gitignore.read_text(encoding="utf-8", errors="replace").splitlines(),
        start=1,
    ):
        rule = raw_line.strip()
        if rule in {".foundry", ".foundry/", "/.foundry", "/.foundry/"}:
            issues.append(
                {
                    "file": ".gitignore",
                    "line": str(line_number),
                    "rule": rule,
                    "replacement": ".foundry/runs/",
                }
            )
    return issues


def _validate_manifest_not_ignored(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-v", "--no-index", ".foundry/app.yaml"],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode == 0:
        return result.stdout.strip() or "git ignore rules hide .foundry/app.yaml"
    return None


def discover_app(workspace: Path) -> dict[str, Any]:
    root = workspace.resolve()
    if not root.is_dir():
        raise ValueError(f"Workspace does not exist: {root}")

    app_id = _kebab_id(root.name)
    tags: list[str] = []
    commands: dict[str, dict[str, Any]] = {}
    unresolved: list[dict[str, str]] = []

    targets = _makefile_targets(root)
    makefile = next(
        (candidate for candidate in (root / "Makefile", root / "makefile") if candidate.is_file()),
        None,
    )
    if makefile is not None:
        evidence = _repo_relative(root, makefile)
        for name, timeout in (("build", BUILD_TIMEOUT), ("test", DEFAULT_TIMEOUT)):
            if name in targets:
                commands[name] = _command_entry(["make", name], timeout_seconds=timeout)

    go_mod = root / "go.mod"
    if go_mod.is_file():
        tags.append("go")
        if "build" not in commands:
            commands["build"] = _command_entry(["go", "build", "./..."], timeout_seconds=BUILD_TIMEOUT)
        if "test" not in commands:
            commands["test"] = _command_entry(["go", "test", "./..."], timeout_seconds=DEFAULT_TIMEOUT)

    package_json = root / "package.json"
    if package_json.is_file():
        tags.append("node")
        try:
            package = json.loads(package_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            package = {}
        scripts = package.get("scripts") if isinstance(package, dict) else {}
        if isinstance(scripts, dict):
            for command_name, script_names in {
                "build": ("build",),
                "test": ("test",),
            }.items():
                if command_name in commands:
                    continue
                for script_name in script_names:
                    if script_name in scripts:
                        commands[command_name] = _command_entry(
                            ["npm", "run", script_name],
                            timeout_seconds=DEFAULT_TIMEOUT,
                        )
                        break

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        tags.append("python")
        if "test" not in commands:
            commands["test"] = _command_entry(
                ["python", "-m", "pytest"],
                timeout_seconds=DEFAULT_TIMEOUT,
            )
        if "build" not in commands:
            commands["build"] = _command_entry(
                ["python", "-m", "build"],
                timeout_seconds=BUILD_TIMEOUT,
            )

    solution_files = sorted(root.glob("*.sln"))
    if solution_files:
        tags.append("dotnet")
        solution = solution_files[0]
        if "build" not in commands:
            commands["build"] = _command_entry(
                ["dotnet", "build", solution.name],
                timeout_seconds=BUILD_TIMEOUT,
            )
        if "test" not in commands:
            commands["test"] = _command_entry(
                ["dotnet", "test", solution.name],
                timeout_seconds=DEFAULT_TIMEOUT,
            )
        if len(solution_files) > 1:
            unresolved.append(
                {
                    "field": "commands.dotnet_solution",
                    "question": "Select the solution file used by each .NET command.",
                }
            )

    if "test" not in commands:
        commands["test"] = _command_entry(
            ["python", "-c", "print('ok')"],
            timeout_seconds=60,
        )
        unresolved.append(
            {
                "field": "commands.test",
                "question": "No test command discovered; confirm the fallback verify command.",
            }
        )

    if "build" not in commands:
        unresolved.append(
            {
                "field": "commands.build",
                "question": "Supply the build argv, cwd, and timeout.",
            }
        )

    verification_commands = ["test"]
    if "build" in commands:
        verification_commands = ["build", "test"]

    proposed_manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "id": app_id,
        "commands": commands,
        "verification": {
            "implementation": verification_commands,
            "post_repair": list(verification_commands),
        },
        "builders": {
            "default_owner": DEFAULT_BUILDER,
            "routes": [
                {
                    "id": "default",
                    "owner": DEFAULT_BUILDER,
                    "priority": 0,
                    "globs": ["**/*"],
                }
            ],
        },
    }
    if tags:
        proposed_manifest["tags"] = sorted(set(tags))

    unresolved.extend(
        [
            {
                "field": "id",
                "question": f"Confirm the stable application id {app_id!r}.",
            },
            {
                "field": "verification",
                "question": "Confirm implementation and post-repair command order.",
            },
            {
                "field": "builders",
                "question": "Confirm the default builder and routing globs.",
            },
        ]
    )

    return {
        "workspace": str(root),
        "manifest_path": str(manifest_path(root)),
        "proposed_manifest": proposed_manifest,
        "unresolved_questions": unresolved,
        "ignore_issues": _gitignore_issues(root),
    }


def init_app_manifest(
    workspace: Path,
    manifest_file: Path,
    foundry_bundle: Path,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    root = workspace.resolve()
    if not root.is_dir():
        raise ValueError(f"Workspace does not exist: {root}")

    source = manifest_file.resolve()
    manifest = _load_yaml_mapping(source, "Manifest input")
    errors = validate_manifest_data(manifest, foundry_bundle)
    if errors:
        raise ValueError("Manifest validation failed: " + "; ".join(errors))

    target = manifest_path(root)
    ignore_error = _validate_manifest_not_ignored(root)
    if ignore_error:
        raise ValueError(
            "Git ignore rules hide .foundry/app.yaml. Ignore only .foundry/runs/. "
            f"Evidence: {ignore_error}"
        )

    rendered = render_manifest(manifest)
    target_existed = target.is_file()
    existing_same = False
    if target_existed:
        try:
            existing = _load_yaml_mapping(target, "Application manifest")
            existing_same = existing == manifest
        except (FileNotFoundError, ValueError):
            existing_same = False
        if not existing_same and not force and not dry_run:
            raise FileExistsError(f"Application manifest already exists: {target}")

    changed = not existing_same
    written = False
    if not dry_run and changed:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
        written = True

    validation = validate_manifest(root, foundry_bundle) if written or (target_existed and existing_same) else {
        "ok": True,
        "manifest_id": manifest.get("id"),
        "errors": [],
    }

    return {
        "workspace": str(root),
        "manifest_path": str(target),
        "manifest_id": manifest.get("id"),
        "dry_run": dry_run,
        "changed": changed,
        "written": written,
        "force": force,
        "requires_force": bool(target_existed and changed and not force),
        "rendered_manifest": rendered if dry_run else None,
        "validated": validation.get("ok") is True,
        "validation_errors": validation.get("errors") or [],
    }
