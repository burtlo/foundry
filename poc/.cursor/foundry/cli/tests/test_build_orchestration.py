"""Tests for implement.build orchestration: delegation enforcement and exit gates."""

import json
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace

CLI_DIR = Path(__file__).resolve().parents[1]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry  # noqa: E402
import foundry_observability  # noqa: E402
from app_manifest_support import attach_run_manifest, routed_builders  # noqa: E402
from test_foundry import base_state  # noqa: E402


def minimal_graph(*, completed: bool = False) -> dict:
    status = "completed" if completed else "pending"
    receipt_id = "aaaaaaaa-0001-4000-8000-000000000001" if completed else None
    item_a = {
        "id": "client-models",
        "description": "Client models",
        "owner": "client-builder",
        "depends_on": [],
        "ac_refs": ["ac-1"],
        "files_hint": ["Client/Models/Item.cs"],
        "evidence_required": ["unit-tests"],
        "status": status,
    }
    if receipt_id:
        item_a["receipt_id"] = receipt_id
    item_b = {
        "id": "iris-send",
        "description": "Iris send path",
        "owner": "backend-builder",
        "depends_on": ["client-models"],
        "ac_refs": ["ac-2"],
        "files_hint": ["EmailSender.cs"],
        "evidence_required": ["unit-tests"],
        "status": "pending",
    }
    return {
        "schema_version": foundry.SCHEMA_VERSION,
        "graph_id": "22222222-2222-4222-8222-222222222222",
        "run_id": "11111111-1111-4111-8111-111111111111",
        "issue_key": "TICKET-1234",
        "risk_tier": "medium",
        "approved_ac_version": 1,
        "topology": "sequential",
        "work_items": [item_a, item_b],
        "verification_plan": [],
        "created_at": "2026-09-10T12:00:00Z",
    }


def builder_receipt(
    *,
    receipt_id: str,
    work_item_id: str,
    agent: str,
) -> dict:
    return {
        "schema_version": foundry.SCHEMA_VERSION,
        "receipt_id": receipt_id,
        "run_id": "11111111-1111-4111-8111-111111111111",
        "work_item_id": work_item_id,
        "timestamp": "2026-09-10T12:30:00Z",
        "agent": {"name": agent, "mode": "implement"},
        "status": "completed",
        "recommended_next_state": "implement.build",
        "outputs": {
            "summary_markdown": f"Completed {work_item_id}.",
            "files_changed": [f"src/{work_item_id}.cs"],
        },
        "commands": [{"command": "dotnet test", "exit_code": 0}],
    }


def orchestrator_receipt(*, child_receipt_ids: list[str]) -> dict:
    return {
        "schema_version": foundry.SCHEMA_VERSION,
        "receipt_id": "bbbbbbbb-0002-4000-8000-000000000002",
        "run_id": "11111111-1111-4111-8111-111111111111",
        "timestamp": "2026-09-10T12:45:00Z",
        "agent": {"name": "feature-builder", "mode": "orchestrate"},
        "status": "completed",
        "recommended_next_state": "implement.validate",
        "child_receipt_ids": child_receipt_ids,
        "commands": [
            {"command": "foundry.py build", "exit_code": 0},
            {"command": "foundry.py test", "exit_code": 0},
        ],
    }


class BuildOrchestrationTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run_dir = Path(self.tmp.name)
        self.app_folder = self.run_dir / "app"
        self.app_folder.mkdir()
        self.state_path = self.run_dir / "state.json"
        self.graph_path = self.run_dir / "execution-graph.json"
        self.receipts_dir = self.run_dir / "receipts"
        self.receipts_dir.mkdir()
        (self.run_dir / "events.jsonl").touch()
        self.config_path = self.run_dir / "config.json"
        self.config_path.write_text(
            json.dumps(foundry.load_config(None)),
            encoding="utf-8",
        )

    def write_state(self, **overrides):
        state = base_state(
            current_step="implement.build",
            app_folder=str(self.app_folder),
            feature_branch="lynn/TICKET-1234",
            execution_graph_id="22222222-2222-4222-8222-222222222222",
            steps={"implement.build": {"status": "in_progress"}},
            **overrides,
        )
        attach_run_manifest(state, self.app_folder, self.run_dir, builders=routed_builders())
        foundry.write_state(self.state_path, state)
        return state

    def write_graph(self, graph: dict):
        self.graph_path.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")

    def write_receipt_file(self, receipt: dict) -> Path:
        path = self.receipts_dir / f"{receipt['receipt_id']}.json"
        path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        return path

    def complete_work_item(
        self,
        *,
        work_item_id: str,
        agent: str,
        receipt_id: str | None = None,
    ) -> str:
        launch = foundry.observability_subagent_launch(
            self.state_path,
            agent=agent,
            mode="implement",
            work_item=work_item_id,
            config_path=str(self.config_path),
        )
        staging_path = Path(launch["craft_staging_path"])
        receipt_id = str(launch["receipt_id"])
        receipt = builder_receipt(
            receipt_id=receipt_id,
            work_item_id=work_item_id,
            agent=agent,
        )
        craft = {
            key: receipt[key]
            for key in ("schema_version", "status", "outputs", "commands", "recommended_next_state")
        }
        staging_path.write_text(json.dumps(craft, indent=2) + "\n", encoding="utf-8")
        foundry.observability_subagent_complete(
            self.state_path,
            receipt=str(staging_path),
            launch_id=launch["launch_id"],
            config_path=str(self.config_path),
        )
        foundry.graph_complete_item(
            str(self.graph_path),
            work_item_id,
            receipt_id,
            state_path=self.state_path,
        )
        return receipt_id

    def test_FlowCurrent_ImplementBuild_ExposesOrchestrationNotSubagent(self):
        self.write_state()
        payload = foundry.flow_current(
            self.state_path,
            str(self.config_path),
            None,
        )
        self.assertIsNone(payload["subagent"])
        self.assertIn("orchestration", payload)
        self.assertEqual(payload["orchestration"]["kind"], "execution_graph_work_items")

    def test_SubagentLaunch_ImplementBuild_RequiresWorkItem(self):
        self.write_state()
        self.write_graph(minimal_graph())
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.observability_subagent_launch(
                self.state_path,
                agent="client-builder",
                mode="implement",
                work_item=None,
                config_path=str(self.config_path),
            )
        self.assertEqual(caught.exception.error_code, "WORK_ITEM_REQUIRED")

    def test_SubagentLaunch_ImplementBuild_RejectsAgentOwnerMismatch(self):
        self.write_state()
        self.write_graph(minimal_graph())
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.observability_subagent_launch(
                self.state_path,
                agent="backend-builder",
                mode="implement",
                work_item="client-models",
                config_path=str(self.config_path),
            )
        self.assertEqual(caught.exception.error_code, "AGENT_OWNER_MISMATCH")

    def test_SubagentComplete_ImplementBuild_RequiresLaunchId(self):
        self.write_state()
        self.write_graph(minimal_graph())
        launch = foundry.observability_subagent_launch(
            self.state_path,
            agent="client-builder",
            mode="implement",
            work_item="client-models",
            config_path=str(self.config_path),
        )
        staging_path = Path(launch["craft_staging_path"])
        staging_path.write_text(
            json.dumps(
                builder_receipt(
                    receipt_id="cccccccc-0003-4000-8000-000000000003",
                    work_item_id="client-models",
                    agent="client-builder",
                ),
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.observability_subagent_complete(
                self.state_path,
                receipt=str(staging_path),
                launch_id=None,
                config_path=str(self.config_path),
            )
        self.assertEqual(caught.exception.error_code, "LAUNCH_ID_REQUIRED")

    def test_SubagentComplete_RejectsReceiptUnderReceiptsDir(self):
        foundry.write_state(
            self.state_path,
            base_state(
                current_step="intake.refine",
                app_folder=str(self.app_folder),
                steps={"intake.refine": {"status": "in_progress"}},
            ),
        )
        launch = foundry.observability_subagent_launch(
            self.state_path,
            agent="story-writer",
            mode="implementation",
            work_item=None,
            config_path=str(self.config_path),
        )
        receipt_path = self.write_receipt_file(
            {
                "schema_version": foundry.SCHEMA_VERSION,
                "receipt_id": "dddddddd-0004-4000-8000-000000000004",
                "run_id": "11111111-1111-4111-8111-111111111111",
                "timestamp": "2026-09-11T12:00:00Z",
                "agent": {"name": "story-writer", "mode": "implementation"},
                "status": "completed",
                "outputs": {"summary_markdown": "ok"},
                "recommended_next_state": "intake.grill",
            }
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.observability_subagent_complete(
                self.state_path,
                receipt=str(receipt_path),
                launch_id=launch["launch_id"],
                config_path=str(self.config_path),
            )
        self.assertEqual(caught.exception.error_code, "RECEIPT_PARENT_AUTHORED")

    def test_Transition_ImplementBuildToValidate_BlockedWhenGraphIncomplete(self):
        self.write_state()
        self.write_graph(minimal_graph())
        step_receipt = orchestrator_receipt(child_receipt_ids=[])
        step_path = self.write_receipt_file(step_receipt)
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.transition(
                self.state_path,
                "implement.validate",
                config_path=str(self.config_path),
                flow_path=None,
                evidence=str(step_path),
                decision=None,
                assignments=[],
            )
        self.assertEqual(caught.exception.error_code, "BUILD_GRAPH_INCOMPLETE")

    def test_Transition_ImplementBuildToValidate_BlockedWithOpenLaunch(self):
        self.write_state()
        self.write_graph(minimal_graph())
        foundry.observability_subagent_launch(
            self.state_path,
            agent="client-builder",
            mode="implement",
            work_item="client-models",
            config_path=str(self.config_path),
        )
        step_path = self.write_receipt_file(orchestrator_receipt(child_receipt_ids=[]))
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.transition(
                self.state_path,
                "implement.validate",
                config_path=str(self.config_path),
                flow_path=None,
                evidence=str(step_path),
                decision=None,
                assignments=[],
            )
        self.assertIn(
            caught.exception.error_code,
            ("OPEN_SUBAGENT_LAUNCH", "BUILD_GRAPH_INCOMPLETE"),
        )

    def test_Transition_ImplementBuildToValidate_RejectsAggregateFeatureBuilderReceipt(self):
        self.write_state()
        self.write_graph(minimal_graph())
        self._complete_both_items()
        bad_step = {
            "schema_version": foundry.SCHEMA_VERSION,
            "receipt_id": "eeeeeeee-0005-4000-8000-000000000005",
            "run_id": "11111111-1111-4111-8111-111111111111",
            "timestamp": "2026-09-10T12:45:00Z",
            "agent": {"name": "feature-builder", "mode": "implement"},
            "status": "completed",
            "recommended_next_state": "implement.validate",
            "outputs": {
                "work_items_completed": ["client-models", "iris-send"],
            },
            "commands": [{"command": "dotnet build", "exit_code": 0}],
        }
        step_path = self.write_receipt_file(bad_step)
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.transition(
                self.state_path,
                "implement.validate",
                config_path=str(self.config_path),
                flow_path=None,
                evidence=str(step_path),
                decision=None,
                assignments=[],
            )
        self.assertEqual(caught.exception.error_code, "BUILD_STEP_RECEIPT_INVALID")

    def test_WorkerNextBuilder_ReturnsFirstReadyItem(self):
        self.write_state()
        self.write_graph(minimal_graph())
        payload = foundry.worker_next_builder(
            state_path=self.state_path,
            graph_path=str(self.graph_path),
            config_path=str(self.config_path),
        )
        self.assertFalse(payload["done"])
        self.assertEqual(payload["work_item_id"], "client-models")
        self.assertEqual(payload["packet"]["subagent"], "client-builder")

    def test_WorkerNextBuilder_WhenAllComplete_ReturnsDone(self):
        self.write_state()
        graph = minimal_graph(completed=True)
        graph["work_items"][1]["status"] = "completed"
        graph["work_items"][1]["receipt_id"] = "dddddddd-0004-4000-8000-000000000004"
        self.write_graph(graph)
        payload = foundry.worker_next_builder(
            state_path=self.state_path,
            graph_path=str(self.graph_path),
            config_path=str(self.config_path),
        )
        self.assertTrue(payload["done"])

    def test_CompleteItem_WithoutDelegationEvent_IsBlocked(self):
        self.write_state()
        self.write_graph(minimal_graph())
        receipt_id = "ffffffff-0006-4000-8000-000000000006"
        self.write_receipt_file(
            builder_receipt(
                receipt_id=receipt_id,
                work_item_id="client-models",
                agent="client-builder",
            )
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.graph_complete_item(
                str(self.graph_path),
                "client-models",
                receipt_id,
                state_path=self.state_path,
            )
        self.assertEqual(caught.exception.error_code, "BUILD_DELEGATION_UNPROVEN")

    def test_BuildStepVerify_FailsWhenDelegationIncomplete(self):
        self.write_state()
        self.write_graph(minimal_graph())
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.build_step_verify(
                self.state_path,
                graph_path=str(self.graph_path),
                config_path=str(self.config_path),
                runner=lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="ok", stderr=""),
            )
        self.assertEqual(caught.exception.error_code, "BUILD_GRAPH_INCOMPLETE")

    def _complete_both_items(self) -> tuple[str, str]:
        foundry.cursor_session_record(self.state_path, conversation_id="build-session-a")
        first_id = self.complete_work_item(
            work_item_id="client-models",
            agent="client-builder",
            receipt_id="aaaaaaaa-0001-4000-8000-000000000001",
        )
        foundry.run_handoff(self.state_path, config_path=str(self.config_path))
        foundry.cursor_session_record(self.state_path, conversation_id="build-session-b")
        second_id = self.complete_work_item(
            work_item_id="iris-send",
            agent="backend-builder",
            receipt_id="dddddddd-0004-4000-8000-000000000004",
        )
        foundry.run_handoff(self.state_path, config_path=str(self.config_path))
        foundry.cursor_session_record(self.state_path, conversation_id="build-session-c")
        return first_id, second_id

    def _zero_exit_runner(self, *_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    def test_BuildStepVerify_ExitCodeZero_Succeeds(self):
        self.write_state()
        self.write_graph(minimal_graph())
        self._complete_both_items()
        result = foundry.build_step_verify(
            self.state_path,
            graph_path=str(self.graph_path),
            config_path=str(self.config_path),
            runner=self._zero_exit_runner,
        )
        self.assertTrue(result["receipt_path"])
        state = foundry.load_state(self.state_path)
        self.assertEqual(
            state["steps"]["implement.build"]["build_step_verify_receipt_id"],
            result["receipt_id"],
        )
        receipt = json.loads(Path(result["receipt_path"]).read_text(encoding="utf-8"))
        self.assertEqual(receipt["provenance"]["source"], "build_step_verify")

    def test_HappyPath_TwoWorkItems_CanTransitionToValidate(self):
        self.write_state()
        self.write_graph(minimal_graph())
        self._complete_both_items()
        verify = foundry.build_step_verify(
            self.state_path,
            graph_path=str(self.graph_path),
            config_path=str(self.config_path),
            runner=self._zero_exit_runner,
        )
        foundry.run_handoff(
            self.state_path,
            config_path=str(self.config_path),
            flow_path=None,
        )
        result = foundry.transition(
            self.state_path,
            "implement.validate",
            config_path=str(self.config_path),
            flow_path=None,
            evidence=verify["receipt_path"],
            decision=None,
            assignments=[],
        )
        self.assertEqual(result["current_step"], "implement.validate")

    def test_Transition_BuildValidate_RequiresBuildStepVerifyEvent(self):
        self.write_state()
        self.write_graph(minimal_graph())
        first_id, second_id = self._complete_both_items()
        step_path = self.write_receipt_file(
            orchestrator_receipt(child_receipt_ids=[first_id, second_id])
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.transition(
                self.state_path,
                "implement.validate",
                config_path=str(self.config_path),
                flow_path=None,
                evidence=str(step_path),
                decision=None,
                assignments=[],
            )
        self.assertIn(
            caught.exception.error_code,
            ("BUILD_VERIFY_RECEIPT_FORGED", "CLI_EVIDENCE_MISSING", "BUILD_VERIFY_NOT_RUN"),
        )

    def test_Transition_BuildValidate_RejectsForgedReceipt(self):
        self.write_state()
        self.write_graph(minimal_graph())
        self._complete_both_items()
        verify = foundry.build_step_verify(
            self.state_path,
            graph_path=str(self.graph_path),
            config_path=str(self.config_path),
            runner=self._zero_exit_runner,
        )
        forged = orchestrator_receipt(child_receipt_ids=verify["child_receipt_ids"])
        forged["provenance"] = {
            "source": "build_step_verify",
            "cli_command": "build-step verify",
            "run_id": "11111111-1111-4111-8111-111111111111",
        }
        forged_path = self.write_receipt_file(forged)
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.transition(
                self.state_path,
                "implement.validate",
                config_path=str(self.config_path),
                flow_path=None,
                evidence=str(forged_path),
                decision=None,
                assignments=[],
            )
        self.assertEqual(caught.exception.error_code, "BUILD_VERIFY_RECEIPT_FORGED")

    def test_RunBlock_PreventsTransition(self):
        self.write_state()
        foundry.run_block(self.state_path, reason="manual block", step_id="implement.build")
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.transition(
                self.state_path,
                "implement.validate",
                config_path=str(self.config_path),
                flow_path=None,
                evidence=None,
                decision=None,
                assignments=[],
            )
        self.assertEqual(caught.exception.error_code, "RUN_BLOCKED")
        nxt = foundry.flow_next(self.state_path, str(self.config_path), None, None)
        self.assertIsNone(nxt["next_step"])
        self.assertTrue(nxt["blocked_by"])

    def test_GraphAddRepairItem_AppendsRepairerWorkItem(self):
        self.write_state()
        self.write_graph(minimal_graph())
        result = foundry.graph_add_repair_item(
            str(self.graph_path),
            state_path=self.state_path,
            item_id="repair-build-verify-1",
            reason="build-step verify BUILD_FAILED",
        )
        self.assertEqual(result["owner"], "repairer")
        self.assertEqual(result["kind"], "repair")
        graph = json.loads(self.graph_path.read_text(encoding="utf-8"))
        repair = next(item for item in graph["work_items"] if item["id"] == "repair-build-verify-1")
        self.assertEqual(repair["status"], "ready")
        self.assertGreaterEqual(graph["plan_stability"]["changes_after_build_started"], 1)
        packet = foundry.worker_next_builder(
            state_path=self.state_path,
            graph_path=str(self.graph_path),
            config_path=str(self.config_path),
        )
        self.assertEqual(packet["work_item_id"], "client-models")
        graph["work_items"][0]["status"] = "completed"
        graph["work_items"][0]["receipt_id"] = "aaaaaaaa-0001-4000-8000-000000000001"
        graph["work_items"][1]["status"] = "completed"
        graph["work_items"][1]["receipt_id"] = "dddddddd-0004-4000-8000-000000000004"
        self.write_graph(graph)
        ready = foundry.worker_next_builder(
            state_path=self.state_path,
            graph_path=str(self.graph_path),
            config_path=str(self.config_path),
        )
        self.assertEqual(ready["work_item_id"], "repair-build-verify-1")
        self.assertEqual(ready["packet"]["subagent"], "repairer")
        self.assertEqual(ready["packet"]["subagent_mode"], "repair")

    def test_OrchestratorPacket_ThinPayload(self):
        self.write_state()
        packet = foundry.flow_orchestrator_packet(
            self.state_path,
            str(self.config_path),
            None,
        )
        expected = {
            "foundry_cli",
            "factory_root",
            "app_folder",
            "state_path",
            "config_path",
            "run_dir",
            "run_id",
            "app_manifest_path",
            "app_manifest_id",
            "app_manifest_hash",
            "app_manifest_platform",
            "issue_key",
            "current_step",
            "step_title",
            "unit_relative",
            "task_subagent_type",
            "subagent_mode",
            "blocked",
            "gate",
            "next_invocations",
            "next_commands",
            "forbidden",
            "allowed",
            "open_subagent_launches",
            "interaction_mode",
            "gate_policy",
            "session_stop_hint",
            "valid_intents",
            "handoff_blurb",
            "worker_launch_contract",
            "steward_allowlist",
        }
        self.assertEqual(set(packet.keys()), expected)
        self.assertNotIn("factory_config", packet)
        self.assertNotIn("orchestration", packet)
        self.assertEqual(packet["current_step"], "implement.build")
        self.assertIn("app_source_edits", packet["forbidden"])
        self.assertIn("parent_write_brief_md", packet["forbidden"])
        self.assertIn("parent_write_execution_graph_json", packet["forbidden"])
        self.assertTrue(
            str(packet.get("worker_launch_contract") or "").endswith("worker-launch-contract.md")
        )
        self.assertTrue(packet["next_commands"])
        self.assertTrue(packet["next_invocations"])
        if sys.platform == "win32":
            self.assertIn("foundry.ps1", packet["foundry_cli"])
        else:
            self.assertIn("foundry.sh", packet["foundry_cli"])
        self.assertTrue(all(cmd.startswith(packet["foundry_cli"]) for cmd in packet["next_commands"]))
        self.assertEqual(
            [item["shell"] for item in packet["next_invocations"]],
            packet["next_commands"],
        )


if __name__ == "__main__":
    unittest.main()
