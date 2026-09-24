"""Idempotent external-operation tests."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[1]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry  # noqa: E402
import foundry_integrations  # noqa: E402
from test_foundry import base_state  # noqa: E402


class IntegrationOperationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_path = Path(self.tmp.name) / "state.json"
        self.state_path.write_text(json.dumps(base_state()), encoding="utf-8")
        (self.state_path.parent / "events.jsonl").write_text("", encoding="utf-8")

    def test_OperationId_IsDeterministicForSameRequest(self):
        kwargs = {
            "run_id": base_state()["run_id"],
            "integration": "jira",
            "operation": "add_comment",
            "target": "TICKET-1",
            "request": {"body": "hello"},
        }
        self.assertEqual(
            foundry_integrations.operation_id(**kwargs),
            foundry_integrations.operation_id(**kwargs),
        )

    def test_PrepareThenSuccessThenRetry_IsIdempotent(self):
        prepared = foundry.record_external_operation(
            self.state_path,
            integration="jira",
            operation="add_comment",
            target="TICKET-1",
            status="prepared",
            evidence_json=None,
            request_json='{"body":"hello"}',
        )
        operation_id = prepared["payload"]["operation_id"]
        succeeded = foundry.record_external_operation(
            self.state_path,
            integration="jira",
            operation="add_comment",
            target="TICKET-1",
            status="succeeded",
            evidence_json='{"url":"https://example.test/comment/1"}',
            request_json='{"body":"hello"}',
            operation_id=operation_id,
            remote_id="comment-1",
        )
        retried = foundry.record_external_operation(
            self.state_path,
            integration="jira",
            operation="add_comment",
            target="TICKET-1",
            status="succeeded",
            evidence_json=None,
            request_json='{"body":"hello"}',
            operation_id=operation_id,
        )
        self.assertFalse(succeeded["idempotent"])
        self.assertTrue(retried["idempotent"])
        self.assertEqual(retried["event_id"], succeeded["event_id"])


if __name__ == "__main__":
    unittest.main()
