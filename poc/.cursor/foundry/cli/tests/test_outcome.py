"""Offline PR outcome observation tests."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

CLI_DIR = Path(__file__).resolve().parents[1]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry_outcome  # noqa: E402
from test_foundry import base_state  # noqa: E402


class OutcomeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_path = Path(self.tmp.name) / "state.json"
        self.pr_url = "https://github.com/example/repo/pull/1"
        state = base_state(
            outcome_status="completed",
            pr_url=self.pr_url,
            app_folder=self.tmp.name,
        )
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        (self.state_path.parent / "learning_record.json").write_text(
            json.dumps({"run_id": state["run_id"]}),
            encoding="utf-8",
        )

    @staticmethod
    def runner(*_args, **_kwargs):
        return SimpleNamespace(
            returncode=0,
            stderr="",
            stdout=json.dumps(
                {
                    "url": "https://github.com/example/repo/pull/1",
                    "state": "MERGED",
                    "mergedAt": "2026-09-17T12:00:00Z",
                    "closedAt": "2026-09-17T12:00:00Z",
                    "title": "FOUNDRY-1 - Durable outcomes",
                    "headRefName": "lynn/FOUNDRY-1",
                    "headRefOid": "a" * 40,
                    "statusCheckRollup": [
                        {"name": "tests", "conclusion": "SUCCESS"},
                    ],
                    "reviews": [{"state": "APPROVED"}],
                }
            ),
        )

    def test_Observe_WritesAppendOnlyOutcomeAndEnrichedLearning(self):
        result = foundry_outcome.observe(self.state_path, runner=self.runner)
        self.assertFalse(result["idempotent"])
        self.assertEqual(result["checks_total"], 1)
        self.assertTrue((self.state_path.parent / "learning_record.observed.json").is_file())

    def test_Observe_SameSnapshotIsIdempotent(self):
        first = foundry_outcome.observe(self.state_path, runner=self.runner)
        second = foundry_outcome.observe(self.state_path, runner=self.runner)
        self.assertFalse(first["idempotent"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(
            len((self.state_path.parent / "outcomes.jsonl").read_text(encoding="utf-8").splitlines()),
            1,
        )


if __name__ == "__main__":
    unittest.main()
