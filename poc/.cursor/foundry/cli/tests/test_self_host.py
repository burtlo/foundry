"""Frozen Foundry self-host profile and ticket smoke lane."""

import sys
import tempfile
import unittest
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[1]
FOUNDRY_ROOT = CLI_DIR.parent
REPO_ROOT = FOUNDRY_ROOT.parents[1]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry  # noqa: E402
from app_manifest_support import write_app_manifest  # noqa: E402


class SelfHostTests(unittest.TestCase):
    def test_FrozenFrameworkTicket_InitializesLocalProtocolRun(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory)
            write_app_manifest(app, app_id="foundry-self-host")
            result = foundry.run_init(
                app_folder=str(app),
                issue_key="FOUNDRY-EVAL-001",
                run_mode="implementation",
                factory_root=str(REPO_ROOT),
                config_path=str(FOUNDRY_ROOT / "profiles" / "foundry-self-host.yaml"),
                developer_first_name="foundry",
                risk_tier="high",
                flow_path=None,
                run_id=None,
                ticket_file=str(FOUNDRY_ROOT / "eval" / "tickets" / "FOUNDRY-EVAL-001.md"),
            )
            state = foundry.load_state(Path(result["state_path"]))
        self.assertEqual(state["schema_version"], "2.2.0")
        self.assertEqual(state["ticket_source"], "local")
        self.assertEqual(state["current_step"], "intake.local")
        self.assertTrue(state["ticket_sealed"])


if __name__ == "__main__":
    unittest.main()
