from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

CLI_DIR = Path(__file__).resolve().parents[1]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry_mechanics as factory_cli  # noqa: E402


MINIMAL_YAML = """
# Team variables
```yaml
workspace:
  org_folder: github-private
  resolve_templates_from_org: true
jira:
  enabled: true
  project_key: TICKET
  issue_key_pattern: "^TICKET-\\\\d+$"
  pick_list_jql: |
    project = {{project_key}} AND sprint in openSprints()
git:
  pr_title_pattern: "{issue_key} - {brief_description}"
  feature_branch_pattern: "{developer_first_name}/{issue_key}"
templates:
  create_branch: ".cursor/commands/templates/create-branch-step.md"
  implement: ".cursor/commands/templates/implement-changes-step.md"
  add_tests: ".cursor/commands/templates/add-tests-step.md"
  run_tests: ".cursor/commands/templates/run-tests-step.md"
  update_docs: ".cursor/commands/templates/update-docs-step.md"
  generate_prd: ".cursor/commands/templates/generate-prd-step.md"
  code_review: ".cursor/commands/templates/code-review-step.md"
  commit_push: ".cursor/commands/templates/commit-push-step.md"
  documentation_workflow: ".cursor/commands/documentation-workflow.md"
  sync_prd_step: ".cursor/foundry/templates/sync-prd-step.md"
org:
  display_name: IoT
  required_labels: []
builders:
  enabled: true
  build_order:
    - backend
    - client
analysis:
  deliverable_sections:
    - findings
    - recommendations
  confluence:
    enabled: true
    title_pattern: "{issue_key} {summary}"
```
"""


class YamlFenceTests(unittest.TestCase):
    def test_extract_and_defaults(self) -> None:
        data = factory_cli.parse_team_variables_markdown(MINIMAL_YAML)
        self.assertTrue(data["devops"]["enabled"])
        self.assertTrue(data["review"]["run_before_pr"])
        self.assertEqual(data["review"]["mode"], "both")
        self.assertTrue(data["story_writer"]["require_full_ac_presentation"])
        self.assertEqual(data["jira"]["project_key"], "TICKET")

    def test_missing_fence(self) -> None:
        with self.assertRaises(factory_cli.FactoryError) as ctx:
            factory_cli.parse_team_variables_markdown("# no yaml here\n")
        self.assertEqual(ctx.exception.error_code, "INVALID_YAML")

    def test_invalid_yaml(self) -> None:
        with self.assertRaises(factory_cli.FactoryError) as ctx:
            factory_cli.parse_team_variables_markdown("```yaml\n:\n  -\n```\n")
        self.assertEqual(ctx.exception.error_code, "INVALID_YAML")


class ConfigGetLiveTests(unittest.TestCase):
    def test_live_team_variables_backend_role(self) -> None:
        factory_root = Path(__file__).resolve().parents[4]
        sliced = factory_cli.config_get(factory_root, "backend-builder", "Example.Api")
        self.assertEqual(sliced["role"], "backend-builder")
        self.assertIn("implement", sliced["templates"])
        self.assertNotIn("jira", sliced)
        self.assertNotIn("devops", sliced)


class RoleSliceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = factory_cli.parse_team_variables_markdown(MINIMAL_YAML)

    def test_backend_omits_unrelated(self) -> None:
        sliced = factory_cli.slice_role(
            self.data,
            "backend-builder",
            app_folder="Example.Api",
            factory_root="/factory",
        )
        self.assertEqual(sliced["role"], "backend-builder")
        self.assertNotIn("builders", sliced)
        self.assertNotIn("jira", sliced)
        self.assertNotIn("devops", sliced)

    def test_researcher_only_paths(self) -> None:
        sliced = factory_cli.slice_role(
            self.data,
            "codebase-researcher",
            app_folder="app",
            factory_root="/factory",
        )
        self.assertEqual(set(sliced.keys()), {"role", "app_folder", "factory_root"})

    def test_documentation_writer_includes_analysis(self) -> None:
        sliced = factory_cli.slice_role(
            self.data,
            "documentation-writer",
            app_folder="app",
            factory_root="/factory",
        )
        self.assertEqual(sliced["role"], "documentation-writer")
        self.assertIn("documentation_workflow", sliced["templates"])
        self.assertEqual(
            sliced["analysis"]["deliverable_sections"],
            ["findings", "recommendations"],
        )
        self.assertEqual(sliced["analysis"]["confluence"]["title_pattern"], "{issue_key} {summary}")
        self.assertNotIn("jira", sliced)
        self.assertNotIn("story_writer", sliced)

    def test_ticket_workflow_omits_factory_only(self) -> None:
        sliced = factory_cli.slice_role(
            self.data,
            "ticket-workflow",
            app_folder="Example.Api",
            factory_root="/factory",
        )
        self.assertEqual(sliced["role"], "ticket-workflow")
        self.assertEqual(sliced["jira"]["project_key"], "TICKET")
        self.assertIn("create_branch", sliced["templates"])
        self.assertIn("commit_push", sliced["templates"])
        self.assertNotIn("devops", sliced)
        self.assertNotIn("story_writer", sliced)
        self.assertNotIn("builders", sliced)

    def test_documentation_workflow_minimal(self) -> None:
        sliced = factory_cli.slice_role(
            self.data,
            "documentation-workflow",
            app_folder="Example.Api",
            factory_root="/factory",
        )
        self.assertEqual(sliced["role"], "documentation-workflow")
        self.assertIn("documentation_workflow", sliced["templates"])
        self.assertIn("sync_prd_step", sliced["templates"])
        self.assertNotIn("jira", sliced)
        self.assertNotIn("git", sliced)
        self.assertNotIn("devops", sliced)

    def test_unknown_role(self) -> None:
        with self.assertRaises(factory_cli.FactoryError) as ctx:
            factory_cli.slice_role(self.data, "not-a-role", app_folder=None, factory_root=None)
        self.assertEqual(ctx.exception.error_code, "UNKNOWN_ROLE")


class IssueKeyTests(unittest.TestCase):
    pattern = r"^TICKET-\d+$"

    def test_browse_url(self) -> None:
        key = factory_cli.parse_issue_key(
            "https://example.atlassian.net/browse/TICKET-2378",
            self.pattern,
        )
        self.assertEqual(key, "TICKET-2378")

    def test_project_issues_url(self) -> None:
        key = factory_cli.parse_issue_key(
            "https://example.atlassian.net/jira/software/projects/TICKET/issues/TICKET-12",
            self.pattern,
        )
        self.assertEqual(key, "TICKET-12")

    def test_jira_browse(self) -> None:
        key = factory_cli.parse_issue_key(
            "https://example.atlassian.net/jira/browse/TICKET-9",
            self.pattern,
        )
        self.assertEqual(key, "TICKET-9")

    def test_bare_key(self) -> None:
        key = factory_cli.parse_issue_key("please do TICKET-100", self.pattern)
        self.assertEqual(key, "TICKET-100")

    def test_pattern_reject(self) -> None:
        with self.assertRaises(factory_cli.FactoryError) as ctx:
            factory_cli.parse_issue_key("ABC-1", self.pattern)
        self.assertEqual(ctx.exception.error_code, "INVALID_ISSUE_KEY")

    def test_missing(self) -> None:
        with self.assertRaises(factory_cli.FactoryError) as ctx:
            factory_cli.parse_issue_key("no key here", self.pattern)
        self.assertEqual(ctx.exception.error_code, "MISSING_ISSUE_KEY")


class PrTitleTests(unittest.TestCase):
    def test_happy_path(self) -> None:
        title = factory_cli.build_pr_title(
            issue_key="TICKET-1",
            summary="Add webhook retry",
            pattern="{issue_key} - {brief_description}",
            jira_enabled=True,
        )
        self.assertEqual(title, "TICKET-1 - Add webhook retry")

    def test_reject_conventional(self) -> None:
        with self.assertRaises(factory_cli.FactoryError) as ctx:
            factory_cli.build_pr_title(
                issue_key="TICKET-1",
                summary="feat(TICKET-1): Upgrade",
                pattern="{brief_description}",
                jira_enabled=True,
            )
        self.assertEqual(ctx.exception.error_code, "INVALID_CONVENTIONAL_COMMIT_TITLE")

    def test_jira_missing_key(self) -> None:
        with self.assertRaises(factory_cli.FactoryError) as ctx:
            factory_cli.build_pr_title(
                issue_key=None,
                summary="goal phrase",
                pattern=None,
                jira_enabled=True,
            )
        self.assertEqual(ctx.exception.error_code, "MISSING_ISSUE_KEY")

    def test_free_text(self) -> None:
        title = factory_cli.build_pr_title(
            issue_key=None,
            summary="Add retry with idempotency",
            pattern="{issue_key} - {brief_description}",
            jira_enabled=False,
        )
        self.assertEqual(title, "Add retry with idempotency")


