"""Evidence lineage and invalidation tests."""

import sys
import tempfile
import unittest
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[1]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry_lineage  # noqa: E402


class LineageTests(unittest.TestCase):
    def state(self):
        return {
            "approved_ac_version": 2,
            "approved_ac": [{"id": "ac-1", "text": "Works", "source": "proposed"}],
            "brief_snapshot": {"hash": "a" * 64},
            "steps": {
                "plan.graph": {"status": "completed", "human_approved": True},
                "implement.build": {"status": "completed"},
                "implement.validate": {"status": "completed"},
            },
            "delivery_seal": {"index_tree": "b" * 40},
        }

    def test_StampedGraph_IsCurrent(self):
        state = self.state()
        graph = {}
        foundry_lineage.stamp_graph(graph, state)
        foundry_lineage.assert_graph_current(graph, state)

    def test_ChangedAcVersion_MakesGraphStale(self):
        state = self.state()
        graph = foundry_lineage.stamp_graph({}, state)
        state["approved_ac_version"] = 3
        with self.assertRaises(foundry_lineage.LineageError) as caught:
            foundry_lineage.assert_graph_current(graph, state)
        self.assertEqual(caught.exception.error_code, "STALE_EXECUTION_GRAPH")

    def test_ReworkInvalidatesDescendantsAndDeliverySeal(self):
        state = self.state()
        invalidated = foundry_lineage.invalidate_after(state, "implement.build")
        self.assertIn("implement.validate", invalidated)
        self.assertNotIn("implement.validate", state["steps"])
        self.assertNotIn("delivery_seal", state)

    def test_GateDigest_ChangesWhenBriefChanges(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            state = self.state()
            before = foundry_lineage.gate_artifact_digest("plan.brief", state, run_dir)
            state["brief_snapshot"]["hash"] = "c" * 64
            after = foundry_lineage.gate_artifact_digest("plan.brief", state, run_dir)
        self.assertNotEqual(before, after)


if __name__ == "__main__":
    unittest.main()
