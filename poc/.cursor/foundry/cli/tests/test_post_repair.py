"""Phase 5 tests: post-repair verification and implementation-policy regression."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

CLI_DIR = Path(__file__).resolve().parents[1]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry  # noqa: E402
from app_manifest_support import attach_run_manifest, manifest_value, write_app_manifest  # noqa: E402
from test_foundry import base_state, shipping_state, write_critic_receipts  # noqa: E402


def failing_post_repair_manifest():
    payload = manifest_value()
    payload["commands"]["fail"] = {
        "default": {
            "argv": [sys.executable, "-c", "raise SystemExit(1)"],
            "cwd": ".",
            "timeout_seconds": 30,
        }
    }
    payload["verification"]["post_repair"] = ["fail"]
    return payload


class PostRepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run_dir = Path(self.tmp.name)
        self.app = self.run_dir / "app"
        self.app.mkdir()
        self.state_path = self.run_dir / "state.json"
        self.graph_path = self.run_dir / "execution-graph.json"
        self.receipts_dir = self.run_dir / "receipts"
        self.receipts_dir.mkdir()
        (self.run_dir / "events.jsonl").touch()
        self.config = foundry.load_config(None)
        self.config_path = self.run_dir / "config.json"
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")

    def write_state(self, **overrides):
        defaults = {
            "current_step": "implement.build",
            "app_folder": str(self.app),
            "factory_root": str(foundry.REPO_ROOT),
            "feature_branch": "lynn/TICKET-1234",
            "default_branch": "main",
            "execution_graph_id": "22222222-2222-4222-8222-222222222222",
            "steps": {"implement.build": {"status": "in_progress"}},
        }
        defaults.update(overrides)
        state = base_state(**defaults)
        attach_run_manifest(state, self.app, self.run_dir)
        foundry.write_state(self.state_path, state)
        return state

    def write_repair_graph(self):
        graph = {
            "schema_version": foundry.SCHEMA_VERSION,
            "graph_id": "22222222-2222-4222-8222-222222222222",
            "run_id": "11111111-1111-4111-8111-111111111111",
            "issue_key": "TICKET-1234",
            "risk_tier": "medium",
            "approved_ac_version": 1,
            "topology": "sequential",
            "work_items": [
                {
                    "id": "repair-1",
                    "description": "Fix after verify",
                    "owner": "repairer",
                    "kind": "repair",
                    "depends_on": [],
                    "ac_refs": [],
                    "files_hint": [],
                    "evidence_required": ["build-pass"],
                    "status": "ready",
                }
            ],
            "verification_plan": [],
            "created_at": "2026-09-10T12:00:00Z",
        }
        self.graph_path.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
        return graph

    def test_PostRepair_AddRepairItemAlone_DoesNotRunVerification(self):
        self.write_state()
        self.write_repair_graph()
        with mock.patch.object(foundry, "run_manifest_verification") as verify:
            foundry.graph_add_repair_item(
                str(self.graph_path),
                state_path=self.state_path,
                item_id="repair-extra",
                reason="schedule only",
            )
            verify.assert_not_called()
        state = foundry.load_state(self.state_path)
        self.assertTrue(state["rework"]["post_repair_required"])
        self.assertFalse(state["rework"]["post_repair_ok"])
        self.assertNotIn("post_repair_at", state["rework"])

    def test_PostRepair_RepairerComplete_RunsSnapshotPolicy(self):
        self.write_state()
        self.write_repair_graph()
        captured = []
        real = foundry.run_manifest_verification

        def wrapper(state_path, policy, runner=None):
            captured.append(policy)
            return real(state_path, policy, runner=runner)

        launch = foundry.observability_subagent_launch(
            self.state_path,
            agent="repairer",
            mode="repair",
            work_item="repair-1",
            config_path=str(self.config_path),
        )
        craft = {
            "schema_version": foundry.SCHEMA_VERSION,
            "status": "completed",
            "outputs": {
                "summary_markdown": "Repaired the build.",
                "files_changed": ["src/Fix.cs"],
            },
            "commands": [{"command": "dotnet test", "exit_code": 0}],
            "recommended_next_state": "implement.build",
        }
        Path(launch["craft_staging_path"]).write_text(
            json.dumps(craft, indent=2) + "\n",
            encoding="utf-8",
        )
        with mock.patch.object(foundry, "run_manifest_verification", wrapper):
            foundry.observability_subagent_complete(
                self.state_path,
                receipt=launch["craft_staging_path"],
                launch_id=launch["launch_id"],
                config_path=str(self.config_path),
            )
        self.assertEqual(captured, ["post_repair"])
        state = foundry.load_state(self.state_path)
        self.assertTrue(state["rework"]["post_repair_ok"])
        self.assertFalse(state["rework"]["post_repair_required"])

    def test_PostRepair_CommandFailed_BlocksPrePrAndDelivery(self):
        write_app_manifest(self.app, manifest=failing_post_repair_manifest())
        state = self.write_state()
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.run_post_repair_verification(self.state_path)
        self.assertEqual(caught.exception.error_code, "COMMAND_FAILED")
        saved = foundry.load_state(self.state_path)
        self.assertFalse(saved["rework"]["post_repair_ok"])
        self.assertTrue(saved["rework"]["post_repair_required"])

        pre_pr = saved
        pre_pr["current_step"] = "implement.pre_pr_review"
        pre_pr.setdefault("steps", {})["implement.pre_pr_review"] = {
            "status": "in_progress",
            "report": "received",
        }
        write_critic_receipts(
            self.run_dir,
            run_id=pre_pr["run_id"],
            branch_point="main",
        )
        foundry.write_state(self.state_path, pre_pr)
        with self.assertRaises(foundry.FoundryError) as blocked:
            foundry.assert_pre_pr_transition_allowed(
                pre_pr,
                self.state_path,
                from_step="implement.pre_pr_review",
                target="implement.documentation",
                decision="approve",
                config=self.config,
            )
        self.assertEqual(blocked.exception.error_code, "COMMAND_FAILED")

        ship = foundry.load_state(self.state_path)
        ship["current_step"] = "deliver.scope_comment"
        ship["feature_branch"] = "lynn/TICKET-1234"
        ship["default_branch"] = "main"
        ship["pr_extras_register"] = []
        ship["steps"] = shipping_state()["steps"]
        foundry.write_state(self.state_path, ship)
        with self.assertRaises(foundry.FoundryError) as delivery:
            foundry.delivery_check(ship, self.config, state_path=self.state_path)
        self.assertEqual(delivery.exception.error_code, "DELIVERY_GATES_FAILED")
        codes = [failure.split(":", 1)[0] for failure in delivery.exception.extra["failures"]]
        self.assertIn("POST_REPAIR", codes)

    def test_PostRepair_NotRunAfterMutatingRework_BlocksReview(self):
        state = self.write_state(
            current_step="implement.pre_pr_review",
            rework={
                "validator_loops": 0,
                "builder_to_bugbot_loops": 1,
                "post_repair_required": True,
            },
            steps={
                "implement.pre_pr_review": {
                    "status": "in_progress",
                    "report": "received",
                }
            },
        )
        write_critic_receipts(
            self.run_dir,
            run_id=state["run_id"],
            branch_point="main",
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.assert_pre_pr_transition_allowed(
                state,
                self.state_path,
                from_step="implement.pre_pr_review",
                target="implement.documentation",
                decision="approve",
                config=self.config,
            )
        self.assertEqual(caught.exception.error_code, "POST_REPAIR_NOT_RUN")

    def test_BuildStepVerify_StillUsesImplementationPolicy(self):
        self.write_state()
        self.write_repair_graph()
        captured: list[str] = []
        real = foundry.run_manifest_verification

        def wrapper(state_path, policy, runner=None):
            captured.append(policy)
            return real(state_path, policy, runner=runner)

        with mock.patch.object(foundry, "validate_build_exit"), mock.patch.object(
            foundry, "run_manifest_verification", wrapper
        ):
            foundry.build_step_verify(
                self.state_path,
                graph_path=str(self.graph_path),
                config_path=str(self.config_path),
            )
        self.assertEqual(captured, ["implementation"])


if __name__ == "__main__":
    unittest.main()