class BranchNameTests(unittest.TestCase):
    def test_expand(self) -> None:
        name = factory_cli.expand_branch_name(
            "{developer_first_name}/{issue_key}",
            developer_first_name="Alex",
            issue_key="TICKET-4",
        )
        self.assertEqual(name, "Alex/TICKET-4")


class DefaultBranchTests(unittest.TestCase):
    def test_last_segment(self) -> None:
        def runner(args, repo):
            if args[:3] == ["git", "rev-parse", "--abbrev-ref"]:
                return SimpleNamespace(returncode=0, stdout="origin/main\n", stderr="")
            return SimpleNamespace(returncode=1, stdout="", stderr="")

        branch = factory_cli.git_default_branch(Path("."), runner)
        self.assertEqual(branch, "main")

    def test_fallback_master(self) -> None:
        def runner(args, repo):
            if "rev-parse" in args:
                return SimpleNamespace(returncode=1, stdout="", stderr="")
            if args[-1].endswith("origin/main"):
                return SimpleNamespace(returncode=1, stdout="", stderr="")
            if args[-1].endswith("origin/master"):
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return SimpleNamespace(returncode=1, stdout="", stderr="")

        branch = factory_cli.git_default_branch(Path("."), runner)
        self.assertEqual(branch, "master")

    def test_local_master_without_remote(self) -> None:
        def runner(args, repo):
            if args[-1] == "refs/heads/master":
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return SimpleNamespace(returncode=1, stdout="", stderr="")

        branch = factory_cli.git_default_branch(Path("."), runner)
        self.assertEqual(branch, "master")


class BranchCreateTests(unittest.TestCase):
    def test_start_point_skips_default_checkout_and_pull(self) -> None:
        calls: list[list[str]] = []

        def runner(args, repo):
            calls.append(args)
            if args[:3] == ["git", "branch", "--show-current"]:
                return SimpleNamespace(returncode=0, stdout="version-0.4.0\n", stderr="")
            if args[:3] == ["git", "checkout", "-b"]:
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            if args[:2] == ["git", "checkout"]:
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            if args[:3] == ["git", "rev-parse", "HEAD"]:
                return SimpleNamespace(returncode=0, stdout="abc123\n", stderr="")
            return SimpleNamespace(returncode=1, stdout="", stderr="")

        result = factory_cli.branch_create(
            Path("."),
            "Lynn/ASST-003",
            runner,
            start_point="version-0.4.0",
        )
        self.assertEqual(result["branch"], "Lynn/ASST-003")
        self.assertEqual(result["default_branch"], "version-0.4.0")
        self.assertEqual(result["start_point"], "version-0.4.0")
        self.assertTrue(result["created"])
        self.assertFalse(any(args[:2] == ["git", "pull"] for args in calls))
        self.assertFalse(any(args == ["git", "checkout", "main"] for args in calls))
        self.assertIn(["git", "checkout", "-b", "Lynn/ASST-003"], calls)

    def test_start_point_already_on_feature_branch(self) -> None:
        def runner(args, repo):
            if args[:3] == ["git", "branch", "--show-current"]:
                return SimpleNamespace(returncode=0, stdout="Lynn/ASST-003\n", stderr="")
            if args[:3] == ["git", "rev-parse", "HEAD"]:
                return SimpleNamespace(returncode=0, stdout="def456\n", stderr="")
            return SimpleNamespace(returncode=1, stdout="", stderr="")

        result = factory_cli.branch_create(
            Path("."),
            "Lynn/ASST-003",
            runner,
            start_point="version-0.4.0",
        )
        self.assertFalse(result["created"])
        self.assertTrue(result["already_checked_out"])
        self.assertEqual(result["default_branch"], "version-0.4.0")
        self.assertEqual(result["head"], "def456")


