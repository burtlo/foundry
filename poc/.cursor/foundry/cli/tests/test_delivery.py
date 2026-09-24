"""Phase 9 tests: delivery sequence, scope comments, PR title, and run completion."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

CLI_DIR = Path(__file__).resolve().parents[1]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry  # noqa: E402
import foundry_deliver  # noqa: E402
from app_manifest_support import attach_run_manifest  # noqa: E402
from test_foundry import base_state, shipping_state, write_critic_receipts  # noqa: E402


def delivery_config(**overrides):
    config = foundry.deep_merge(
        foundry.load_config(None),
        {
            "intake": {"source": "jira", "tickets_root": "tickets"},
            "jira": {
                "enabled": True,
                "cloud_id": "00000000-0000-4000-8000-000000000001",
                "project_key": "TICKET",
            },
            "git": {"pr_title_pattern": "{issue_key} - {brief_description}"},
        },
    )
    config = foundry.deep_merge(config, overrides)
    return foundry.normalize_intake_config(config)


class ScopeCommentDraftTests(unittest.TestCase):
    def setUp(self):
        self.config = delivery_config()
        self.state = shipping_state(
            current_step="deliver.scope_comment",
            pr_extras_register=[
                {
                    "path": ".github/workflows/sync-prd.yml",
                    "reason": "Factory Step 7d",
                    "step_id": "implement.documentation",
                }
            ],
        )

    def test_DraftScopeComment_RegisterRows_BuildsMarkdownTable(self):
        payload = foundry_deliver.draft_scope_comment(self.state, self.config)
        self.assertFalse(payload["skip"])
        self.assertIn("| File / area | Purpose | Notes |", payload["table"])
        self.assertIn("`.github/workflows/sync-prd.yml`", payload["markdown"])
        self.assertIn("Factory Step 7d", payload["markdown"])
        self.assertIn("TICKET-1234", payload["markdown"])

    def test_DraftScopeComment_EmptyRegister_Skips(self):
        state = shipping_state(current_step="deliver.scope_comment", pr_extras_register=[])
        payload = foundry_deliver.draft_scope_comment(state, self.config)
        self.assertTrue(payload["skip"])
        self.assertEqual(payload["reason"], "pr_extras_register is empty")

    def test_DraftScopeComment_WrongStep_IsBlocked(self):
        state = shipping_state(current_step="deliver.ship")
        with self.assertRaises(foundry_deliver.DeliverError) as caught:
            foundry_deliver.draft_scope_comment(state, self.config)
        self.assertEqual(caught.exception.error_code, "JIRA_COMMENT_WRONG_STEP")


class JiraFormatCommentTests(unittest.TestCase):
    def setUp(self):
        self.config = delivery_config()
        self.state = shipping_state(
            current_step="deliver.scope_comment",
            pr_extras_register=[
                {"path": "AGENTS.md", "reason": "Factory Step 7", "step_id": "implement.documentation"}
            ],
        )

    def test_FormatComment_AtScopeCommentStep_ReturnsMcpPayload(self):
        body = "Scope comment body"
        payload = foundry_deliver.jira_format_comment(self.state, self.config, body)
        self.assertEqual(payload["mcp_tool"], "addCommentToJiraIssue")
        self.assertEqual(payload["arguments"]["issueIdOrKey"], "TICKET-1234")
        self.assertEqual(payload["arguments"]["commentBody"], body)
        self.assertEqual(payload["allowed_step"], "deliver.scope_comment")

    def test_FormatComment_OnDeliverShip_IsBlocked(self):
        state = shipping_state(current_step="deliver.ship")
        with self.assertRaises(foundry_deliver.DeliverError) as caught:
            foundry_deliver.jira_format_comment(state, self.config, "too late")
        self.assertEqual(caught.exception.error_code, "JIRA_COMMENT_WRONG_STEP")

    def test_FormatComment_AnalysisRun_IsBlocked(self):
        state = base_state(
            run_mode="analysis",
            current_step="analysis.deliver",
            pr_extras_register=[{"path": "x", "reason": "y"}],
        )
        with self.assertRaises(foundry_deliver.DeliverError) as caught:
            foundry_deliver.jira_format_comment(state, self.config, "never")
        self.assertEqual(caught.exception.error_code, "JIRA_COMMENT_FORBIDDEN")


class PrTitleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = delivery_config()
        self.config_path = Path(self.tmp.name) / "config.json"
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")
        self.state_path = Path(self.tmp.name) / "state.json"

    def write_state(self, **overrides):
        state = shipping_state(
            current_step="deliver.ship",
            resolved_pr_title=None,
            **overrides,
        )
        state["resolved_profile_hash"] = foundry.profile_hash(self.config)
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        return state

    def test_PrTitle_FromState_UsesConfigPattern(self):
        self.write_state()
        payload = foundry.pr_title(
            None,
            "Add profile support",
            None,
            True,
            state=foundry.load_state(self.state_path),
            config=self.config,
        )
        self.assertEqual(payload["title"], "TICKET-1234 - Add profile support")
        self.assertEqual(payload["pattern"], "{issue_key} - {brief_description}")

    def test_PrTitle_ConventionalPrefix_IsRejected(self):
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.pr_title(
                None,
                "feat(scope): do the thing",
                None,
                False,
            )
        self.assertEqual(caught.exception.error_code, "INVALID_CONVENTIONAL_COMMIT_TITLE")


class RunCompleteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = delivery_config()
        self.config_path = Path(self.tmp.name) / "config.json"
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")
        self.state_path = Path(self.tmp.name) / "state.json"
        self.app = Path(self.tmp.name) / "app"
        self.app.mkdir()
        (self.state_path.parent / "events.jsonl").write_text("", encoding="utf-8")

    def write_ship_state(self, **overrides):
        state = shipping_state(
            current_step="deliver.ship",
            app_folder=str(self.app),
            resolved_pr_title="TICKET-1234 - Add profile support",
            delivery_seal={
                "branch": "lynn/TICKET-1234",
                "base_head": "a" * 40,
                "index_tree": "b" * 40,
                "prepared_at": "2026-09-10T12:00:00Z",
                "staged_secrets_passed": True,
            },
            **overrides,
        )
        state["resolved_profile_hash"] = foundry.profile_hash(self.config)
        state.setdefault("steps", {}).setdefault("deliver.ship", {})["gate_decision"] = "approve"
        attach_run_manifest(state, self.app, self.state_path.parent)
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        write_critic_receipts(
            self.state_path.parent,
            run_id=state.get("run_id"),
            branch_point=state.get("default_branch") or "main",
        )
        return state

    @staticmethod
    def matching_gh_runner(argv, _cwd):
        if argv[:3] == ["gh", "pr", "view"]:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "url": "https://github.com/example/example/pull/42",
                        "title": "TICKET-1234 - Add profile support",
                        "headRefName": "lynn/TICKET-1234",
                        "headRefOid": "c" * 40,
                        "commits": [{"oid": "c" * 40}],
                    }
                ),
                stderr="",
            )
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"tree": {"sha": "b" * 40}}),
            stderr="",
        )

    def test_RunComplete_RecordsPrUrlAndEmitsRunCompleted(self):
        self.write_ship_state()
        with mock.patch.object(
            foundry,
            "validate_delivery_seal",
            return_value={
                "branch": "lynn/TICKET-1234",
                "head": "c" * 40,
                "index_tree": "b" * 40,
            },
        ):
            foundry.verify_github_pr(
                self.state_path,
                pr_url="https://github.com/example/example/pull/42",
                resolved_pr_title="TICKET-1234 - Add profile support",
                runner=self.matching_gh_runner,
            )
            result = foundry.run_complete(
                self.state_path,
                pr_url="https://github.com/example/example/pull/42",
                config_path=str(self.config_path),
            )
        self.assertEqual(result["pr_url"], "https://github.com/example/example/pull/42")
        saved = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["pr_url"], result["pr_url"])
        self.assertEqual(saved["steps"]["deliver.ship"]["status"], "completed")
        events = [
            json.loads(line)
            for line in (self.state_path.parent / "events.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        completed = [event for event in events if event["event_type"] == "run_completed"]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0]["payload"]["pr_url"], result["pr_url"])
        self.assertEqual(completed[0]["step_id"], "deliver.ship")
        verified = [
            event
            for event in events
            if event["event_type"] == "external_operation"
            and event["payload"]["operation"] == "pr_verify"
        ]
        self.assertEqual(len(verified), 1)
        self.assertEqual(verified[0]["actor"], "engine")
        self.assertEqual(verified[0]["payload"]["evidence"]["verifier"], "authenticated_gh")

    def test_RunComplete_WithoutDeliverySeal_IsBlocked(self):
        state = self.write_ship_state()
        state.pop("delivery_seal")
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.run_complete(
                self.state_path,
                pr_url="https://github.com/example/example/pull/42",
                config_path=str(self.config_path),
            )
        self.assertEqual(caught.exception.error_code, "DELIVERY_SEAL_REQUIRED")

    def test_RunComplete_WithOpenWorkerLaunch_IsBlocked(self):
        self.write_ship_state(
            open_subagent_launches=[
                {
                    "launch_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
                    "step_id": "implement.build",
                    "agent": "feature-builder",
                    "work_item_id": "implement",
                    "started_at": "2026-09-10T12:00:00Z",
                }
            ]
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.run_complete(
                self.state_path,
                pr_url="https://github.com/example/example/pull/42",
                config_path=str(self.config_path),
            )
        self.assertEqual(caught.exception.error_code, "OPEN_WORK_REMAINS")

    def test_RunComplete_PrUrlWithoutExternalVerification_IsBlocked(self):
        self.write_ship_state()
        with mock.patch.object(
            foundry,
            "validate_delivery_seal",
            return_value={
                "branch": "lynn/TICKET-1234",
                "head": "c" * 40,
                "index_tree": "b" * 40,
            },
        ):
            with self.assertRaises(foundry.FoundryError) as caught:
                foundry.run_complete(
                    self.state_path,
                    pr_url="https://github.com/example/example/pull/42",
                    config_path=str(self.config_path),
                )
        self.assertEqual(caught.exception.error_code, "PR_VERIFICATION_REQUIRED")

    def test_PrVerify_MissingAuthenticationOrLookupFailure_IsRejected(self):
        self.write_ship_state()

        def failed_runner(_argv, _cwd):
            return SimpleNamespace(returncode=1, stdout="", stderr="not logged in")

        with mock.patch.object(
            foundry,
            "validate_delivery_seal",
            return_value={
                "branch": "lynn/TICKET-1234",
                "head": "c" * 40,
                "index_tree": "b" * 40,
            },
        ):
            with self.assertRaises(foundry.FoundryError) as caught:
                foundry.verify_github_pr(
                    self.state_path,
                    pr_url="https://github.com/example/example/pull/42",
                    resolved_pr_title="TICKET-1234 - Add profile support",
                    runner=failed_runner,
                )
        self.assertEqual(caught.exception.error_code, "PR_VERIFICATION_LOOKUP_FAILED")
        self.assertEqual((self.state_path.parent / "events.jsonl").read_text(encoding="utf-8"), "")

    def test_PrVerify_RemoteMismatch_EmitsNoSuccessEvidence(self):
        self.write_ship_state()

        def mismatching_runner(argv, _cwd):
            result = self.matching_gh_runner(argv, _cwd)
            if argv[:3] == ["gh", "pr", "view"]:
                payload = json.loads(result.stdout)
                payload["headRefName"] = "attacker/forged"
                result.stdout = json.dumps(payload)
            return result

        with mock.patch.object(
            foundry,
            "validate_delivery_seal",
            return_value={
                "branch": "lynn/TICKET-1234",
                "head": "c" * 40,
                "index_tree": "b" * 40,
            },
        ):
            with self.assertRaises(foundry.FoundryError) as caught:
                foundry.verify_github_pr(
                    self.state_path,
                    pr_url="https://github.com/example/example/pull/42",
                    resolved_pr_title="TICKET-1234 - Add profile support",
                    runner=mismatching_runner,
                )
        self.assertEqual(caught.exception.error_code, "PR_VERIFICATION_MISMATCH")
        self.assertIn("branch", caught.exception.extra["mismatches"])
        self.assertEqual((self.state_path.parent / "events.jsonl").read_text(encoding="utf-8"), "")

    def test_RunComplete_ForgedParentPrVerificationEvent_IsRejected(self):
        state = self.write_ship_state()
        forged = foundry.make_event(
            state["run_id"],
            "external_operation",
            "parent",
            step_id="deliver.ship",
            payload={
                "integration": "github",
                "operation": "pr_verify",
                "target": "https://github.com/example/example/pull/42",
                "status": "succeeded",
                "evidence": {
                    "branch": "lynn/TICKET-1234",
                    "head_sha": "c" * 40,
                    "tree": "b" * 40,
                    "title": "TICKET-1234 - Add profile support",
                    "verifier": "authenticated_gh",
                },
            },
        )
        foundry.append_event(self.state_path.parent / "events.jsonl", forged)
        with mock.patch.object(
            foundry,
            "validate_delivery_seal",
            return_value={
                "branch": "lynn/TICKET-1234",
                "head": "c" * 40,
                "index_tree": "b" * 40,
            },
        ):
            with self.assertRaises(foundry.FoundryError) as caught:
                foundry.run_complete(
                    self.state_path,
                    pr_url="https://github.com/example/example/pull/42",
                    config_path=str(self.config_path),
                )
        self.assertEqual(caught.exception.error_code, "PR_VERIFICATION_REQUIRED")

    def test_ExternalOperation_ParentPrVerificationAttestation_IsRejected(self):
        self.write_ship_state()
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.record_external_operation(
                self.state_path,
                integration="github",
                operation="pr_verify",
                target="https://github.com/example/example/pull/42",
                status="succeeded",
                evidence_json="{}",
            )
        self.assertEqual(caught.exception.error_code, "ENGINE_OWNED_EVIDENCE_REQUIRED")

    def test_DeliverySeal_WhenPreparedTreeChanged_IsBlocked(self):
        state = self.write_ship_state()
        with mock.patch.object(
            foundry,
            "call_shared",
            return_value={
                "branch": "lynn/TICKET-1234",
                "head": "c" * 40,
                "index_tree": "d" * 40,
            },
        ):
            with self.assertRaises(foundry.FoundryError) as caught:
                foundry.validate_delivery_seal(state)
        self.assertEqual(caught.exception.error_code, "DELIVERY_SEAL_STALE")

    def test_RunComplete_WithoutGateApproval_IsBlocked(self):
        state = self.write_ship_state()
        state["steps"]["deliver.ship"]["gate_decision"] = "skip"
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.run_complete(
                self.state_path,
                pr_url="https://github.com/example/example/pull/42",
                config_path=str(self.config_path),
            )
        self.assertEqual(caught.exception.error_code, "GATE_UNRESOLVED")


class DeliveryCliDispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = delivery_config()
        self.config_path = Path(self.tmp.name) / "config.json"
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")
        self.state_path = Path(self.tmp.name) / "state.json"
        state = shipping_state(
            current_step="deliver.scope_comment",
            pr_extras_register=[{"path": "AGENTS.md", "reason": "Factory Step 7"}],
        )
        state["resolved_profile_hash"] = foundry.profile_hash(self.config)
        self.state_path.write_text(json.dumps(state), encoding="utf-8")

    def test_FoundryCli_DraftScopeComment_Dispatches(self):
        payload = foundry.dispatch(
            foundry.build_parser().parse_args(
                [
                    "deliver",
                    "draft-scope-comment",
                    "--state",
                    str(self.state_path),
                    "--config",
                    str(self.config_path),
                ]
            )
        )
        self.assertFalse(payload["skip"])
        self.assertIn("AGENTS.md", payload["markdown"])

    def test_FoundryCli_JiraFormatComment_Dispatches(self):
        payload = foundry.dispatch(
            foundry.build_parser().parse_args(
                [
                    "jira",
                    "format-comment",
                    "--state",
                    str(self.state_path),
                    "--config",
                    str(self.config_path),
                    "--body",
                    "Posted scope comment",
                ]
            )
        )
        self.assertEqual(payload["mcp_tool"], "addCommentToJiraIssue")

    def test_FoundryCli_PrTitleFromState_Dispatches(self):
        ship_state = shipping_state(
            current_step="deliver.ship",
            resolved_pr_title="TICKET-1234 - Add profile support",
        )
        ship_state["resolved_profile_hash"] = foundry.profile_hash(self.config)
        ship_state_path = Path(self.tmp.name) / "ship-state.json"
        ship_state_path.write_text(json.dumps(ship_state), encoding="utf-8")
        payload = foundry.dispatch(
            foundry.build_parser().parse_args(
                [
                    "pr-title",
                    "--state",
                    str(ship_state_path),
                    "--config",
                    str(self.config_path),
                    "--summary",
                    "Add profile support",
                ]
            )
        )
        self.assertEqual(payload["title"], "TICKET-1234 - Add profile support")


class DeliveryTransitionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = foundry.deep_merge(
            foundry.load_config(None),
            {"devops": {"enabled": True, "run_before_pr": True}},
        )
        self.config_path = Path(self.tmp.name) / "config.json"
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")
        self.state_path = Path(self.tmp.name) / "state.json"

    def transition(self, state, target):
        app = Path(self.tmp.name) / "app"
        app.mkdir(exist_ok=True)
        state["app_folder"] = str(app)
        attach_run_manifest(state, app, self.state_path.parent)
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        write_critic_receipts(
            self.state_path.parent,
            run_id=state.get("run_id"),
            branch_point=state.get("default_branch") or "main",
        )
        return foundry.transition(
            self.state_path,
            target,
            config_path=str(self.config_path),
            flow_path=None,
            evidence=None,
            decision=None,
            assignments=[],
        )

    def test_Ship_DeliveryCheckFailing_IsBlocked(self):
        state = shipping_state()
        del state["steps"]["implement.pre_pr_review"]
        with self.assertRaises(foundry.FoundryError) as caught:
            self.transition(state, "deliver.ship")
        self.assertEqual(caught.exception.error_code, "DELIVERY_GATES_FAILED")


class DeliveryGitIntegrationTests(unittest.TestCase):
    def test_DeliveryPrepareAndComplete_RealGitSeal_RemainsValid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = root / "app"
            app.mkdir()

            def git(*args):
                return subprocess.run(
                    ["git", *args],
                    cwd=app,
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()

            git("init", "-b", "main")
            git("config", "user.email", "foundry@example.invalid")
            git("config", "user.name", "Foundry Test")
            (app / "README.md").write_text("baseline\n", encoding="utf-8")
            git("add", "README.md")
            git("commit", "-m", "baseline")
            branch = "lynn/TICKET-1234"
            git("checkout", "-b", branch)
            (app / "feature.txt").write_text("sealed content\n", encoding="utf-8")
            git("add", "feature.txt")

            run_dir = app / ".foundry" / "runs" / "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            run_dir.mkdir(parents=True)
            state_path = run_dir / "state.json"
            (run_dir / "events.jsonl").touch()
            config = delivery_config(
                foundry={
                    "orchestrator": {"require_integrity_check": False},
                    "delivery": {"require_pr_verification": True},
                }
            )
            (run_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")
            state = shipping_state(
                current_step="deliver.ship",
                app_folder=str(app),
                factory_root=str(foundry.REPO_ROOT),
                feature_branch=branch,
                resolved_pr_title="TICKET-1234 - Add profile support",
            )
            state["resolved_profile_hash"] = foundry.profile_hash(config)
            attach_run_manifest(state, app, run_dir)
            state.setdefault("steps", {}).setdefault("deliver.ship", {})["gate_decision"] = "approve"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            write_critic_receipts(
                run_dir,
                run_id=state.get("run_id"),
                head_sha=git("rev-parse", "HEAD"),
                branch_point="main",
            )

            prepared = foundry.prepare_delivery_seal(state_path, str(foundry.REPO_ROOT))
            git("commit", "-m", "feat: sealed delivery")
            head = git("rev-parse", "HEAD")
            tree = prepared["delivery_seal"]["index_tree"]

            def gh_runner(argv, _cwd):
                if argv[:3] == ["gh", "pr", "view"]:
                    payload = {
                        "url": "https://github.com/example/example/pull/42",
                        "title": "TICKET-1234 - Add profile support",
                        "headRefName": branch,
                        "headRefOid": head,
                        "commits": [{"oid": head}],
                    }
                else:
                    payload = {"tree": {"sha": tree}}
                return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

            foundry.verify_github_pr(
                state_path,
                pr_url="https://github.com/example/example/pull/42",
                resolved_pr_title="TICKET-1234 - Add profile support",
                runner=gh_runner,
            )
            result = foundry.run_complete(
                state_path,
                pr_url="https://github.com/example/example/pull/42",
                config_path=str(run_dir / "config.json"),
            )

            self.assertEqual(result["pr_url"], "https://github.com/example/example/pull/42")
            self.assertEqual(foundry.load_state(state_path)["outcome_status"], "completed")


if __name__ == "__main__":
    unittest.main()
