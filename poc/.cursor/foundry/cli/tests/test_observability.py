"""Phase 10 tests: observability, receipts, events, metrics, and transcript lint."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

CLI_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = CLI_DIR.parents[2]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry  # noqa: E402
import foundry_observability  # noqa: E402
from app_manifest_support import write_app_manifest  # noqa: E402
from test_foundry import base_state, write_jira_config  # noqa: E402

EVAL_SCRIPTS = REPO_ROOT / "evaluation" / "scripts"


class StepIdParsingTests(unittest.TestCase):
    def test_ParseStepId_SplitsPhaseAndStep(self):
        self.assertEqual(
            foundry_observability.parse_step_id("shape.examine"),
            {"phase": "shape", "step": "examine"},
        )
        self.assertEqual(
            foundry_observability.parse_step_id("verify.code_quality"),
            {"phase": "verify", "step": "code_quality"},
        )

    def test_BuildStatusPayload_IncludesInferredPhase(self):
        flow = {
            "entry": "shape.intake",
            "steps": {"shape.intake": {}, "shape.examine": {}},
            "edges": [{"from": "shape.intake", "to": "shape.examine"}],
        }
        state = {"current_step": "shape.examine", "steps": {}, "receipt_ids": []}
        with tempfile.TemporaryDirectory() as tmp:
            events = Path(tmp) / "events.jsonl"
            events.write_text("", encoding="utf-8")
            payload = foundry_observability.build_status_payload(state, events, flow=flow)
        self.assertEqual(payload["phase"], "shape")
        self.assertEqual(payload["step"], "examine")


class ObservabilityHelpersTests(unittest.TestCase):
    def test_AssertReceiptStagingPath_RejectsReceiptsDir(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            receipts_dir = run_dir / "receipts"
            receipts_dir.mkdir()
            staging = run_dir / "staging" / "launch.json"
            staging.parent.mkdir()
            staging.write_text("{}", encoding="utf-8")
            receipt_in_receipts = receipts_dir / "bad.json"
            receipt_in_receipts.write_text("{}", encoding="utf-8")
            with self.assertRaises(foundry_observability.ObservabilityError) as caught:
                foundry_observability.assert_receipt_staging_path(
                    receipt_in_receipts,
                    receipts_dir,
                    staging,
                )
            self.assertEqual(caught.exception.error_code, "RECEIPT_PARENT_AUTHORED")

    def test_SubagentLaunch_ReturnsCraftPathWithoutMutableScaffold(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            events_path = run_dir / "events.jsonl"
            events_path.touch()
            payload = foundry_observability.subagent_launch(
                run_id="11111111-1111-4111-8111-111111111111",
                run_dir=run_dir,
                events_path=events_path,
                step_id="intake.refine",
                agent="story-writer",
                mode="implementation",
                work_item_id=None,
                append_event=foundry.append_event,
                make_event=foundry.make_event,
                emit_events=False,
            )
            staging_path = Path(payload["craft_staging_path"])
            self.assertNotIn("receipt_staging_path", payload)
            self.assertFalse(staging_path.exists())
            self.assertTrue(Path(payload["receipt_meta_path"]).is_file())

    def test_ValidateReceiptDurable_ForbidsTranscriptFields(self):
        receipt = {
            "receipt_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "outputs": {"summary_markdown": "ok"},
            "transcript": "full model turns",
        }
        issues = foundry_observability.validate_receipt_durable(receipt)
        self.assertTrue(any("transcript" in issue for issue in issues))

    def test_ValidateReceiptDurable_AllowsSummaryAndFiles(self):
        receipt = {
            "outputs": {
                "summary_markdown": "Implemented idempotency.",
                "files_changed": ["src/Foo.cs"],
            }
        }
        self.assertEqual(foundry_observability.validate_receipt_durable(receipt), [])


class ObservabilityRunTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.app = self.root / "app"
        self.app.mkdir()
        write_app_manifest(self.app)
        init = foundry.run_init(
            app_folder=str(self.app),
            issue_key="TICKET-2327",
            run_mode="implementation",
            factory_root=str(foundry.REPO_ROOT),
            config_path=write_jira_config(self.root),
            developer_first_name="lynn",
            risk_tier="high",
            flow_path=None,
            run_id="33333333-3333-4333-8333-333333333333",
        )
        self.state_path = Path(init["state_path"])
        self.events_path = self.state_path.parent / "events.jsonl"
        self.receipts_dir = self.state_path.parent / "receipts"

    def tearDown(self):
        self.tempdir.cleanup()

    def write_receipt(self, receipt_id: str, **overrides) -> Path:
        receipt = {
            "schema_version": foundry.SCHEMA_VERSION,
            "receipt_id": receipt_id,
            "run_id": "33333333-3333-4333-8333-333333333333",
            "timestamp": "2026-09-10T12:00:00Z",
            "agent": {"name": "story-writer", "mode": "implementation"},
            "status": "completed",
            "outputs": {"summary_markdown": "Refined story.", "files_changed": []},
            "recommended_next_state": "intake.present_ac",
        }
        receipt.update(overrides)
        path = self.root / f"{receipt_id}.json"
        path.write_text(json.dumps(receipt), encoding="utf-8")
        return path

    def test_Status_IncompleteRun_ReturnsCurrentStepAndEvents(self):
        payload = foundry.observability_status(self.state_path, config_path=None, flow_path=None)
        self.assertEqual(payload["current_step"], "intake.jira")
        self.assertTrue(payload["incomplete"])
        self.assertGreaterEqual(len(payload["recent_events"]), 1)
        self.assertEqual(payload["recent_events"][-1]["event_type"], "run_started")

    def test_SubagentLaunchAndComplete_WritesEventsAndReceipt(self):
        launch = foundry.observability_subagent_launch(
            self.state_path,
            agent="story-writer",
            mode="implementation",
            work_item=None,
            config_path=None,
        )
        self.assertIn("craft_staging_path", launch)
        staging_path = Path(launch["craft_staging_path"])
        receipt = {
            "schema_version": foundry.SCHEMA_VERSION,
            "status": "completed",
            "outputs": {"summary_markdown": "Refined story.", "files_changed": []},
            "recommended_next_state": "intake.present_ac",
        }
        staging_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        receipt_id = launch["receipt_id"]
        complete = foundry.observability_subagent_complete(
            self.state_path,
            receipt=str(staging_path),
            launch_id=launch["launch_id"],
            config_path=None,
        )
        self.assertTrue((self.receipts_dir / f"{receipt_id}.json").is_file())
        events = foundry_observability.load_events(self.events_path)
        event_types = [event["event_type"] for event in events]
        self.assertIn("subagent_launched", event_types)
        self.assertIn("subagent_completed", event_types)
        self.assertIn("evidence_recorded", event_types)
        self.assertIn("formatted", complete)

    def test_WorkerLaunchPacket_AtomicallyLogsBoundedProtocolPacket(self):
        state = foundry.load_state(self.state_path)
        state["current_step"] = "intake.refine"
        state.setdefault("steps", {})["intake.refine"] = {"status": "in_progress"}
        foundry.write_state(self.state_path, state)
        packet = foundry.worker_launch_packet(
            self.state_path,
            agent=None,
            mode=None,
            work_item=None,
            config_path=None,
            flow_path=None,
        )
        self.assertEqual(packet["schema_version"], foundry.SCHEMA_VERSION)
        self.assertEqual(packet["agent"], "story-writer")
        self.assertIn(packet["craft_staging_path"], packet["allowed_writes"])
        self.assertIn(packet["craft_staging_path"], packet["prompt"])
        self.assertFalse(Path(packet["craft_staging_path"]).exists())
        launches = [
            event
            for event in foundry_observability.load_events(self.events_path)
            if event["event_type"] == "subagent_launched"
            and event["payload"]["launch_id"] == packet["launch_id"]
        ]
        self.assertEqual(len(launches), 1)

    def test_WorkerLaunchPacket_SchemaFailure_LeavesNoLaunchStateEventsOrArtifacts(self):
        state = foundry.load_state(self.state_path)
        state["current_step"] = "intake.refine"
        state.setdefault("steps", {})["intake.refine"] = {"status": "in_progress"}
        foundry.write_state(self.state_path, state)
        state_before = self.state_path.read_text(encoding="utf-8")
        events_before = self.events_path.read_text(encoding="utf-8")
        staging_dir = self.state_path.parent / "staging"
        files_before = sorted(path.name for path in staging_dir.glob("*")) if staging_dir.exists() else []
        real_validate = foundry.foundry_protocol.validate_schema

        def fail_launch_packet(instance, schema_name, *, artifact):
            if schema_name == "packets/worker-launch-packet.schema.json":
                raise foundry.foundry_protocol.ProtocolError(
                    "SCHEMA_VALIDATION_FAILED",
                    "forced worker packet failure",
                )
            return real_validate(instance, schema_name, artifact=artifact)

        with mock.patch.object(
            foundry.foundry_protocol,
            "validate_schema",
            side_effect=fail_launch_packet,
        ):
            with self.assertRaises(foundry.FoundryError) as caught:
                foundry.worker_launch_packet(
                    self.state_path,
                    agent=None,
                    mode=None,
                    work_item=None,
                    config_path=None,
                    flow_path=None,
                )

        self.assertEqual(caught.exception.error_code, "SCHEMA_VALIDATION_FAILED")
        self.assertEqual(self.state_path.read_text(encoding="utf-8"), state_before)
        self.assertEqual(self.events_path.read_text(encoding="utf-8"), events_before)
        files_after = sorted(path.name for path in staging_dir.glob("*")) if staging_dir.exists() else []
        self.assertEqual(files_after, files_before)

    def test_SubagentComplete_InvalidRecommendedNextState_IsRejected(self):
        state = foundry.load_state(self.state_path)
        state["current_step"] = "intake.refine"
        state.setdefault("steps", {})["intake.refine"] = {"status": "in_progress"}
        foundry.write_state(self.state_path, state)
        packet = foundry.worker_launch_packet(
            self.state_path,
            agent=None,
            mode=None,
            work_item=None,
            config_path=None,
            flow_path=None,
        )
        craft = {
            "schema_version": foundry.SCHEMA_VERSION,
            "status": "completed",
            "outputs": {"summary_markdown": "Refined story."},
            "recommended_next_state": "deliver.ship",
        }
        Path(packet["craft_staging_path"]).write_text(json.dumps(craft), encoding="utf-8")
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.observability_subagent_complete(
                self.state_path,
                receipt=packet["craft_staging_path"],
                launch_id=packet["launch_id"],
                config_path=None,
            )
        self.assertEqual(caught.exception.error_code, "RECEIPT_NEXT_STATE_INVALID")

    def test_ReceiptShow_FormatsSummaryWithoutTelemetry(self):
        launch = foundry.observability_subagent_launch(
            self.state_path,
            agent="story-writer",
            mode="implementation",
            work_item=None,
            config_path=None,
        )
        staging_path = Path(launch["craft_staging_path"])
        engine_receipt_id = launch["receipt_id"]
        receipt = {
            "schema_version": foundry.SCHEMA_VERSION,
            "status": "completed",
            "outputs": {"summary_markdown": "Refined story.", "files_changed": []},
            "recommended_next_state": "intake.present_ac",
        }
        staging_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        foundry.observability_subagent_complete(
            self.state_path,
            receipt=str(staging_path),
            launch_id=launch["launch_id"],
            config_path=None,
        )
        payload = foundry.observability_receipt_show(
            receipt_id=engine_receipt_id,
            state_path=self.state_path,
            receipts_dir=None,
        )
        self.assertIn("Refined story.", payload["formatted"])
        self.assertEqual(payload["telemetry_issues"], [])

    def test_SubagentCompleteFailure_AutoBlocksRun(self):
        launch = foundry.observability_subagent_launch(
            self.state_path,
            agent="story-writer",
            mode="implementation",
            work_item=None,
            config_path=None,
        )
        receipt_path = self.receipts_dir / "parent-authored.json"
        receipt_path.write_text("not-json", encoding="utf-8")
        exit_code = foundry.main(
            [
                "observability",
                "subagent",
                "complete",
                "--state",
                str(self.state_path),
                "--receipt",
                str(receipt_path),
                "--launch-id",
                launch["launch_id"],
            ]
        )
        self.assertNotEqual(exit_code, 0)
        state = foundry.load_state(self.state_path)
        self.assertIsNotNone(state.get("blocked"))

    def test_EventsTail_ReturnsRecentEvents(self):
        foundry.observability_subagent_launch(
            self.state_path,
            agent="story-writer",
            mode="implementation",
            work_item=None,
            config_path=None,
        )
        payload = foundry.observability_events_tail(self.state_path, count=5)
        self.assertGreaterEqual(payload["count"], 2)

    def test_MetricsExport_ProducesCompareRunsJson(self):
        state = foundry.load_state(self.state_path)
        state["rework"] = {"validator_loops": 1, "builder_to_bugbot_loops": 0}
        state["approved_ac_version"] = 2
        foundry.write_state(self.state_path, state)
        foundry.append_event(
            self.events_path,
            foundry.make_event(
                str(state["run_id"]),
                "gate_resolved",
                "human",
                step_id="intake.grill",
                payload={"gate_kind": "human_approval", "decision": "revise_ac", "material_change": True},
            ),
        )
        foundry.append_event(
            self.events_path,
            foundry.make_event(
                str(state["run_id"]),
                "cli_invoked",
                "cli",
                step_id="intake.jira",
                payload={"command": "flow current", "argv": ["flow", "current"]},
            ),
        )
        export = foundry.observability_metrics_export(self.state_path, None)
        self.assertEqual(export["artifact"], "foundry-run-metrics")
        metrics = export["metrics"]
        self.assertEqual(metrics["rework"]["validator_loops"], 1)
        self.assertEqual(metrics["cli_adoption"]["cli_invoked_count"], 1)
        self.assertEqual(metrics["clarification_yield"]["approved_ac_version"], 2)

    def test_StatusMarkdown_WritesStatusFile(self):
        payload = foundry.observability_status_markdown(
            self.state_path,
            config_path=None,
            flow_path=None,
            write_file=True,
        )
        status_path = Path(payload["status_path"])
        self.assertTrue(status_path.is_file())
        text = status_path.read_text(encoding="utf-8")
        self.assertIn("TICKET-2327", text)
        self.assertIn("intake.jira", text)

    def test_TransitionEvidence_RecordsSubagentCompleted(self):
        receipt_path = self.write_receipt("ae57a681-0000-4000-8000-000000000003")
        state = foundry.load_state(self.state_path)
        config = foundry.load_run_config(self.state_path, state, None)
        foundry.record_transition_receipt_events(
            self.state_path,
            state,
            config,
            receipt_path,
            ["ae57a681-0000-4000-8000-000000000003"],
            "intake.refine",
        )
        events = foundry_observability.load_events(self.events_path)
        event_types = [event["event_type"] for event in events]
        self.assertIn("subagent_completed", event_types)
        self.assertIn("evidence_recorded", event_types)

    def test_TopLevelStatusCommand_WorksOnIncompleteRun(self):
        payload = foundry.dispatch(
            foundry.build_parser().parse_args(
                [
                    "status",
                    "--state",
                    str(self.state_path),
                ]
            )
        )
        self.assertEqual(payload["current_step"], "intake.jira")
        self.assertTrue(payload["incomplete"])

    def test_SubagentComplete_RejectsAgentIdentityTamper(self):
        launch = foundry.observability_subagent_launch(
            self.state_path,
            agent="story-writer",
            mode="implementation",
            work_item=None,
            config_path=None,
        )
        staging_path = Path(launch["craft_staging_path"])
        receipt = {
            "schema_version": foundry.SCHEMA_VERSION,
            "status": "completed",
            "agent": {"name": "planner", "mode": "brief"},
            "outputs": {"summary_markdown": "tampered agent"},
            "recommended_next_state": "intake.present_ac",
        }
        staging_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        with self.assertRaises(foundry.FoundryError) as ctx:
            foundry.observability_subagent_complete(
                self.state_path,
                receipt=str(staging_path),
                launch_id=launch["launch_id"],
                config_path=None,
            )
        self.assertEqual(ctx.exception.error_code, "INVALID_CRAFT_OVERLAY")

    def test_SubagentComplete_RejectsScaffoldIdentityTamper(self):
        launch = foundry.observability_subagent_launch(
            self.state_path,
            agent="story-writer",
            mode="implementation",
            work_item=None,
            config_path=None,
        )
        staging_path = Path(launch["craft_staging_path"])
        receipt = {
            "schema_version": foundry.SCHEMA_VERSION,
            "status": "completed",
            "receipt_id": "ffffffff-ffff-4fff-8fff-ffffffffffff",
            "outputs": {"summary_markdown": "tampered"},
            "recommended_next_state": "intake.present_ac",
        }
        staging_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        with self.assertRaises(foundry.FoundryError) as ctx:
            foundry.observability_subagent_complete(
                self.state_path,
                receipt=str(staging_path),
                launch_id=launch["launch_id"],
                config_path=None,
            )
        self.assertEqual(ctx.exception.error_code, "INVALID_CRAFT_OVERLAY")

    def test_SubagentComplete_CraftOverlay_RejectsIdentityFields(self):
        launch = foundry.observability_subagent_launch(
            self.state_path,
            agent="story-writer",
            mode="implementation",
            work_item=None,
            config_path=None,
        )
        craft_path = Path(launch["craft_staging_path"])
        craft_path.write_text(
            json.dumps(
                {
                    "schema_version": foundry.SCHEMA_VERSION,
                    "status": "completed",
                    "outputs": {"summary_markdown": "craft only"},
                    "recommended_next_state": "intake.present_ac",
                    "receipt_id": "ffffffff-ffff-4fff-8fff-ffffffffffff",
                    "timestamp": "2000-01-01T00:00:00Z",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        with self.assertRaises(foundry.FoundryError) as ctx:
            foundry.observability_subagent_complete(
                self.state_path,
                receipt=str(craft_path),
                launch_id=launch["launch_id"],
                config_path=None,
            )
        self.assertEqual(ctx.exception.error_code, "INVALID_CRAFT_OVERLAY")

class TranscriptLintTests(unittest.TestCase):
    def test_AnalyzeTranscript_FlagsConfiguredRules(self):
        analyze = EVAL_SCRIPTS / "analyze-transcript.py"
        rules = EVAL_SCRIPTS / "transcript-rules.yaml"
        self.assertTrue(analyze.is_file())
        self.assertTrue(rules.is_file())
        import importlib.util

        spec = importlib.util.spec_from_file_location("analyze_transcript", analyze)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            transcript = Path(tmp) / "transcript.txt"
            transcript.write_text(
                "The parent read team-variables.md before launch and ran documentation-writer before code review.\n",
                encoding="utf-8",
            )
            payload = module.analyze_transcript(
                transcript.read_text(encoding="utf-8"),
                module.load_rules(rules),
            )
        rule_ids = {finding["rule_id"] for finding in payload["findings"]}
        self.assertIn("SKIP_STEP_ORDER", rule_ids)
        self.assertNotIn("READ_TEAM_VARIABLES", rule_ids)


if __name__ == "__main__":
    unittest.main()
