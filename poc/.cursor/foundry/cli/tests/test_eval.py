"""Phase 11 tests: eval harness, failure taxonomy, compare-runs, quality gates."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = CLI_DIR.parents[2]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry  # noqa: E402
import foundry_eval  # noqa: E402
from app_manifest_support import write_app_manifest  # noqa: E402


class EvalHarnessTests(unittest.TestCase):
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
            config_path=None,
            developer_first_name="lynn",
            risk_tier="high",
            flow_path=None,
            run_id="44444444-4444-4444-8444-444444444444",
        )
        self.state_path = Path(init["state_path"])
        self.events_path = self.state_path.parent / "events.jsonl"
        self.receipts_dir = self.state_path.parent / "receipts"
        self.receipts_dir.mkdir(exist_ok=True)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_NormalizeFailureClass_AcceptsCodeAndName(self):
        self.assertEqual(foundry_eval.normalize_failure_class("A"), "ambiguity")
        self.assertEqual(foundry_eval.normalize_failure_class("process_violation"), "process_violation")

    def test_ClassifyFailure_WritesFailureClassifiedEvent(self):
        payload = foundry.metrics_classify(
            self.state_path,
            failure_class="C",
            source_step="plan.graph",
            notes="Wrong decomposition",
            receipt_id=None,
            actor="human",
        )
        self.assertEqual(payload["failure_class"], "plan_error")
        events = foundry_eval.load_events(self.events_path)
        classified = [event for event in events if event.get("event_type") == "failure_classified"]
        self.assertEqual(len(classified), 1)
        self.assertEqual(classified[0]["payload"]["failure_class"], "plan_error")

    def test_SuggestFailureClass_UsesReceiptHints(self):
        receipt_path = self.receipts_dir / "hint.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "receipt_id": "hint",
                    "failure_class": "missing_knowledge",
                    "blockers": ["Skipped AGENTS.md"],
                }
            ),
            encoding="utf-8",
        )
        payload = foundry.metrics_suggest(self.state_path, source_step="implement.build")
        self.assertEqual(payload["suggested"], "missing_knowledge")
        self.assertTrue(payload["hints"])

    def test_EnrichMetrics_AddsEvalSignals(self):
        state = foundry.load_state(self.state_path)
        state["feature_branch"] = "lynn/TICKET-2327"
        state["resolved_pr_title"] = "TICKET-2327 - Iris support"
        foundry.write_state(self.state_path, state)
        foundry.append_event(
            self.events_path,
            foundry.make_event(
                str(state["run_id"]),
                "subagent_launched",
                "parent",
                step_id="implement.documentation",
                payload={"agent": "documentation-writer", "mode": "implementation"},
            ),
        )
        metrics = foundry.observability_metrics_summarize(self.state_path)
        self.assertIn("eval_signals", metrics)
        self.assertEqual(metrics["eval_signals"]["documentation_writer_runs"], 1)
        self.assertEqual(metrics["eval_signals"]["pr_title_branch_violations"], 0)

    def test_GateUtility_ExcludesAutoResolutions(self):
        state = foundry.load_state(self.state_path)
        events = [
            foundry.make_event(
                str(state["run_id"]),
                "gate_resolved",
                "engine",
                step_id="plan.brief",
                payload={
                    "gate_kind": "human_approval",
                    "decision": "approve",
                    "source": "auto",
                    "gate_source": "auto",
                    "material_change": False,
                },
            ),
            foundry.make_event(
                str(state["run_id"]),
                "gate_resolved",
                "human",
                step_id="implement.code_review",
                payload={
                    "gate_kind": "human_approval",
                    "decision": "changes",
                    "source": "human",
                    "gate_source": "human",
                    "material_change": True,
                },
            ),
        ]
        signals = foundry_eval.derive_eval_signals(state=state, events=events)
        self.assertEqual(signals["gate_resolved_count"], 1)
        self.assertEqual(signals["gate_resolved_total_count"], 2)
        self.assertEqual(signals["gate_utility_ratio"], 1.0)

    def test_CompareRuns_ComputesDeltas(self):
        baseline = {
            "artifact": "foundry-run-metrics",
            "factory_version": "foundry",
            "metrics": {
                "eval_signals": {
                    "subagent_invocations": 27,
                    "documentation_writer_runs": 3,
                    "security_review_loops": 2,
                },
                "rework": {"validator_loops": 2, "builder_to_bugbot_loops": 2},
            },
        }
        candidate = {
            "artifact": "foundry-run-metrics",
            "factory_version": "foundry",
            "metrics": {
                "eval_signals": {
                    "subagent_invocations": 14,
                    "documentation_writer_runs": 1,
                    "security_review_loops": 1,
                },
                "rework": {"validator_loops": 1, "builder_to_bugbot_loops": 1},
            },
        }
        baseline_path = self.root / "baseline.json"
        candidate_path = self.root / "candidate.json"
        baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
        candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
        payload = foundry.metrics_compare_runs(str(baseline_path), str(candidate_path))
        self.assertEqual(payload["artifact"], "foundry-compare-runs")
        self.assertEqual(payload["deltas"]["subagent_invocations"], -13)
        self.assertEqual(payload["deltas"]["documentation_writer_runs"], -2)

    def test_CheckThresholds_PassesGoodCandidate(self):
        candidate = {
            "metrics": {
                "eval_signals": {
                    "subagent_invocations": 14,
                    "documentation_writer_runs": 1,
                    "delivery_check_bypass": 0,
                    "pr_title_branch_violations": 0,
                    "security_review_loops": 1,
                    "builder_launches_with_work_item": 6,
                    "orphan_launches": 0,
                    "hand_written_receipt_detected": 0,
                    "parent_app_edit_detected": 0,
                    "build_step_verify_bypass": 0,
                    "orphan_completions": 0,
                    "raw_dotnet_orchestrator": 0,
                    "missing_handoff": 0,
                    "invalid_delivery_proof": 0,
                    "auto_grill_with_clarifying_questions": 0,
                    "continued_after_worker_without_handoff": 0,
                }
            }
        }
        candidate_path = self.root / "candidate-metrics.json"
        candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
        payload = foundry.metrics_check_thresholds(
            candidate_path=str(candidate_path),
            state_path=None,
            baseline_path=str(candidate_path),
            packet="iris-eval-001",
            thresholds_path=str(foundry.DEFAULT_THRESHOLDS_PATH),
            transcript_path=None,
            scorecard_baseline=None,
            scorecard_candidate=None,
        )
        self.assertTrue(payload["passed"])

    def test_CheckThresholds_FailsDocWriterRework(self):
        candidate = {
            "metrics": {
                "eval_signals": {
                    "subagent_invocations": 14,
                    "documentation_writer_runs": 3,
                    "delivery_check_bypass": 0,
                    "pr_title_branch_violations": 0,
                    "security_review_loops": 0,
                    "builder_launches_with_work_item": 6,
                    "hand_written_receipt_detected": 0,
                    "parent_app_edit_detected": 0,
                    "build_step_verify_bypass": 0,
                    "orphan_launches": 0,
                    "orphan_completions": 0,
                    "raw_dotnet_orchestrator": 0,
                    "missing_handoff": 0,
                    "invalid_delivery_proof": 0,
                    "auto_grill_with_clarifying_questions": 0,
                    "continued_after_worker_without_handoff": 0,
                }
            }
        }
        candidate_path = self.root / "bad-metrics.json"
        candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
        payload = foundry.metrics_check_thresholds(
            candidate_path=str(candidate_path),
            state_path=None,
            baseline_path=None,
            packet="iris-eval-001",
            thresholds_path=str(foundry.DEFAULT_THRESHOLDS_PATH),
            transcript_path=None,
            scorecard_baseline=None,
            scorecard_candidate=None,
        )
        self.assertFalse(payload["passed"])
        failed = [check for check in payload["checks"] if not check["pass"]]
        self.assertEqual(failed[0]["name"], "documentation_writer_runs")

    def test_CheckThresholds_MissingRequiredDetectorFailsClosed(self):
        payload = foundry_eval.check_thresholds(
            {"eval_signals": {"present": 0}},
            {"required_signals": ["present", "mutated_away"]},
        )
        self.assertFalse(payload["passed"])
        missing = [
            check for check in payload["checks"]
            if check["name"] == "required_signal.mutated_away"
        ]
        self.assertEqual(missing[0]["actual"], "missing")

    def test_SchemaValidateExamples_PassesFixtures(self):
        payload = foundry.schema_validate_examples()
        self.assertEqual(payload["validated"], 8)

    def test_MetricsClassifyCommand_UsesRunId(self):
        payload = foundry.dispatch(
            foundry.build_parser().parse_args(
                [
                    "metrics",
                    "classify",
                    "--state",
                    str(self.state_path),
                    "--failure-class",
                    "I",
                    "--source-step",
                    "implement.code_review",
                    "--notes",
                    "Skipped step order",
                ]
            )
        )
        self.assertEqual(payload["failure_class"], "process_violation")


if __name__ == "__main__":
    unittest.main()
