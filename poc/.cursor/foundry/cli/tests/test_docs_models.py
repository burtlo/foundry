"""Phase 6 tests: factory-shipped documentation backends and delivery gates."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

CLI_DIR = Path(__file__).resolve().parents[1]
FOUNDRY_ROOT = CLI_DIR.parent
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry  # noqa: E402
import foundry_app  # noqa: E402
import foundry_docs  # noqa: E402
from app_manifest_support import manifest_value, write_app_manifest  # noqa: E402
from test_docs import write_sample_app  # noqa: E402
from test_foundry import shipping_state  # noqa: E402
from test_foundry_app import base_manifest  # noqa: E402

IOT_REFERENCE_APP = FOUNDRY_ROOT / "fixtures" / "apps" / "iot-reference"
PYTHON_REFERENCE_APP = FOUNDRY_ROOT / "fixtures" / "apps" / "python-reference"


class GitResult:
    def __init__(self, stdout: str = "") -> None:
        self.stdout = stdout
        self.stderr = ""


class DocsModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.app = self.root / "app"
        self.app.mkdir()
        self.config = foundry.deep_merge(
            foundry.load_config(None),
            {"devops": {"enabled": True, "run_before_pr": True}},
        )

    def write_run(self, app: Path, *, run_mode: str = "implementation") -> Path:
        context = foundry_app.validate_app_manifest(app, run_mode=run_mode)
        run_dir = app / ".foundry" / "runs" / "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
        run_dir.mkdir(parents=True)
        foundry_app.write_run_manifest_snapshot(run_dir, context["manifest"])
        state = {
            "schema_version": foundry.SCHEMA_VERSION,
            "run_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
            "app_folder": str(app),
            "steps": {"implement.documentation": {}},
            "state_revision": 0,
        }
        state_path = run_dir / "state.json"
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        return state_path

    def assert_fails_delivery(self, state, code: str):
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.delivery_check(state, self.config)
        self.assertEqual(caught.exception.error_code, "DELIVERY_GATES_FAILED")
        codes = [failure.split(":", 1)[0] for failure in caught.exception.extra["failures"]]
        self.assertIn(code, codes)
        return caught.exception

    def test_ValidateManifest_UnknownDocumentationModel_Fails(self) -> None:
        manifest = base_manifest()
        manifest["documentation"]["model"] = "custom-plugin"
        write_app_manifest(self.app, manifest=manifest)
        with self.assertRaises(foundry_app.AppManifestError) as caught:
            foundry_app.validate_app_manifest(self.app, run_mode="implementation")
        self.assertEqual(
            caught.exception.error_code,
            "APP_MANIFEST_DOCUMENTATION_MODEL_UNKNOWN",
        )

    def test_ValidateManifest_IotAgentsPrd_Passes(self) -> None:
        result = foundry_app.validate_app_manifest(
            IOT_REFERENCE_APP,
            run_mode="implementation",
        )
        self.assertEqual(result["manifest"]["documentation"]["model"], "iot-agents-prd")

    def test_ValidateManifest_FeatureRecordsEmptyConfig_Passes(self) -> None:
        result = foundry_app.validate_app_manifest(
            PYTHON_REFERENCE_APP,
            run_mode="implementation",
        )
        self.assertEqual(result["manifest"]["documentation"]["model"], "feature-records")
        self.assertEqual(result["manifest"]["documentation"]["config"], {})

    def test_DocsPipeline_FeatureRecords_DoesNotRequireSln(self) -> None:
        write_app_manifest(self.app)
        features = self.app / "docs" / "features"
        features.mkdir(parents=True)
        (features / "routing.md").write_text("# routing\n", encoding="utf-8")
        state_path = self.write_run(self.app)
        result = foundry_docs.docs_pipeline(
            str(state_path),
            "main",
            git_runner=lambda command, cwd: GitResult("docs/features/routing.md\n"),
        )
        self.assertEqual(result["model"], "feature-records")
        self.assertEqual(result["workflow"], "feature-records")
        self.assertEqual(result["status"], "completed")
        self.assertIn("docs/features/routing.md", result["artifacts"])
        self.assertTrue(result["changed"])
        self.assertFalse(result["publication"]["required"])
        self.assertTrue(result["publication"]["passed"])
        self.assertTrue(result["validation"]["passed"])
        state = json.loads(state_path.read_text(encoding="utf-8"))
        step = state["steps"]["implement.documentation"]
        self.assertEqual(step["model"], "feature-records")
        self.assertEqual(step["documentation_result"]["workflow"], "feature-records")
        self.assertNotIn("prd_created_or_updated", step)

    def test_DocsPipeline_IotAgentsPrd_RunsDiscoverAuditPrd(self) -> None:
        app = write_sample_app(self.root / "Sample.App")
        payload = manifest_value(app_id="sample-app")
        payload["documentation"] = {"model": "iot-agents-prd", "config": {}}
        write_app_manifest(app, manifest=payload)
        state_path = self.write_run(app)
        result = foundry_docs.docs_pipeline(
            str(state_path),
            "HEAD~1",
            git_runner=lambda command, cwd: GitResult("AGENTS.md\n"),
        )
        self.assertEqual(result["model"], "iot-agents-prd")
        self.assertEqual(result["workflow"], "iot-documentation-workflow")
        self.assertEqual(result["status"], "completed")
        self.assertIn("discover", result["validation"]["checks"])
        self.assertIn("audit", result["validation"]["checks"])
        self.assertIn("prd_generate", result["validation"]["checks"])
        self.assertIn("prd_validate", result["validation"]["checks"])
        self.assertTrue(result["changed"])
        self.assertTrue(result["publication"]["required"])
        self.assertFalse(result["publication"]["passed"])
        self.assertTrue(result["validation"]["passed"])
        state = json.loads(state_path.read_text(encoding="utf-8"))
        step = state["steps"]["implement.documentation"]
        self.assertTrue(step["prd_created_or_updated"])
        self.assertNotIn("sync_prd_ok", step)
        self.assertTrue((app / "Documentation").exists())

    def test_DeliveryCheck_FeatureRecords_SkipsSyncPrd(self) -> None:
        state = shipping_state()
        state["steps"]["implement.documentation"]["model"] = "feature-records"
        state["steps"]["implement.documentation"]["documentation_result"] = {
            "model": "feature-records",
            "status": "completed",
            "artifacts": ["docs/features/routing.md"],
            "changed": True,
            "validation": {"passed": True, "checks": ["discover"]},
            "publication": {"required": False, "passed": True},
            "blockers": [],
            "workflow": "feature-records",
        }
        result = foundry.delivery_check(state, self.config)
        self.assertTrue(result["passed"])
        self.assertNotIn("SYNC_PRD", result["gates"])
        self.assertNotIn("DOCUMENTATION_PUBLICATION", result["gates"])

    def test_DeliveryCheck_IotPrdChangedWithoutSync_FailsPublication(self) -> None:
        state = shipping_state()
        state["steps"]["implement.documentation"]["model"] = "iot-agents-prd"
        state["steps"]["implement.documentation"]["prd_created_or_updated"] = True
        state["steps"]["implement.documentation"]["documentation_result"] = {
            "model": "iot-agents-prd",
            "status": "completed",
            "artifacts": ["Documentation/prd-sample-app-generated.md"],
            "changed": True,
            "validation": {"passed": True, "checks": ["prd_generate"]},
            "publication": {"required": True, "passed": False},
            "blockers": [],
            "workflow": "iot-documentation-workflow",
        }
        self.assert_fails_delivery(state, "DOCUMENTATION_PUBLICATION")

    def test_RunInit_UnknownDocumentationModel_FailsBeforeRunDir(self) -> None:
        manifest = manifest_value()
        manifest["documentation"]["model"] = "custom-plugin"
        write_app_manifest(self.app, manifest=manifest)
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.run_init(
                app_folder=str(self.app),
                issue_key="DOTNETIOT-1234",
                run_mode="implementation",
                factory_root=str(foundry.REPO_ROOT),
                config_path=None,
                developer_first_name="lynn",
                risk_tier="medium",
                flow_path=None,
                run_id="33333333-3333-4333-8333-333333333355",
            )
        self.assertEqual(
            caught.exception.error_code,
            "APP_MANIFEST_DOCUMENTATION_MODEL_UNKNOWN",
        )
        self.assertFalse((self.app / ".foundry" / "runs").exists())

    def test_AppValidate_UnknownDocumentationModel_Fails(self) -> None:
        manifest = manifest_value()
        manifest["documentation"]["model"] = "custom-plugin"
        write_app_manifest(self.app, manifest=manifest)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = foundry.main(
                [
                    "app",
                    "validate",
                    "--app-folder",
                    str(self.app),
                    "--run-mode",
                    "implementation",
                ]
            )
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload["errorCode"], "APP_MANIFEST_DOCUMENTATION_MODEL_UNKNOWN")

    def test_DocsPipelineCli_DispatchesToKernel(self) -> None:
        write_app_manifest(self.app)
        (self.app / "docs" / "features").mkdir(parents=True)
        (self.app / "docs" / "features" / "one.md").write_text("# one\n", encoding="utf-8")
        state_path = self.write_run(self.app)
        with mock.patch(
            "foundry_docs_feature_records.git_changed_files",
            return_value=[],
        ):
            payload = foundry.dispatch(
                foundry.build_parser().parse_args(
                    ["docs", "pipeline", "--state", str(state_path), "--since", "HEAD"]
                )
            )
        self.assertEqual(payload["model"], "feature-records")
        self.assertFalse(payload["publication"]["required"])


if __name__ == "__main__":
    unittest.main()
