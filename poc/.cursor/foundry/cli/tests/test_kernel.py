"""Capability registry and retired-mode discovery tests."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[1]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry  # noqa: E402
import foundry_protocol  # noqa: E402


class KernelTests(unittest.TestCase):
    def test_ContractRegistry_LoadsPerWorkerContractFiles(self):
        registry = foundry_protocol.load_contract_registry()
        self.assertEqual(registry["protocol_version"], foundry_protocol.PROTOCOL_VERSION)
        agents = registry["agents"]
        self.assertIn("story-writer", agents)
        self.assertIn("backend-builder", agents)
        self.assertGreaterEqual(len(agents), 13)

    def test_WorkerContract_MergesModeBlock(self):
        contract = foundry_protocol.worker_contract("contracts/planner.yaml", "plan")
        self.assertEqual(contract["agent"], "planner")
        self.assertEqual(contract["mode"], "plan")
        self.assertIn("implement.branch", contract["valid_next_states"])

    def test_StepReceiptSchemas_AcceptsScalarOrArrayPaths(self):
        scalar = foundry.step_receipt_schemas(
            {"receipts": "schemas/intake-receipt.schema.json", "worker": {"prompt": "a", "contract": "b", "mode": "c"}}
        )
        self.assertEqual(scalar, ["schemas/intake-receipt.schema.json"])
        array_step = {
            "receipts": [
                "schemas/agent-receipt.schema.json",
                "schemas/intake-receipt.schema.json",
            ]
        }
        self.assertEqual(
            foundry.step_receipt_schemas(array_step),
            ["schemas/agent-receipt.schema.json", "schemas/intake-receipt.schema.json"],
        )
        self.assertTrue(foundry.intake_receipt_required(array_step))
        self.assertTrue(foundry.worker_receipt_required(array_step))

    def test_RunOnEnterAction_RecordsIntakeCheckStub(self):
        state = {"steps": {}}
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            foundry.run_on_enter_action(
                "validate_manifest",
                state_path=state_path,
                state=state,
                step_id="shape.intake",
            )
        self.assertEqual(
            state["steps"]["shape.intake"]["required_intake_checks"],
            ["validate_manifest"],
        )

    def test_StepWorker_ResolvesExplicitPromptAndContractPaths(self):
        step = {
            "worker": {
                "prompt": "agents/intake-checker.md",
                "contract": "contracts/intake-checker.yaml",
                "mode": "shape",
            }
        }
        worker = foundry.step_worker(step)
        self.assertEqual(worker["prompt"], "agents/intake-checker.md")
        self.assertEqual(worker["contract"], "contracts/intake-checker.yaml")
        self.assertEqual(worker["agent"], "intake-checker")
        self.assertEqual(worker["mode"], "shape")

    def test_WorkItemCapability_ResolvesRegisteredBuilders(self):
        agents = foundry_protocol.agents_for_capability("work_item")
        self.assertIn("backend-builder", agents)
        self.assertIn("feature-builder", agents)
        self.assertNotIn("implementation-validator", agents)

    def test_RetiredSyncInvocation_ReturnsClearUnsupportedError(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = foundry.main(["run", "sync", "--state", "stale.json"])
        payload = json.loads(output.getvalue())
        self.assertEqual(result, 1)
        self.assertEqual(payload["errorCode"], "UNSUPPORTED_MODE")

    def test_RetiredBugSquashInvocation_ReturnsClearUnsupportedError(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = foundry.main(
                ["run", "init", "--app-folder", ".", "--run-mode", "bug_squash"]
            )
        payload = json.loads(output.getvalue())
        self.assertEqual(result, 1)
        self.assertEqual(payload["errorCode"], "UNSUPPORTED_MODE")


if __name__ == "__main__":
    unittest.main()