class DeliveryCheckTests(unittest.TestCase):
    def ready_state(self, **overrides):
        state = {
            "step6_approved": True,
            "step7_doc_change_report": "received",
            "step7_human_approved": True,
            "prd_created_or_updated": False,
            "sync_prd_ok": False,
            "devops_enabled": True,
            "devops_run_before_pr": True,
            "step7b_report": "received",
            "step7b_approved": True,
            "review_enabled": True,
            "review_run_before_pr": True,
            "step7c_report": "received",
            "step7c_approved": True,
            "feature_branch_ok": True,
            "pr_extras_register": [],
        }
        state.update(overrides)
        return state

    def test_all_gates_pass(self) -> None:
        result = factory_cli.delivery_check(self.ready_state())
        self.assertTrue(result["passed"])

    def test_missing_step7_report(self) -> None:
        with self.assertRaises(factory_cli.FactoryError) as ctx:
            factory_cli.delivery_check(self.ready_state(step7_doc_change_report="missing"))
        self.assertEqual(ctx.exception.error_code, "DELIVERY_GATES_FAILED")
        self.assertIn("STEP7", ctx.exception.message)

    def test_7b_gated_off(self) -> None:
        result = factory_cli.delivery_check(
            self.ready_state(
                devops_run_before_pr=False,
                step7b_report="missing",
                step7b_approved=False,
            )
        )
        self.assertTrue(result["passed"])

    def test_7c_gated_off(self) -> None:
        result = factory_cli.delivery_check(
            self.ready_state(
                review_enabled=False,
                step7c_report="missing",
                step7c_approved=False,
            )
        )
        self.assertTrue(result["passed"])

    def test_sync_prd_required(self) -> None:
        with self.assertRaises(factory_cli.FactoryError) as ctx:
            factory_cli.delivery_check(
                self.ready_state(prd_created_or_updated=True, sync_prd_ok=False)
            )
        self.assertIn("SYNC_PRD", ctx.exception.message)

    def test_state_file_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text(json.dumps(self.ready_state()), encoding="utf-8")
            result = factory_cli.delivery_check(factory_cli.load_state(path))
            self.assertTrue(result["passed"])


class ManifestCommandTests(unittest.TestCase):
    def command(self, argv=None, cwd=".") -> dict:
        return {
            "argv": argv or ["python", "-c", "print('ok')"],
            "cwd": cwd,
            "timeout_seconds": 30,
        }

    def test_argv_is_passed_without_shell_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            captured: list[list[str]] = []

            def runner(args, cwd):
                captured.append(args)
                return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

            factory_cli.run_manifest_command(
                root,
                "test",
                self.command(["dotnet", "test", "My App/App.Tests.csproj"]),
                runner=runner,
            )
            self.assertEqual(captured[0], ["dotnet", "test", "My App/App.Tests.csproj"])

    def test_nonzero_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def runner(args, cwd):
                return SimpleNamespace(returncode=1, stdout="FAILED\n", stderr="")

            with self.assertRaises(factory_cli.FactoryError) as ctx:
                factory_cli.run_manifest_command(
                    root,
                    "test",
                    self.command(),
                    runner=runner,
                )
            self.assertEqual(ctx.exception.error_code, "COMMAND_FAILED")
            self.assertEqual(ctx.exception.extra["exitCode"], 1)

    def test_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def runner(args, cwd):
                return SimpleNamespace(returncode=0, stdout="Passed!\n", stderr="")

            result = factory_cli.run_manifest_command(
                root,
                "build",
                self.command(["python", "-c", "print('ok')"]),
                runner=runner,
            )
            self.assertEqual(result["exitCode"], 0)
            self.assertEqual(result["commandName"], "build")

    def test_parent_cwd_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(factory_cli.FactoryError) as ctx:
                factory_cli.run_manifest_command(
                    Path(tmp),
                    "build",
                    self.command(cwd=".."),
                )
            self.assertEqual(ctx.exception.error_code, "APP_MANIFEST_CWD_UNSAFE")

    def test_timeout_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(factory_cli.FactoryError) as ctx:
                factory_cli.run_manifest_command(
                    Path(tmp),
                    "build",
                    {
                        "argv": [sys.executable, "-c", "import time; time.sleep(5)"],
                        "cwd": ".",
                        "timeout_seconds": 1,
                    },
                )
            self.assertEqual(ctx.exception.error_code, "COMMAND_TIMEOUT")
            self.assertEqual(ctx.exception.extra["timeoutSeconds"], 1)


class StagedSecretsCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.factory_root = Path(__file__).resolve().parents[4]

    def runner(self, stdout: str = "") -> factory_cli.GitRunner:
        def _runner(args, repo):
            self.assertEqual(args, ["git", "diff", "--cached", "--name-only"])
            return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

        return _runner

    def test_allows_clean_staged_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = factory_cli.git_staged_secrets_check(
                Path(tmp),
                self.factory_root,
                runner=self.runner("src/Program.cs\nREADME.md\n"),
            )
            self.assertTrue(result["passed"])
            self.assertEqual(result["stagedCount"], 2)

    def test_blocks_default_sensitive_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(factory_cli.FactoryError) as ctx:
                factory_cli.git_staged_secrets_check(
                    Path(tmp),
                    self.factory_root,
                    runner=self.runner("appsettings.json\n.env\n"),
                )
            self.assertEqual(ctx.exception.error_code, "STAGED_SECRETS")
            self.assertEqual(ctx.exception.extra["blockedPaths"], [".env"])

    def test_pattern_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(factory_cli.FactoryError) as ctx:
                factory_cli.git_staged_secrets_check(
                    Path(tmp),
                    self.factory_root,
                    pattern_override=r"\.pfx$",
                    runner=self.runner("cert.pfx\n"),
                )
            self.assertEqual(ctx.exception.error_code, "STAGED_SECRETS")

    def test_compile_extra_patterns(self) -> None:
        config = {"extra_patterns": [r"\.pfx$"]}
        compiled = factory_cli.compile_staged_secrets_patterns(config)
        self.assertEqual(len(compiled), 2)
        self.assertTrue(compiled[1].search("cert.pfx"))

    def test_invalid_regex(self) -> None:
        with self.assertRaises(factory_cli.FactoryError) as ctx:
            factory_cli.compile_staged_secrets_patterns({"pattern": "("})
        self.assertEqual(ctx.exception.error_code, "INVALID_REGEX")

    def test_disabled_skips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            factory_dir = Path(tmp) / ".cursor" / "factory"
            factory_dir.mkdir(parents=True)
            (factory_dir / "team-variables.md").write_text(
                """```yaml
git:
  staged_secrets_check:
    enabled: false
```
""",
                encoding="utf-8",
            )
            result = factory_cli.git_staged_secrets_check(
                Path(tmp),
                Path(tmp),
                runner=self.runner(".env\n"),
            )
            self.assertTrue(result["skipped"])


class CliDispatchTests(unittest.TestCase):
    def test_pr_title_via_main(self) -> None:
        code = factory_cli.main(
            [
                "pr-title",
                "--issue-key",
                "TICKET-1",
                "--summary",
                "Do the thing",
                "--pattern",
                "{issue_key} - {brief_description}",
                "--jira-enabled",
                "true",
            ]
        )
        self.assertEqual(code, 0)

    def test_missing_issue_key_via_main(self) -> None:
        code = factory_cli.main(
            [
                "pr-title",
                "--summary",
                "goal",
                "--jira-enabled",
                "true",
            ]
        )
        self.assertEqual(code, 1)

    def test_staged_secrets_check_via_main(self) -> None:
        factory_root = Path(__file__).resolve().parents[4]
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init = factory_cli.subprocess.run(
                ["git", "init"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(init.returncode, 0)
            code = factory_cli.main(
                [
                    "git",
                    "staged-secrets-check",
                    "--repo",
                    str(repo),
                    "--factory-root",
                    str(factory_root),
                ]
            )
            self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
