"""Static contracts for the app-manifest bootstrap surfaces."""

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
BOOTSTRAP_SKILL = (
    REPO_ROOT / ".cursor" / "skills" / "foundry-app-bootstrap" / "SKILL.md"
)
BOOTSTRAP_COMMAND = (
    REPO_ROOT / ".cursor" / "commands" / "foundry-app-bootstrap.md"
)


class FoundryAppBootstrapTests(unittest.TestCase):
    def test_bootstrap_command_is_thin_and_skill_delegates_to_cli(self) -> None:
        command = BOOTSTRAP_COMMAND.read_text(encoding="utf-8")
        skill = BOOTSTRAP_SKILL.read_text(encoding="utf-8")
        self.assertIn("@.cursor/skills/foundry-app-bootstrap/SKILL.md", command)
        self.assertNotIn("schema_version:", command)
        for subcommand in ("app discover", "app init", "app validate"):
            self.assertIn(subcommand, skill)
        self.assertIn("do not hand-write the manifest", skill)


if __name__ == "__main__":
    unittest.main()
