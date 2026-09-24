from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[1]
FOUNDRY_ROOT = CLI_DIR.parent
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry  # noqa: E402
import foundry_handoff  # noqa: E402
import foundry_tickets as tickets  # noqa: E402
from app_manifest_support import write_app_manifest  # noqa: E402


FIXTURE = FOUNDRY_ROOT / "fixtures" / "tickets" / "AUTH-001.md"
LOCAL_PROFILE = FOUNDRY_ROOT / "profiles" / "local-markdown.yaml"


class TicketLoadTests(unittest.TestCase):
    def test_LoadFixture_ReturnsPacket(self) -> None:
        packet = tickets.load_ticket_file(FIXTURE)
        self.assertEqual(packet["issue_key"], "AUTH-001")
        self.assertEqual(packet["ticket_source"], "local")
        self.assertIn("AUTH-001", packet["description"])
        self.assertGreaterEqual(len(packet["acceptance_criteria"]), 2)

    def test_IdMismatch_Raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "AUTH-001.md"
            path.write_text(
                "---\nid: OTHER\ntitle: x\n---\n\n# OTHER\n\nbody OTHER\n",
                encoding="utf-8",
            )
            with self.assertRaises(tickets.TicketError) as ctx:
                tickets.load_ticket_file(path)
            self.assertEqual(ctx.exception.error_code, "TICKET_ID_MISMATCH")

    def test_ListAndPick(self) -> None:
        root = FIXTURE.parent
        listed = tickets.list_tickets(root)
        self.assertGreaterEqual(listed["count"], 1)
        picked = tickets.pick_ticket(root, selection="AUTH-001")
        self.assertEqual(picked["selected"]["issue_key"], "AUTH-001")
        numbered = tickets.pick_ticket(root, selection="1")
        self.assertEqual(numbered["selected"]["issue_key"], listed["tickets"][0]["issue_key"])


