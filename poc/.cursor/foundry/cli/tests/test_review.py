"""Phase 8 tests: review bundle and critic receipt validation."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[1]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry  # noqa: E402
import foundry_review  # noqa: E402
from app_manifest_support import attach_run_manifest  # noqa: E402
from test_foundry import base_state, shipping_state, write_critic_receipts  # noqa: E402


class ReviewCriticsTests(unittest.TestCase):
    def test_ReviewCritics_BothMode_ReturnsSequentialCritics(self):
        payload = foundry_review.review_critics("both")
        self.assertEqual(payload["critics"], ["bugbot", "security-review"])
        self.assertTrue(payload["sequential"])

    def test_ReviewCritics_AskModeWithoutSelection_RequiresHuman(self):
        payload = foundry_review.review_critics("ask")
        self.assertTrue(payload["requires_human_selection"])
        self.assertEqual(payload["critics"], [])


class ReviewBundleTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name) / "Sample.App"
        self.root.mkdir()
        (self.root / "Program.cs").write_text("class Program {}\n", encoding="utf-8")

    def test_ReviewBundle_ReturnsDiffStats(self):
        class Result:
            stdout = "Program.cs\n.github/workflows/ci.yml\n"

        def runner(command, cwd):
            if "--numstat" in command:
                result = Result()
                result.stdout = "2\t1\tProgram.cs\n"
                return result
            return Result()

        payload = foundry_review.review_bundle(
            str(self.root),
            "main",
            git_runner=runner,
        )
        self.assertEqual(payload["file_count"], 2)
        self.assertEqual(payload["insertions"], 2)
        self.assertEqual(payload["deletions"], 1)
        self.assertIn("subagent_launch", payload)


class ReviewReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.receipts_dir = Path(self.tempdir.name)

    def write_receipt(self, name: str, agent: str, receipt_id: str, **overrides) -> Path:
        path = self.receipts_dir / name
        payload = {
            "schema_version": foundry.SCHEMA_VERSION,
            "receipt_id": receipt_id,
            "run_id": "11111111-1111-4111-8111-111111111111",
            "timestamp": "2026-09-10T12:00:00Z",
            "agent": {"name": agent, "mode": "review"},
            "status": "completed",
            "recommended_next_state": "implement.documentation",
        }
        payload.update(overrides)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_ReviewValidateReceipts_BothCritics_Pass(self):
        bugbot = self.write_receipt("bugbot.json", "bugbot", "aaaaaaaa-bbbb-cccc-dddd-000000000001")
        security = self.write_receipt(
            "security.json",
            "security-review",
            "aaaaaaaa-bbbb-cccc-dddd-000000000002",
        )
        payload = foundry_review.review_validate_receipts(
            str(self.receipts_dir),
            ["bugbot", "security-review"],
            receipt_paths=[str(bugbot.name), str(security.name)],
        )
        self.assertTrue(payload["valid"])
        self.assertEqual(len(payload["receipt_ids"]), 2)

    def test_ReviewValidateReceipts_MissingCritic_Fails(self):
        self.write_receipt("bugbot.json", "bugbot", "aaaaaaaa-bbbb-cccc-dddd-000000000001")
        payload = foundry_review.review_validate_receipts(
            str(self.receipts_dir),
            ["bugbot", "security-review"],
            receipt_paths=["bugbot.json"],
        )
        self.assertFalse(payload["valid"])


class ReviewCliDispatchTests(unittest.TestCase):
    def test_FoundryCli_ReviewCritics_Dispatches(self):
        payload = foundry.dispatch(
            foundry.build_parser().parse_args(["review", "critics", "--mode", "both"])
        )
        self.assertEqual(payload["critics"], ["bugbot", "security-review"])

    def test_FoundryCli_ReviewValidateReceiptsInvalid_NonZeroExit(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipts = Path(tmp)
            with self.assertRaises(foundry.FoundryError) as caught:
                foundry.dispatch(
                    foundry.build_parser().parse_args(
                        [
                            "review",
                            "validate-receipts",
                            "--receipts-dir",
                            str(receipts),
                            "--critic",
                            "bugbot",
                        ]
                    )
                )
            self.assertEqual(caught.exception.error_code, "CRITIC_RECEIPTS_INVALID")


class ReviewReceiptBindingTests(unittest.TestCase):
    RUN_ID = "11111111-1111-4111-8111-111111111111"
    HEAD = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.receipts_dir = Path(self.tempdir.name)

    def write_receipt(self, name, agent, receipt_id, **overrides):
        payload = {
            "schema_version": foundry.SCHEMA_VERSION,
            "receipt_id": receipt_id,
            "run_id": self.RUN_ID,
            "timestamp": "2026-09-10T12:00:00Z",
            "agent": {"name": agent, "mode": "review"},
            "status": "completed",
            "recommended_next_state": "implement.documentation",
            "provenance": {
                "source": "worker_launch",
                "run_id": self.RUN_ID,
                "launch_id": "33333333-3333-4333-8333-333333333333",
                "step_id": "implement.pre_pr_review",
                "agent": agent,
                "mode": "review",
                "branch_point": "main",
                "reviewed_head_sha": self.HEAD,
            },
        }
        payload.update(overrides)
        path = self.receipts_dir / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_ReviewValidateReceipts_DuplicateCritic_Fails(self):
        self.write_receipt("bugbot-a.json", "bugbot", "aaaaaaaa-bbbb-cccc-dddd-000000000001")
        self.write_receipt("bugbot-b.json", "bugbot", "aaaaaaaa-bbbb-cccc-dddd-000000000002")
        payload = foundry_review.review_validate_receipts(str(self.receipts_dir), ["bugbot"])
        self.assertFalse(payload["valid"])
        self.assertEqual(payload["results"][0]["error_code"], "CRITIC_RECEIPT_DUPLICATE")

    def test_ReviewValidateReceipts_WrongAgent_Fails(self):
        security = self.write_receipt(
            "security.json",
            "security-review",
            "aaaaaaaa-bbbb-cccc-dddd-000000000002",
        )
        payload = foundry_review.review_validate_receipts(
            str(self.receipts_dir),
            ["bugbot"],
            receipt_paths=[str(security.name)],
        )
        self.assertFalse(payload["valid"])
        self.assertEqual(payload["results"][0]["error_code"], "CRITIC_RECEIPT_WRONG_AGENT")

    def test_ReviewValidateReceipts_ForeignRun_Fails(self):
        self.write_receipt("bugbot.json", "bugbot", "aaaaaaaa-bbbb-cccc-dddd-000000000001")
        payload = foundry_review.review_validate_receipts(
            str(self.receipts_dir),
            ["bugbot"],
            expected_run_id="99999999-9999-4999-8999-999999999999",
        )
        self.assertFalse(payload["valid"])
        self.assertEqual(payload["results"][0]["error_code"], "RECEIPT_RUN_MISMATCH")

    def test_ReviewValidateReceipts_PartialStatus_Fails(self):
        self.write_receipt(
            "bugbot.json",
            "bugbot",
            "aaaaaaaa-bbbb-cccc-dddd-000000000001",
            status="partial",
        )
        payload = foundry_review.review_validate_receipts(str(self.receipts_dir), ["bugbot"])
        self.assertFalse(payload["valid"])
        self.assertEqual(payload["results"][0]["error_code"], "CRITIC_RECEIPT_PARTIAL")

    def test_ReviewValidateReceipts_StaleHead_Fails(self):
        self.write_receipt("bugbot.json", "bugbot", "aaaaaaaa-bbbb-cccc-dddd-000000000001")
        payload = foundry_review.review_validate_receipts(
            str(self.receipts_dir),
            ["bugbot"],
            expected_head_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        )
        self.assertFalse(payload["valid"])
        self.assertEqual(payload["results"][0]["error_code"], "CRITIC_RECEIPT_STALE_HEAD")

    def test_ReviewValidateReceipts_BothModeBugbotAndSecurity_Pass(self):
        self.write_receipt(
            "bugbot.json",
            "bugbot",
            "aaaaaaaa-bbbb-cccc-dddd-000000000001",
            provenance={
                "source": "worker_launch",
                "run_id": self.RUN_ID,
                "launch_id": "33333333-3333-4333-8333-333333333331",
                "step_id": "implement.pre_pr_review",
                "agent": "bugbot",
                "mode": "review",
                "branch_point": "main",
                "reviewed_head_sha": self.HEAD,
            },
        )
        self.write_receipt(
            "security.json",
            "security-review",
            "aaaaaaaa-bbbb-cccc-dddd-000000000002",
            provenance={
                "source": "worker_launch",
                "run_id": self.RUN_ID,
                "launch_id": "33333333-3333-4333-8333-333333333332",
                "step_id": "implement.pre_pr_review",
                "agent": "security-review",
                "mode": "review",
                "branch_point": "main",
                "reviewed_head_sha": self.HEAD,
            },
        )
        payload = foundry_review.review_validate_receipts(
            str(self.receipts_dir),
            foundry_review.review_critics("both")["critics"],
            expected_run_id=self.RUN_ID,
            expected_step_id="implement.pre_pr_review",
            expected_head_sha=self.HEAD,
            expected_branch_point="main",
        )
        self.assertTrue(payload["valid"])
        self.assertEqual(len(payload["receipt_ids"]), 2)


class ReviewGateIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.app = self.root / "app"
        self.app.mkdir()
        self.state_path = self.root / "state.json"
        self.config = foundry.load_config(None)

    def write_pre_pr_state(self, **overrides):
        state = base_state(
            current_step="implement.pre_pr_review",
            app_folder=str(self.app),
            default_branch="main",
            feature_branch="lynn/TICKET-1234",
            steps={
                "implement.pre_pr_review": {
                    "status": "in_progress",
                    "report": "received",
                    "human_approved": True,
                }
            },
            **overrides,
        )
        attach_run_manifest(state, self.app, self.root)
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        return state

    def test_PrePrTransition_MissingCriticReceipts_Blocked(self):
        state = self.write_pre_pr_state()
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.assert_pre_pr_transition_allowed(
                state,
                self.state_path,
                from_step="implement.pre_pr_review",
                target="implement.documentation",
                decision="approve",
                config=self.config,
            )
        self.assertEqual(caught.exception.error_code, "CRITIC_RECEIPTS_INVALID")

    def test_PrePrTransition_ValidBothReceipts_AllowsDocumentation(self):
        state = self.write_pre_pr_state()
        write_critic_receipts(
            self.root,
            run_id=state["run_id"],
            branch_point="main",
        )
        foundry.assert_pre_pr_transition_allowed(
            state,
            self.state_path,
            from_step="implement.pre_pr_review",
            target="implement.documentation",
            decision="approve",
            config=self.config,
        )

    def test_DeliveryCheck_MissingCriticReceipts_FailsPrePrCritics(self):
        state = shipping_state(app_folder=str(self.app))
        attach_run_manifest(state, self.app, self.root)
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.delivery_check(state, self.config, state_path=self.state_path)
        self.assertEqual(caught.exception.error_code, "DELIVERY_GATES_FAILED")
        codes = [failure.split(":", 1)[0] for failure in caught.exception.extra["failures"]]
        self.assertIn("PRE_PR_CRITICS", codes)

    def test_DeliveryCheck_StaleHeadReceipts_FailsPrePrCritics(self):
        state = shipping_state(app_folder=str(self.app), default_branch="main")
        attach_run_manifest(state, self.app, self.root)
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        write_critic_receipts(
            self.root,
            run_id=state["run_id"],
            head_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            branch_point="main",
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.delivery_check(
                state,
                self.config,
                state_path=self.state_path,
                git_snapshot={"head": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},
            )
        self.assertEqual(caught.exception.error_code, "DELIVERY_GATES_FAILED")
        codes = [failure.split(":", 1)[0] for failure in caught.exception.extra["failures"]]
        self.assertIn("PRE_PR_CRITICS", codes)


if __name__ == "__main__":
    unittest.main()
