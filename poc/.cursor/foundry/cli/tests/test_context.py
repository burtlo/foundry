"""Worker context budget and redaction tests."""

import sys
import unittest
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[1]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry_context  # noqa: E402


class ContextTests(unittest.TestCase):
    def test_Redact_RemovesNestedSensitiveValues(self):
        value, paths = foundry_context.redact(
            {"service": {"access_token": "secret", "site_url": "https://example.test"}}
        )
        self.assertEqual(value["service"]["access_token"], "[REDACTED]")
        self.assertEqual(value["service"]["site_url"], "https://example.test")
        self.assertEqual(paths, ["service.access_token"])

    def test_EnforcePacket_CountsEntirePacket(self):
        with self.assertRaises(foundry_context.ContextError) as caught:
            foundry_context.enforce_packet(
                {"inputs": {}, "config": {}, "prompt": "x" * 100},
                {"max_input_chars": 50, "max_summary_chars": 20},
            )
        self.assertEqual(caught.exception.error_code, "WORKER_CONTEXT_BUDGET_EXCEEDED")

    def test_EnforceSummary_RejectsOversizeCraft(self):
        with self.assertRaises(foundry_context.ContextError) as caught:
            foundry_context.enforce_summary(
                {"outputs": {"summary_markdown": "x" * 21}},
                {"max_input_chars": 100, "max_summary_chars": 20},
            )
        self.assertEqual(caught.exception.error_code, "WORKER_SUMMARY_BUDGET_EXCEEDED")


if __name__ == "__main__":
    unittest.main()
