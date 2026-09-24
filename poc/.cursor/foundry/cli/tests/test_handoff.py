"""Tests for multi-chat handoff, interaction modes, and learning finalize."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[1]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry  # noqa: E402
import foundry_handoff  # noqa: E402
from app_manifest_support import attach_run_manifest  # noqa: E402


def base_state(**overrides):
    state = {
        "schema_version": foundry.SCHEMA_VERSION,
        "run_id": "11111111-1111-4111-8111-111111111111",
        "factory_version": "foundry",
        "run_mode": "implementation",
        "current_step": "implement.code_review",
        "issue_key": "TICKET-1234",
        "app_folder": "/repo/app",
        "factory_root": "/repo/github-private",
        "risk_tier": "medium",
        "interaction_mode": "interactive",
        "steps": {},
        "pr_extras_register": [],
        "receipt_ids": [],
        "resolved_profile_hash": "92b7f02e46b6afaaed6e944a22fe150957008e9befa3d78c736c744188c33ad1",
        "created_at": "2026-09-10T12:00:00Z",
        "updated_at": "2026-09-10T12:00:00Z",
    }
    state.update(overrides)
    return state


class HandoffAndGatesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.app = self.root / "app"
        self.app.mkdir()
        profile = foundry.FOUNDRY_ROOT / "profiles" / "default.yaml"
        self.config = foundry.load_config(profile, factory_root=str(foundry.REPO_ROOT))

    def tearDown(self):
        self.tmp.cleanup()

    def _write_run(self, **overrides):
        run_id = overrides.pop("run_id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        run_dir = self.app / ".foundry" / "runs" / run_id
        run_dir.mkdir(parents=True)
        cfg_path = run_dir / "config.json"
        cfg_path.write_text(json.dumps(self.config), encoding="utf-8")
        state = base_state(
            run_id=run_id,
            app_folder=str(self.app),
            factory_root=str(foundry.REPO_ROOT),
            current_step=overrides.pop("current_step", "plan.brief"),
            interaction_mode=overrides.pop("interaction_mode", "drive_to_pr"),
            resolved_profile_hash=foundry.profile_hash(self.config),
            **overrides,
        )
        attach_run_manifest(state, self.app, run_dir)
        state_path = run_dir / "state.json"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        (run_dir / "events.jsonl").touch()
        return state_path, run_dir

    def test_list_and_latest(self):
        self._write_run(issue_key="TICKET-1")
        self._write_run(
            run_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            issue_key="TICKET-2",
            current_step="implement.build",
        )
        listed = foundry.run_list(str(self.app))
        self.assertGreaterEqual(len(listed["runs"]), 2)
        latest = foundry.run_latest(str(self.app), issue_key="TICKET-2")
        self.assertEqual(latest["run"]["issue_key"], "TICKET-2")

    def test_Handoff_NewConversationIdentity_FulfillsObligation(self):
        state_path, run_dir = self._write_run(
            active_conversation_id="conversation-a",
            session_stop_obligation={
                "reason": "stop_after_worker",
                "step_id": "plan.brief",
                "created_at": "2026-09-10T12:00:00Z",
                "launch_id": None,
            }
        )
        result = foundry.run_handoff(state_path)
        self.assertTrue(Path(result["handoff_md"]).is_file())
        self.assertTrue(Path(result["handoff_json"]).is_file())
        self.assertIn("Intent: resume", result["kickoff_prompt"])
        body = Path(result["handoff_md"]).read_text(encoding="utf-8")
        self.assertIn("run_id:", body)
        saved = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertIn("session_stop_obligation", saved)
        self.assertIn("last_handoff_at", saved)
        foundry.cursor_session_record(state_path, conversation_id="conversation-b")
        saved = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertNotIn("session_stop_obligation", saved)
        events = [
            json.loads(line)
            for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        self.assertTrue(events[-1]["payload"]["fresh_conversation_proven"])

    def test_Handoff_SameConversationIdentity_DoesNotFulfillObligation(self):
        state_path, _ = self._write_run(
            active_conversation_id="conversation-a",
            session_stop_obligation={
                "reason": "stop_after_worker",
                "step_id": "plan.brief",
                "created_at": "2026-09-10T12:00:00Z",
            },
        )
        foundry.run_handoff(state_path)
        foundry.cursor_session_record(state_path, conversation_id="conversation-a")
        saved = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertIn("session_stop_obligation", saved)

    def test_Handoff_NoSourceIdentity_FirstHostIdentityFulfillsWithoutClaimingProof(self):
        state_path, run_dir = self._write_run(
            session_stop_obligation={
                "reason": "stop_after_worker",
                "step_id": "plan.brief",
                "created_at": "2026-09-10T12:00:00Z",
            },
        )
        foundry.run_handoff(state_path)
        foundry.cursor_session_record(state_path, conversation_id="conversation-first-host-id")

        saved = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertNotIn("session_stop_obligation", saved)
        events = [
            json.loads(line)
            for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        session_event = events[-1]
        self.assertFalse(session_event["payload"]["fresh_conversation_proven"])
        self.assertEqual(
            session_event["payload"]["fulfilled_obligation"]["fulfillment_semantics"],
            "first_host_identity_after_handoff",
        )

    def test_GateResolve_DecisionOutsideConfiguredOptions_IsRejected(self):
        state_path, _ = self._write_run(current_step="plan.brief")
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.gate_resolve(
                state_path,
                decision="invented_outcome",
                source="human",
                config_path=None,
            )
        self.assertEqual(caught.exception.error_code, "INVALID_GATE_DECISION")

    def test_GateResolve_ReworkDecision_IsResolvedButNotHumanApproved(self):
        state_path, _ = self._write_run(
            current_step="plan.brief",
            interaction_mode="interactive",
        )
        foundry.observability_gate_present(state_path, config_path=None)
        foundry.gate_resolve(
            state_path,
            decision="changes",
            source="human",
            config_path=None,
        )
        evidence = foundry.load_state(state_path)["steps"]["plan.brief"]
        self.assertTrue(evidence["gate_resolved"])
        self.assertFalse(evidence["human_approved"])
        self.assertEqual(evidence["gate_outcome"], "changes")

    def test_transition_blocks_until_worker_handoff(self):
        state_path, _ = self._write_run(
            current_step="plan.brief",
            session_stop_obligation={
                "reason": "stop_after_worker",
                "step_id": "plan.brief",
                "created_at": "2026-09-10T12:00:00Z",
            },
        )
        with self.assertRaises(foundry.FoundryError) as ctx:
            foundry.transition(
                state_path,
                "plan.research",
                config_path=None,
                flow_path=None,
                evidence=None,
                decision="revise_research",
                assignments=[],
            )
        self.assertEqual(ctx.exception.error_code, "SESSION_HANDOFF_REQUIRED")

    def test_auto_gate_brief_when_snapshot_present(self):
        state_path, run_dir = self._write_run(
            current_step="plan.brief",
            interaction_mode="drive_to_pr",
            brief_snapshot={
                "version": 1,
                "hash": "a" * 64,
                "path": "brief.md",
                "captured_at": "2026-09-10T12:00:00Z",
            },
        )
        result = foundry.gate_resolve(
            state_path, decision="approve", source="auto", config_path=None
        )
        self.assertEqual(result["gate_source"], "auto")
        duplicate = foundry.gate_resolve(
            state_path, decision="approve", source="auto", config_path=None
        )
        self.assertTrue(duplicate["idempotent"])
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["steps"]["plan.brief"]["gate_source"], "auto")
        events = [
            json.loads(line)
            for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        resolved = [event for event in events if event["event_type"] == "gate_resolved"]
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["payload"]["gate_kind"], "human_approval")

    def test_auto_gate_rejected_in_interactive(self):
        state_path, _ = self._write_run(
            current_step="plan.brief",
            interaction_mode="interactive",
            brief_snapshot={
                "version": 1,
                "hash": "b" * 64,
                "path": "brief.md",
                "captured_at": "2026-09-10T12:00:00Z",
            },
        )
        with self.assertRaises(foundry.FoundryError) as ctx:
            foundry.gate_resolve(state_path, decision="approve", source="auto")
        self.assertEqual(ctx.exception.error_code, "AUTO_GATE_NOT_ELIGIBLE")

    def test_resume_packet_planner_for_brief(self):
        state_path, _ = self._write_run(current_step="plan.brief")
        packet = foundry.flow_resume_packet(state_path, None, None)
        self.assertEqual(packet["task_subagent_type"], "planner")
        self.assertEqual(packet["subagent_mode"], "brief")
        self.assertIn("session_stop_hint", packet)
        self.assertEqual(packet["schema_version"], foundry.SCHEMA_VERSION)
        self.assertIn("parent_write_brief_md", packet["forbidden"])
        self.assertIn("parent_write_execution_graph_json", packet["forbidden"])
        self.assertTrue(str(packet.get("worker_launch_contract") or "").endswith("worker-launch-contract.md"))

    def test_resume_packet_planner_for_graph(self):
        state_path, _ = self._write_run(current_step="plan.graph")
        packet = foundry.flow_orchestrator_packet(state_path, None, None)
        self.assertEqual(packet["task_subagent_type"], "planner")

    def test_graph_auto_requires_validated_flag(self):
        state = {
            "interaction_mode": "drive_to_pr",
            "steps": {},
        }
        run_dir = self.root / "graph-gate"
        run_dir.mkdir()
        (run_dir / "execution-graph.json").write_text("{}", encoding="utf-8")
        self.assertIsNone(
            foundry_handoff.gate_auto_decision("plan.graph", state, self.config, run_dir)
        )
        self.assertIsNotNone(
            foundry_handoff.gate_auto_decision(
                "plan.graph",
                state,
                self.config,
                run_dir,
                extras={"graph_validated": True},
            )
        )

    def test_finalize_learning(self):
        state_path, run_dir = self._write_run(current_step="deliver.ship")
        result = foundry.run_finalize_learning(state_path, outcome_status="completed")
        self.assertTrue(Path(result["learning_record"]).is_file())
        record = json.loads(Path(result["learning_record"]).read_text(encoding="utf-8"))
        self.assertEqual(record["outcome"]["status"], "completed")
        self.assertIn("gate_source_histogram", record)
        self.assertTrue(Path(result["learning_review"]).is_file())

    def test_sync_disabled(self):
        state_path, _ = self._write_run()
        with self.assertRaises(foundry.FoundryError) as ctx:
            foundry.run_sync(state_path)
        self.assertEqual(ctx.exception.error_code, "SYNC_DISABLED")

    def test_gate_policy_matrix(self):
        state = {
            "interaction_mode": "drive_to_pr",
            "grilling_unresolved_count": 0,
            "pr_extras_register": [],
            "steps": {"implement.documentation": {"report": "received"}},
        }
        run_dir = self.root / "r"
        run_dir.mkdir()
        self.assertIsNotNone(
            foundry_handoff.gate_auto_decision("intake.grill", state, self.config, run_dir)
        )
        self.assertIsNone(
            foundry_handoff.gate_auto_decision(
                "implement.code_review", state, self.config, run_dir
            )
        )
        self.assertEqual(
            foundry_handoff.gate_auto_decision(
                "deliver.scope_comment", state, self.config, run_dir
            )["decision"],
            "skip",
        )


if __name__ == "__main__":
    unittest.main()
