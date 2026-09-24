"""Foundry application-manifest loading, validation, and canonicalization.

Canonical manifests flatten platform command variants and normalize relative
paths to ``/``. Declared list order is preserved because verification order can
be executable policy; JSON object keys are sorted only when serializing or hashing.
"""

from __future__ import annotations

import fnmatch
import json
import math
import os
import re
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError:  # pragma: no cover - dependency guard
    yaml = None

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - dependency guard
    Draft202012Validator = None

import foundry_lineage
import foundry_protocol
import foundry_store


FOUNDRY_ROOT = Path(__file__).resolve().parents[1]
APP_MANIFEST_RELATIVE_PATH = Path(".foundry") / "app.yaml"
RUN_MANIFEST_FILENAME = "app-manifest.json"
APP_MANIFEST_SCHEMA_PATH = FOUNDRY_ROOT / "schemas" / "app-manifest.schema.json"
SUPPORTED_SCHEMA_VERSION = 1
RUN_MODES = frozenset({"implementation", "analysis"})
DRIVE_PATH_RE = re.compile(r"^[A-Za-z]:")


class AppManifestError(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        errors: list[str] | None = None,
        required_input: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.errors = errors or []
        self.required_input = required_input


class _UniqueKeyLoader(yaml.SafeLoader if yaml is not None else object):
    """Safe YAML loader that rejects keys hidden by YAML's last-value-wins rule."""


if yaml is not None:

    def _construct_unique_mapping(
        loader: _UniqueKeyLoader,
        node: Any,
        deep: bool = False,
    ) -> dict[Any, Any]:
        loader.flatten_mapping(node)
        mapping: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            try:
                duplicate = key in mapping
            except TypeError as exc:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "found unhashable key",
                    key_node.start_mark,
                ) from exc
            if duplicate:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"found duplicate key {key!r}",
                    key_node.start_mark,
                )
            mapping[key] = loader.construct_object(value_node, deep=deep)
        return mapping

    _UniqueKeyLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        _construct_unique_mapping,
    )


def current_platform_key(platform: str | None = None) -> str:
    value = (platform or ("windows" if os.name == "nt" else "posix")).lower()
    if value in {"windows", "win32", "nt"}:
        return "windows"
    if value in {"posix", "linux", "darwin", "macos"}:
        return "posix"
    raise AppManifestError(
        "UNSUPPORTED_APP_PLATFORM",
        f"Unsupported application-manifest platform: {platform!r}.",
        required_input="platform",
    )


def app_manifest_path(app_folder: str | Path) -> Path:
    return Path(app_folder).resolve() / APP_MANIFEST_RELATIVE_PATH


def _load_yaml_mapping(
    path: Path,
    *,
    missing_code: str,
    missing_label: str,
) -> dict[str, Any]:
    if yaml is None:
        raise AppManifestError(
            "MISSING_DEPENDENCY",
            "PyYAML is required to load .foundry/app.yaml.",
            required_input="PyYAML",
        )
    if not path.is_file():
        message = f"{missing_label} not found: {path}"
        if missing_code == "APP_MANIFEST_MISSING":
            message = (
                f"{missing_label} not found: {path}. "
                "Create one with /foundry-app-bootstrap "
                "(or foundry app discover / app init). "
                "Do not infer commands from AGENTS.md, solution files, or Makefiles."
            )
        raise AppManifestError(
            missing_code,
            message,
            required_input=str(path),
        )
    try:
        value = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise AppManifestError(
            "APP_MANIFEST_YAML_INVALID",
            f"Application manifest is not valid YAML: {path}",
            errors=[str(exc)],
        ) from exc
    if not isinstance(value, dict):
        raise AppManifestError(
            "APP_MANIFEST_ROOT_INVALID",
            f"{missing_label} root must be an object.",
        )
    return value


def load_app_manifest(app_folder: str | Path) -> tuple[Path, dict[str, Any]]:
    path = app_manifest_path(app_folder)
    value = _load_yaml_mapping(
        path,
        missing_code="APP_MANIFEST_MISSING",
        missing_label="Application manifest",
    )
    return path, value


