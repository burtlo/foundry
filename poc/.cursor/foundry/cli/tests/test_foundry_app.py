"""Tests for Foundry application-manifest validation and canonicalization."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


CLI_DIR = Path(__file__).resolve().parents[1]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry  # noqa: E402
import foundry_app  # noqa: E402

VALID_FIXTURES_PATH = (
    CLI_DIR.parent / "schemas" / "fixtures" / "app-manifest.valid.yaml"
)
IOT_REFERENCE_APP = CLI_DIR.parent / "fixtures" / "apps" / "iot-reference"


def base_manifest() -> dict:
    return {
        "schema_version": 1,
        "id": "sample-app",
        "tags": ["python", "service"],
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
            "default_owner": "feature-builder",
            "routes": [
                {
                    "id": "client",
                    "owner": "client-builder",
                    "priority": 200,
                    "globs": ["web/**", "**/*.js"],
                },
                {
                    "id": "backend",
                    "owner": "backend-builder",
                    "priority": 100,
                    "globs": ["internal/**"],
                },
            ],
        },
        "documentation": {
            "model": "feature-records",
            "config": {"include": ["docs/features/**"]},
        },
    }


class FoundryAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = Path(self.tmp.name) / "app"
        (self.app / ".foundry").mkdir(parents=True)

    def write_manifest(self, manifest: dict | str) -> Path:
        path = self.app / ".foundry" / "app.yaml"
        text = manifest if isinstance(manifest, str) else yaml.safe_dump(manifest, sort_keys=False)
        path.write_text(text, encoding="utf-8")
        return path

    def write_manifest_input(self, manifest: dict, name: str = "answers.yaml") -> Path:
        path = Path(self.tmp.name) / name
        path.write_text(
            yaml.safe_dump(manifest, sort_keys=False),
            encoding="utf-8",
        )
        return path

    def assert_error(self, code: str, callback) -> foundry_app.AppManifestError:
        with self.assertRaises(foundry_app.AppManifestError) as caught:
            callback()
        self.assertEqual(caught.exception.error_code, code)
        return caught.exception

    def test_validate_resolves_platform_and_returns_stable_hash(self) -> None:
        manifest = base_manifest()
        manifest["commands"]["test"]["windows"] = {
            "argv": ["pwsh", "-File", "test.ps1"],
            "cwd": "scripts\\tests",
            "timeout_seconds": 600,
        }
        self.write_manifest(manifest)

        first = foundry_app.validate_app_manifest(
            self.app,
            run_mode="implementation",
            platform="windows",
        )
        second = foundry_app.validate_app_manifest(
            self.app,
            run_mode="implementation",
            platform="windows",
        )

        self.assertEqual(first["app_manifest_hash"], second["app_manifest_hash"])
        self.assertEqual(
            first["manifest"]["commands"]["test"]["argv"],
            ["pwsh", "-File", "test.ps1"],
        )
        self.assertEqual(first["manifest"]["commands"]["test"]["cwd"], "scripts/tests")
        self.assertNotIn("default", first["manifest"]["commands"]["test"])

    def test_phase_zero_valid_fixtures_pass_semantic_validation_on_both_platforms(self) -> None:
        fixture = yaml.safe_load(VALID_FIXTURES_PATH.read_text(encoding="utf-8"))
        for case in fixture["cases"]:
            run_mode = (
                "analysis"
                if case["name"] == "analysis-capable-minimum"
                else "implementation"
            )
            for platform in ("windows", "posix"):
                with self.subTest(case=case["name"], platform=platform):
                    self.write_manifest(case["manifest"])
                    result = foundry_app.validate_app_manifest(
                        self.app,
                        run_mode=run_mode,
                        platform=platform,
                    )
                    self.assertEqual(result["platform"], platform)

    def test_iot_reference_manifest_passes_on_both_platforms(self) -> None:
        for run_mode in ("implementation", "analysis"):
            for platform in ("windows", "posix"):
                with self.subTest(run_mode=run_mode, platform=platform):
                    result = foundry_app.validate_app_manifest(
                        IOT_REFERENCE_APP,
                        run_mode=run_mode,
                        platform=platform,
                    )
                    self.assertEqual(
                        result["app_manifest_id"],
                        "kt-shared-emailprocessor-iris",
                    )
                    if run_mode == "analysis":
                        self.assertEqual(result["manifest"]["commands"], {})
                        self.assertEqual(result["manifest"]["verification"], {})
                    else:
                        self.assertTrue(result["manifest"]["commands"])

    def test_discover_reports_evidence_without_writing(self) -> None:
        (self.app / "Makefile").write_text(
            "build:\n\t@echo build\n"
            "test:\n\t@echo test\n"
            "precommit: build test\n\t@echo precommit\n",
            encoding="utf-8",
        )
        (self.app / "go.mod").write_text("module example.com/sample\n", encoding="utf-8")
        (self.app / "internal").mkdir()
        (self.app / "docs" / "features").mkdir(parents=True)
        (self.app / "web").mkdir()
        (self.app / "web" / "app.js").write_text("", encoding="utf-8")
        (self.app / ".deps").mkdir()
        (self.app / ".deps" / "vendor.ts").write_text("", encoding="utf-8")

        result = foundry_app.discover_app(self.app)

        self.assertEqual(result["candidates"]["id"]["value"], "app")
        self.assertEqual(
            result["candidates"]["commands"]["build"][0]["default"]["argv"],
            ["make", "build"],
        )
        self.assertIn(
            {"value": "go", "evidence": ["go.mod"]},
            result["candidates"]["tags"],
        )
        self.assertEqual(
            result["candidates"]["documentation"][0]["model"],
            "feature-records",
        )
        client_route = result["candidates"]["builder_routes"][0]
        self.assertEqual(client_route["id"], "client")
        self.assertEqual(client_route["evidence"], ["web/app.js"])
        self.assertNotIn("**/*.ts", client_route["globs"])
        self.assertFalse((self.app / ".foundry" / "app.yaml").exists())

    def test_discover_unknown_repo_reports_required_questions(self) -> None:
        result = foundry_app.discover_app(self.app)
        fields = {question["field"] for question in result["unresolved_questions"]}
        self.assertIn("commands.build", fields)
        self.assertIn("commands.test", fields)
        self.assertEqual(result["candidates"]["commands"]["build"], [])

    def test_discover_reports_broad_foundry_ignore_rule(self) -> None:
        (self.app / ".gitignore").write_text(".foundry/\n", encoding="utf-8")
        result = foundry_app.discover_app(self.app)
        self.assertEqual(
            result["ignore_issues"],
            [
                {
                    "file": ".gitignore",
                    "line": "1",
                    "rule": ".foundry/",
                    "replacement": ".foundry/runs/",
                }
            ],
        )

    def test_init_dry_run_writes_nothing(self) -> None:
        source = self.write_manifest_input(base_manifest())

        result = foundry_app.init_app_manifest(
            self.app,
            source,
            run_mode="implementation",
            dry_run=True,
        )

        self.assertTrue(result["dry_run"])
        self.assertTrue(result["changed"])
        self.assertFalse(result["written"])
        self.assertIn("schema_version: 1", result["rendered_manifest"])
        self.assertFalse((self.app / ".foundry" / "app.yaml").exists())

    def test_init_blocks_manifest_hidden_by_gitignore(self) -> None:
        subprocess.run(
            ["git", "init"],
            cwd=self.app,
            capture_output=True,
            check=True,
        )
        (self.app / ".gitignore").write_text(".foundry/\n", encoding="utf-8")
        source = self.write_manifest_input(base_manifest())

        self.assert_error(
            "APP_MANIFEST_GITIGNORE_BLOCKED",
            lambda: foundry_app.init_app_manifest(
                self.app,
                source,
                run_mode="implementation",
            ),
        )
        self.assertFalse((self.app / ".foundry" / "app.yaml").exists())

    def test_init_writes_valid_manifest_and_is_idempotent(self) -> None:
        source = self.write_manifest_input(base_manifest())

        first = foundry_app.init_app_manifest(
            self.app,
            source,
            run_mode="implementation",
        )
        second = foundry_app.init_app_manifest(
            self.app,
            source,
            run_mode="implementation",
        )

        self.assertTrue(first["written"])
        self.assertFalse(second["changed"])
        self.assertFalse(second["written"])
        validated = foundry_app.validate_app_manifest(
            self.app,
            run_mode="implementation",
        )
        self.assertEqual(validated["app_manifest_hash"], first["app_manifest_hash"])

    def test_init_refuses_overwrite_without_force(self) -> None:
        first = base_manifest()
        second = base_manifest()
        second["id"] = "replacement-app"
        foundry_app.init_app_manifest(
            self.app,
            self.write_manifest_input(first, "first.yaml"),
            run_mode="implementation",
        )

        self.assert_error(
            "APP_MANIFEST_EXISTS",
            lambda: foundry_app.init_app_manifest(
                self.app,
                self.write_manifest_input(second, "second.yaml"),
                run_mode="implementation",
            ),
        )

    def test_init_dry_run_previews_existing_change_without_overwrite(self) -> None:
        first = base_manifest()
        second = base_manifest()
        second["id"] = "replacement-app"
        foundry_app.init_app_manifest(
            self.app,
            self.write_manifest_input(first, "first.yaml"),
            run_mode="implementation",
        )

        result = foundry_app.init_app_manifest(
            self.app,
            self.write_manifest_input(second, "second.yaml"),
            run_mode="implementation",
            dry_run=True,
        )

        self.assertTrue(result["requires_force"])
        self.assertFalse(result["written"])
        self.assertEqual(
            foundry_app.load_app_manifest(self.app)[1]["id"],
            "sample-app",
        )

    def test_init_force_replaces_existing_manifest(self) -> None:
        first = base_manifest()
        second = base_manifest()
        second["id"] = "replacement-app"
        foundry_app.init_app_manifest(
            self.app,
            self.write_manifest_input(first, "first.yaml"),
            run_mode="implementation",
        )

        result = foundry_app.init_app_manifest(
            self.app,
            self.write_manifest_input(second, "second.yaml"),
            run_mode="implementation",
            force=True,
        )

        self.assertTrue(result["written"])
        self.assertEqual(
            foundry_app.load_app_manifest(self.app)[1]["id"],
            "replacement-app",
        )

    def test_canonical_hash_ignores_yaml_mapping_order(self) -> None:
        manifest = base_manifest()
        reversed_manifest = {
            key: manifest[key]
            for key in reversed(list(manifest))
        }
        first = foundry_app.canonicalize_manifest(manifest, platform="posix")
        second = foundry_app.canonicalize_manifest(
            reversed_manifest,
            platform="posix",
        )
        self.assertEqual(
            foundry_app.canonical_json(first),
            foundry_app.canonical_json(second),
        )
        self.assertEqual(foundry_app.manifest_hash(first), foundry_app.manifest_hash(second))

    def test_analysis_manifest_does_not_require_commands_or_builders(self) -> None:
        manifest = base_manifest()
        manifest["commands"] = {}
        manifest["verification"] = {"implementation": [], "post_repair": []}
        manifest["builders"] = {}
        self.write_manifest(manifest)

        result = foundry_app.validate_app_manifest(self.app, run_mode="analysis")

        self.assertEqual(result["manifest"]["commands"], {})
        self.assertEqual(result["manifest"]["verification"], {})
        self.assertEqual(result["app_manifest_id"], "sample-app")

    def test_missing_manifest_fails(self) -> None:
        error = self.assert_error(
            "APP_MANIFEST_MISSING",
            lambda: foundry_app.validate_app_manifest(self.app),
        )
        self.assertIn("/foundry-app-bootstrap", error.message)

    def test_malformed_yaml_fails(self) -> None:
        self.write_manifest("schema_version: 1\ncommands: [\n")
        self.assert_error(
            "APP_MANIFEST_YAML_INVALID",
            lambda: foundry_app.validate_app_manifest(self.app),
        )

    def test_duplicate_yaml_key_fails(self) -> None:
        self.write_manifest("schema_version: 1\nid: one\nid: two\n")
        self.assert_error(
            "APP_MANIFEST_YAML_INVALID",
            lambda: foundry_app.validate_app_manifest(self.app),
        )

    def test_non_json_yaml_value_fails_before_canonicalization(self) -> None:
        manifest = yaml.safe_dump(base_manifest(), sort_keys=False)
        manifest = manifest.replace(
            "config:\n    include:",
            "config:\n    released: 2026-09-20\n    include:",
        )
        self.write_manifest(manifest)
        self.assert_error(
            "APP_MANIFEST_JSON_INCOMPATIBLE",
            lambda: foundry_app.validate_app_manifest(self.app),
        )

    def test_unsupported_schema_version_fails(self) -> None:
        manifest = base_manifest()
        manifest["schema_version"] = 2
        self.write_manifest(manifest)
        self.assert_error(
            "APP_MANIFEST_VERSION_UNSUPPORTED",
            lambda: foundry_app.validate_app_manifest(self.app),
        )

    def test_command_string_fails_schema(self) -> None:
        manifest = base_manifest()
        manifest["commands"]["build"] = "python -m build"
        self.write_manifest(manifest)
        self.assert_error(
            "APP_MANIFEST_SCHEMA_INVALID",
            lambda: foundry_app.validate_app_manifest(self.app),
        )

    def test_parent_cwd_fails_with_stable_code(self) -> None:
        manifest = base_manifest()
        manifest["commands"]["build"]["default"]["cwd"] = "../other"
        self.write_manifest(manifest)
        self.assert_error(
            "APP_MANIFEST_CWD_UNSAFE",
            lambda: foundry_app.validate_app_manifest(self.app),
        )

    def test_schema_errors_take_precedence_over_cwd_semantics(self) -> None:
        manifest = base_manifest()
        manifest["commands"]["build"]["default"]["cwd"] = "../other"
        del manifest["commands"]["build"]["default"]["argv"]
        self.write_manifest(manifest)
        self.assert_error(
            "APP_MANIFEST_SCHEMA_INVALID",
            lambda: foundry_app.validate_app_manifest(self.app),
        )

    def test_absolute_windows_cwd_fails_on_posix_too(self) -> None:
        manifest = base_manifest()
        manifest["commands"]["build"]["default"]["cwd"] = "C:\\source\\app"
        self.write_manifest(manifest)
        self.assert_error(
            "APP_MANIFEST_CWD_UNSAFE",
            lambda: foundry_app.validate_app_manifest(self.app, platform="posix"),
        )

    def test_missing_current_platform_command_fails(self) -> None:
        manifest = base_manifest()
        manifest["commands"]["build"] = {
            "windows": {
                "argv": ["pwsh", "-File", "build.ps1"],
                "cwd": ".",
                "timeout_seconds": 900,
            }
        }
        self.write_manifest(manifest)
        self.assert_error(
            "APP_MANIFEST_PLATFORM_COMMAND_MISSING",
            lambda: foundry_app.validate_app_manifest(
                self.app,
                run_mode="implementation",
                platform="posix",
            ),
        )

    def test_analysis_ignores_unneeded_platform_commands(self) -> None:
        manifest = base_manifest()
        manifest["commands"]["build"] = {
            "windows": {
                "argv": ["pwsh", "-File", "build.ps1"],
                "cwd": ".",
                "timeout_seconds": 900,
            }
        }
        self.write_manifest(manifest)
        result = foundry_app.validate_app_manifest(
            self.app,
            run_mode="analysis",
            platform="posix",
        )
        self.assertEqual(result["manifest"]["commands"], {})

    def test_unknown_verification_command_fails(self) -> None:
        manifest = base_manifest()
        manifest["verification"]["implementation"].append("lint")
        self.write_manifest(manifest)
        self.assert_error(
            "APP_MANIFEST_COMMAND_REFERENCE_UNKNOWN",
            lambda: foundry_app.validate_app_manifest(self.app),
        )

    def test_implementation_requires_verification_commands(self) -> None:
        manifest = base_manifest()
        manifest["verification"]["implementation"] = []
        self.write_manifest(manifest)
        self.assert_error(
            "APP_MANIFEST_IMPLEMENTATION_COMMANDS_REQUIRED",
            lambda: foundry_app.validate_app_manifest(
                self.app,
                run_mode="implementation",
            ),
        )

    def test_implementation_requires_post_repair_commands(self) -> None:
        manifest = base_manifest()
        manifest["verification"]["post_repair"] = []
        self.write_manifest(manifest)
        self.assert_error(
            "APP_MANIFEST_POST_REPAIR_COMMANDS_REQUIRED",
            lambda: foundry_app.validate_app_manifest(
                self.app,
                run_mode="implementation",
            ),
        )

    def test_implementation_requires_default_builder(self) -> None:
        manifest = base_manifest()
        del manifest["builders"]["default_owner"]
        self.write_manifest(manifest)
        self.assert_error(
            "APP_MANIFEST_DEFAULT_BUILDER_REQUIRED",
            lambda: foundry_app.validate_app_manifest(
                self.app,
                run_mode="implementation",
            ),
        )

    def test_unsupported_run_mode_has_stable_error(self) -> None:
        self.write_manifest(base_manifest())
        self.assert_error(
            "APP_MANIFEST_RUN_MODE_UNSUPPORTED",
            lambda: foundry_app.validate_app_manifest(
                self.app,
                run_mode="deployment",
            ),
        )

    def test_unknown_builder_owner_fails(self) -> None:
        manifest = base_manifest()
        manifest["builders"]["default_owner"] = "invented-builder"
        self.write_manifest(manifest)
        self.assert_error(
            "APP_MANIFEST_BUILDER_OWNER_UNKNOWN",
            lambda: foundry_app.validate_app_manifest(self.app),
        )

    def test_duplicate_route_id_fails(self) -> None:
        manifest = base_manifest()
        duplicate = copy.deepcopy(manifest["builders"]["routes"][0])
        duplicate["globs"] = ["desktop/**"]
        manifest["builders"]["routes"].append(duplicate)
        self.write_manifest(manifest)
        self.assert_error(
            "APP_MANIFEST_BUILDER_ROUTE_DUPLICATE",
            lambda: foundry_app.validate_app_manifest(self.app),
        )

    def test_exact_equal_priority_route_tie_fails_validation(self) -> None:
        manifest = base_manifest()
        manifest["builders"]["routes"].append(
            {
                "id": "client-copy",
                "owner": "feature-builder",
                "priority": 200,
                "globs": ["web/**"],
            }
        )
        self.write_manifest(manifest)
        self.assert_error(
            "APP_MANIFEST_BUILDER_ROUTE_TIE",
            lambda: foundry_app.validate_app_manifest(self.app),
        )

    def test_overlapping_equal_priority_routes_fail_validation(self) -> None:
        manifest = base_manifest()
        manifest["builders"]["routes"] = [
            {
                "id": "web",
                "owner": "client-builder",
                "priority": 200,
                "globs": ["web/**"],
            },
            {
                "id": "web-javascript",
                "owner": "feature-builder",
                "priority": 200,
                "globs": ["web/**/*.js"],
            },
        ]
        self.write_manifest(manifest)
        self.assert_error(
            "APP_MANIFEST_BUILDER_ROUTE_TIE",
            lambda: foundry_app.validate_app_manifest(self.app),
        )

    def test_provably_disjoint_equal_priority_routes_pass_validation(self) -> None:
        manifest = base_manifest()
        manifest["builders"]["routes"] = [
            {
                "id": "web",
                "owner": "client-builder",
                "priority": 100,
                "globs": ["web/**"],
            },
            {
                "id": "backend",
                "owner": "backend-builder",
                "priority": 100,
                "globs": ["internal/**"],
            },
        ]
        self.write_manifest(manifest)
        result = foundry_app.validate_app_manifest(
            self.app,
            run_mode="implementation",
        )
        self.assertEqual(len(result["manifest"]["builders"]["routes"]), 2)

    def test_route_resolution_uses_priority_and_default(self) -> None:
        manifest = base_manifest()
        self.assertEqual(
            foundry_app.resolve_builder_owner(manifest, "web/internal/app.js"),
            "client-builder",
        )
        self.assertEqual(
            foundry_app.resolve_builder_owner(manifest, "README.md"),
            "feature-builder",
        )

    def test_route_resolution_rejects_equal_priority_overlap(self) -> None:
        manifest = base_manifest()
        manifest["builders"]["routes"].append(
            {
                "id": "javascript",
                "owner": "feature-builder",
                "priority": 200,
                "globs": ["**/*.js"],
            }
        )
        self.assert_error(
            "APP_MANIFEST_BUILDER_ROUTE_TIE",
            lambda: foundry_app.resolve_builder_owner(manifest, "web/app.js"),
        )

    def test_multi_path_resolution_requires_one_owner(self) -> None:
        manifest = base_manifest()
        self.assert_error(
            "APP_MANIFEST_MULTIPLE_BUILDER_OWNERS",
            lambda: foundry_app.resolve_builder_for_paths(
                manifest,
                ["web/app.js", "internal/server.py"],
            ),
        )

    def test_route_resolution_rejects_parent_path(self) -> None:
        self.assert_error(
            "APP_MANIFEST_FILES_HINT_UNSAFE",
            lambda: foundry_app.resolve_builder_owner(
                base_manifest(),
                "../other-app/file.py",
            ),
        )

    def test_work_item_owner_uses_default_when_files_hint_empty(self) -> None:
        self.assertEqual(
            foundry_app.resolve_work_item_owner(
                base_manifest(),
                {"id": "docs", "owner": "feature-builder", "files_hint": []},
            ),
            "feature-builder",
        )

    def test_work_item_owner_exact_and_priority_match(self) -> None:
        manifest = base_manifest()
        self.assertEqual(
            foundry_app.resolve_work_item_owner(
                manifest,
                {"id": "ui", "owner": "client-builder", "files_hint": ["web/app.js"]},
            ),
            "client-builder",
        )
        self.assertEqual(
            foundry_app.resolve_work_item_owner(
                manifest,
                {
                    "id": "overlap",
                    "owner": "client-builder",
                    "files_hint": ["web/internal/app.js"],
                },
            ),
            "client-builder",
        )

    def test_repair_work_item_ignores_files_hint(self) -> None:
        self.assertEqual(
            foundry_app.resolve_work_item_owner(
                base_manifest(),
                {
                    "id": "repair-1",
                    "kind": "repair",
                    "owner": "repairer",
                    "files_hint": ["web/app.js"],
                },
            ),
            "repairer",
        )
        self.assert_error(
            "APP_MANIFEST_REPAIR_OWNER_INVALID",
            lambda: foundry_app.assert_work_item_owner(
                base_manifest(),
                {
                    "id": "repair-1",
                    "kind": "repair",
                    "owner": "backend-builder",
                    "files_hint": ["internal/server.py"],
                },
            ),
        )

    def test_assert_work_item_owner_rejects_mismatch(self) -> None:
        self.assert_error(
            "APP_MANIFEST_GRAPH_OWNER_MISMATCH",
            lambda: foundry_app.assert_work_item_owner(
                base_manifest(),
                {
                    "id": "ui",
                    "owner": "backend-builder",
                    "files_hint": ["web/app.js"],
                },
            ),
        )

    def test_glob_matches_root_nested_and_dot_directories(self) -> None:
        self.assertTrue(foundry_app.glob_matches("app.js", "**/*.js"))
        self.assertTrue(foundry_app.glob_matches("web/nested/app.js", "**/*.js"))
        self.assertTrue(foundry_app.glob_matches(".cursor/rules/app.mdc", ".cursor/**"))
        self.assertTrue(foundry_app.glob_matches("web/app1.js", "web/app[0-9].js"))
        self.assertFalse(foundry_app.glob_matches("web/app.css", "**/*.js"))

    def test_cli_validate_and_print_context(self) -> None:
        self.write_manifest(base_manifest())
        validate_output = io.StringIO()
        with contextlib.redirect_stdout(validate_output):
            validate_code = foundry.main(
                [
                    "app",
                    "validate",
                    "--app-folder",
                    str(self.app),
                    "--run-mode",
                    "implementation",
                ]
            )
        validate_payload = json.loads(validate_output.getvalue())

        context_output = io.StringIO()
        with contextlib.redirect_stdout(context_output):
            context_code = foundry.main(
                [
                    "app",
                    "print-context",
                    "--app-folder",
                    str(self.app),
                    "--run-mode",
                    "implementation",
                ]
            )
        context_payload = json.loads(context_output.getvalue())

        self.assertEqual(validate_code, 0)
        self.assertTrue(validate_payload["valid"])
        self.assertNotIn("manifest", validate_payload)
        self.assertEqual(context_code, 0)
        self.assertEqual(context_payload["manifest"]["id"], "sample-app")
        self.assertEqual(
            context_payload["app_manifest_hash"],
            validate_payload["app_manifest_hash"],
        )

    def test_cli_discover_and_init_dry_run(self) -> None:
        (self.app / "go.mod").write_text("module example.com/sample\n", encoding="utf-8")
        discover_output = io.StringIO()
        with contextlib.redirect_stdout(discover_output):
            discover_code = foundry.main(
                ["app", "discover", "--app-folder", str(self.app)]
            )
        discover_payload = json.loads(discover_output.getvalue())

        source = self.write_manifest_input(base_manifest())
        init_output = io.StringIO()
        with contextlib.redirect_stdout(init_output):
            init_code = foundry.main(
                [
                    "app",
                    "init",
                    "--app-folder",
                    str(self.app),
                    "--manifest-file",
                    str(source),
                    "--run-mode",
                    "implementation",
                    "--dry-run",
                ]
            )
        init_payload = json.loads(init_output.getvalue())

        self.assertEqual(discover_code, 0)
        self.assertEqual(discover_payload["candidates"]["tags"][0]["value"], "go")
        self.assertEqual(init_code, 0)
        self.assertTrue(init_payload["dry_run"])
        self.assertFalse((self.app / ".foundry" / "app.yaml").exists())

    def test_cli_error_uses_stable_envelope(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = foundry.main(
                [
                    "app",
                    "validate",
                    "--app-folder",
                    str(self.app),
                    "--run-mode",
                    "analysis",
                ]
            )
        payload = json.loads(output.getvalue())

        self.assertEqual(code, 1)
        self.assertFalse(payload["success"])
        self.assertEqual(payload["errorCode"], "APP_MANIFEST_MISSING")
        self.assertIn("/foundry-app-bootstrap", payload["message"])

    def test_cli_commands_require_run_mode(self) -> None:
        parser = foundry.build_parser()
        for command in ("validate", "print-context"):
            with self.subTest(command=command):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        parser.parse_args(
                            ["app", command, "--app-folder", str(self.app)]
                        )


if __name__ == "__main__":
    unittest.main()