class TicketCliTests(unittest.TestCase):
    def test_TicketLoad_ViaDispatch(self) -> None:
        parser = foundry.build_parser()
        args = parser.parse_args(["ticket", "load", "--file", str(FIXTURE)])
        result = foundry.dispatch(args)
        self.assertEqual(result["issue_key"], "AUTH-001")

    def test_RunInit_LocalProfile_AcceptsLocalKey(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "Example.Api"
            app.mkdir()
            write_app_manifest(app)
            tickets_dir = app / "tickets"
            tickets_dir.mkdir()
            (tickets_dir / "AUTH-001.md").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
            result = foundry.run_init(
                app_folder=str(app),
                issue_key="AUTH-001",
                run_mode="implementation",
                factory_root=str(FOUNDRY_ROOT.parents[1]),
                config_path=str(LOCAL_PROFILE),
                developer_first_name="lynn",
                risk_tier="medium",
                flow_path=None,
                run_id=None,
                interaction_mode="drive_to_pr",
            )
            state = json.loads(Path(result["state_path"]).read_text(encoding="utf-8"))
            self.assertEqual(state["factory_version"], "foundry")
            self.assertEqual(state["ticket_source"], "local")
            self.assertEqual(state["issue_key"], "AUTH-001")
            self.assertEqual(state["current_step"], "intake.local")

    def test_NormalizeIntake_DefaultsFromJiraEnabled(self) -> None:
        cfg = foundry.normalize_intake_config(
            {"jira": {"enabled": False, "project_key": "X"}, "intake": {}}
        )
        self.assertEqual(cfg["intake"]["source"], "chat")
        cfg2 = foundry.normalize_intake_config({"jira": {"enabled": True, "project_key": "X"}})
        self.assertEqual(cfg2["intake"]["source"], "jira")


class TicketSealTests(unittest.TestCase):
    def test_IngestAndSeal_OnRunInit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "Example.Api"
            app.mkdir()
            write_app_manifest(app)
            result = foundry.run_init(
                app_folder=str(app),
                issue_key=None,
                run_mode="implementation",
                factory_root=str(FOUNDRY_ROOT.parents[1]),
                config_path=str(LOCAL_PROFILE),
                developer_first_name="lynn",
                risk_tier="medium",
                flow_path=None,
                run_id=None,
                interaction_mode="drive_to_pr",
                ticket_file=str(FIXTURE),
            )
            ticket_path = Path(result["run_dir"]) / "ticket.json"
            self.assertTrue(ticket_path.is_file())
            sealed = json.loads(ticket_path.read_text(encoding="utf-8"))
            self.assertEqual(sealed["id"], "AUTH-001")
            self.assertEqual(sealed["source"], "local_file")
            state = json.loads(Path(result["state_path"]).read_text(encoding="utf-8"))
            self.assertEqual(state["issue_key"], "AUTH-001")
            self.assertTrue(state.get("ticket_sealed"))
            from jsonschema import Draft202012Validator

            schema = json.loads(
                (FOUNDRY_ROOT / "schemas" / "packets" / "ticket.schema.json").read_text(encoding="utf-8")
            )
            self.assertEqual(list(Draft202012Validator(schema).iter_errors(sealed)), [])

    def test_PasteIngest_ViaDispatch(self) -> None:
        text = FIXTURE.read_text(encoding="utf-8")
        parser = foundry.build_parser()
        args = parser.parse_args(["ticket", "ingest", "--text", text, "--source", "paste"])
        result = foundry.dispatch(args)
        self.assertEqual(result["source"], "paste")
        self.assertEqual(result["id"], "AUTH-001")

    def test_SaveTicket_WritesMarkdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sealed = tickets.ingest_ticket(file=FIXTURE, source="local_file")
            saved = tickets.save_ticket(sealed, tickets_root=root)
            self.assertTrue(Path(saved["path"]).is_file())
            loaded = tickets.load_ticket_file(Path(saved["path"]))
            self.assertEqual(loaded["issue_key"], "AUTH-001")


class IntegrityAndGateTests(unittest.TestCase):
    def test_GrillAuto_BlockedWhenClarifyingQuestionsRemain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            app.mkdir()
            write_app_manifest(app)
            init = foundry.run_init(
                app_folder=str(app),
                issue_key="AUTH-001",
                run_mode="implementation",
                factory_root=str(FOUNDRY_ROOT.parents[1]),
                config_path=str(LOCAL_PROFILE),
                developer_first_name="lynn",
                risk_tier="medium",
                flow_path=None,
                run_id=None,
                interaction_mode="drive_to_pr",
                ticket_file=str(FIXTURE),
            )
            state_path = Path(init["state_path"])
            state = foundry.load_state(state_path)
            state["current_step"] = "intake.grill"
            state["clarifying_questions_count"] = 3
            state["grilling_unresolved_count"] = 0
            foundry.write_state(state_path, state)
            with self.assertRaises(foundry.FoundryError) as ctx:
                foundry.gate_resolve(
                    state_path,
                    decision="approve",
                    source="auto",
                    config_path=str(init["config_path"]),
                )
            self.assertEqual(ctx.exception.error_code, "AUTO_GATE_NOT_ELIGIBLE")

    def test_SessionStop_WorkerStep(self) -> None:
        hint = foundry_handoff.session_stop_hint(
            "intake.refine",
            {"kind": "none"},
            has_subagent=True,
        )
        self.assertEqual(hint, "stop_after_worker")

    def test_IntegrityCheck_OkOnFreshSealedRun(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            app.mkdir()
            write_app_manifest(app)
            init = foundry.run_init(
                app_folder=str(app),
                issue_key="AUTH-001",
                run_mode="implementation",
                factory_root=str(FOUNDRY_ROOT.parents[1]),
                config_path=str(LOCAL_PROFILE),
                developer_first_name="lynn",
                risk_tier="medium",
                flow_path=None,
                run_id=None,
                interaction_mode="drive_to_pr",
                ticket_file=str(FIXTURE),
            )
            result = foundry.dispatch(
                foundry.build_parser().parse_args(
                    ["run", "integrity-check", "--state", init["state_path"]]
                )
            )
            self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
