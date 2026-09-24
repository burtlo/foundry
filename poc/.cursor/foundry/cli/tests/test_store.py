"""Transactional persistence tests for Foundry run state."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[1]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry_store  # noqa: E402


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run_dir = Path(self.tmp.name)
        self.state_path = self.run_dir / "state.json"

    def test_WriteStateCas_IncrementsRevisionAndUsesTransactionId(self):
        state = {"run_id": "run", "state_revision": 0}
        transaction_id = foundry_store.write_state_cas(
            self.state_path,
            state,
            expected_revision=0,
        )
        written = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(written["state_revision"], 1)
        self.assertEqual(written["last_transaction_id"], transaction_id)

    def test_WriteStateCas_StaleRevisionIsRejectedWithoutOverwrite(self):
        first = {"value": "first", "state_revision": 0}
        foundry_store.write_state_cas(self.state_path, first, expected_revision=0)
        stale = {"value": "stale", "state_revision": 0}
        with self.assertRaises(foundry_store.StoreError) as caught:
            foundry_store.write_state_cas(self.state_path, stale, expected_revision=0)
        self.assertEqual(caught.exception.error_code, "STALE_STATE_REVISION")
        self.assertEqual(
            json.loads(self.state_path.read_text(encoding="utf-8"))["value"],
            "first",
        )

    def test_RunLease_SecondWriterTimesOut(self):
        with foundry_store.run_lease(self.run_dir):
            with self.assertRaises(foundry_store.StoreError) as caught:
                with foundry_store.run_lease(self.run_dir, timeout_seconds=0.01):
                    pass
        self.assertEqual(caught.exception.error_code, "RUN_LEASE_TIMEOUT")

    def test_RecoverRun_RemovesTemporaryFilesAndReportsAlignment(self):
        transaction_id = foundry_store.write_state_cas(
            self.state_path,
            {"state_revision": 0},
            expected_revision=0,
        )
        foundry_store.append_jsonl(
            self.run_dir / "events.jsonl",
            {"transaction_id": transaction_id},
        )
        abandoned = self.run_dir / ".state.json.abandoned.tmp"
        abandoned.write_text("partial", encoding="utf-8")
        result = foundry_store.recover_run(self.run_dir)
        self.assertFalse(abandoned.exists())
        self.assertTrue(result["last_transaction_has_event"])
        self.assertTrue(result["last_transaction_committed"])


if __name__ == "__main__":
    unittest.main()
