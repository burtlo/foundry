"""Phase 7 tests: deterministic docs, PRD, and knowledge CLI."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[1]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry  # noqa: E402
import foundry_docs  # noqa: E402

IRIS_APP = Path(os.environ.get("FOUNDRY_IRIS_APP", r"C:\repos\kwik-trip-iot\KT.Shared.EmailProcessor.Iris"))


def write_sample_app(app: Path) -> Path:
    app.mkdir(parents=True, exist_ok=True)
    (app / "Sample.App.sln").write_text(
            '\n'.join(
                [
                    "Microsoft Visual Studio Solution File, Format Version 12.00",
                    'Project("{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}") = "Sample.App.Functions", "Sample.App.Functions\\Sample.App.Functions.csproj", "{GUID1}"',
                    'Project("{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}") = "Sample.App.Models", "Sample.App.Models\\Sample.App.Models.csproj", "{GUID2}"',
                    'Project("{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}") = "Sample.App.Tests", "Sample.App.Tests\\Sample.App.Tests.csproj", "{GUID3}"',
                    "EndProject",
                ]
            ),
            encoding="utf-8",
        )
    (app / "AGENTS.md").write_text(
            "\n".join(
                [
                    "# AGENTS.md",
                    "",
                    "## Application Metadata",
                    "",
                    "| Field | Value |",
                    "|-------|-------|",
                    "| **Application Name** | Sample.App |",
                    "| **Description** | Sample worker app |",
                    "| **URL** | https://example.test |",
                    "",
                    "### Ownership",
                    "",
                    "| Field | Value |",
                    "|-------|-------|",
                    "| **Tech Owner** | IoT |",
                    "| **Business Owner** | Ops |",
                    "| **Department** | Engineering |",
                    "| **Dev Team** | IoT |",
                    "",
                    "## Technical Stack",
                    "",
                    "| Field | Value |",
                    "|-------|-------|",
                    "| **Framework** | .NET 10 |",
                    "| **Programming Language** | C# |",
                    "",
                    "### Infrastructure",
                    "",
                    "| Field | Value |",
                    "|-------|-------|",
                    "| **Hosting Location** | Azure |",
                    "| **Infrastructure** | Azure Functions |",
                    "| **Source Control** | GitHub |",
                    "",
                    "## Security & Compliance",
                    "",
                    "### Authentication & Access",
                    "",
                    "| Field | Value |",
                    "|-------|-------|",
                    "| **Authentication** | Function keys |",
                    "",
                    "### Compliance",
                    "",
                    "| Field | Value |",
                    "|-------|-------|",
                    "| **Compliance Requirements** | SOC2 |",
                    "| **Security Assessment - DAST** | TBD |",
                    "| **Security Assessment - SAST** | CodeQL |",
                    "",
                    "### Secret Management",
                    "",
                    "| Field | Value |",
                    "|-------|-------|",
                    "| **Secret Management** | Azure App Settings |",
                    "",
                    "## Data Classification",
                    "",
                    "| Field | Value |",
                    "|-------|-------|",
                    "| **Data Sensitivity** | Internal |",
                    "| **Data Type** | Messages |",
                    "",
                    "## Database",
                    "",
                    "| Field | Value |",
                    "|-------|-------|",
                    "| **Database Type** | SQL Server |",
                    "| **Database Name** | SampleDb |",
                    "",
                    "### Server Locations",
                    "",
                    "| Environment | Server Name |",
                    "|-------------|-------------|",
                    "| Dev | dev-sql |",
                    "",
                    "## Store Data Scope",
                    "",
                    "| Field | Value |",
                    "|-------|-------|",
                    "| **Store Data** | Not Applicable |",
                    "",
                    "## Environment Data Replication",
                    "",
                    "| Field | Value |",
                    "|-------|-------|",
                    "| **Environment Data Replication** | Not Applicable |",
                    "",
                    "## Business Impact",
                    "",
                    "| Field | Value |",
                    "|-------|-------|",
                    "| **Number of Users per Month** | 100 |",
                    "| **Revenue Impact** | Low |",
                    "| **Criticality** | Medium |",
                    "",
                    "## CI/CD",
                    "",
                    "| Field | Value |",
                    "|-------|-------|",
                    "| **Platform** | GitHub Actions |",
                    "",
                    "### Workflows",
                    "",
                    "| Workflow | File |",
                    "|----------|------|",
                    "| CI | ci.yml |",
                    "",
                    "### Deployment Environments",
                    "",
                    "| Environment | Order |",
                    "|-------------|-------|",
                    "| dev | 1 |",
                    "",
                    "## External Service Integrations",
                    "",
                    "Uses Azure Service Bus.",
                    "",
                    "## Entry Point Index",
                    "",
                    "- Sample.App.Functions",
                ]
            ),
            encoding="utf-8",
        )
    return app


class DocsFixtureTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.app = write_sample_app(self.root / "Sample.App")

    def tearDown(self):
        self.tempdir.cleanup()

    def test_DocsDiscover_ClassifiesProjects(self):
        result = foundry_docs.docs_discover(str(self.app))
        self.assertEqual(result["solution"], "Sample.App.sln")
        self.assertEqual(len(result["entry_points"]), 1)
        self.assertEqual(result["entry_points"][0]["name"], "Sample.App.Functions")
        self.assertEqual(len(result["libraries"]), 1)
        self.assertEqual(len(result["tests"]), 1)

    def test_DocsAudit_ReportsRootAgents(self):
        result = foundry_docs.docs_audit(str(self.app))
        self.assertEqual(result["summary"]["agents_file_count"], 1)
        self.assertTrue(result["agents_audits"][0]["complete"])

    def test_PrdGenerateAndValidate_FixtureApp(self):
        generated = foundry_docs.prd_generate(str(self.app))
        self.assertTrue(generated["created_or_updated"])
        validated = foundry_docs.prd_validate(str(self.app))
        self.assertTrue(validated["passed"])
        self.assertEqual(validated["summary"]["failed"], 0)

    def test_PrdGenerate_NarrowDiffNoChanges_Skips(self):
        first = foundry_docs.prd_generate(str(self.app))
        self.assertTrue(first["created_or_updated"])

        class Result:
            stdout = ""
            stderr = ""

        second = foundry_docs.prd_generate(
            str(self.app),
            "HEAD~1",
            git_runner=lambda command, cwd: Result(),
        )
        self.assertTrue(second["skipped"])
        self.assertEqual(second["reason"], "no_agents_changes")

    def test_PrdGenerate_WideDiff_IsBlocked(self):
        foundry_docs.prd_generate(str(self.app))

        class Result:
            stdout = "src/Program.cs\nAGENTS.md\n"

        with self.assertRaises(foundry_docs.DocsError) as caught:
            foundry_docs.prd_generate(
                str(self.app),
                "HEAD~1",
                git_runner=lambda command, cwd: Result(),
            )
        self.assertEqual(caught.exception.error_code, "PRD_WIDE_DIFF")

    def test_KnowledgeSuggest_DoesNotWriteFiles(self):
        receipt_path = self.root / "receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "receipt_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    "exploration": {
                        "hypotheses": [
                            {
                                "text": "MarkSending must be after SMTP",
                                "status": "accepted",
                            }
                        ]
                    },
                    "decisions": [{"text": "Use Subject_Scenario_ExpectedOutcome test naming", "confidence": "high"}],
                }
            ),
            encoding="utf-8",
        )
        before = list((CLI_DIR.parent / "knowledge").glob("**/*"))
        result = foundry_docs.knowledge_suggest(str(receipt_path), str(CLI_DIR.parents[2]))
        after = list((CLI_DIR.parent / "knowledge").glob("**/*"))
        self.assertEqual(before, after)
        self.assertGreaterEqual(result["suggestion_count"], 1)
        self.assertTrue(all(item["requires_human_promotion"] for item in result["suggestions"]))
        self.assertTrue(all(not item["auto_commit"] for item in result["suggestions"]))


class DocsCliDispatchTests(unittest.TestCase):
    def test_FoundryCli_DocsDiscover_Dispatches(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "App"
            app.mkdir()
            (app / "App.sln").write_text(
                'Project("{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}") = "App.Functions", "App.Functions\\App.Functions.csproj", "{G}"\nEndProject',
                encoding="utf-8",
            )
            (app / "AGENTS.md").write_text("# AGENTS.md\n", encoding="utf-8")
            payload = foundry.dispatch(
                foundry.build_parser().parse_args(["docs", "discover", "--app-folder", str(app)])
            )
            self.assertIn("entry_points", payload)


@unittest.skipUnless(IRIS_APP.is_dir(), "Iris eval app not available")
class IrisEvalDocsTests(unittest.TestCase):
    def test_Iris_PrdValidate_Passes(self):
        payload = foundry_docs.prd_validate(str(IRIS_APP))
        self.assertTrue(payload["passed"])

    def test_Iris_PrdGenerate_NarrowDiff_SkipsWithoutLlm(self):
        class Result:
            stdout = ""

        payload = foundry_docs.prd_generate(
            str(IRIS_APP),
            "HEAD",
            git_runner=lambda command, cwd: Result(),
        )
        self.assertTrue(payload.get("skipped"))
        self.assertEqual(payload.get("method"), "deterministic")


if __name__ == "__main__":
    unittest.main()
