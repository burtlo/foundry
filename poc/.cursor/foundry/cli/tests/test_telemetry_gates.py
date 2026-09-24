"""Tests for gate presentation, brief snapshots, receipt semantics, and review guards."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[1]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry  # noqa: E402
import foundry_observability  # noqa: E402
from app_manifest_support import write_app_manifest  # noqa: E402
from test_foundry import base_state, complete_worker_step  # noqa: E402


class TelemetryGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run_dir = Path(self.tmp.name)
        self.app = self.run_dir / "app"
        self.app.mkdir()
        write_app_manifest(self.app)
        init = foundry.run_init(
            app_folder=str(self.app),
            issue_key="TICKET-2327",
            run_mode="implementation",
            factory_root=str(foundry.REPO_ROOT),
            config_path=None,
            developer_first_name="lynn",
            risk_tier="medium",
            flow_path=None,
            run_id="44444444-4444-4444-8444-444444444444",
        )
        self.state_path = Path(init["state_path"])
        self.config_path = self.state_path.parent / "config.json"

    def write_state(self, **overrides):
        existing = json.loads(self.state_path.read_text(encoding="utf-8"))
        steps = overrides.pop("steps", {"plan.brief": {"status": "in_progress"}})
        state = base_state(
            run_id="44444444-4444-4444-8444-444444444444",
            current_step="plan.brief",
            app_folder=str(self.app),
            factory_root=str(foundry.REPO_ROOT),
            resolved_profile_hash=existing.get("resolved_profile_hash"),
            app_manifest_id=existing.get("app_manifest_id"),
            app_manifest_hash=existing.get("app_manifest_hash"),
            app_manifest_platform=existing.get("app_manifest_platform"),
            interaction_mode=existing.get("interaction_mode", "drive_to_pr"),
            steps=steps,
            **overrides,
        )
        foundry.write_state(self.state_path, state)
        return state

    def test_GatePresent_ThenTransitionWithDecision_Succeeds(self):
        self.write_state()
        brief_path = self.state_path.parent / "brief.md"
        brief_path.write_text("# Brief\n", encoding="utf-8")
        foundry.plan_record_brief(self.state_path, brief_file=str(brief_path))
        complete_worker_step(
            self.state_path,
            self.config_path,
            agent="planner",
            mode="brief",
            next_state="plan.graph",
        )
        presented = foundry.observability_gate_present(self.state_path, config_path=str(self.config_path))
        self.assertEqual(presented["step_id"], "plan.brief")
        foundry.gate_resolve(
            self.state_path,
            decision="approve",
            source="human",
            config_path=str(self.config_path),
        )
        foundry.run_handoff(
            self.state_path,
            config_path=str(self.config_path),
            flow_path=None,
        )
        foundry.cursor_session_record(
            self.state_path,
            conversation_id="telemetry-plan-gate-resumed",
        )
        result = foundry.transition(
            self.state_path,
            "plan.graph",
            config_path=str(self.config_path),
            flow_path=None,
            evidence=None,
            decision="approve",
            assignments=[],
        )
        self.assertEqual(result["current_step"], "plan.graph")

    def test_TransitionWithDecision_WithoutGatePresent_IsBlocked(self):
        self.write_state()
        brief_path = self.state_path.parent / "brief.md"
        brief_path.write_text("# Brief\n", encoding="utf-8")
        foundry.plan_record_brief(self.state_path, brief_file=str(brief_path))
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.transition(
                self.state_path,
                "plan.graph",
                config_path=str(self.config_path),
                flow_path=None,
                evidence=None,
                decision="approve",
                assignments=[],
            )
        self.assertEqual(caught.exception.error_code, "GATE_UNRESOLVED")

    def test_PlanGraph_RequiresBriefSnapshot(self):
        self.write_state(
            steps={
                "plan.brief": {
                    "status": "in_progress",
                    "gate_presented": True,
                    "gate_decision": "approve",
                    "gate_outcome": "approve",
                }
            }
        )
        foundry.observability_gate_present(self.state_path, config_path=str(self.config_path))
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.transition(
                self.state_path,
                "plan.graph",
                config_path=str(self.config_path),
                flow_path=None,
                evidence=None,
                decision="approve",
                assignments=[],
            )
        self.assertEqual(caught.exception.error_code, "BRIEF_SNAPSHOT_MISSING")

    def test_ValidatorTransition_BlocksImportantGapsWithoutAcceptGaps(self):
        state = base_state(
            run_id="44444444-4444-4444-8444-444444444444",
            current_step="implement.validate",
            app_folder=str(self.app),
            steps={
                "implement.validate": {
                    "status": "completed",
                    "receipt_id": "99999999-9999-4999-8999-999999999999",
                }
            },
        )
        foundry.write_state(self.state_path, state)
        receipts_dir = self.state_path.parent / "receipts"
        receipts_dir.mkdir(exist_ok=True)
        receipt = {
            "schema_version": foundry.SCHEMA_VERSION,
            "receipt_id": "99999999-9999-4999-8999-999999999999",
            "run_id": state["run_id"],
            "timestamp": "2026-09-10T12:00:00Z",
            "agent": {"name": "implementation-validator", "mode": "validate"},
            "status": "completed",
            "recommended_next_state": "implement.code_review",
            "outputs": {
                "critical_count": 0,
                "important_count": 2,
                "findings": [{"severity": "important", "path": "Foo.cs", "issue": "gap"}],
            },
        }
        (receipts_dir / f"{receipt['receipt_id']}.json").write_text(
            json.dumps(receipt),
            encoding="utf-8",
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.transition(
                self.state_path,
                "implement.code_review",
                config_path=str(self.config_path),
                flow_path=None,
                evidence=None,
                decision=None,
                assignments=[],
            )
        self.assertEqual(caught.exception.error_code, "VALIDATOR_GAPS_UNACKNOWLEDGED")

    def test_ReceiptSemanticValidator_RequiresFindingsWhenCountsSet(self):
        receipt = {
            "agent": {"name": "implementation-validator"},
            "outputs": {"important_count": 1},
        }
        issues = foundry_observability.validate_receipt_semantic(receipt)
        self.assertTrue(issues)

    def test_SubagentMetrics_CountOrphanCompletions(self):
        events = [
            {
                "event_type": "subagent_launched",
                "payload": {"launch_id": "launch-1", "agent": "story-writer"},
            },
            {
                "event_type": "subagent_completed",
                "payload": {"agent": "grilling"},
            },
        ]
        metrics = foundry_observability.subagent_invocation_metrics(events)
        self.assertEqual(metrics["orphan_completions"], 1)


if __name__ == "__main__":
    unittest.main()
