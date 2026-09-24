"""End-to-end walk of both flows through main(), the way the parent agent drives it.

Exercises the argv surface rather than the Python API, so a broken argparse
wiring or JSON envelope fails here rather than in a live run.
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

CLI_DIR = Path(__file__).resolve().parents[1]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry  # noqa: E402
from app_manifest_support import write_app_manifest  # noqa: E402

REVIEWS_OFF = {
    "devops": {"enabled": False, "run_before_pr": False},
    "review": {"enabled": False, "run_before_pr": False},
}


class WalkthroughTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.session_number = 0

    def run_cli(self, *argv, expect_success=True):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = foundry.main(list(argv))
        payload = json.loads(buffer.getvalue())
        self.assertEqual(
            payload["success"],
            expect_success,
            msg=f"{argv} -> {payload}",
        )
        self.assertEqual(code, 0 if expect_success else 1)
        return payload

    def config_file(self, data):
        path = self.root / "config.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return str(path)

    def init(self, run_mode, config_path):
        app = self.root / "app"
        app.mkdir(exist_ok=True)
        write_app_manifest(app)
        argv = [
            "run", "init",
            "--app-folder", str(app),
            "--issue-key", "TICKET-1234",
            "--run-mode", run_mode,
            "--developer-first-name", "lynn",
            "--config", config_path,
        ]
        config = json.loads(Path(config_path).read_text(encoding="utf-8"))
        if (config.get("intake") or {}).get("source") == "local":
            ticket = self.root / "TICKET-1234.md"
            ticket.write_text(
                "---\nid: TICKET-1234\ntype: Story\nsummary: Local walkthrough\n---\n\n"
                "# TICKET-1234 Local ticket\n\n## Acceptance criteria\n\n"
                "- The walkthrough reaches delivery.\n",
                encoding="utf-8",
            )
            argv.extend(["--ticket-file", str(ticket)])
        return self.run_cli(*argv)

    def present_gate(self, state, config):
        return self.run_cli(
            "observability", "gate", "present", "--state", state, "--config", config,
        )

    def record_brief(self, state):
        run_dir = Path(state).parent
        brief_path = run_dir / "brief.md"
        brief_path.write_text("# Brief\n", encoding="utf-8")
        return self.run_cli(
            "plan", "record-brief", "--state", state, "--brief-file", str(brief_path),
        )

    def step(self, state, config, target, *sets, decision=None):
        state_path = Path(state)
        snapshot = foundry.load_state(state_path)
        flow = foundry.get_flow(foundry.load_registry(None), snapshot["run_mode"])
        step_meta = foundry.get_step(flow, snapshot["current_step"])
        if step_meta.get("receipt_required") is True and not (
            (snapshot.get("steps") or {}).get(snapshot["current_step"], {}).get("launch_id")
        ):
            self.session_number += 1
            foundry.cursor_session_record(
                state_path,
                conversation_id=f"walkthrough-worker-{self.session_number}",
            )
            packet = foundry.worker_launch_packet(
                state_path,
                agent=None,
                mode=None,
                work_item=None,
                config_path=config,
                flow_path=None,
            )
            craft = {
                "schema_version": foundry.SCHEMA_VERSION,
                "status": "completed",
                "outputs": {
                    "summary_markdown": f"Completed {snapshot['current_step']}.",
                    "files_changed": [],
                    "artifacts": [packet["named_artifact_path"]] if packet["named_artifact_path"] else [],
                    "findings": [],
                },
                "exploration": {"files_examined": [], "questions_generated": []},
                "decisions": [],
                "commands": [],
                "recommended_next_state": target,
            }
            Path(packet["craft_staging_path"]).write_text(
                json.dumps(craft, indent=2) + "\n",
                encoding="utf-8",
            )
            foundry.observability_subagent_complete(
                state_path,
                receipt=packet["craft_staging_path"],
                launch_id=packet["launch_id"],
                config_path=config,
            )
            self.run_cli("run", "handoff", "--state", state, "--config", config)
            self.session_number += 1
            foundry.cursor_session_record(
                state_path,
                conversation_id=f"walkthrough-worker-{self.session_number}",
            )
        if decision:
            self.present_gate(state, config)
            self.run_cli(
                "gate", "resolve",
                "--state", state,
                "--config", config,
                "--source", "human",
                "--decision", decision,
            )
            if "session_stop_obligation" in json.loads(Path(state).read_text(encoding="utf-8")):
                current = foundry.load_state(state_path)
                if not current.get("active_conversation_id"):
                    self.session_number += 1
                    foundry.cursor_session_record(
                        state_path,
                        conversation_id=f"walkthrough-gate-{self.session_number}",
                    )
                self.run_cli("run", "handoff", "--state", state, "--config", config)
                self.session_number += 1
                foundry.cursor_session_record(
                    state_path,
                    conversation_id=f"walkthrough-gate-{self.session_number}",
                )
        argv = ["transition", "--state", state, "--to", target, "--config", config]
        for assignment in sets:
            if step_meta.get("receipt_required") is True and ".receipt_id=" in assignment:
                continue
            argv += ["--set", assignment]
        if decision:
            argv += ["--decision", decision]
        return self.run_cli(*argv)

    def complete_implement_build(self, state, config):
        foundry.cursor_session_record(Path(state), conversation_id="walkthrough-build-a")
        run_dir = Path(state).parent
        graph_path = run_dir / "execution-graph.json"
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        work_item = graph["work_items"][0]
        work_item_id = work_item["id"]
        agent = work_item["owner"]
        launch = self.run_cli(
            "observability",
            "subagent",
            "launch",
            "--state",
            state,
            "--agent",
            agent,
            "--mode",
            "implement",
            "--work-item",
            work_item_id,
            "--config",
            config,
        )
        staging_path = Path(launch["craft_staging_path"])
        receipt_id = launch["receipt_id"]
        receipt = {
            "schema_version": foundry.SCHEMA_VERSION,
            "status": "completed",
            "recommended_next_state": "implement.build",
            "outputs": {
                "summary_markdown": "Implemented the approved work item.",
                "files_changed": ["src/Feature.cs"],
            },
            "commands": [{"command": "dotnet test", "exit_code": 0}],
        }
        staging_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        self.run_cli(
            "observability",
            "subagent",
            "complete",
            "--state",
            state,
            "--receipt",
            str(staging_path),
            "--launch-id",
            launch["launch_id"],
            "--config",
            config,
        )
        self.run_cli(
            "worker",
            "complete-item",
            "--file",
            str(graph_path),
            "--work-item",
            work_item_id,
            "--receipt",
            receipt_id,
            "--state",
            state,
        )
        self.run_cli("run", "handoff", "--state", state, "--config", config)
        foundry.cursor_session_record(Path(state), conversation_id="walkthrough-build-b")
        verify = foundry.build_step_verify(
            Path(state),
            graph_path=str(graph_path),
            config_path=config,
            runner=lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="ok", stderr=""),
        )
        self.run_cli(
            "transition",
            "--state",
            state,
            "--to",
            "implement.validate",
            "--config",
            config,
            "--evidence",
            verify["receipt_path"],
        )

    def seed_execution_graph(self, state_path, ac_ids=("ac-1",)):
        state = json.loads(Path(state_path).read_text(encoding="utf-8"))
        graph = {
            "schema_version": foundry.SCHEMA_VERSION,
            "graph_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "run_id": state["run_id"],
            "issue_key": state.get("issue_key", "TICKET-1234"),
            "risk_tier": state.get("risk_tier", "medium"),
            "approved_ac_version": state.get("approved_ac_version", 1),
            "topology": "single_worker",
            "work_items": [
                {
                    "id": "implement",
                    "description": "Implement approved acceptance criteria",
                    "owner": "feature-builder",
                    "depends_on": [],
                    "ac_refs": list(ac_ids),
                    "status": "pending",
                }
            ],
            "verification_plan": [
                {"step": "implementation-validator", "after": ["implement"], "required": True},
                {"step": "documentation-writer", "after": ["step6_human_approval"], "required": True},
            ],
            "plan_stability": {"changes_after_build_started": 0},
            "created_at": "2026-09-10T12:00:00Z",
        }
        graph_path = Path(state_path).parent / "execution-graph.json"
        graph_path.write_text(json.dumps(graph), encoding="utf-8")
        return str(graph_path)

    def test_ImplementationFlow_ReviewsOff_WalksIntakeToShip(self):
        self._walk_implementation_source("jira")

    def test_ImplementationFlow_LocalSource_WalksToShipWithoutAtlassian(self):
        self._walk_implementation_source("local")

    def test_ImplementationFlow_ChatSource_WalksToShipWithoutAtlassian(self):
        self._walk_implementation_source("chat")

    def _walk_implementation_source(self, source):
        config = self.config_file(
            {
                **REVIEWS_OFF,
                "intake": {"source": source},
                "jira": {"enabled": source == "jira"},
            }
        )
        state = self.init("implementation", config)["state_path"]

        self.assertEqual(
            self.run_cli("flow", "current", "--state", state, "--config", config)["step_id"],
            {"jira": "intake.jira", "local": "intake.local", "chat": "intake.free_text"}[source],
        )

        if source == "local":
            self.step(state, config, "intake.pivot")
        elif source == "chat":
            self.step(state, config, "intake.pivot")
        else:
            self.step(state, config, "intake.pivot")
        self.step(state, config, "intake.refine", "run_mode=implementation")
        self.step(
            state,
            config,
            "intake.present_ac",
            'readiness="Ready"',
            "clarifying_questions_count=0",
            'steps.intake.refine.receipt_id="ae57a681-0000-4000-8000-000000000001"',
        )
        ac = '[{"id":"ac-1","text":"Given valid input, when processed, then success.","source":"proposed"}]'
        self.step(
            state,
            config,
            "intake.approve_ac",
            f"presented_ac={ac}",
            decision="approve",
        )
        self.step(
            state,
            config,
            "plan.research",
            f"approved_ac={ac}",
            "approved_ac_version=1",
            decision="approve",
        )
        self.step(state, config, "plan.brief")
        self.record_brief(state)
        self.seed_execution_graph(state)
        self.step(
            state,
            config,
            "plan.graph",
            decision="approve",
        )
        self.step(
            state, config, "implement.branch",
            decision="approve",
        )
        self.step(
            state, config, "implement.build",
            'default_branch="main"',
            'feature_branch="lynn/TICKET-1234"',
        )
        self.complete_implement_build(state, config)
        self.step(state, config, "implement.code_review")

        # Documentation is unreachable until the code review gate resolves.
        blocked = self.run_cli(
            "transition", "--state", state, "--to", "implement.documentation", "--config", config,
            expect_success=False,
        )
        self.assertEqual(blocked["errorCode"], "GATE_UNRESOLVED")

        self.step(
            state, config, "implement.documentation",
            decision="approve",
        )

        # Shipping is unreachable until delivery-check passes.
        self.run_cli("delivery-check", "--state", state, "--config", config, expect_success=False)

        self.step(
            state, config, "deliver.gate",
            'steps.implement.documentation.report="received"',
            decision="approve",
        )
        self.run_cli("delivery-check", "--state", state, "--config", config)
        if source == "jira":
            self.step(state, config, "deliver.scope_comment")
            self.step(state, config, "deliver.ship", decision="skip")
        else:
            self.step(state, config, "deliver.ship")

        final = self.run_cli("flow", "next", "--state", state, "--config", config)
        self.assertIsNone(final["next_step"])
        self.assertTrue(final["terminal"])

        summary = self.run_cli("run", "show", "--state", state)
        self.assertEqual(summary["current_step"], "deliver.ship")
        self.assertEqual(
            summary["step_evidence"]["intake.grill"]["status"], "skipped"
        )

        self.run_cli("schema", "validate", "--file", state, "--schema", "run-state")
        if source != "jira":
            events = [
                json.loads(line)
                for line in (Path(state).parent / "events.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            jira_operations = [
                event
                for event in events
                if event.get("event_type") == "external_operation"
                and (event.get("payload") or {}).get("integration") == "jira"
            ]
            self.assertEqual(jira_operations, [])

    def test_AnalysisFlow_ConfluenceOff_WalksIntakeToDeliver(self):
        config = self.config_file(
            {"analysis": {"confluence": {"enabled": False}, "follow_up_stories": {"enabled": False}}}
        )
        state = self.init("analysis", config)["state_path"]

        self.step(state, config, "intake.pivot")
        self.step(state, config, "intake.refine", "run_mode=analysis")
        self.step(
            state,
            config,
            "intake.present_ac",
            'readiness="Ready"',
            "clarifying_questions_count=0",
            'steps.intake.refine.receipt_id="ae57a681-0000-4000-8000-000000000001"',
        )
        ac = '[{"id":"d-1","text":"Deliver findings document.","source":"proposed"}]'
        self.step(
            state,
            config,
            "intake.approve_ac",
            f"presented_ac={ac}",
            decision="approve",
        )
        self.step(
            state,
            config,
            "analysis.research",
            f"approved_ac={ac}",
            "approved_ac_version=1",
            decision="approve",
        )
        self.step(
            state, config, "analysis.report",
            decision="approve",
        )
        self.step(
            state, config, "analysis.deliver",
            decision="approve",
        )

        final = self.run_cli("flow", "next", "--state", state, "--config", config)
        self.assertTrue(final["terminal"])
        self.present_gate(state, config)
        self.run_cli(
            "gate", "resolve",
            "--state", state,
            "--config", config,
            "--source", "human",
            "--decision", "approve",
        )
        self.run_cli("run", "handoff", "--state", state, "--config", config)
        foundry.cursor_session_record(
            Path(state),
            conversation_id="walkthrough-analysis-complete",
        )
        self.run_cli("run", "complete", "--state", state, "--config", config)
        self.run_cli("schema", "validate", "--file", state, "--schema", "run-state")

    def test_AnalysisFlow_CannotReachImplementationSteps(self):
        config = self.config_file({})
        state = self.init("analysis", config)["state_path"]
        self.step(state, config, "intake.pivot")
        failure = self.run_cli(
            "transition", "--state", state, "--to", "implement.build", "--config", config,
            expect_success=False,
        )
        self.assertEqual(failure["errorCode"], "UNKNOWN_STEP")


if __name__ == "__main__":
    unittest.main()
