"""Phase 4 graph routing and dispatch ownership tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

CLI_DIR = Path(__file__).resolve().parents[1]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry  # noqa: E402
import foundry_app  # noqa: E402
from app_manifest_support import (  # noqa: E402
    attach_run_manifest,
    routed_builders,
    write_app_manifest,
)
from test_foundry import base_state  # noqa: E402


def graph_for(
    *,
    owner: str,
    files_hint: list[str] | None = None,
    kind: str | None = None,
    work_item_id: str = "item-a",
) -> dict:
    item = {
        "id": work_item_id,
        "description": "Routed work",
        "owner": owner,
        "depends_on": [],
        "ac_refs": ["ac-1"],
        "files_hint": files_hint or [],
        "status": "pending",
    }
    if kind is not None:
        item["kind"] = kind
    return {
        "schema_version": foundry.SCHEMA_VERSION,
        "graph_id": "22222222-2222-4222-8222-222222222222",
        "run_id": "11111111-1111-4111-8111-111111111111",
        "issue_key": "TICKET-1234",
        "risk_tier": "medium",
        "approved_ac_version": 1,
        "topology": "sequential",
        "work_items": [item],
        "verification_plan": [
            {
                "step": "documentation-writer",
                "after": ["step6_human_approval"],
                "required": True,
            }
        ],
        "created_at": "2026-09-10T12:00:00Z",
    }


class BuilderRoutingRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run_dir = Path(self.tmp.name)
        self.app = self.run_dir / "app"
        self.app.mkdir()
        self.state_path = self.run_dir / "state.json"
        self.graph_path = self.run_dir / "execution-graph.json"
        self.config = foundry.load_config(None)
        state = base_state(
            current_step="implement.build",
            app_folder=str(self.app),
            approved_ac=[{"id": "ac-1", "text": "Done.", "source": "proposed"}],
            approved_ac_version=1,
            execution_graph_id="22222222-2222-4222-8222-222222222222",
            steps={"implement.build": {"status": "in_progress"}},
        )
        attach_run_manifest(state, self.app, self.run_dir, builders=routed_builders())
        foundry.write_state(self.state_path, state)
        (self.run_dir / "events.jsonl").touch()
        (self.run_dir / "receipts").mkdir()

    def write_graph(self, **kwargs) -> None:
        self.graph_path.write_text(
            json.dumps(graph_for(**kwargs), indent=2) + "\n",
            encoding="utf-8",
        )

    def validate(self):
        return foundry.graph_validate(
            str(self.graph_path),
            state_path=str(self.state_path),
            config=self.config,
        )

    def test_GraphValidate_ExactClientMatch_Passes(self):
        self.write_graph(owner="client-builder", files_hint=["Client/Models/Item.cs"])
        result = self.validate()
        self.assertTrue(result["valid"])

    def test_GraphValidate_PriorityOverlap_UsesHigherPriorityOwner(self):
        self.write_graph(owner="client-builder", files_hint=["Client/Widget.cs"])
        self.assertTrue(self.validate()["valid"])
        self.write_graph(owner="backend-builder", files_hint=["Client/Widget.cs"])
        with self.assertRaises(foundry.FoundryError) as caught:
            self.validate()
        self.assertEqual(caught.exception.error_code, "GRAPH_INVALID")
        self.assertTrue(
            any("client-builder" in err for err in caught.exception.extra["errors"])
        )

    def test_GraphValidate_NoMatch_UsesDefaultOwner(self):
        self.write_graph(owner="feature-builder", files_hint=["README.md"])
        self.assertTrue(self.validate()["valid"])
        self.write_graph(owner="backend-builder", files_hint=["README.md"])
        with self.assertRaises(foundry.FoundryError) as caught:
            self.validate()
        self.assertEqual(caught.exception.error_code, "GRAPH_INVALID")

    def test_GraphValidate_EmptyFilesHint_UsesDefaultOwner(self):
        self.write_graph(owner="feature-builder", files_hint=[])
        self.assertTrue(self.validate()["valid"])

    def test_GraphValidate_MultiOwnerFilesHint_IsRejected(self):
        self.write_graph(
            owner="feature-builder",
            files_hint=["Client/Models/Item.cs", "EmailSender.cs"],
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            self.validate()
        self.assertEqual(caught.exception.error_code, "GRAPH_INVALID")
        self.assertTrue(
            any("more than one builder owner" in err for err in caught.exception.extra["errors"])
        )

    def test_GraphValidate_UnknownOwner_IsRejected(self):
        self.write_graph(owner="invented-builder", files_hint=["README.md"])
        with self.assertRaises(foundry.FoundryError) as caught:
            self.validate()
        self.assertEqual(caught.exception.error_code, "GRAPH_INVALID")

    def test_GraphValidate_Tie_IsRejected(self):
        snapshot = foundry_app.load_run_manifest_snapshot(self.run_dir)
        snapshot["builders"]["routes"].append(
            {
                "id": "javascript",
                "owner": "feature-builder",
                "priority": 200,
                "globs": ["Client/**"],
            }
        )
        foundry_app.write_run_manifest_snapshot(self.run_dir, snapshot)
        state = foundry.load_state(self.state_path)
        state["app_manifest_hash"] = foundry_app.manifest_hash(snapshot)
        foundry.write_state(self.state_path, state)
        self.write_graph(owner="client-builder", files_hint=["Client/app.js"])
        with self.assertRaises(foundry.FoundryError) as caught:
            self.validate()
        self.assertEqual(caught.exception.error_code, "GRAPH_INVALID")
        self.assertTrue(any("tie" in err.lower() for err in caught.exception.extra["errors"]))

    def test_GraphValidate_RepairItem_SkipsAppRouting(self):
        self.write_graph(
            owner="repairer",
            kind="repair",
            files_hint=["Client/Models/Item.cs"],
            work_item_id="repair-build-1",
        )
        self.assertTrue(self.validate()["valid"])
        self.write_graph(
            owner="backend-builder",
            kind="repair",
            files_hint=["EmailSender.cs"],
            work_item_id="repair-build-1",
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            self.validate()
        self.assertEqual(caught.exception.error_code, "GRAPH_INVALID")

    def test_Dispatch_OwnerDisagreeingWithSnapshot_IsRejected(self):
        self.write_graph(owner="client-builder", files_hint=["EmailSender.cs"])
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.observability_subagent_launch(
                self.state_path,
                agent="client-builder",
                mode="implement",
                work_item="item-a",
                config_path=None,
            )
        self.assertEqual(caught.exception.error_code, "APP_MANIFEST_GRAPH_OWNER_MISMATCH")

    def test_BuilderPacket_CarriesSnapshotRouting(self):
        self.write_graph(owner="backend-builder", files_hint=["EmailSender.cs"])
        packet = foundry.builder_packet(
            state_path=self.state_path,
            graph_path=str(self.graph_path),
            work_item_id="item-a",
            receipts_dir=None,
            config_path=None,
        )
        self.assertEqual(packet["builder_routing"]["resolved_owner"], "backend-builder")
        self.assertEqual(packet["project_context"]["builders"]["default_owner"], "feature-builder")
        self.assertNotIn("backend_path_globs", packet["factory_config"].get("builders") or {})

    def test_GraphValidate_WithoutState_DoesNotRequireRouting(self):
        self.write_graph(owner="backend-builder", files_hint=["Client/Models/Item.cs"])
        result = foundry.graph_validate(
            str(self.graph_path),
            approved_ac="ac-1",
            config=self.config,
        )
        self.assertTrue(result["valid"])

    def test_GraphValidate_LiveYamlChange_DoesNotAffectSnapshotRouting(self):
        write_app_manifest(
            self.app,
            builders={
                "default_owner": "feature-builder",
                "routes": [
                    {
                        "id": "backend",
                        "owner": "backend-builder",
                        "priority": 100,
                        "globs": ["**/*.cs"],
                    }
                ],
            },
        )
        self.write_graph(owner="client-builder", files_hint=["Client/Models/Item.cs"])
        self.assertTrue(self.validate()["valid"])
        self.write_graph(owner="backend-builder", files_hint=["Client/Models/Item.cs"])
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.observability_subagent_launch(
                self.state_path,
                agent="backend-builder",
                mode="implement",
                work_item="item-a",
                config_path=None,
            )
        self.assertEqual(caught.exception.error_code, "APP_MANIFEST_GRAPH_OWNER_MISMATCH")


class ProfileSlimmingTests(unittest.TestCase):
    def test_TeamProfile_HasNoApplicationPathGlobs(self):
        foundry_dir = Path(__file__).resolve().parents[2]
        sources = sorted((foundry_dir / "profiles").glob("*.yaml"))
        sources.extend(
            [
                foundry_dir / "team-variables.md",
                foundry_dir / "team-variables.example.md",
            ]
        )
        self.assertTrue(sources)
        for path in sources:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("backend_path_globs", text, path.name)
            self.assertNotIn("client_path_globs", text, path.name)

    def test_RoleKeys_DoNotExposeBuilderPathGlobs(self):
        import foundry_mechanics

        for keys in foundry_mechanics.ROLE_KEYS.values():
            if not keys:
                continue
            self.assertNotIn("builders.backend_path_globs", keys)
            self.assertNotIn("builders.client_path_globs", keys)


if __name__ == "__main__":
    unittest.main()
