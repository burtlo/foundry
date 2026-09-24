"""Tests for foundry-invoke fence parsing and rendering."""

import sys
import unittest
from pathlib import Path
from unittest import mock

CLI_DIR = Path(__file__).resolve().parents[1]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry  # noqa: E402
import foundry_invoke  # noqa: E402


class FoundryInvokeTests(unittest.TestCase):
    def test_FormatFoundryCli_Windows_UsesCallOperatorAndQuotesPathsWithSpaces(self):
        with mock.patch.object(sys, "platform", "win32"):
            cli = foundry_invoke.format_foundry_cli(
                r"C:\Program Files\Python313\python.exe",
                r"C:\repos\My Org\factory\.cursor\foundry\cli\foundry.py",
            )
        self.assertEqual(
            cli,
            "& 'C:\\Program Files\\Python313\\python.exe' "
            "'C:\\repos\\My Org\\factory\\.cursor\\foundry\\cli\\foundry.py'",
        )

    def test_FormatFoundryCli_Posix_QuotesPathsWithSpaces(self):
        with mock.patch.object(sys, "platform", "linux"):
            cli = foundry_invoke.format_foundry_cli(
                "/opt/homebrew/bin/python3",
                "/Users/dev/My Projects/factory/.cursor/foundry/cli/foundry.py",
            )
        self.assertEqual(
            cli,
            "/opt/homebrew/bin/python3 '/Users/dev/My Projects/factory/.cursor/foundry/cli/foundry.py'",
        )

    def test_FormatLauncherCli_Windows_UsesCallOperator(self):
        with mock.patch.object(sys, "platform", "win32"):
            cli = foundry_invoke.format_launcher_cli(r"C:\repos\factory\.cursor\foundry\cli\foundry.ps1")
        self.assertEqual(cli, "& 'C:\\repos\\factory\\.cursor\\foundry\\cli\\foundry.ps1'")

    def test_FormatLauncherCli_Posix_UsesBash(self):
        with mock.patch.object(sys, "platform", "darwin"):
            cli = foundry_invoke.format_launcher_cli("/Users/dev/My Projects/factory/.cursor/foundry/cli/foundry.sh")
        self.assertEqual(cli, "bash '/Users/dev/My Projects/factory/.cursor/foundry/cli/foundry.sh'")

    def test_RenderFoundryInvoke_ResolvesRunContextPlaceholders(self):
        rendered = foundry_invoke.render_foundry_invoke(
            'worker validator-ready --file "{run_dir}/execution-graph.json"',
            'python "/factory/foundry.py"',
            {"run_dir": "/app/.foundry/runs/abc"},
        )
        self.assertEqual(
            rendered["argv_tail"],
            'worker validator-ready --file "/app/.foundry/runs/abc/execution-graph.json"',
        )
        self.assertIn('python "/factory/foundry.py"', rendered["shell"])

    def test_ValidateMarkdown_RejectsFoundryCliInsideFence(self):
        markdown = "```foundry-invoke\n{foundry_cli} run show --state x\n```"
        errors = foundry_invoke.validate_markdown(markdown, source="sample.md")
        self.assertTrue(any("foundry_cli" in error for error in errors))

    def test_ValidateMarkdown_RejectsMultiLineFence(self):
        markdown = "```foundry-invoke\nrun show --state a\nrun block --state a\n```"
        errors = foundry_invoke.validate_markdown(markdown, source="sample.md")
        self.assertTrue(any("exactly one invocation" in error for error in errors))

    def test_ValidateStepUnits_PassesCurrentRepo(self):
        payload = foundry_invoke.validate_step_units(foundry.FOUNDRY_ROOT / "steps")
        self.assertTrue(payload["valid"])
        self.assertGreater(payload["checked"], 0)
        self.assertEqual(payload["errors"], [])

    def test_InvokeRender_DispatchesThroughCli(self):
        payload = foundry.dispatch(
            foundry.build_parser().parse_args(
                [
                    "invoke",
                    "render",
                    "--tail",
                    'worker validator-ready --file "{run_dir}/execution-graph.json"',
                    "--factory-root",
                    str(foundry.REPO_ROOT),
                    "--foundry-cli",
                    'python "/factory/foundry.py"',
                ]
            )
        )
        self.assertIn("worker validator-ready", payload["argv_tail"])
        self.assertIn('python "/factory/foundry.py"', payload["shell"])


if __name__ == "__main__":
    unittest.main()