def _load_schema() -> dict[str, Any]:
    if Draft202012Validator is None:
        raise AppManifestError(
            "MISSING_DEPENDENCY",
            "jsonschema is required to validate .foundry/app.yaml.",
            required_input="jsonschema",
        )
    try:
        schema = json.loads(APP_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover - packaged invariant
        raise AppManifestError(
            "APP_MANIFEST_SCHEMA_MISSING",
            f"App-manifest schema could not be loaded: {APP_MANIFEST_SCHEMA_PATH}",
            errors=[str(exc)],
        ) from exc
    return schema


def _validate_json_compatible(value: Any, *, path: str = "<root>") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise AppManifestError(
                    "APP_MANIFEST_JSON_INCOMPATIBLE",
                    "Application manifest object keys must be strings.",
                    errors=[f"{path}: {key!r}"],
                )
            _validate_json_compatible(child, path=f"{path}/{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _validate_json_compatible(child, path=f"{path}/{index}")
        return
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float) and math.isfinite(value):
        return
    raise AppManifestError(
        "APP_MANIFEST_JSON_INCOMPATIBLE",
        "Application manifest values must be representable as canonical JSON.",
        errors=[f"{path}: {type(value).__name__}"],
    )


def _normalized_relative_path(value: str) -> str:
    return value.replace("\\", "/")


def _is_unsafe_relative_path(value: str) -> bool:
    normalized = _normalized_relative_path(value)
    return (
        not normalized
        or normalized.startswith("/")
        or bool(DRIVE_PATH_RE.match(normalized))
        or ".." in normalized.split("/")
    )


def _validate_command_cwds(
    manifest: dict[str, Any],
    *,
    app_folder: Path | None = None,
) -> None:
    commands = manifest.get("commands")
    if not isinstance(commands, dict):
        return
    for command_name, variants in commands.items():
        if not isinstance(variants, dict):
            continue
        for platform_name, command in variants.items():
            if not isinstance(command, dict):
                continue
            cwd = command.get("cwd")
            if isinstance(cwd, str) and _is_unsafe_relative_path(cwd):
                raise AppManifestError(
                    "APP_MANIFEST_CWD_UNSAFE",
                    f"Command {command_name!r} ({platform_name}) has unsafe cwd {cwd!r}.",
                    errors=[f"commands/{command_name}/{platform_name}/cwd"],
                )
            if isinstance(cwd, str) and app_folder is not None:
                root = app_folder.resolve()
                resolved = (root / cwd).resolve()
                if not resolved.is_relative_to(root):
                    raise AppManifestError(
                        "APP_MANIFEST_CWD_UNSAFE",
                        f"Command {command_name!r} ({platform_name}) cwd escapes the app folder.",
                        errors=[f"commands/{command_name}/{platform_name}/cwd"],
                    )


def validate_schema(
    manifest: dict[str, Any],
    *,
    app_folder: Path | None = None,
) -> None:
    version = manifest.get("schema_version")
    if version != SUPPORTED_SCHEMA_VERSION:
        raise AppManifestError(
            "APP_MANIFEST_VERSION_UNSUPPORTED",
            f"Application manifest must use schema_version {SUPPORTED_SCHEMA_VERSION}.",
            errors=[f"got: {version!r}"],
        )
    _validate_json_compatible(manifest)
    schema = _load_schema()
    errors = sorted(Draft202012Validator(schema).iter_errors(manifest), key=str)
    if errors:
        rendered = [
            f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
            for error in errors
        ]
        if all(
            list(error.absolute_path)[-1:] == ["cwd"]
            and error.validator == "pattern"
            for error in errors
        ):
            raise AppManifestError(
                "APP_MANIFEST_CWD_UNSAFE",
                "Application manifest contains an unsafe command cwd.",
                errors=rendered,
            )
        raise AppManifestError(
            "APP_MANIFEST_SCHEMA_INVALID",
            f"Application manifest failed schema validation with {len(errors)} error(s).",
            errors=rendered,
        )
    _validate_command_cwds(manifest, app_folder=app_folder)


def resolve_commands(
    manifest: dict[str, Any],
    *,
    platform: str | None = None,
    command_names: Iterable[str] | None = None,
) -> dict[str, dict[str, Any]]:
    platform_key = current_platform_key(platform)
    resolved: dict[str, dict[str, Any]] = {}
    names = list(command_names) if command_names is not None else list(manifest["commands"])
    for command_name in names:
        variants = manifest["commands"][command_name]
        command = variants.get(platform_key) or variants.get("default")
        if command is None:
            raise AppManifestError(
                "APP_MANIFEST_PLATFORM_COMMAND_MISSING",
                f"Command {command_name!r} has no {platform_key!r} or default definition.",
                errors=[f"commands/{command_name}"],
            )
        resolved[command_name] = {
            "argv": list(command["argv"]),
            "cwd": _normalized_relative_path(command["cwd"]),
            "timeout_seconds": command["timeout_seconds"],
        }
    return resolved


def _validate_command_references(
    manifest: dict[str, Any],
) -> None:
    commands = manifest["commands"]
    for policy_name, references in manifest["verification"].items():
        missing = [name for name in references if name not in commands]
        if missing:
            raise AppManifestError(
                "APP_MANIFEST_COMMAND_REFERENCE_UNKNOWN",
                f"verification.{policy_name} references unknown commands.",
                errors=missing,
            )


def _registered_agents(registry_path: Path | None = None) -> set[str]:
    try:
        registry = foundry_protocol.load_agent_registry(registry_path)
    except foundry_protocol.ProtocolError as exc:
        raise AppManifestError(
            "APP_MANIFEST_AGENT_REGISTRY_INVALID",
            exc.message,
            errors=exc.errors,
        ) from exc
    return set(registry["agents"])


def _validate_glob(glob: str, *, route_id: str) -> str:
    normalized = _normalized_relative_path(glob)
    if _is_unsafe_relative_path(normalized):
        raise AppManifestError(
            "APP_MANIFEST_BUILDER_GLOB_UNSAFE",
            f"Builder route {route_id!r} has unsafe glob {glob!r}.",
            errors=[f"builders/routes/{route_id}/globs"],
        )
    return normalized


def _segment_provably_disjoint(first: str, second: str) -> bool:
    meta = "*?["
    first_has_meta = any(character in first for character in meta)
    second_has_meta = any(character in second for character in meta)
    if not first_has_meta and not second_has_meta:
        return first != second
    if not first_has_meta:
        return not fnmatch.fnmatchcase(first, second)
    if not second_has_meta:
        return not fnmatch.fnmatchcase(second, first)

    def literal_prefix(pattern: str) -> str:
        index = min(
            (pattern.find(character) for character in meta if character in pattern),
            default=len(pattern),
        )
        return pattern[:index]

    def literal_suffix(pattern: str) -> str:
        index = max(pattern.rfind(character) for character in "*?]")
        return pattern[index + 1 :]

    first_prefix = literal_prefix(first)
    second_prefix = literal_prefix(second)
    if (
        first_prefix
        and second_prefix
        and not first_prefix.startswith(second_prefix)
        and not second_prefix.startswith(first_prefix)
    ):
        return True
    first_suffix = literal_suffix(first)
    second_suffix = literal_suffix(second)
    return bool(
        first_suffix
        and second_suffix
        and not first_suffix.endswith(second_suffix)
        and not second_suffix.endswith(first_suffix)
    )


def _globs_provably_disjoint(first: str, second: str) -> bool:
    first_parts = _normalized_relative_path(first).split("/")
    second_parts = _normalized_relative_path(second).split("/")
    if "**" not in first_parts and "**" not in second_parts:
        if len(first_parts) != len(second_parts):
            return True
        return any(
            _segment_provably_disjoint(left, right)
            for left, right in zip(first_parts, second_parts)
        )

    for left, right in zip(first_parts, second_parts):
        if left == "**" or right == "**":
            break
        if _segment_provably_disjoint(left, right):
            return True
    for left, right in zip(reversed(first_parts), reversed(second_parts)):
        if left == "**" or right == "**":
            break
        if _segment_provably_disjoint(left, right):
            return True
    return False


def validate_builders(
    manifest: dict[str, Any],
    *,
    registry_path: Path | None = None,
) -> None:
    builders = manifest["builders"]
    routes = builders.get("routes") or []
    route_ids: set[str] = set()
    owners: set[str] = set()
    if builders.get("default_owner"):
        owners.add(builders["default_owner"])
    for route in routes:
        route_id = route["id"]
        if route_id in route_ids:
            raise AppManifestError(
                "APP_MANIFEST_BUILDER_ROUTE_DUPLICATE",
                f"Builder route id {route_id!r} is duplicated.",
                errors=[route_id],
            )
        route_ids.add(route_id)
        owners.add(route["owner"])
        for raw_glob in route["globs"]:
            _validate_glob(raw_glob, route_id=route_id)
    for index, route in enumerate(routes):
        for other in routes[index + 1 :]:
            if route["priority"] != other["priority"]:
                continue
            overlap_possible = any(
                not _globs_provably_disjoint(first, second)
                for first in route["globs"]
                for second in other["globs"]
            )
            if overlap_possible:
                raise AppManifestError(
                    "APP_MANIFEST_BUILDER_ROUTE_TIE",
                    f"Equal-priority builder routes {route['id']!r} and "
                    f"{other['id']!r} are not provably disjoint.",
                    errors=[route["id"], other["id"]],
                )
    unknown = sorted(owners - _registered_agents(registry_path))
    if unknown:
        raise AppManifestError(
            "APP_MANIFEST_BUILDER_OWNER_UNKNOWN",
            "Application manifest names unregistered builder owners.",
            errors=unknown,
        )


def validate_capabilities(manifest: dict[str, Any], *, run_mode: str | None) -> None:
    if run_mode is None:
        return
    if run_mode not in RUN_MODES:
        raise AppManifestError(
            "APP_MANIFEST_RUN_MODE_UNSUPPORTED",
            f"Unsupported app-manifest run mode: {run_mode!r}.",
            required_input="run_mode",
        )
    if run_mode == "analysis":
        return
    verification = manifest["verification"]
    if not verification["implementation"]:
        raise AppManifestError(
            "APP_MANIFEST_IMPLEMENTATION_COMMANDS_REQUIRED",
            "Implementation runs require at least one verification.implementation command.",
        )
    if not verification["post_repair"]:
        raise AppManifestError(
            "APP_MANIFEST_POST_REPAIR_COMMANDS_REQUIRED",
            "Implementation runs require at least one verification.post_repair command.",
        )
    if not manifest["builders"].get("default_owner"):
        raise AppManifestError(
            "APP_MANIFEST_DEFAULT_BUILDER_REQUIRED",
            "Implementation runs require builders.default_owner.",
        )


def validate_documentation_model(manifest: dict[str, Any]) -> None:
    documentation = manifest.get("documentation")
    if not isinstance(documentation, dict):
        return
    model = documentation.get("model")
    config = documentation.get("config")
    import foundry_docs

    try:
        backend = foundry_docs.resolve_documentation_backend(str(model or ""))
        backend.validate_config(config)
    except foundry_docs.DocsError as exc:
        code = exc.error_code
        if code != "APP_MANIFEST_DOCUMENTATION_MODEL_UNKNOWN":
            code = "APP_MANIFEST_DOCUMENTATION_CONFIG_INVALID"
        raise AppManifestError(
            code,
            exc.message,
            errors=list((exc.extra or {}).get("errors") or []),
        ) from exc


def canonicalize_manifest(
    manifest: dict[str, Any],
    *,
    platform: str | None = None,
    command_names: Iterable[str] | None = None,
) -> dict[str, Any]:
    resolved_commands = resolve_commands(
        manifest,
        platform=platform,
        command_names=command_names,
    )
    builders = json.loads(json.dumps(manifest["builders"]))
    for route in builders.get("routes") or []:
        route["globs"] = [_normalized_relative_path(pattern) for pattern in route["globs"]]
    resolved_names = set(resolved_commands)
    if not resolved_names:
        verification: dict[str, Any] = {}
    else:
        verification = {
            policy: list(references)
            for policy, references in manifest["verification"].items()
            if set(references).issubset(resolved_names)
        }
    canonical: dict[str, Any] = {
        "schema_version": manifest["schema_version"],
        "id": manifest["id"],
        "commands": resolved_commands,
        "verification": verification,
        "builders": builders,
        "documentation": json.loads(json.dumps(manifest["documentation"])),
    }
    if "tags" in manifest:
        canonical["tags"] = list(manifest["tags"])
    return canonical


def canonical_json(manifest: dict[str, Any]) -> str:
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def manifest_hash(manifest: dict[str, Any]) -> str:
    return foundry_lineage.digest_value(manifest)


def write_run_manifest_snapshot(run_dir: Path, manifest: dict[str, Any]) -> Path:
    """Write the canonical, platform-resolved manifest frozen for one run."""
    _validate_run_manifest_snapshot(manifest)
    target = run_dir / RUN_MANIFEST_FILENAME
    foundry_store.atomic_write_text(target, canonical_json(manifest) + "\n")
    return target


def _validate_run_manifest_snapshot(manifest: Any) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise AppManifestError(
            "APP_MANIFEST_SNAPSHOT_INVALID",
            "Run app-manifest snapshot must be a JSON object.",
        )
    required = (
        "schema_version",
        "id",
        "commands",
        "verification",
        "builders",
        "documentation",
    )
    missing = [key for key in required if key not in manifest]
    if missing:
        raise AppManifestError(
            "APP_MANIFEST_SNAPSHOT_INVALID",
            "Run app-manifest snapshot is missing required fields.",
            errors=missing,
        )
    if manifest.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        raise AppManifestError(
            "APP_MANIFEST_SNAPSHOT_INVALID",
            f"Run app-manifest snapshot must use schema_version {SUPPORTED_SCHEMA_VERSION}.",
        )
    if not isinstance(manifest.get("id"), str) or not manifest["id"]:
        raise AppManifestError(
            "APP_MANIFEST_SNAPSHOT_INVALID",
            "Run app-manifest snapshot id must be a non-empty string.",
        )
    for key in ("commands", "verification", "builders", "documentation"):
        if not isinstance(manifest.get(key), dict):
            raise AppManifestError(
                "APP_MANIFEST_SNAPSHOT_INVALID",
                f"Run app-manifest snapshot {key} must be an object.",
            )
    _validate_json_compatible(manifest)
    return manifest


def load_run_manifest_snapshot(run_dir: Path) -> dict[str, Any]:
    source = run_dir / RUN_MANIFEST_FILENAME
    if not source.is_file():
        raise AppManifestError(
            "APP_MANIFEST_SNAPSHOT_MISSING",
            f"Run app-manifest snapshot not found: {source}",
            required_input="appManifestSnapshot",
        )
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AppManifestError(
            "APP_MANIFEST_SNAPSHOT_INVALID",
            f"Could not read run app-manifest snapshot: {exc}",
        ) from exc
    return _validate_run_manifest_snapshot(value)


def manifest_project_context(
    state: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    _validate_run_manifest_snapshot(snapshot)
    return {
        "app_manifest_id": state.get("app_manifest_id"),
        "app_manifest_hash": state.get("app_manifest_hash"),
        "app_manifest_platform": state.get("app_manifest_platform"),
        "app_folder": state.get("app_folder"),
        "tags": list(snapshot.get("tags") or []),
        "commands": json.loads(json.dumps(snapshot["commands"])),
        "verification": json.loads(json.dumps(snapshot["verification"])),
        "builders": json.loads(json.dumps(snapshot["builders"])),
        "documentation": json.loads(json.dumps(snapshot["documentation"])),
    }


def assert_run_manifest_current(
    state: dict[str, Any],
    run_dir: Path,
    *,
    check_live: bool = True,
) -> dict[str, Any]:
    snapshot = load_run_manifest_snapshot(run_dir)
    expected_id = state.get("app_manifest_id")
    expected_hash = state.get("app_manifest_hash")
    snapshot_hash = manifest_hash(snapshot)
    if snapshot.get("id") != expected_id or snapshot_hash != expected_hash:
        raise AppManifestError(
            "APP_MANIFEST_SNAPSHOT_MISMATCH",
            "Run app-manifest snapshot does not match the identity frozen in state.",
            errors=[
                f"id: expected {expected_id!r}, got {snapshot.get('id')!r}",
                f"hash: expected {expected_hash!r}, got {snapshot_hash!r}",
            ],
        )
    if not check_live:
        return snapshot
    try:
        live = validate_app_manifest(
            Path(str(state.get("app_folder") or "")),
            run_mode=str(state.get("run_mode") or ""),
            platform=str(state.get("app_manifest_platform") or ""),
        )
    except AppManifestError as exc:
        raise AppManifestError(
            "APP_MANIFEST_DRIFT",
            "Live .foundry/app.yaml no longer validates against the run snapshot; abandon and restart the run.",
            errors=[f"{exc.error_code}: {exc.message}", *exc.errors],
        ) from exc
    if live["app_manifest_id"] != expected_id or live["app_manifest_hash"] != expected_hash:
        raise AppManifestError(
            "APP_MANIFEST_DRIFT",
            "Live .foundry/app.yaml changed after run initialization; abandon and restart the run.",
            errors=[
                f"id: expected {expected_id!r}, got {live['app_manifest_id']!r}",
                f"hash: expected {expected_hash!r}, got {live['app_manifest_hash']!r}",
            ],
        )
    return snapshot


def validate_manifest_value(
    manifest: dict[str, Any],
    *,
    app_folder: str | Path,
    manifest_path: str | Path,
    run_mode: str | None = None,
    platform: str | None = None,
    registry_path: Path | None = None,
) -> dict[str, Any]:
    validate_schema(manifest, app_folder=Path(app_folder))
    _validate_command_references(manifest)
    validate_builders(manifest, registry_path=registry_path)
    validate_capabilities(manifest, run_mode=run_mode)
    validate_documentation_model(manifest)
    required_commands: set[str] | None = None
    if run_mode == "implementation":
        required_commands = set(manifest["verification"]["implementation"])
        required_commands.update(manifest["verification"]["post_repair"])
    elif run_mode == "analysis":
        required_commands = set()
    canonical = canonicalize_manifest(
        manifest,
        platform=platform,
        command_names=sorted(required_commands) if required_commands is not None else None,
    )
    return {
        "manifest_path": str(manifest_path),
        "app_manifest_id": canonical["id"],
        "app_manifest_hash": manifest_hash(canonical),
        "platform": current_platform_key(platform),
        "run_mode": run_mode,
        "manifest": canonical,
    }


def validate_app_manifest(
    app_folder: str | Path,
    *,
    run_mode: str | None = None,
    platform: str | None = None,
    registry_path: Path | None = None,
) -> dict[str, Any]:
    path, manifest = load_app_manifest(app_folder)
    return validate_manifest_value(
        manifest,
        app_folder=app_folder,
        manifest_path=path,
        run_mode=run_mode,
        platform=platform,
        registry_path=registry_path,
    )


def _repo_relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _candidate_command(
    argv: list[str],
    *,
    evidence: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    return {
        "default": {
            "argv": argv,
            "cwd": ".",
            "timeout_seconds": timeout_seconds,
        },
        "evidence": [evidence],
    }


def discover_app(app_folder: str | Path) -> dict[str, Any]:
    root = Path(app_folder).resolve()
    if not root.is_dir():
        raise AppManifestError(
            "INVALID_APP_FOLDER",
            f"Application folder does not exist: {root}",
            required_input="app_folder",
        )

    candidate_id = re.sub(r"[^a-z0-9]+", "-", root.name.lower()).strip("-") or "app"
    tags: list[dict[str, Any]] = []
    commands: dict[str, list[dict[str, Any]]] = {
        "build": [],
        "test": [],
        "precommit": [],
    }
    routes: list[dict[str, Any]] = []
    documentation: list[dict[str, Any]] = []

    makefile = next(
        (candidate for candidate in (root / "Makefile", root / "makefile") if candidate.is_file()),
        None,
    )
    if makefile is not None:
        makefile_text = makefile.read_text(encoding="utf-8", errors="replace")
        targets = {
            match.group(1)
            for match in re.finditer(r"(?m)^([A-Za-z0-9][A-Za-z0-9_.-]*)\s*:(?!=)", makefile_text)
        }
        evidence = _repo_relative(root, makefile)
        for name, timeout in (("build", 900), ("test", 1200), ("precommit", 1800)):
            if name in targets:
                commands[name].append(
                    _candidate_command(
                        ["make", name],
                        evidence=evidence,
                        timeout_seconds=timeout,
                    )
                )

    go_mod = root / "go.mod"
    if go_mod.is_file():
        evidence = _repo_relative(root, go_mod)
        tags.append({"value": "go", "evidence": [evidence]})
        commands["build"].append(
            _candidate_command(
                ["go", "build", "./..."],
                evidence=evidence,
                timeout_seconds=900,
            )
        )
        commands["test"].append(
            _candidate_command(
                ["go", "test", "./..."],
                evidence=evidence,
                timeout_seconds=1200,
            )
        )

    solution_files = sorted(root.glob("*.sln"))
    if solution_files:
        solution_evidence = [_repo_relative(root, solution) for solution in solution_files]
        tags.append({"value": "dotnet", "evidence": solution_evidence})
        for solution in solution_files:
            evidence = _repo_relative(root, solution)
            commands["build"].append(
                _candidate_command(
                    ["dotnet", "build", solution.name],
                    evidence=evidence,
                    timeout_seconds=900,
                )
            )
            commands["test"].append(
                _candidate_command(
                    ["dotnet", "test", solution.name],
                    evidence=evidence,
                    timeout_seconds=1200,
                )
            )

    package_json = root / "package.json"
    if package_json.is_file():
        evidence = _repo_relative(root, package_json)
        tags.append({"value": "node", "evidence": [evidence]})
        try:
            package = json.loads(package_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            package = {}
        scripts = package.get("scripts") if isinstance(package, dict) else {}
        if isinstance(scripts, dict):
            for command_name, script_names in {
                "build": ("build",),
                "test": ("test",),
                "precommit": ("precommit", "check"),
            }.items():
                for script_name in script_names:
                    if script_name in scripts:
                        commands[command_name].append(
                            _candidate_command(
                                ["npm", "run", script_name],
                                evidence=evidence,
                                timeout_seconds=1800 if command_name == "precommit" else 1200,
                            )
                        )
                        break

    client_globs: list[str] = []
    client_evidence: list[str] = []
    for extension in ("js", "ts", "tsx", "css", "html"):
        match = next(
            (
                path
                for path in root.rglob(f"*.{extension}")
                if not {".git", ".foundry", ".deps", "node_modules"}.intersection(path.parts)
            ),
            None,
        )
        if match is not None:
            client_globs.append(f"**/*.{extension}")
            client_evidence.append(_repo_relative(root, match))
    if client_globs:
        routes.append(
            {
                "id": "client",
                "owner": "client-builder",
                "priority": 200,
                "globs": client_globs,
                "evidence": client_evidence,
            }
        )

    route_candidates = (
        ("backend", "backend-builder", 100, ("cmd/**", "internal/**", "migrations/**")),
    )
    for route_id, owner, priority, globs in route_candidates:
        evidence_dirs = [
            name
            for name in (glob.split("/", 1)[0] for glob in globs if not glob.startswith("**"))
            if (root / name).exists()
        ]
        if evidence_dirs:
            routes.append(
                {
                    "id": route_id,
                    "owner": owner,
                    "priority": priority,
                    "globs": list(globs),
                    "evidence": sorted(set(evidence_dirs)),
                }
            )

    feature_docs = root / "docs" / "features"
    if feature_docs.is_dir():
        documentation.append(
            {
                "model": "feature-records",
                "config": {
                    "include": ["docs/features/**"],
                    "exclude": ["docs/plans/**", ".cursor/skills/**"],
                },
                "evidence": ["docs/features/"],
            }
        )
    agents_file = root / "AGENTS.md"
    if solution_files and agents_file.is_file():
        documentation.append(
            {
                "model": "iot-agents-prd",
                "config": {},
                "evidence": [_repo_relative(root, agents_file), _repo_relative(root, solution_files[0])],
            }
        )

    unresolved: list[dict[str, str]] = [
        {
            "field": "id",
            "question": f"Confirm the stable application id {candidate_id!r}.",
        },
        {
            "field": "verification",
            "question": "Confirm implementation and post-repair command order.",
        },
        {
            "field": "builders",
            "question": "Confirm the default builder and every routing glob.",
        },
        {
            "field": "documentation",
            "question": "Select and configure a registered documentation model.",
        },
    ]
    for required_command in ("build", "test"):
        if not commands[required_command]:
            unresolved.append(
                {
                    "field": f"commands.{required_command}",
                    "question": f"Supply the {required_command} argv, cwd, and timeout.",
                }
            )
    if len(solution_files) > 1:
        unresolved.append(
            {
                "field": "commands.dotnet_solution",
                "question": "Select the solution file used by each .NET command.",
            }
        )

    ignore_issues: list[dict[str, str]] = []
    gitignore = root / ".gitignore"
    if gitignore.is_file():
        for line_number, raw_line in enumerate(
            gitignore.read_text(encoding="utf-8", errors="replace").splitlines(),
            start=1,
        ):
            rule = raw_line.strip()
            if rule in {".foundry", ".foundry/", "/.foundry", "/.foundry/"}:
                ignore_issues.append(
                    {
                        "file": ".gitignore",
                        "line": str(line_number),
                        "rule": rule,
                        "replacement": ".foundry/runs/",
                    }
                )

    return {
        "app_folder": str(root),
        "manifest_path": str(app_manifest_path(root)),
        "candidates": {
            "id": {"value": candidate_id, "evidence": [root.name]},
            "tags": tags,
            "commands": commands,
            "builder_routes": routes,
            "documentation": documentation,
        },
        "unresolved_questions": unresolved,
        "ignore_issues": ignore_issues,
    }


def _ordered_authoring_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    order = ("schema_version", "id", "tags", "commands", "verification", "builders", "documentation")
    return {
        key: json.loads(json.dumps(manifest[key]))
        for key in order
        if key in manifest
    }


def render_authoring_manifest(manifest: dict[str, Any]) -> str:
    if yaml is None:
        raise AppManifestError(
            "MISSING_DEPENDENCY",
            "PyYAML is required to write .foundry/app.yaml.",
            required_input="PyYAML",
        )
    return yaml.safe_dump(
        _ordered_authoring_manifest(manifest),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )


def _validate_manifest_not_ignored(root: Path) -> None:
    try:
        result = subprocess.run(
            [
                "git",
                "check-ignore",
                "-v",
                "--no-index",
                APP_MANIFEST_RELATIVE_PATH.as_posix(),
            ],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return
    if result.returncode == 0:
        evidence = result.stdout.strip()
        raise AppManifestError(
            "APP_MANIFEST_GITIGNORE_BLOCKED",
            "Git ignore rules hide .foundry/app.yaml. Ignore only .foundry/runs/.",
            errors=[evidence] if evidence else [],
        )


def init_app_manifest(
    app_folder: str | Path,
    manifest_file: str | Path,
    *,
    run_mode: str,
    dry_run: bool = False,
    force: bool = False,
    platform: str | None = None,
    registry_path: Path | None = None,
) -> dict[str, Any]:
    root = Path(app_folder).resolve()
    if not root.is_dir():
        raise AppManifestError(
            "INVALID_APP_FOLDER",
            f"Application folder does not exist: {root}",
            required_input="app_folder",
        )
    source = Path(manifest_file).resolve()
    manifest = _load_yaml_mapping(
        source,
        missing_code="APP_MANIFEST_SOURCE_MISSING",
        missing_label="App-manifest input",
    )
    target = app_manifest_path(root)
    context = validate_manifest_value(
        manifest,
        app_folder=root,
        manifest_path=target,
        run_mode=run_mode,
        platform=platform,
        registry_path=registry_path,
    )
    rendered = render_authoring_manifest(manifest)
    _validate_manifest_not_ignored(root)

    existing_same = False
    target_existed = target.is_file()
    if target_existed:
        try:
            existing = _load_yaml_mapping(
                target,
                missing_code="APP_MANIFEST_MISSING",
                missing_label="Application manifest",
            )
            existing_same = existing == manifest
        except AppManifestError:
            existing_same = False
        if not existing_same and not force and not dry_run:
            raise AppManifestError(
                "APP_MANIFEST_EXISTS",
                f"Application manifest already exists: {target}",
                required_input="force",
            )

    changed = not existing_same
    if not dry_run and changed:
        target.parent.mkdir(parents=True, exist_ok=True)
        foundry_store.atomic_write_text(target, rendered)

    return {
        **{key: value for key, value in context.items() if key != "manifest"},
        "dry_run": dry_run,
        "changed": changed,
        "written": bool(changed and not dry_run),
        "force": force,
        "requires_force": bool(target_existed and changed and not force),
        "rendered_manifest": rendered if dry_run else None,
    }


def glob_matches(path: str, pattern: str) -> bool:
    normalized_path = _normalized_relative_path(path)
    if normalized_path.startswith("./"):
        normalized_path = normalized_path[2:]
    path_parts = tuple(normalized_path.split("/"))
    pattern_parts = tuple(_normalized_relative_path(pattern).split("/"))

    @lru_cache(maxsize=None)
    def matches(path_index: int, pattern_index: int) -> bool:
        if pattern_index == len(pattern_parts):
            return path_index == len(path_parts)
        pattern_part = pattern_parts[pattern_index]
        if pattern_part == "**":
            return matches(path_index, pattern_index + 1) or (
                path_index < len(path_parts)
                and matches(path_index + 1, pattern_index)
            )
        return (
            path_index < len(path_parts)
            and fnmatch.fnmatchcase(path_parts[path_index], pattern_part)
            and matches(path_index + 1, pattern_index + 1)
        )

    return matches(0, 0)


def resolve_builder_owner(manifest: dict[str, Any], path: str) -> str:
    if _is_unsafe_relative_path(path):
        raise AppManifestError(
            "APP_MANIFEST_FILES_HINT_UNSAFE",
            f"Builder routing path must be relative to the app folder: {path!r}.",
            errors=[path],
        )
    matches: list[dict[str, Any]] = []
    for route in manifest["builders"].get("routes") or []:
        if any(glob_matches(path, pattern) for pattern in route["globs"]):
            matches.append(route)
    if not matches:
        owner = manifest["builders"].get("default_owner")
        if not owner:
            raise AppManifestError(
                "APP_MANIFEST_DEFAULT_BUILDER_REQUIRED",
                f"No builder route matches {path!r} and no default owner is configured.",
            )
        return owner
    winning_priority = max(route["priority"] for route in matches)
    winners = [route for route in matches if route["priority"] == winning_priority]
    if len(winners) > 1:
        raise AppManifestError(
            "APP_MANIFEST_BUILDER_ROUTE_TIE",
            f"Builder routes tie for {path!r} at priority {winning_priority}.",
            errors=sorted(route["id"] for route in winners),
        )
    return winners[0]["owner"]


def resolve_builder_for_paths(manifest: dict[str, Any], paths: Iterable[str]) -> str:
    owners = {resolve_builder_owner(manifest, path) for path in paths}
    if not owners:
        raise AppManifestError(
            "APP_MANIFEST_FILES_HINT_REQUIRED",
            "Builder routing requires at least one hinted path.",
        )
    if len(owners) > 1:
        raise AppManifestError(
            "APP_MANIFEST_MULTIPLE_BUILDER_OWNERS",
            "Hinted paths resolve to more than one builder owner; split the work item.",
            errors=sorted(owners),
        )
    return next(iter(owners))


REPAIR_OWNER = "repairer"


def work_item_is_repair(item: dict[str, Any]) -> bool:
    return str(item.get("kind") or "") == "repair"


def resolve_work_item_owner(manifest: dict[str, Any], item: dict[str, Any]) -> str:
    """Resolve the required owner for one execution-graph work item."""
    if work_item_is_repair(item):
        return REPAIR_OWNER
    builders = manifest.get("builders") if isinstance(manifest.get("builders"), dict) else {}
    paths = [
        path
        for path in (item.get("files_hint") or [])
        if isinstance(path, str) and path
    ]
    if not paths:
        owner = builders.get("default_owner")
        if not owner:
            raise AppManifestError(
                "APP_MANIFEST_DEFAULT_BUILDER_REQUIRED",
                f"Work item {item.get('id')!r} has no files_hint and no default owner is configured.",
                errors=[str(item.get("id") or "")],
            )
        return str(owner)
    return resolve_builder_for_paths(manifest, paths)


def assert_work_item_owner(manifest: dict[str, Any], item: dict[str, Any]) -> str:
    """Fail when a graph work-item owner disagrees with the manifest snapshot."""
    item_id = str(item.get("id") or "")
    owner = str(item.get("owner") or "")
    if work_item_is_repair(item) and owner != REPAIR_OWNER:
        raise AppManifestError(
            "APP_MANIFEST_REPAIR_OWNER_INVALID",
            f"Repair work item {item_id!r} must be owned by {REPAIR_OWNER!r}.",
            errors=[item_id, owner],
        )
    resolved = resolve_work_item_owner(manifest, item)
    if owner != resolved:
        raise AppManifestError(
            "APP_MANIFEST_GRAPH_OWNER_MISMATCH",
            (
                f"Work item {item_id!r} owner {owner!r} does not match "
                f"manifest routing owner {resolved!r}."
            ),
            errors=[item_id, owner, resolved],
        )
    return resolved
