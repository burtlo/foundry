"""feature-records documentation backend: docs/features records, no .sln or PRD sync."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any, Callable

from foundry_docs import (
    DocsError,
    common_result,
    git_changed_files,
    unsafe_relative_path,
    validate_common_result,
)

DEFAULT_INCLUDE = ["docs/features/**"]
SKIP_DIR_NAMES = {".git", ".foundry", ".deps", "node_modules", "__pycache__"}


class FeatureRecordsBackend:
    model = "feature-records"
    workflow = "feature-records"

    def validate_config(self, config: Any) -> None:
        include, exclude = self._normalized_globs(config, require_object=True)
        for pattern in include + exclude:
            if unsafe_relative_path(pattern):
                raise DocsError(
                    "APP_MANIFEST_DOCUMENTATION_CONFIG_INVALID",
                    f"feature-records glob escapes the app folder: {pattern!r}.",
                )

    def discover(self, snapshot: dict[str, Any], app_folder: str) -> dict[str, Any]:
        root = Path(app_folder)
        if not root.is_dir():
            raise DocsError("INVALID_APP_FOLDER", f"App folder does not exist: {app_folder}")
        include, exclude, escaped = self._include_exclude(snapshot, root)
        records = [] if escaped else self._list_records(root, include, exclude)
        return {
            "app_folder": str(root),
            "model": self.model,
            "workflow": self.workflow,
            "include": include,
            "exclude": exclude,
            "records": records,
            "escaped_globs": escaped,
        }

    def execute(
        self,
        snapshot: dict[str, Any],
        app_folder: str,
        since: str | None,
        *,
        git_runner: Callable[..., Any] | None = None,
    ) -> dict[str, Any]:
        discovery = self.discover(snapshot, app_folder)
        include = list(discovery.get("include") or [])
        exclude = list(discovery.get("exclude") or [])
        records = list(discovery.get("records") or [])
        escaped = list(discovery.get("escaped_globs") or [])
        checks = ["discover"]
        blockers: list[str] = []
        changed = False
        if escaped:
            blockers.extend(f"glob escapes app folder: {pattern}" for pattern in escaped)
        if since:
            changed_files = git_changed_files(Path(app_folder), since, runner=git_runner)
            checks.append("git_diff")
            changed = any(
                self._matches_any(path, include) and not self._matches_any(path, exclude)
                for path in changed_files
            )
        validation_passed = not escaped
        return common_result(
            model=self.model,
            workflow=self.workflow,
            status="failed" if blockers else "completed",
            artifacts=records,
            changed=changed,
            validation_passed=validation_passed,
            checks=checks,
            publication_required=False,
            publication_passed=True,
            blockers=blockers,
        )

    def validate_receipt(self, receipt: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
        return validate_common_result(receipt, snapshot, expected_model=self.model)

    def delivery_requirements(
        self,
        snapshot: dict[str, Any],
        step_evidence: dict[str, Any] | None,
    ) -> dict[str, bool]:
        return {"required": False, "passed": True}

    def _normalized_globs(
        self,
        config: Any,
        *,
        require_object: bool,
    ) -> tuple[list[str], list[str]]:
        if config is None:
            config = {}
        if not isinstance(config, dict):
            if require_object:
                raise DocsError(
                    "APP_MANIFEST_DOCUMENTATION_CONFIG_INVALID",
                    "feature-records documentation.config must be an object.",
                )
            return [], []
        include = config.get("include")
        exclude = config.get("exclude")
        if include is None:
            include_list: list[str] = []
        elif isinstance(include, list) and all(isinstance(item, str) and item.strip() for item in include):
            include_list = [item.replace("\\", "/") for item in include]
        else:
            raise DocsError(
                "APP_MANIFEST_DOCUMENTATION_CONFIG_INVALID",
                "feature-records documentation.config.include must be an array of relative globs.",
            )
        if exclude is None:
            exclude_list: list[str] = []
        elif isinstance(exclude, list) and all(isinstance(item, str) and item.strip() for item in exclude):
            exclude_list = [item.replace("\\", "/") for item in exclude]
        else:
            raise DocsError(
                "APP_MANIFEST_DOCUMENTATION_CONFIG_INVALID",
                "feature-records documentation.config.exclude must be an array of relative globs.",
            )
        return include_list, exclude_list

    def _include_exclude(
        self,
        snapshot: dict[str, Any],
        root: Path,
    ) -> tuple[list[str], list[str], list[str]]:
        documentation = snapshot.get("documentation") if isinstance(snapshot.get("documentation"), dict) else {}
        config = documentation.get("config") if isinstance(documentation, dict) else {}
        include, exclude = self._normalized_globs(config, require_object=False)
        if not include:
            if (root / "docs" / "features").is_dir():
                include = list(DEFAULT_INCLUDE)
            else:
                include = []
        escaped = [pattern for pattern in include + exclude if unsafe_relative_path(pattern)]
        return include, exclude, escaped

    def _list_records(self, root: Path, include: list[str], exclude: list[str]) -> list[str]:
        if not include:
            return []
        records: list[str] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if SKIP_DIR_NAMES.intersection(path.parts):
                continue
            try:
                relative = path.relative_to(root).as_posix()
            except ValueError:
                continue
            if self._matches_any(relative, include) and not self._matches_any(relative, exclude):
                records.append(relative)
        return sorted(records)

    def _matches_any(self, relative: str, patterns: list[str]) -> bool:
        normalized = relative.replace("\\", "/")
        return any(_glob_matches(normalized, pattern) for pattern in patterns)


def _glob_matches(relative: str, pattern: str) -> bool:
    pattern = pattern.replace("\\", "/")
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        if relative == prefix or relative.startswith(prefix + "/"):
            return True
    if fnmatch.fnmatch(relative, pattern):
        return True
    if pattern.endswith("/") and relative.startswith(pattern):
        return True
    return False
