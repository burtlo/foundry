"""Protocol 2.2 runtime cutover tests for app-manifest snapshots."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

CLI_DIR = Path(__file__).resolve().parents[1]
FOUNDRY_ROOT = CLI_DIR.parent
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry  # noqa: E402
import foundry_app  # noqa: E402
import foundry_integrity  # noqa: E402
import foundry_mechanics  # noqa: E402
from app_manifest_support import manifest_value, write_app_manifest  # noqa: E402

FIXTURES = FOUNDRY_ROOT / "fixtures" / "apps"


class AppManifestRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = Path(self.tmp.name) / "app"
        self.app.mkdir()

    def init(self, *, run_mode: str = "implementation") -> tuple[dict, Path]:
        result = foundry.run_init(
            app_folder=str(self.app),
            issue_key="TICKET-1234",
            run_mode=run_mode,
            factory_root=str(foundry.REPO_ROOT),
            config_path=None,
            developer_first_name="lynn",
            risk_tier="medium",
            flow_path=None,
            run_id="33333333-3333-4333-8333-333333333333",
        )
        return result, Path(result["state_path"])

    def test_RunInit_MissingManifest_FailsBeforeRunArtifacts(self):
        with self.assertRaises(foundry.FoundryError) as caught:
            self.init()
        self.assertEqual(caught.exception.error_code, "APP_MANIFEST_MISSING")
        self.assertIn("/foundry-app-bootstrap", caught.exception.message)
        self.assertFalse((self.app / ".foundry" / "runs").exists())

    def test_RunInit_AgentsAndSolutionWithoutManifest_StillFails(self):
        (self.app / "AGENTS.md").write_text(
            "## Common Commands\n\n- Build: `dotnet build`\n- Test: `dotnet test`\n",
            encoding="utf-8",
        )
        (self.app / "App.sln").write_text("", encoding="utf-8")
        (self.app / "Makefile").write_text("build:\n\t@echo hi\n", encoding="utf-8")
        with self.assertRaises(foundry.FoundryError) as caught:
            self.init()
        self.assertEqual(caught.exception.error_code, "APP_MANIFEST_MISSING")
        self.assertIn("/foundry-app-bootstrap", caught.exception.message)
        self.assertFalse((self.app / ".foundry" / "runs").exists())

    def test_RunInit_InvalidYaml_FailsBeforeRunArtifacts(self):
        manifest_dir = self.app / ".foundry"
        manifest_dir.mkdir()
        (manifest_dir / "app.yaml").write_text("id: [unterminated\n", encoding="utf-8")
        with self.assertRaises(foundry.FoundryError) as caught:
            self.init()
        self.assertEqual(caught.exception.error_code, "APP_MANIFEST_YAML_INVALID")
        self.assertFalse((self.app / ".foundry" / "runs").exists())

    def test_RunInit_ImplementationWithoutCommands_FailsBeforeRunArtifacts(self):
        write_app_manifest(
            self.app,
            manifest={
                "schema_version": 1,
                "id": "analysis-only",
                "commands": {},
                "verification": {"implementation": [], "post_repair": []},
                "builders": {},
                "documentation": {"model": "feature-records", "config": {}},
            },
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            self.init()
        self.assertEqual(
            caught.exception.error_code,
            "APP_MANIFEST_IMPLEMENTATION_COMMANDS_REQUIRED",
        )
        self.assertFalse((self.app / ".foundry" / "runs").exists())

    def test_RunInit_UnknownDocumentationModel_FailsBeforeRunArtifacts(self):
        write_app_manifest(
            self.app,
            manifest={
                "schema_version": 1,
                "id": "unknown-docs",
                "commands": {
                    "build": {
                        "default": {
                            "argv": [sys.executable, "-c", "print('build')"],
                            "cwd": ".",
                            "timeout_seconds": 30,
                        }
                    },
                    "test": {
                        "default": {
                            "argv": [sys.executable, "-c", "print('test')"],
                            "cwd": ".",
                            "timeout_seconds": 30,
                        }
                    },
                },
                "verification": {
                    "implementation": ["build", "test"],
                    "post_repair": ["build", "test"],
                },
                "builders": {"default_owner": "feature-builder", "routes": []},
                "documentation": {"model": "custom-plugin", "config": {}},
            },
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            self.init()
        self.assertEqual(
            caught.exception.error_code,
            "APP_MANIFEST_DOCUMENTATION_MODEL_UNKNOWN",
        )
        self.assertFalse((self.app / ".foundry" / "runs").exists())

    def test_RunInit_FreezesCanonicalSnapshotIdentityInState(self):
        write_app_manifest(self.app)
        result, state_path = self.init()
        state = json.loads(state_path.read_text(encoding="utf-8"))
        snapshot = foundry_app.load_run_manifest_snapshot(state_path.parent)
        self.assertEqual(result["app_manifest_path"], str(state_path.parent / "app-manifest.json"))
        self.assertEqual(state["app_manifest_id"], snapshot["id"])
        self.assertEqual(state["app_manifest_hash"], foundry_app.manifest_hash(snapshot))
        self.assertIn(state["app_manifest_platform"], {"windows", "posix"})
        self.assertEqual(state["schema_version"], "2.2.0")

    def test_AnalysisRun_SnapshotsMetadataWithoutImplementationCommands(self):
        write_app_manifest(self.app)
        _, state_path = self.init(run_mode="analysis")
        snapshot = foundry_app.load_run_manifest_snapshot(state_path.parent)
        self.assertEqual(snapshot["commands"], {})
        self.assertEqual(snapshot["verification"], {})
        self.assertEqual(snapshot["documentation"]["model"], "feature-records")

    def test_LoadState_RejectsProtocol210(self):
        state_path = self.app / "state.json"
        state_path.write_text(
            json.dumps({"schema_version": "2.1.0", "run_id": "x"}),
            encoding="utf-8",
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.load_state(state_path)
        self.assertEqual(caught.exception.error_code, "UNSUPPORTED_PROTOCOL_VERSION")

    def test_TamperedSnapshot_BlocksStateBoundContext(self):
        write_app_manifest(self.app)
        _, state_path = self.init()
        snapshot_path = state_path.parent / foundry_app.RUN_MANIFEST_FILENAME
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        snapshot["tags"].append("tampered")
        snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.project_context(state_path)
        self.assertEqual(caught.exception.error_code, "APP_MANIFEST_SNAPSHOT_MISMATCH")

    def test_LiveManifestDrift_BlocksIntegrityHandoffAndDelivery(self):
        write_app_manifest(self.app)
        _, state_path = self.init()
        changed = manifest_value(app_id="changed-app")
        (self.app / ".foundry" / "app.yaml").write_text(
            __import__("yaml").safe_dump(changed, sort_keys=False),
            encoding="utf-8",
        )
        integrity = foundry_integrity.run_integrity_check(state_path)
        self.assertFalse(integrity["ok"])
        self.assertTrue(any("APP_MANIFEST_DRIFT" in issue for issue in integrity["issues"]))
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.run_handoff(state_path)
        self.assertEqual(caught.exception.error_code, "APP_MANIFEST_DRIFT")
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.delivery_check(
                foundry.load_state(state_path),
                foundry.load_config(None),
                state_path=state_path,
            )
        self.assertEqual(caught.exception.error_code, "APP_MANIFEST_DRIFT")
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.run_complete(state_path, pr_url=None, config_path=None)
        self.assertEqual(caught.exception.error_code, "APP_MANIFEST_DRIFT")

    def test_BuildTestAndProjectContext_RequireState(self):
        parser = foundry.build_parser()
        for argv in (["build"], ["test"], ["project-context"]):
            with self.assertRaises(SystemExit):
                parser.parse_args(argv)

    def test_RunInitBuildAndTest_DoNotCallDiscoverApp(self):
        import inspect

        for fn in (foundry.run_init, foundry.run_build, foundry.run_test):
            with self.subTest(fn=fn.__name__):
                self.assertNotIn("discover_app", inspect.getsource(fn))

    def test_Verification_ImplementationOrderIsDeclaredOrder(self):
        write_app_manifest(
            self.app,
            manifest={
                "schema_version": 1,
                "id": "order-app",
                "commands": {
                    "build": {
                        "default": {
                            "argv": [sys.executable, "-c", "print('build')"],
                            "cwd": ".",
                            "timeout_seconds": 30,
                        }
                    },
                    "test": {
                        "default": {
                            "argv": [sys.executable, "-c", "print('test')"],
                            "cwd": ".",
                            "timeout_seconds": 30,
                        }
                    },
                },
                "verification": {
                    "implementation": ["test", "build"],
                    "post_repair": ["build", "test"],
                },
                "builders": {"default_owner": "feature-builder", "routes": []},
                "documentation": {"model": "feature-records", "config": {}},
            },
        )
        _, state_path = self.init()

        def runner(args, cwd):
            return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

        results = foundry.run_manifest_verification(
            state_path,
            "implementation",
            runner=runner,
        )
        self.assertEqual([item["commandName"] for item in results], ["test", "build"])

    def test_PythonReferenceFixture_ExecutesImplementationVerification(self):
        source = FIXTURES / "python-reference"
        app = Path(self.tmp.name) / "python-reference"
        shutil.copytree(source, app)
        manifest_path = app / ".foundry" / "app.yaml"
        payload = __import__("yaml").safe_load(manifest_path.read_text(encoding="utf-8"))
        for command in payload["commands"].values():
            command["default"]["argv"][0] = sys.executable
        manifest_path.write_text(
            __import__("yaml").safe_dump(payload, sort_keys=False),
            encoding="utf-8",
        )
        result = foundry.run_init(
            app_folder=str(app),
            issue_key="TICKET-1234",
            run_mode="implementation",
            factory_root=str(foundry.REPO_ROOT),
            config_path=None,
            developer_first_name="lynn",
            risk_tier="low",
            flow_path=None,
            run_id="33333333-3333-4333-8333-333333333344",
        )
        state_path = Path(result["state_path"])
        results = foundry.run_manifest_verification(state_path, "implementation")
        self.assertEqual([item["commandName"] for item in results], ["build", "test"])
        self.assertTrue(all(item["exitCode"] == 0 for item in results))

    def test_AnalysisReferenceFixture_StartsWithoutBuildCommands(self):
        source = FIXTURES / "analysis-reference"
        app = Path(self.tmp.name) / "analysis-reference"
        shutil.copytree(source, app)
        result = foundry.run_init(
            app_folder=str(app),
            issue_key="TICKET-1234",
            run_mode="analysis",
            factory_root=str(foundry.REPO_ROOT),
            config_path=None,
            developer_first_name="lynn",
            risk_tier="low",
            flow_path=None,
            run_id="33333333-3333-4333-8333-333333333355",
        )
        snapshot = foundry_app.load_run_manifest_snapshot(Path(result["state_path"]).parent)
        self.assertEqual(snapshot["commands"], {})
        self.assertEqual(snapshot["id"], "analysis-reference")
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.run_build(Path(result["state_path"]))
        self.assertEqual(caught.exception.error_code, "APP_MANIFEST_COMMAND_NOT_SNAPSHOTTED")

    def test_RuntimeSources_DoNotInferProjectTypeOrAgentsCommands(self):
        mechanics = (CLI_DIR / "foundry_mechanics.py").read_text(encoding="utf-8")
        self.assertNotIn("projectType", mechanics)
        self.assertNotIn("find_sln", mechanics)
        self.assertNotIn("makefile_has_target", mechanics)
        self.assertNotIn("extract_commands_from_agents", mechanics)
        self.assertTrue(hasattr(foundry_mechanics, "run_manifest_command"))
        self.assertFalse(hasattr(foundry_mechanics, "project_context"))


if __name__ == "__main__":
    unittest.main()
