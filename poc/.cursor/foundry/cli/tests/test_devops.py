"""Phase 8 tests: DevOps workflow scan, pin-report, and apply-pin CLI."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[1]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry  # noqa: E402
import foundry_devops  # noqa: E402


class DevOpsFixtureTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name) / "Sample.App"
        self.workflow_dir = self.root / ".github" / "workflows"
        self.workflow_dir.mkdir(parents=True)
        self.workflow = self.workflow_dir / "ci.yml"
        self.workflow.write_text(
            "\n".join(
                [
                    "name: CI",
                    "on: push",
                    "jobs:",
                    "  build:",
                    "    runs-on: ubuntu-latest",
                    "    steps:",
                    "      - uses: actions/checkout@v4",
                    "      - uses: ncipollo/release-tag-action@v1.6",
                    "      - uses: dorny/paths-filter@a1b2c3d4e5f6789012345678901234567890abcd # dorny/paths-filter@v3.0.2",
                ]
            ),
            encoding="utf-8",
        )

    def test_DevOpsScan_InventoryWorkflowUses(self):
        result = foundry_devops.devops_scan(str(self.root))
        self.assertEqual(result["workflow_count"], 1)
        self.assertEqual(result["inventory_count"], 3)
        classes = {item["class"] for item in result["inventory"]}
        self.assertIn("github_owned", classes)
        self.assertIn("third_party", classes)

    def test_DevOpsPinReport_FlagsUnpinnedAndRefreshCandidates(self):
        result = foundry_devops.devops_pin_report(str(self.root))
        self.assertEqual(len(result["unpinned_third_party"]), 1)
        self.assertEqual(result["unpinned_third_party"][0]["action"], "ncipollo/release-tag-action")
        self.assertEqual(len(result["same_tag_refresh_candidates"]), 1)
        self.assertTrue(result["policy"]["major_bump_requires_human"])

    def test_DevOpsApplyPin_RewritesUsesLine(self):
        sha = "fedcba9876543210fedcba9876543210fedcba98"
        result = foundry_devops.devops_apply_pin(
            ".github/workflows/ci.yml",
            "ncipollo/release-tag-action",
            sha,
            app_folder=str(self.root),
            tag="v1.6",
        )
        self.assertTrue(result["applied"])
        updated = self.workflow.read_text(encoding="utf-8")
        self.assertIn(f"ncipollo/release-tag-action@{sha}", updated)
        self.assertIn("# ncipollo/release-tag-action@v1.6", updated)

    def test_DevOpsApplyPin_InvalidSha_IsRejected(self):
        with self.assertRaises(foundry_devops.DevOpsError) as caught:
            foundry_devops.devops_apply_pin(
                ".github/workflows/ci.yml",
                "ncipollo/release-tag-action",
                "not-a-sha",
                app_folder=str(self.root),
            )
        self.assertEqual(caught.exception.error_code, "INVALID_SHA")


class DevOpsCliDispatchTests(unittest.TestCase):
    def test_FoundryCli_DevOpsScan_Dispatches(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "App"
            workflow = app / ".github" / "workflows"
            workflow.mkdir(parents=True)
            (workflow / "ci.yml").write_text("steps:\n  - uses: actions/checkout@v4\n", encoding="utf-8")
            payload = foundry.dispatch(
                foundry.build_parser().parse_args(["devops", "scan", "--app-folder", str(app)])
            )
            self.assertEqual(payload["inventory_count"], 1)


if __name__ == "__main__":
    unittest.main()
