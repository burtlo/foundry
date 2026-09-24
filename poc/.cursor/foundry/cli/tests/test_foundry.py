"""Unit tests for the Foundry v2 state engine.

Covers the Phase 2 acceptance criteria:
  * `flow validate` passes on the committed registry
  * illegal transitions are blocked
  * `deliver.ship` is unreachable without `delivery-check` exit 0
  * `implement.documentation` cannot run before `implement.code_review` is approved
  * the generated mermaid diagram matches the YAML
"""

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

CLI_DIR = Path(__file__).resolve().parents[1]
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))

import foundry  # noqa: E402
from app_manifest_support import attach_run_manifest, write_app_manifest  # noqa: E402


def base_state(**overrides):
    state = {
        "schema_version": foundry.SCHEMA_VERSION,
        "run_id": "11111111-1111-4111-8111-111111111111",
        "factory_version": "foundry",
        "run_mode": "implementation",
        "current_step": "implement.code_review",
        "issue_key": "TICKET-1234",
        "app_folder": "/repo/app",
        "factory_root": "/repo/github-private",
        "app_manifest_id": "test-app",
        "app_manifest_hash": "0" * 64,
        "app_manifest_platform": "windows",
        "risk_tier": "medium",
        "interaction_mode": "interactive",
        "steps": {},
        "pr_extras_register": [],
        "receipt_ids": [],
        "rework": {
            "validator_loops": 0,
            "builder_to_bugbot_loops": 0,
            "post_repair_required": False,
        },
        "created_at": "2026-09-10T12:00:00Z",
        "updated_at": "2026-09-10T12:00:00Z",
    }
    state.update(overrides)
    return state


def write_critic_receipts(
    run_dir,
    *,
    run_id,
    head_sha=None,
    branch_point="main",
    step_id="implement.pre_pr_review",
    status="completed",
    agents=("bugbot", "security-review"),
):
    """Write bound critic receipts used by pre-PR and delivery gates."""
    receipts_dir = Path(run_dir) / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, agent in enumerate(agents):
        receipt_id = f"aaaaaaaa-bbbb-cccc-dddd-{index + 1:012d}"
        launch_id = f"bbbbbbbb-bbbb-4bbb-8bbb-{index + 1:012d}"
        provenance = {
            "source": "worker_launch",
            "run_id": run_id,
            "launch_id": launch_id,
            "step_id": step_id,
            "agent": agent,
            "mode": "review",
            "branch_point": branch_point,
        }
        if head_sha:
            provenance["reviewed_head_sha"] = head_sha
        receipt = {
            "schema_version": foundry.SCHEMA_VERSION,
            "receipt_id": receipt_id,
            "run_id": run_id,
            "timestamp": "2026-09-10T12:00:00Z",
            "agent": {"name": agent, "mode": "review"},
            "status": status,
            "outputs": {"summary_markdown": f"{agent} review complete.", "findings": []},
            "recommended_next_state": "implement.documentation",
            "provenance": provenance,
        }
        path = receipts_dir / f"{receipt_id}.json"
        path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def complete_worker_step(state_path, config_path, *, agent, mode, next_state):
    foundry.cursor_session_record(state_path, conversation_id=f"{agent}-{mode}-source")
    packet = foundry.worker_launch_packet(
        state_path,
        agent=agent,
        mode=mode,
        work_item=None,
        config_path=str(config_path),
        flow_path=None,
    )
    craft = {
        "schema_version": foundry.SCHEMA_VERSION,
        "status": "completed",
        "outputs": {
            "summary_markdown": f"Completed {agent}/{mode}.",
            "files_changed": [],
            "artifacts": [packet["named_artifact_path"]] if packet["named_artifact_path"] else [],
            "findings": [],
        },
        "exploration": {"files_examined": [], "questions_generated": []},
        "decisions": [],
        "commands": [],
        "recommended_next_state": next_state,
    }
    Path(packet["craft_staging_path"]).write_text(
        json.dumps(craft, indent=2) + "\n",
        encoding="utf-8",
    )
    foundry.observability_subagent_complete(
        state_path,
        receipt=packet["craft_staging_path"],
        launch_id=packet["launch_id"],
        config_path=str(config_path),
    )
    foundry.run_handoff(state_path, config_path=str(config_path), flow_path=None)
    foundry.cursor_session_record(state_path, conversation_id=f"{agent}-{mode}-resumed")


def jira_enabled_config(**overrides):
    """Default profile plus Jira intake, for tests that are not chat-mode."""
    merged = foundry.deep_merge(
        foundry.load_config(None),
        {
            "intake": {"source": "jira", "tickets_root": "tickets"},
            "jira": {
                "enabled": True,
                "project_key": "TICKET",
                "issue_key_pattern": r"^[A-Z][A-Z0-9]+-\d+$",
            },
        },
    )
    if overrides:
        merged = foundry.deep_merge(merged, overrides)
    return foundry.normalize_intake_config(merged)


def write_jira_config(directory) -> str:
    path = Path(directory) / "jira-enabled.json"
    path.write_text(json.dumps(jira_enabled_config()), encoding="utf-8")
    return str(path)


def shipping_state(**overrides):
    """State that satisfies every delivery gate."""
    state = base_state(
        current_step="deliver.scope_comment",
        default_branch="main",
        feature_branch="lynn/TICKET-1234",
        steps={
            "implement.code_review": {"status": "completed", "human_approved": True},
            "implement.devops_review": {
                "status": "completed",
                "report": "received",
                "human_approved": True,
            },
            "implement.pre_pr_review": {
                "status": "completed",
                "report": "received",
                "human_approved": True,
            },
            "implement.documentation": {
                "status": "completed",
                "report": "received",
                "human_approved": True,
            },
            "deliver.gate": {"status": "completed"},
            "deliver.scope_comment": {
                "status": "in_progress",
                "gate_decision": "skip",
                "gate_outcome": "skip",
                "gate_presented": True,
            },
        },
    )
    state.update(overrides)
    return state


class ExpressionTests(unittest.TestCase):
    def test_DottedPath_StepIdKeyedMap_ResolvesLongestPrefix(self):
        state = base_state(steps={"implement.code_review": {"approved": True}})
        context = foundry.build_context(state, {}, None)
        self.assertTrue(
            foundry.truthy("state.steps.implement.code_review.approved", context)
        )

    def test_DottedPath_MissingEvidence_IsFalsy(self):
        context = foundry.build_context(base_state(), {}, None)
        self.assertFalse(
            foundry.truthy("state.steps.implement.code_review.approved", context)
        )

    def test_Operators_NegationAndConjunction_MatchPythonSemantics(self):
        context = foundry.build_context(
            base_state(),
            {"devops": {"enabled": True, "run_before_pr": False}},
            "code_changes",
        )
        self.assertFalse(
            foundry.truthy("config.devops.enabled && config.devops.run_before_pr", context)
        )
        self.assertTrue(
            foundry.truthy(
                "!(config.devops.enabled && config.devops.run_before_pr)", context
            )
        )
        self.assertTrue(foundry.truthy("decision == 'code_changes'", context))
        self.assertFalse(foundry.truthy("decision != 'code_changes'", context))

    def test_Comparison_NoneOperand_IsFalseRatherThanTypeError(self):
        context = foundry.build_context(base_state(), {}, None)
        self.assertFalse(foundry.truthy("state.approved_ac_version >= 1", context))

    def test_Parse_UnbalancedParenthesis_RaisesInvalidExpression(self):
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.parse_expression("(config.devops.enabled")
        self.assertEqual(caught.exception.error_code, "INVALID_EXPRESSION")


class RegistryTests(unittest.TestCase):
    def test_FlowValidate_CommittedRegistry_PassesWithoutErrors(self):
        result = foundry.validate_registry(None)
        self.assertEqual(sorted(result["flows"]), ["analysis", "implementation"])
        self.assertEqual(result["warnings"], [])

    def test_FlowValidate_UnitFilesExist_ForEveryStepInBothFlows(self):
        registry = foundry.load_registry(None)
        for flow_name, flow in registry["flows"].items():
            for step_id, step in flow["steps"].items():
                unit = foundry.FOUNDRY_ROOT / step["unit"]
                self.assertTrue(unit.is_file(), f"{flow_name}.{step_id} unit missing")

    def test_Diagram_GeneratedFile_MatchesRegistry(self):
        result = foundry.flow_diagram(None, None, True)
        self.assertFalse(result["stale"])

    def test_SubagentContracts_DoNotInstructAgentsToReadTeamVariables(self):
        registry = foundry.load_registry(None)
        agents = {
            step["subagent"]
            for flow in registry["flows"].values()
            for step in flow["steps"].values()
            if step.get("subagent")
        }
        agents_dir = foundry.REPO_ROOT / ".cursor" / "agents"
        for agent in agents:
            contract = (agents_dir / f"{agent}.md").read_text(encoding="utf-8")
            normalized = contract.replace("`", "")
            self.assertIsNone(
                re.search(r"\bread\s+team-variables\.md\b", normalized, re.IGNORECASE),
                agent,
            )


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.factory_root = str(foundry.REPO_ROOT)

    def test_DefaultProfile_IsOrgNeutralChatIntake(self):
        config = foundry.load_config(None, factory_root=self.factory_root)
        self.assertEqual(config["team"]["id"], "default")
        self.assertFalse(config["jira"]["enabled"])
        self.assertEqual(config["intake"]["source"], "chat")
        self.assertEqual(config["workspace"]["app_folders"], [])

    def test_ConfigGet_UnknownRole_IsRejected(self):
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.config_get(
                factory_root=self.factory_root,
                role="not-a-role",
                app_folder=None,
                profile_path=None,
            )
        self.assertEqual(caught.exception.error_code, "UNKNOWN_ROLE")

    def test_ConfigGet_AllCapabilitiesPlanRoles_AreSupported(self):
        self.assertEqual(
            set(foundry.CONFIG_ROLES),
            {
                "parent",
                "backend-builder",
                "client-builder",
                "feature-builder",
                "devops-builder",
                "documentation-writer",
                "story-writer",
                "codebase-researcher",
                "implementation-validator",
                "build-with-tests",
                "ticket-workflow",
                "documentation-workflow",
            },
        )
        for role in foundry.CONFIG_ROLES:
            packet = foundry.config_get(
                factory_root=self.factory_root,
                role=role,
                app_folder="Example.Api",
                profile_path=None,
            )
            self.assertEqual(packet["role"], role)
            self.assertRegex(packet["resolved_profile_hash"], r"^[a-f0-9]{64}$")

    def test_ConfigGet_BackendBuilder_IsRoleScopedAndResolvesTemplates(self):
        packet = foundry.config_get(
            factory_root=self.factory_root,
            role="backend-builder",
            app_folder="Example.Api",
            profile_path=None,
        )
        self.assertNotIn("builders", packet)
        self.assertNotIn("jira", packet)
        self.assertTrue(Path(packet["templates"]["implement"]).is_absolute())

    def test_ConfigGet_StoryWriter_ContainsDocumentedSlice(self):
        packet = foundry.config_get(
            factory_root=self.factory_root,
            role="story-writer",
            app_folder="Example.Api",
            profile_path=None,
        )
        self.assertEqual(packet["jira"]["project_key"], "TICKET")
        self.assertIn("story_writer", packet)
        self.assertIn("analysis", packet)
        self.assertNotIn("bug_squash", packet)

    def test_ConfigGet_UnknownRole_IsRejected(self):
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.config_get(
                factory_root=self.factory_root,
                role="unknown",
                app_folder=None,
                profile_path=None,
            )
        self.assertEqual(caught.exception.error_code, "UNKNOWN_ROLE")

    def test_SharedMechanics_IssueTitleAndBranch_AreAvailable(self):
        self.assertEqual(
            foundry.issue_key_parse(
                "https://example.atlassian.net/browse/TICKET-1234",
                r"^TICKET-\d+$",
            )["issue_key"],
            "TICKET-1234",
        )
        self.assertEqual(
            foundry.pr_title(
                "TICKET-1234",
                "Add profile support",
                "{issue_key} - {brief_description}",
                True,
            )["title"],
            "TICKET-1234 - Add profile support",
        )
        self.assertEqual(
            foundry.branch_name(
                "{developer_first_name}/{issue_key}", "lynn", "TICKET-1234"
            )["branch"],
            "lynn/TICKET-1234",
        )

    def test_ProjectContext_UsesRunManifestSnapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = root / "app"
            app.mkdir()
            state = base_state(app_folder=str(app))
            attach_run_manifest(state, app, root)
            state_path = root / "state.json"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            context = foundry.project_context(state_path)
            self.assertEqual(context["app_manifest_id"], "test-app")
            self.assertEqual(list(context["commands"]), ["build", "test"])
            self.assertEqual(context["builders"]["default_owner"], "feature-builder")
            self.assertNotIn("projectType", context)


class TransitionTests(unittest.TestCase):
    def setUp(self):
        self.registry = foundry.load_registry(None)
        self.config = foundry.deep_merge(
            foundry.load_config(None),
            {"devops": {"enabled": True, "run_before_pr": True}},
        )
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_path = Path(self.tmp.name) / "state.json"

    def write(self, state):
        app = Path(self.tmp.name) / "app"
        app.mkdir(exist_ok=True)
        state["app_folder"] = str(app)
        attach_run_manifest(
            state,
            app,
            self.state_path.parent,
            builders={"default_owner": "backend-builder", "routes": []},
        )
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        write_critic_receipts(
            self.state_path.parent,
            run_id=state.get("run_id"),
            branch_point=state.get("default_branch") or "main",
        )
        return self.state_path

    def transition(self, state, target, **kwargs):
        kwargs.setdefault("config_path", None)
        kwargs.setdefault("flow_path", None)
        kwargs.setdefault("evidence", None)
        kwargs.setdefault("decision", None)
        kwargs.setdefault("assignments", [])
        current = state["current_step"]
        record = state.setdefault("steps", {}).setdefault(current, {})
        if kwargs["decision"] is not None:
            record["gate_presented"] = True
            record["gate_decision"] = kwargs["decision"]
            record["gate_outcome"] = kwargs["decision"]
        elif record.get("human_approved") is True:
            record["gate_presented"] = True
            record["gate_decision"] = "approve"
            record["gate_outcome"] = "approve"
        return foundry.transition(self.write(state), target, **kwargs)

    # -- illegal transitions -------------------------------------------------

    def test_Transition_NoEdgeBetweenSteps_IsBlocked(self):
        state = base_state(
            current_step="plan.brief",
            steps={"plan.brief": {"status": "in_progress", "human_approved": True}},
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            self.transition(state, "deliver.ship")
        self.assertEqual(caught.exception.error_code, "ILLEGAL_TRANSITION")
        self.assertEqual(caught.exception.extra["allowedSteps"], ["plan.graph"])

    def test_Transition_StepFromOtherFlow_IsUnknown(self):
        state = base_state(
            run_mode="analysis",
            current_step="analysis.report",
            steps={"analysis.report": {"status": "in_progress", "human_approved": True}},
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            self.transition(state, "implement.build")
        self.assertEqual(caught.exception.error_code, "UNKNOWN_STEP")

    def test_Transition_ReworkEdgeWithoutMatchingDecision_IsBlocked(self):
        state = base_state(
            current_step="implement.validate",
            steps={"implement.validate": {"status": "in_progress"}},
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            self.transition(state, "implement.build")
        self.assertEqual(caught.exception.error_code, "ILLEGAL_TRANSITION")

    def test_Transition_ReworkEdgeWithDecision_BypassesTheSourceGate(self):
        state = base_state(
            current_step="implement.code_review",
            feature_branch="lynn/TICKET-1234",
            execution_graph_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            steps={
                "plan.graph": {"status": "completed", "human_approved": True},
                "implement.build": {"status": "completed"},
                "implement.validate": {"status": "completed"},
                "implement.code_review": {"status": "in_progress"},
            },
        )
        graph_path = self.state_path.parent / "execution-graph.json"
        graph_path.write_text(
            (Path(__file__).resolve().parents[2] / "schemas" / "examples" / "execution-graph-iris.example.json").read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
        )
        result = self.transition(state, "implement.build", decision="code_changes")
        self.assertEqual(result["current_step"], "implement.build")
        self.assertTrue(result["rework"])

    def test_Transition_UnresolvedGateOnSourceStep_IsBlocked(self):
        state = base_state(
            current_step="plan.brief",
            brief_snapshot={"hash": "abc123", "version": 1},
            steps={"plan.brief": {"status": "in_progress"}},
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            self.transition(state, "plan.graph")
        self.assertEqual(caught.exception.error_code, "GATE_UNRESOLVED")

    def test_Transition_DecisionConflictingWithResolvedOutcome_IsBlocked(self):
        state = base_state(
            current_step="plan.brief",
            steps={
                "plan.brief": {
                    "status": "in_progress",
                    "gate_presented": True,
                    "gate_decision": "approve",
                    "gate_outcome": "approve",
                }
            },
        )
        self.write(state)
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.transition(
                self.state_path,
                "plan.research",
                config_path=None,
                flow_path=None,
                evidence=None,
                decision="revise_research",
                assignments=[],
            )
        self.assertEqual(caught.exception.error_code, "GATE_OUTCOME_MISMATCH")

    def test_Transition_ApprovedWithoutHumanApproved_IsBlocked(self):
        state = base_state(
            current_step="implement.code_review",
            steps={"implement.code_review": {"status": "in_progress", "approved": True}},
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            self.transition(
                state, "implement.documentation", config_path=self.disabled_reviews()
            )
        self.assertEqual(caught.exception.error_code, "GATE_UNRESOLVED")

    # -- documentation ordering ---------------------------------------------

    def test_Documentation_CodeReviewNotApproved_IsBlocked(self):
        """implement.documentation cannot run before implement.code_review approved."""
        state = base_state(
            current_step="implement.code_review",
            steps={"implement.code_review": {"status": "in_progress"}},
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            self.transition(
                state,
                "implement.documentation",
                config_path=self.disabled_reviews(),
            )
        self.assertEqual(caught.exception.error_code, "GATE_UNRESOLVED")

    def test_Documentation_ArrivingFromPrePrReviewWithoutCodeReview_IsBlocked(self):
        """The requires clause holds even on a path that does not touch code_review."""
        state = base_state(
            current_step="implement.pre_pr_review",
            steps={
                "implement.pre_pr_review": {
                    "status": "in_progress",
                    "report": "received",
                    "human_approved": True,
                }
            },
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            self.transition(state, "implement.documentation")
        self.assertEqual(caught.exception.error_code, "STEP_REQUIREMENTS_UNMET")
        self.assertIn(
            "state.steps.implement.code_review.human_approved",
            caught.exception.extra["unmetRequires"],
        )

    def test_Documentation_PrePrReviewNotApprovedWhenReviewEnabled_IsBlocked(self):
        """implement.documentation cannot run before implement.pre_pr_review when review is on."""
        state = base_state(
            steps={
                "implement.code_review": {"status": "completed", "human_approved": True},
                "implement.pre_pr_review": {
                    "status": "completed",
                    "report": "received",
                    "human_approved": False,
                },
            },
        )
        flow = self.registry["flows"]["implementation"]
        step = flow["steps"]["implement.documentation"]
        context = foundry.build_context(state, self.config, None)
        unmet = foundry.unmet_requires(step, context)
        self.assertTrue(
            any("pre_pr_review.human_approved" in expr for expr in unmet),
            msg=f"expected pre_pr_review require, got {unmet}",
        )

    def test_Documentation_CodeReviewApprovedAndReviewsOff_IsAllowed(self):
        state = base_state(
            current_step="implement.code_review",
            steps={"implement.code_review": {"status": "in_progress", "human_approved": True}},
        )
        result = self.transition(
            state, "implement.documentation", config_path=self.disabled_reviews()
        )
        self.assertEqual(result["current_step"], "implement.documentation")

    def test_Documentation_ReviewsOn_RoutesThroughDevopsFirst(self):
        state = base_state(
            current_step="implement.code_review",
            steps={"implement.code_review": {"status": "in_progress", "human_approved": True}},
        )
        nxt = foundry.compute_next(self.registry, state, self.config, None)
        self.assertEqual(nxt["next_step"], "implement.devops_review")
        with self.assertRaises(foundry.FoundryError) as caught:
            self.transition(state, "implement.documentation")
        self.assertEqual(caught.exception.error_code, "ILLEGAL_TRANSITION")

    def test_DevOpsReview_WhenSkipped_RecordsSkippedStatus(self):
        state = base_state(
            current_step="implement.code_review",
            steps={"implement.code_review": {"status": "in_progress", "human_approved": True}},
        )
        config = foundry.deep_merge(
            self.config,
            {"devops": {"enabled": False, "run_before_pr": False}},
        )
        config_path = Path(self.tmp.name) / "disabled-devops-config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        result = self.transition(state, "implement.pre_pr_review", config_path=str(config_path))
        saved = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["steps"]["implement.devops_review"]["status"], "skipped")
        self.assertEqual(result["current_step"], "implement.pre_pr_review")

    # -- delivery gate -------------------------------------------------------

    def test_Ship_DeliveryCheckFailing_IsBlocked(self):
        state = shipping_state()
        del state["steps"]["implement.pre_pr_review"]
        with self.assertRaises(foundry.FoundryError) as caught:
            self.transition(state, "deliver.ship")
        self.assertEqual(caught.exception.error_code, "DELIVERY_GATES_FAILED")
        self.assertIn(
            "PRE_PR_REVIEW: implement.pre_pr_review report must be received and approved.",
            caught.exception.extra["failures"],
        )

    def test_Ship_DeliveryCheckPassing_IsAllowed(self):
        result = self.transition(shipping_state(), "deliver.ship")
        self.assertEqual(result["current_step"], "deliver.ship")

    def test_LocalDelivery_SkipsScopeCommentAndReachesShip(self):
        state = shipping_state(
            current_step="deliver.gate",
            ticket_source="local",
        )
        state["steps"]["deliver.gate"] = {"status": "in_progress"}
        state["steps"].pop("deliver.scope_comment", None)
        result = self.transition(state, "deliver.ship")
        self.assertEqual(result["current_step"], "deliver.ship")
        written = foundry.load_state(self.state_path)
        self.assertEqual(
            written["steps"]["deliver.scope_comment"]["status"],
            "skipped",
        )

    def test_ScopeComment_DeliveryCheckFailing_IsBlocked(self):
        state = shipping_state(current_step="deliver.gate")
        state["steps"]["deliver.scope_comment"] = {}
        state["feature_branch"] = "main"
        with self.assertRaises(foundry.FoundryError) as caught:
            self.transition(state, "deliver.scope_comment")
        self.assertEqual(caught.exception.error_code, "DELIVERY_GATES_FAILED")

    # -- evidence recording --------------------------------------------------

    def test_Transition_GateResolveRecordsApprovalBeforeValidating(self):
        state = base_state(
            current_step="plan.brief",
            steps={"plan.brief": {"status": "in_progress"}},
        )
        self.write(state)
        (self.state_path.parent / "events.jsonl").touch()
        config_path = self.state_path.parent / "config.json"
        config_path.write_text(json.dumps(foundry.load_config(None)), encoding="utf-8")
        brief_path = self.state_path.parent / "brief.md"
        brief_path.write_text("# Brief\n", encoding="utf-8")
        complete_worker_step(
            self.state_path,
            config_path,
            agent="planner",
            mode="brief",
            next_state="plan.graph",
        )
        foundry.observability_gate_present(self.state_path, config_path=str(config_path))
        foundry.gate_resolve(
            self.state_path,
            decision="approve",
            source="human",
            config_path=str(config_path),
        )
        foundry.run_handoff(
            self.state_path,
            config_path=str(config_path),
            flow_path=None,
        )
        foundry.cursor_session_record(
            self.state_path,
            conversation_id="plan-brief-gate-resumed",
        )
        foundry.plan_record_brief(self.state_path, brief_file=str(brief_path))
        result = foundry.transition(
            self.state_path,
            "plan.graph",
            config_path=str(config_path),
            flow_path=None,
            evidence=None,
            decision="approve",
            assignments=[],
        )
        self.assertEqual(result["current_step"], "plan.graph")
        written = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertIs(written["steps"]["plan.brief"]["human_approved"], True)
        self.assertEqual(written["steps"]["plan.brief"]["status"], "completed")

    def test_Transition_UnownedStateAssignment_IsRejected(self):
        state = base_state(
            current_step="plan.brief",
            steps={"plan.brief": {"status": "in_progress"}},
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            self.transition(state, "plan.graph", assignments=["risk_tier=low"])
        self.assertEqual(caught.exception.error_code, "STATE_KEY_NOT_OWNED")

    def test_ApplyEvidence_AlreadyBoundReceipt_DoesNotReapplyStatePatch(self):
        receipt_path = self.state_path.parent / "bound-receipt.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "receipt_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
                    "state_patch": {"steps": {"plan": {"brief": {"status": "completed"}}}},
                }
            ),
            encoding="utf-8",
        )
        state = base_state(
            current_step="plan.brief",
            steps={
                "plan.brief": {
                    "status": "in_progress",
                    "receipt_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
                }
            },
        )
        step = foundry.get_step(
            foundry.get_flow(foundry.load_registry(None), "implementation"),
            "plan.brief",
        )
        with mock.patch.object(foundry, "nested_set") as nested_set:
            refs = foundry.apply_evidence(state, "plan.brief", step, receipt_path, [])
        nested_set.assert_not_called()
        self.assertEqual(refs, ["aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"])

    def test_Transition_GateStateAssignmentRequiresGateResolve(self):
        state = base_state(
            current_step="plan.brief",
            steps={"plan.brief": {"status": "in_progress"}},
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            self.transition(
                state,
                "plan.graph",
                assignments=["steps.plan.brief.human_approved=true"],
            )
        self.assertEqual(caught.exception.error_code, "GATE_STATE_REQUIRES_RESOLVE")

    def test_Transition_RejectedMove_LeavesStateFileUntouched(self):
        state = base_state(
            current_step="plan.brief",
            steps={"plan.brief": {"status": "in_progress"}},
        )
        with self.assertRaises(foundry.FoundryError):
            self.transition(state, "plan.graph")
        written = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(written["current_step"], "plan.brief")
        self.assertNotIn("human_approved", written["steps"]["plan.brief"])

    def test_Transition_AppendsStateTransitionEvent(self):
        self.transition(shipping_state(), "deliver.ship")
        events = (self.state_path.parent / "events.jsonl").read_text(encoding="utf-8")
        payloads = [json.loads(line) for line in events.splitlines()]
        transitions = [e for e in payloads if e["event_type"] == "state_transition"]
        self.assertEqual(len(transitions), 1)
        self.assertEqual(transitions[0]["payload"]["from_step"], "deliver.scope_comment")
        self.assertEqual(transitions[0]["payload"]["to_step"], "deliver.ship")

    def disabled_reviews(self):
        path = Path(self.tmp.name) / "config.json"
        path.write_text(
            json.dumps(
                {
                    "devops": {"enabled": False, "run_before_pr": False},
                    "review": {"enabled": False, "run_before_pr": False},
                }
            ),
            encoding="utf-8",
        )
        return str(path)


class DeliveryCheckMatrixTests(unittest.TestCase):
    """One case per row of the delivery-check matrix in steps/deliver-gate.md."""

    def setUp(self):
        self.config = foundry.deep_merge(
            foundry.load_config(None),
            {"devops": {"enabled": True, "run_before_pr": True}},
        )

    def assert_fails(self, state, code, config=None):
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.delivery_check(state, config or self.config)
        self.assertEqual(caught.exception.error_code, "DELIVERY_GATES_FAILED")
        codes = [failure.split(":", 1)[0] for failure in caught.exception.extra["failures"]]
        self.assertIn(code, codes)
        return caught.exception

    def test_DeliveryCheck_AllEvidencePresent_Passes(self):
        result = foundry.delivery_check(shipping_state(), self.config)
        self.assertTrue(result["passed"])
        self.assertEqual(
            result["gates"],
            [
                "CODE_REVIEW",
                "DOCUMENTATION",
                "DEVOPS_REVIEW",
                "PRE_PR_REVIEW",
                "FEATURE_BRANCH",
                "PR_EXTRAS",
            ],
        )

    def test_DeliveryCheck_CodeReviewNotApproved_FailsCodeReview(self):
        state = shipping_state()
        state["steps"]["implement.code_review"]["human_approved"] = False
        self.assert_fails(state, "CODE_REVIEW")

    def test_DeliveryCheck_DocumentationReportMissing_FailsDocumentation(self):
        state = shipping_state()
        state["steps"]["implement.documentation"]["report"] = "missing"
        self.assert_fails(state, "DOCUMENTATION")

    def test_DeliveryCheck_DocumentationNotHumanApproved_FailsDocumentation(self):
        state = shipping_state()
        state["steps"]["implement.documentation"]["human_approved"] = False
        self.assert_fails(state, "DOCUMENTATION")

    def test_DeliveryCheck_PrdTouchedWithoutSync_FailsSyncPrd(self):
        state = shipping_state()
        state["steps"]["implement.documentation"]["prd_created_or_updated"] = True
        self.assert_fails(state, "SYNC_PRD")

    def test_DeliveryCheck_PrdTouchedWithSync_Passes(self):
        state = shipping_state()
        state["steps"]["implement.documentation"]["prd_created_or_updated"] = True
        state["steps"]["implement.documentation"]["sync_prd_ok"] = True
        self.assertTrue(foundry.delivery_check(state, self.config)["passed"])

    def test_DeliveryCheck_PrdUntouched_SkipsSyncPrd(self):
        result = foundry.delivery_check(shipping_state(), self.config)
        self.assertNotIn("SYNC_PRD", result["gates"])

    def test_DeliveryCheck_DevopsGateOnAndUnapproved_FailsDevopsReview(self):
        state = shipping_state()
        state["steps"]["implement.devops_review"]["human_approved"] = False
        self.assert_fails(state, "DEVOPS_REVIEW")

    def test_DeliveryCheck_DevopsGateOff_SkipsDevopsReview(self):
        state = shipping_state()
        del state["steps"]["implement.devops_review"]
        config = foundry.deep_merge(
            self.config, {"devops": {"enabled": False, "run_before_pr": False}}
        )
        result = foundry.delivery_check(state, config)
        self.assertNotIn("DEVOPS_REVIEW", result["gates"])

    def test_DeliveryCheck_DevopsEnabledButNotBeforePr_SkipsDevopsReview(self):
        state = shipping_state()
        del state["steps"]["implement.devops_review"]
        config = foundry.deep_merge(
            self.config, {"devops": {"enabled": True, "run_before_pr": False}}
        )
        self.assertTrue(foundry.delivery_check(state, config)["passed"])

    def test_DeliveryCheck_ReviewGateOnAndReportMissing_FailsPrePrReview(self):
        state = shipping_state()
        state["steps"]["implement.pre_pr_review"]["report"] = "missing"
        self.assert_fails(state, "PRE_PR_REVIEW")

    def test_DeliveryCheck_ReviewGateOff_SkipsPrePrReview(self):
        state = shipping_state()
        del state["steps"]["implement.pre_pr_review"]
        config = foundry.deep_merge(
            self.config, {"review": {"enabled": False, "run_before_pr": False}}
        )
        result = foundry.delivery_check(state, config)
        self.assertNotIn("PRE_PR_REVIEW", result["gates"])

    def test_DeliveryCheck_OnDefaultBranch_FailsFeatureBranch(self):
        state = shipping_state(feature_branch="main")
        self.assert_fails(state, "FEATURE_BRANCH")

    def test_DeliveryCheck_NoFeatureBranch_FailsFeatureBranch(self):
        state = shipping_state()
        del state["feature_branch"]
        self.assert_fails(state, "FEATURE_BRANCH")

    def test_DeliveryCheck_PrExtrasNotAList_FailsPrExtras(self):
        state = shipping_state(pr_extras_register=None)
        self.assert_fails(state, "PR_EXTRAS")

    def test_DeliveryCheck_EmptyPrExtras_Passes(self):
        self.assertTrue(foundry.delivery_check(shipping_state(), self.config)["passed"])

    def test_DeliveryCheck_MultipleMissingGates_ReportsAllFailures(self):
        state = base_state(current_step="deliver.gate")
        exception = self.assert_fails(state, "CODE_REVIEW")
        codes = {failure.split(":", 1)[0] for failure in exception.extra["failures"]}
        self.assertEqual(
            codes,
            {
                "CODE_REVIEW",
                "DOCUMENTATION",
                "DEVOPS_REVIEW",
                "PRE_PR_REVIEW",
                "FEATURE_BRANCH",
            },
        )


class FlowNavigationTests(unittest.TestCase):
    def setUp(self):
        self.registry = foundry.load_registry(None)
        self.config = foundry.deep_merge(
            foundry.load_config(None),
            {
                "devops": {"enabled": True, "run_before_pr": True},
                "analysis": {
                    "follow_up_stories": {"enabled": True},
                    "confluence": {"enabled": True},
                },
            },
        )

    def next_step(self, state, decision=None, config=None):
        return foundry.compute_next(self.registry, state, config or self.config, decision)

    def test_Next_JiraDisabled_SkipsIntakeJiraAndLandsOnFreeText(self):
        config = foundry.normalize_intake_config(
            foundry.deep_merge(
                self.config,
                {"jira": {"enabled": False}, "intake": {"source": "chat"}},
            )
        )
        flow = self.registry["flows"]["implementation"]
        entry, skipped = foundry.resolve_entry_step(
            flow, foundry.build_context(base_state(), config)
        )
        self.assertEqual(entry, "intake.free_text")
        self.assertEqual(skipped, ["intake.jira"])

    def test_Next_LocalSource_LandsOnIntakeLocal(self):
        config = foundry.normalize_intake_config(
            foundry.deep_merge(self.config, {"intake": {"source": "local"}, "jira": {"enabled": False}})
        )
        flow = self.registry["flows"]["implementation"]
        entry, skipped = foundry.resolve_entry_step(
            flow, foundry.build_context(base_state(), config)
        )
        self.assertEqual(entry, "intake.local")
        self.assertEqual(skipped, ["intake.jira"])

    def test_Next_ReadyTicket_SkipsGrillAndLandsOnPresentAc(self):
        state = base_state(
            current_step="intake.refine",
            readiness="Ready",
            clarifying_questions_count=0,
            steps={"intake.refine": {"status": "completed", "receipt_id": "ae57a681-0000-4000-8000-000000000001"}},
        )
        result = self.next_step(state)
        self.assertEqual(result["next_step"], "intake.present_ac")
        self.assertEqual(result["skipped"], ["intake.grill"])

    def test_Next_TwoTurnGateUnresolved_ReportsBlockedNotNextStep(self):
        state = base_state(
            current_step="intake.present_ac",
            steps={"intake.present_ac": {}},
        )
        result = self.next_step(state)
        self.assertIsNone(result["next_step"])
        self.assertEqual(result["candidate_step"], "intake.approve_ac")
        self.assertTrue(result["blocked_by"])

    def test_Next_DevopsOffReviewOn_SkipsDevopsReview(self):
        state = base_state(
            current_step="implement.code_review",
            steps={"implement.code_review": {"human_approved": True}},
        )
        config = foundry.deep_merge(self.config, {"devops": {"enabled": False}})
        result = self.next_step(state, config=config)
        self.assertEqual(result["next_step"], "implement.pre_pr_review")

    def test_Next_BothReviewGatesOff_GoesStraightToDocumentation(self):
        state = base_state(
            current_step="implement.code_review",
            steps={"implement.code_review": {"human_approved": True}},
        )
        config = foundry.deep_merge(
            self.config,
            {"devops": {"enabled": False}, "review": {"enabled": False}},
        )
        result = self.next_step(state, config=config)
        self.assertEqual(result["next_step"], "implement.documentation")

    def test_Next_DeliverShip_IsTerminal(self):
        state = shipping_state(current_step="deliver.ship")
        state["steps"]["deliver.ship"] = {"gate_decision": "approve"}
        result = self.next_step(state)
        self.assertIsNone(result["next_step"])
        self.assertTrue(result["terminal"])

    def test_Next_AnalysisFlow_NeverReachesImplementationSteps(self):
        flow = self.registry["flows"]["analysis"]
        self.assertNotIn("implement.build", flow["steps"])
        self.assertNotIn("deliver.ship", flow["steps"])
        self.assertNotIn("deliver.scope_comment", flow["steps"])

    def test_Next_AnalysisReportWithFollowUpWork_DraftsStoriesFirst(self):
        state = base_state(
            run_mode="analysis",
            current_step="analysis.report",
            steps={
                "analysis.research": {"status": "completed", "follow_up_needed": True},
                "analysis.report": {"status": "in_progress", "human_approved": True},
            },
        )
        self.assertEqual(self.next_step(state)["next_step"], "analysis.follow_up_draft")

    def test_Next_AnalysisReportWithoutFollowUpWork_GoesToConfluence(self):
        state = base_state(
            run_mode="analysis",
            current_step="analysis.report",
            steps={
                "analysis.research": {"status": "completed", "follow_up_needed": False},
                "analysis.report": {"status": "in_progress", "human_approved": True},
            },
        )
        self.assertEqual(self.next_step(state)["next_step"], "analysis.confluence")


class IntakePhase4Tests(unittest.TestCase):
    SAMPLE_AC = [
        {"id": "ac-1", "text": "Given valid input, when processed, then success.", "source": "proposed"},
    ]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_path = Path(self.tmp.name) / "state.json"
        self.config = foundry.load_config(None)

    def write_state(self, **overrides):
        state = base_state(**overrides)
        state["resolved_profile_hash"] = foundry.profile_hash(self.config)
        state["factory_root"] = str(foundry.REPO_ROOT)
        app = self.state_path.parent / "app"
        app.mkdir(exist_ok=True)
        state["app_folder"] = str(app)
        attach_run_manifest(state, app, self.state_path.parent)
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        config_path = self.state_path.parent / "config.json"
        config_path.write_text(json.dumps(self.config), encoding="utf-8")
        return state, str(config_path)

    def test_RiskTierSuggest_FewAcCount_ReturnsHigh(self):
        result = foundry.suggest_risk_tier(ac_count=2, issue_type="Story", config_path=None)
        self.assertEqual(result["risk_tier"], "high")

    def test_RiskTierSuggest_AnalysisIssueType_ReturnsMedium(self):
        result = foundry.suggest_risk_tier(ac_count=5, issue_type="Analysis", config_path=None)
        self.assertEqual(result["risk_tier"], "medium")

    def test_JiraFormatBoard_GroupsAndNumbersIssues(self):
        issues = [
            {
                "key": "TICKET-1",
                "fields": {
                    "summary": "First",
                    "status": {"name": "To Do"},
                    "issuetype": {"name": "Story"},
                    "priority": {"name": "High"},
                },
            },
            {
                "key": "TICKET-2",
                "fields": {
                    "summary": "Second",
                    "status": {"name": "In Progress"},
                    "issuetype": {"name": "Task"},
                    "priority": {"name": "Medium"},
                },
            },
        ]
        result = foundry.jira_format_board(
            issues, project_key="TICKET", developer_first_name="lynn"
        )
        self.assertIn("Hi lynn!", result["markdown"])
        self.assertIn("1. TICKET-1", result["markdown"])
        self.assertIn("2. TICKET-2", result["markdown"])
        self.assertEqual(result["counts"]["total"], 2)

    def test_IntakeValidateAc_MatchingTexts_Passes(self):
        ac = self.SAMPLE_AC
        state, _ = self.write_state(presented_ac=ac, approved_ac=ac)
        result = foundry.intake_validate_ac(state)
        self.assertTrue(result["valid"])

    def test_IntakeValidateAc_Mismatch_IsRejected(self):
        self.write_state(
            presented_ac=self.SAMPLE_AC,
            approved_ac=[{**self.SAMPLE_AC[0], "text": "Different text"}],
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.intake_validate_ac(json.loads(self.state_path.read_text(encoding="utf-8")))
        self.assertEqual(caught.exception.error_code, "AC_MISMATCH")

    def test_GrillExit_TenUnresolvedWithoutAcceptRisk_IsBlocked(self):
        _, config_path = self.write_state(
            current_step="intake.grill",
            grilling_unresolved_count=10,
            steps={
                "intake.grill": {
                    "status": "in_progress",
                    "receipt_id": "ae57a681-0000-4000-8000-000000000002",
                    "gate_presented": True,
                    "gate_decision": "approve",
                    "gate_outcome": "approve",
                }
            },
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.transition(
                self.state_path,
                "intake.present_ac",
                config_path=config_path,
                flow_path=None,
                evidence=None,
                decision="approve",
                assignments=[],
            )
        self.assertEqual(caught.exception.error_code, "GRILL_UNRESOLVED")

    def test_GrillExit_AcceptRiskWithoutAssumptions_IsBlocked(self):
        _, config_path = self.write_state(
            current_step="intake.grill",
            grilling_unresolved_count=10,
            assumptions=[],
            steps={
                "intake.grill": {
                    "status": "in_progress",
                    "receipt_id": "ae57a681-0000-4000-8000-000000000002",
                    "gate_presented": True,
                    "gate_decision": "accept_risk",
                    "gate_outcome": "accept_risk",
                }
            },
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.transition(
                self.state_path,
                "intake.present_ac",
                config_path=config_path,
                flow_path=None,
                evidence=None,
                decision="accept_risk",
                assignments=[],
            )
        self.assertEqual(caught.exception.error_code, "GRILL_ASSUMPTIONS_REQUIRED")

    def test_GrillExit_AcceptRiskWithAssumptions_AllowsPresentAc(self):
        _, config_path = self.write_state(
            current_step="intake.grill",
            grilling_unresolved_count=10,
            assumptions=["Default rollout is next sprint"],
            steps={
                "intake.grill": {
                    "status": "in_progress",
                    "receipt_id": "ae57a681-0000-4000-8000-000000000002",
                    "human_approved": True,
                }
            },
        )
        (self.state_path.parent / "events.jsonl").touch()
        complete_worker_step(
            self.state_path,
            config_path,
            agent="grilling",
            mode="intake",
            next_state="intake.present_ac",
        )
        foundry.observability_gate_present(self.state_path, config_path=config_path)
        foundry.gate_resolve(
            self.state_path,
            decision="accept_risk",
            source="human",
            config_path=config_path,
        )
        foundry.run_handoff(
            self.state_path,
            config_path=config_path,
            flow_path=None,
        )
        foundry.cursor_session_record(
            self.state_path,
            conversation_id="grilling-intake-gate-resumed",
        )
        result = foundry.transition(
            self.state_path,
            "intake.present_ac",
            config_path=config_path,
            flow_path=None,
            evidence=None,
            decision="accept_risk",
            assignments=[],
        )
        self.assertEqual(result["current_step"], "intake.present_ac")

    def test_RefineExit_WithoutReceipt_IsBlocked(self):
        _, config_path = self.write_state(
            current_step="intake.refine",
            readiness="Ready",
            clarifying_questions_count=0,
            steps={"intake.refine": {"status": "in_progress"}},
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.transition(
                self.state_path,
                "intake.present_ac",
                config_path=config_path,
                flow_path=None,
                evidence=None,
                decision=None,
                assignments=[],
            )
        self.assertEqual(caught.exception.error_code, "RECEIPT_MISSING")


class RunLifecycleTests(unittest.TestCase):
    def test_RunInit_CreatesStateEventsAndReceiptsDirectory(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_app_manifest(Path(tmp))
            result = foundry.run_init(
                app_folder=tmp,
                issue_key="TICKET-1234",
                run_mode="implementation",
                factory_root=None,
                config_path=write_jira_config(tmp),
                developer_first_name="lynn",
                risk_tier="medium",
                flow_path=None,
                run_id="22222222-2222-4222-8222-222222222222",
            )
            state_path = Path(result["state_path"])
            self.assertTrue(state_path.is_file())
            self.assertTrue((state_path.parent / "config.json").is_file())
            self.assertTrue((state_path.parent / "events.jsonl").is_file())
            self.assertTrue((state_path.parent / "receipts").is_dir())
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["current_step"], "intake.jira")
            self.assertEqual(state["factory_version"], "foundry")
            resolved = json.loads(
                (state_path.parent / "config.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                state["resolved_profile_hash"], foundry.profile_hash(resolved)
            )

    def test_RunInit_DefaultChatProfile_StartsAtFreeText(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_app_manifest(Path(tmp))
            result = foundry.run_init(
                app_folder=tmp,
                issue_key=None,
                run_mode="implementation",
                factory_root=None,
                config_path=None,
                developer_first_name="lynn",
                risk_tier="medium",
                flow_path=None,
                run_id="33333333-3333-4333-8333-333333333333",
            )
            state = json.loads(Path(result["state_path"]).read_text(encoding="utf-8"))
            self.assertEqual(state["current_step"], "intake.free_text")

    def test_RunInit_WrittenState_ValidatesAgainstRunStateSchema(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_app_manifest(Path(tmp))
            result = foundry.run_init(
                app_folder=tmp,
                issue_key="TICKET-1234",
                run_mode="implementation",
                factory_root=None,
                config_path=write_jira_config(tmp),
                developer_first_name="lynn",
                risk_tier="high",
                flow_path=None,
                run_id=None,
            )
            payload = foundry.schema_validate(result["state_path"], "run-state")
            self.assertTrue(payload["valid"])

    def test_RunConfig_ModifiedAfterInit_IsRejectedByProfileHash(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_app_manifest(Path(tmp))
            result = foundry.run_init(
                app_folder=tmp,
                issue_key="TICKET-1234",
                run_mode="implementation",
                factory_root=None,
                config_path=write_jira_config(tmp),
                developer_first_name="lynn",
                risk_tier="medium",
                flow_path=None,
                run_id=None,
            )
            config_path = Path(result["config_path"])
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["jira"]["project_key"] = "CHANGED"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaises(foundry.FoundryError) as caught:
                foundry.flow_current(Path(result["state_path"]), None, None)
            self.assertEqual(caught.exception.error_code, "PROFILE_HASH_MISMATCH")

    def test_RunInit_MalformedIssueKey_IsRejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_app_manifest(Path(tmp))
            with self.assertRaises(foundry.FoundryError) as caught:
                foundry.run_init(
                    app_folder=tmp,
                    issue_key="not-a-key",
                    run_mode="implementation",
                    factory_root=None,
                    config_path=write_jira_config(tmp),
                    developer_first_name=None,
                    risk_tier="low",
                    flow_path=None,
                    run_id=None,
                )
            self.assertEqual(caught.exception.error_code, "INVALID_ISSUE_KEY")

    def test_RunInit_ReturnsRunContext(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_app_manifest(Path(tmp))
            result = foundry.run_init(
                app_folder=tmp,
                issue_key="TICKET-1234",
                run_mode="implementation",
                factory_root=None,
                config_path=write_jira_config(tmp),
                developer_first_name="lynn",
                risk_tier="medium",
                flow_path=None,
                run_id="22222222-2222-4222-8222-222222222222",
            )
            self.assertIn("foundry_cli", result)
            if sys.platform == "win32":
                self.assertIn("foundry.ps1", result["foundry_cli"])
            else:
                self.assertIn("foundry.sh", result["foundry_cli"])
            self.assertEqual(result["state_path"], str(Path(result["state_path"]).resolve()))
            self.assertEqual(result["config_path"], str(Path(result["config_path"]).resolve()))
            self.assertEqual(result["run_dir"], str(Path(result["run_dir"]).resolve()))
            context = foundry.run_context(Path(result["state_path"]))
            self.assertEqual(context["foundry_cli"], result["foundry_cli"])
            self.assertEqual(context["app_folder"], str(Path(tmp).resolve()))

    def test_CliResolve_ReturnsFoundryCli(self):
        payload = foundry.cli_resolve(str(foundry.REPO_ROOT))
        self.assertIn("foundry_cli", payload)
        if sys.platform == "win32":
            self.assertIn("foundry.ps1", payload["foundry_cli"])
            self.assertTrue(payload["foundry_cli"].startswith("& "))
        else:
            self.assertIn("foundry.sh", payload["foundry_cli"])
            self.assertTrue(payload["foundry_cli"].startswith("bash "))
        self.assertEqual(payload["factory_root"], str(foundry.REPO_ROOT.resolve()))
        self.assertTrue(Path(payload["script_path"]).is_file())

    def test_ResolveFoundryCli_FallsBackToInterpreterWhenLauncherMissing(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "foundry.py"
            script.write_text("# stub\n", encoding="utf-8")
            with (
                mock.patch.object(foundry, "resolve_foundry_script", return_value=script),
                mock.patch.object(foundry, "resolve_foundry_launcher", return_value=None),
            ):
                cli = foundry.resolve_foundry_cli(None)
            self.assertIn("foundry.py", cli)
            if sys.platform == "win32":
                self.assertTrue(cli.startswith("& "))
            else:
                self.assertIn(str(script), cli)

    def test_FlowCurrent_ResolvesUnitPathAndGatePrompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            state_path.write_text(
                json.dumps(base_state(current_step="implement.documentation")),
                encoding="utf-8",
            )
            current = foundry.flow_current(state_path, None, None)
            self.assertEqual(current["step_id"], "implement.documentation")
            self.assertEqual(current["subagent"], "documentation-writer")
            self.assertEqual(
                current["factory_config"]["role"], "documentation-writer"
            )
            self.assertTrue(current["delivery_gate"])
            self.assertTrue(Path(current["unit"]).is_file())
            self.assertEqual(current["gate"]["kind"], "human_approval")
            self.assertIn("DocChangeReport", current["gate"]["prompt"])
            self.assertTrue(current["gate"]["unresolved"])


class GraphPhase5Tests(unittest.TestCase):
    IRIS_GRAPH = (
        Path(__file__).resolve().parents[2] / "schemas" / "examples" / "execution-graph-iris.example.json"
    )
    SAMPLE_AC = [
        {"id": "ac-1", "text": "Blob fetch and validate attachments.", "source": "approved"},
        {"id": "ac-2", "text": "Idempotent SMTP send.", "source": "approved"},
    ]

    def setUp(self):
        self.registry = foundry.load_registry(None)
        self.config = foundry.load_config(None)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_path = Path(self.tmp.name) / "state.json"
        self.config_path = self.state_path.parent / "config.json"
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")

    def write_state(self, **overrides):
        state = base_state(**overrides)
        state["resolved_profile_hash"] = foundry.profile_hash(self.config)
        state["factory_root"] = str(foundry.REPO_ROOT)
        app = self.state_path.parent / "app"
        app.mkdir(exist_ok=True)
        state["app_folder"] = str(app)
        attach_run_manifest(state, app, self.state_path.parent)
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        return state

    def transition(self, state, target, **kwargs):
        kwargs.setdefault("config_path", str(self.config_path))
        kwargs.setdefault("flow_path", None)
        kwargs.setdefault("evidence", None)
        kwargs.setdefault("decision", None)
        kwargs.setdefault("assignments", [])
        current = state["current_step"]
        record = state.setdefault("steps", {}).setdefault(current, {})
        if record.get("human_approved") is True:
            record["gate_presented"] = True
            record["gate_decision"] = kwargs["decision"] or "approve"
            record["gate_outcome"] = kwargs["decision"] or "approve"
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        return foundry.transition(self.state_path, target, **kwargs)

    def test_GraphValidate_IrisExample_PassesWithApprovedAc(self):
        result = foundry.graph_validate(
            str(self.IRIS_GRAPH),
            approved_ac=json.dumps(self.SAMPLE_AC),
            config=self.config,
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["work_item_count"], 4)
        self.assertEqual(result["topology"], "sequential")

    def test_GraphValidate_Cycle_IsRejected(self):
        graph_path = Path(self.tmp.name) / "cycle-graph.json"
        graph_path.write_text(
            json.dumps(
                {
                    "schema_version": foundry.SCHEMA_VERSION,
                    "graph_id": "11111111-1111-4111-8111-111111111111",
                    "run_id": "22222222-2222-4222-8222-222222222222",
                    "issue_key": "TICKET-1",
                    "risk_tier": "medium",
                    "approved_ac_version": 1,
                    "topology": "sequential",
                    "work_items": [
                        {
                            "id": "a",
                            "description": "A",
                            "owner": "backend-builder",
                            "depends_on": ["b"],
                            "ac_refs": ["ac-1"],
                            "status": "pending",
                        },
                        {
                            "id": "b",
                            "description": "B",
                            "owner": "backend-builder",
                            "depends_on": ["a"],
                            "ac_refs": ["ac-1"],
                            "status": "pending",
                        },
                    ],
                    "verification_plan": [
                        {
                            "step": "documentation-writer",
                            "after": ["step6_human_approval"],
                            "required": True,
                        }
                    ],
                    "created_at": "2026-09-10T12:00:00Z",
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.graph_validate(str(graph_path), approved_ac="ac-1", config=self.config)
        self.assertEqual(caught.exception.error_code, "GRAPH_INVALID")
        self.assertTrue(
            any("cycle" in err for err in caught.exception.extra["errors"])
        )

    def test_GraphValidate_OrphanAcRef_IsRejected(self):
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.graph_validate(
                str(self.IRIS_GRAPH),
                approved_ac="ac-1,ac-2,ac-3",
                config=self.config,
            )
        self.assertEqual(caught.exception.error_code, "GRAPH_INVALID")
        self.assertTrue(
            any("orphan" in err for err in caught.exception.extra["errors"])
        )

    def test_GraphReady_CompletedBlobFetch_ReturnsAttachmentValidation(self):
        graph_path = Path(self.tmp.name) / "ready-graph.json"
        graph = json.loads(self.IRIS_GRAPH.read_text(encoding="utf-8"))
        graph["work_items"][1]["status"] = "pending"
        graph["work_items"][2]["status"] = "pending"
        graph["work_items"][3]["status"] = "pending"
        graph_path.write_text(json.dumps(graph), encoding="utf-8")
        result = foundry.graph_ready(str(graph_path), completed=["blob-fetch"])
        self.assertEqual(result["ready"], ["attachment-validation"])

    def test_Build_MediumRiskWithoutApprovedGraph_IsBlocked(self):
        state = self.write_state(
            current_step="implement.branch",
            risk_tier="medium",
            feature_branch="lynn/TICKET-1234",
            default_branch="main",
            steps={
                "plan.brief": {"status": "completed", "human_approved": True},
                "plan.graph": {"status": "completed", "human_approved": False},
                "implement.branch": {"status": "in_progress"},
            },
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            self.transition(state, "implement.build")
        self.assertEqual(caught.exception.error_code, "EXECUTION_GRAPH_REQUIRED")

    def test_Build_LowRiskWithoutGraph_IsBlocked(self):
        state = self.write_state(
            current_step="implement.branch",
            risk_tier="low",
            feature_branch="lynn/TICKET-1234",
            default_branch="main",
            steps={
                "plan.brief": {"status": "completed", "human_approved": True},
                "implement.branch": {"status": "in_progress"},
            },
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            self.transition(state, "implement.build")
        self.assertEqual(caught.exception.error_code, "EXECUTION_GRAPH_REQUIRED")

    def test_Build_LowRiskWithInvalidGraph_IsBlocked(self):
        graph_path = self.state_path.parent / "execution-graph.json"
        graph_path.write_text(
            json.dumps(
                {
                    "schema_version": foundry.SCHEMA_VERSION,
                    "graph_id": "11111111-1111-4111-8111-111111111111",
                    "run_id": "22222222-2222-4222-8222-222222222222",
                    "issue_key": "TICKET-1",
                    "risk_tier": "low",
                    "approved_ac_version": 1,
                    "topology": "sequential",
                    "work_items": [
                        {"id": "a", "description": "A", "owner": "backend-builder", "status": "pending"},
                        {"id": "b", "description": "B", "owner": "backend-builder", "status": "pending"},
                    ],
                    "verification_plan": [
                        {
                            "step": "documentation-writer",
                            "after": ["step6_human_approval"],
                            "required": True,
                        }
                    ],
                    "created_at": "2026-09-10T12:00:00Z",
                }
            ),
            encoding="utf-8",
        )
        state = self.write_state(
            current_step="implement.branch",
            risk_tier="low",
            execution_graph_id="11111111-1111-4111-8111-111111111111",
            feature_branch="lynn/TICKET-1234",
            default_branch="main",
            steps={
                "plan.brief": {"status": "completed", "human_approved": True},
                "plan.graph": {"status": "completed", "human_approved": True},
                "implement.branch": {"status": "in_progress"},
            },
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            self.transition(state, "implement.build")
        self.assertEqual(caught.exception.error_code, "GRAPH_LOW_RISK_INVALID")

    def test_GraphRecordChange_AfterBuildStarted_IncrementsStability(self):
        graph_path = Path(self.tmp.name) / "record-graph.json"
        graph_path.write_text(
            json.dumps(
                {
                    "schema_version": foundry.SCHEMA_VERSION,
                    "graph_id": "11111111-1111-4111-8111-111111111111",
                    "run_id": "22222222-2222-4222-8222-222222222222",
                    "issue_key": "TICKET-1",
                    "risk_tier": "low",
                    "approved_ac_version": 1,
                    "topology": "single_worker",
                    "work_items": [
                        {
                            "id": "only",
                            "description": "Single worker item",
                            "owner": "feature-builder",
                            "status": "pending",
                        }
                    ],
                    "verification_plan": [
                        {
                            "step": "documentation-writer",
                            "after": ["step6_human_approval"],
                            "required": True,
                        }
                    ],
                    "plan_stability": {"changes_after_build_started": 0},
                    "created_at": "2026-09-10T12:00:00Z",
                }
            ),
            encoding="utf-8",
        )
        result = foundry.graph_record_change(str(graph_path), after_build_started=True)
        self.assertEqual(result["changes_after_build_started"], 1)
        saved = json.loads(graph_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["plan_stability"]["changes_after_build_started"], 1)

    def test_Next_LowRiskPlanBrief_UsesPlanGraph(self):
        state = base_state(
            current_step="plan.brief",
            risk_tier="low",
            steps={"plan.brief": {"status": "in_progress", "human_approved": True}},
        )
        result = foundry.compute_next(self.registry, state, self.config, "approve")
        self.assertEqual(result["next_step"], "plan.graph")
        self.assertEqual(result["skipped"], [])

    def test_Transition_LowRiskPlanGraph_GeneratesSingleFeatureBuilder(self):
        state = self.write_state(
            current_step="plan.brief",
            risk_tier="low",
            approved_ac=self.SAMPLE_AC,
            approved_ac_version=1,
            brief_snapshot={"hash": "a" * 64, "version": 1},
            steps={"plan.brief": {"status": "in_progress", "human_approved": True}},
        )
        complete_worker_step(
            self.state_path,
            self.config_path,
            agent="planner",
            mode="brief",
            next_state="plan.graph",
        )
        state = foundry.load_state(self.state_path)
        result = self.transition(state, "plan.graph")
        self.assertEqual(result["current_step"], "plan.graph")
        graph = json.loads(
            (self.state_path.parent / "execution-graph.json").read_text(encoding="utf-8")
        )
        self.assertEqual(graph["topology"], "single_worker")
        self.assertEqual(graph["work_items"][0]["owner"], "feature-builder")

    def test_BuildExit_LowRiskRequiresCompletedDelegatedWorkItem(self):
        state = self.write_state(
            current_step="plan.brief",
            risk_tier="low",
            approved_ac=self.SAMPLE_AC,
            approved_ac_version=1,
            brief_snapshot={"hash": "a" * 64, "version": 1},
            steps={"plan.brief": {"status": "in_progress", "human_approved": True}},
        )
        foundry.ensure_execution_graph_reference(self.state_path, state)
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.validate_build_exit(
                state,
                self.config,
                state_path=self.state_path,
                evidence_path=None,
            )
        self.assertEqual(caught.exception.error_code, "BUILD_GRAPH_INCOMPLETE")


class WorkerRuntimeTests(unittest.TestCase):
    IRIS_GRAPH = foundry.FOUNDRY_ROOT / "schemas" / "examples" / "execution-graph-iris.example.json"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = {
            "profile_version": "1.0.0",
            "team": {"id": "test", "display_name": "Test"},
            "workspace": {"app_folders": ["app"], "resolve_templates_from_org": True},
            "jira": {"enabled": True, "project_key": "TICKET"},
            "git": {
                "feature_branch_pattern": "{developer_first_name}/{issue_key}",
                "pr_title_pattern": "{issue_key} - {brief_description}",
            },
            "org": {"display_name": "Test", "required_labels": []},
            "templates": {
                "implement": ".cursor/commands/templates/implement-changes-step.md",
                "add_tests": ".cursor/commands/templates/add-tests-step.md",
                "run_tests": ".cursor/commands/templates/run-tests-step.md",
            },
            "foundry": {
                "enabled": True,
                "default_risk_tier_rules": [],
                "grilling": {"enabled": True, "max_rounds": 2, "skip_when_readiness": "Ready"},
                "planner": {"required_when_risk": ["medium", "high"], "min_work_items": 1},
                "observability": {"emit_receipts": True, "emit_events": True},
                "knowledge": {"auto_suggest": True, "require_human_promotion": True},
                "worker": {
                    "dependency_summary_token_budget": 500,
                    "validator_loop_threshold": 3,
                    "builder_to_bugbot_loop_threshold": 2,
                },
            },
        }
        self.config_path = self.root / "config.json"
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")

    def write_state(self, **overrides):
        defaults = {
            "app_folder": str(self.root / "app"),
            "factory_root": str(foundry.REPO_ROOT),
            "resolved_profile_hash": foundry.profile_hash(self.config),
            "approved_ac": [
                {"id": "ac-1", "text": "Blob fetch works.", "source": "proposed"},
                {"id": "ac-2", "text": "Idempotency holds.", "source": "proposed"},
            ],
            "approved_ac_version": 2,
            "execution_graph_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "feature_branch": "lynn/TICKET-1234",
            "default_branch": "main",
            "steps": {
                "implement.branch": {"status": "completed"},
                "implement.build": {"status": "in_progress"},
            },
        }
        defaults.update(overrides)
        run_id = overrides.get("run_id", "11111111-1111-4111-8111-111111111111")
        run_dir = self.root / "app" / ".foundry" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        run_config_path = run_dir / "config.json"
        run_config_path.write_text(json.dumps(self.config), encoding="utf-8")
        resolved_config = foundry.load_config(run_config_path, factory_root=str(foundry.REPO_ROOT))
        defaults["resolved_profile_hash"] = foundry.profile_hash(resolved_config)
        state = base_state(**defaults)
        attach_run_manifest(
            state,
            Path(str(defaults["app_folder"])),
            run_dir,
            builders={"default_owner": "backend-builder", "routes": []},
        )
        state_path = run_dir / "state.json"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        return state_path

    def seed_graph(self, state_path):
        graph_path = state_path.parent / "execution-graph.json"
        graph_path.write_text(self.IRIS_GRAPH.read_text(encoding="utf-8"), encoding="utf-8")
        return graph_path

    def seed_receipt(self, state_path, receipt_id, work_item_id, summary):
        receipts_dir = state_path.parent / "receipts"
        receipts_dir.mkdir(exist_ok=True)
        receipt = {
            "schema_version": foundry.SCHEMA_VERSION,
            "receipt_id": receipt_id,
            "run_id": json.loads(state_path.read_text())["run_id"],
            "timestamp": "2026-09-10T12:00:00Z",
            "agent": {"name": "backend-builder", "mode": "implement"},
            "status": "completed",
            "work_item_id": work_item_id,
            "outputs": {"summary_markdown": summary, "files_changed": ["src/Foo.cs"]},
            "recommended_next_state": "implement.build",
        }
        (receipts_dir / f"{receipt_id}.json").write_text(json.dumps(receipt), encoding="utf-8")

    def test_BuilderPacket_Idempotency_OmitsSiblingWorkItemProse(self):
        app = self.root / "app"
        app.mkdir(parents=True, exist_ok=True)
        state_path = self.write_state()
        graph_path = self.seed_graph(state_path)
        self.seed_receipt(
            state_path,
            "b52a05e2-0000-4000-8000-000000000011",
            "attachment-validation",
            "Validated attachments only.",
        )
        packet = foundry.builder_packet(
            state_path=state_path,
            graph_path=str(graph_path),
            work_item_id="idempotency",
            receipts_dir=None,
            config_path=None,
        )
        prompt = packet["prompt"]
        self.assertIn("idempotency", prompt)
        self.assertIn("Idempotency key storage", prompt)
        self.assertNotIn("Fetch attachment bytes from blob storage", prompt)
        self.assertNotIn("SMTP send with MarkSending", prompt)
        self.assertEqual(packet["work_item"]["id"], "idempotency")
        self.assertEqual(packet["subagent"], "backend-builder")
        self.assertEqual(len(packet["approved_ac"]), 1)
        self.assertEqual(packet["approved_ac"][0]["id"], "ac-2")
        context = packet["project_context"]
        self.assertEqual(context["app_manifest_id"], "test-app")
        self.assertNotIn("projectType", context)
        self.assertNotIn("solution", context)
        self.assertNotIn("makefile", context)
        self.assertEqual(packet["builder_routing"]["resolved_owner"], "backend-builder")
        self.assertEqual(packet["builder_routing"]["default_owner"], "backend-builder")
        self.assertIn("builders", context)

    def test_SummarizeReceipt_CapsFilesChanged(self):
        paths = [f"src/File{i}.cs" for i in range(30)]
        summary = foundry.summarize_receipt(
            {
                "receipt_id": "r1",
                "work_item_id": "wi-1",
                "status": "completed",
                "outputs": {"summary_markdown": "Done.", "files_changed": paths},
            },
            max_chars=2000,
        )
        self.assertEqual(len(summary["files_changed"]), foundry.DEFAULT_RECEIPT_FILES_CHANGED_LIMIT)
        self.assertEqual(summary["files_changed_omitted"], 5)

    def test_SlimBuilderPacketForLaunch_DropsDuplicateFields(self):
        packet = {
            "work_item": {"id": "wi-1"},
            "factory_config": {"templates": {}},
            "prompt": "builder prompt",
            "subagent": "backend-builder",
        }
        slim = foundry.slim_builder_packet_for_launch(packet)
        self.assertNotIn("factory_config", slim)
        self.assertNotIn("prompt", slim)
        self.assertEqual(slim["work_item"]["id"], "wi-1")

    def test_ValidatorReady_IncompleteGraph_IsNotReady(self):
        graph_path = self.root / "graph.json"
        graph = json.loads(self.IRIS_GRAPH.read_text(encoding="utf-8"))
        graph["work_items"][-1]["status"] = "pending"
        graph_path.write_text(json.dumps(graph), encoding="utf-8")
        result = foundry.validator_ready_check(str(graph_path))
        self.assertFalse(result["ready"])
        self.assertIn("smtp-send", result["incomplete"])

    def test_ValidatorReady_AllComplete_IsReady(self):
        result = foundry.validator_ready_check(str(self.IRIS_GRAPH))
        self.assertTrue(result["ready"])

    def test_ValidatorPacket_BeforeAllComplete_IsBlocked(self):
        state_path = self.write_state()
        graph_path = self.seed_graph(state_path)
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        graph["work_items"][-1]["status"] = "pending"
        graph_path.write_text(json.dumps(graph), encoding="utf-8")
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.validator_packet(
                state_path=state_path,
                graph_path=str(graph_path),
                receipts_dir=None,
                config_path=None,
            )
        self.assertEqual(caught.exception.error_code, "VALIDATOR_NOT_READY")

    def test_RouteCritical_AcRef_RoutesToGraphOwner(self):
        findings = json.dumps(
            [{"severity": "critical", "ac_ref": "ac-2", "text": "Missing reclaim semantics."}]
        )
        result = foundry.route_critical_findings(str(self.IRIS_GRAPH), findings)
        routed_ids = {route["work_item_id"] for route in result["routes"]}
        self.assertIn("idempotency", routed_ids)
        self.assertTrue(all(route["owner"] == "backend-builder" for route in result["routes"]))

    def test_BuildAndTest_ReturnReceiptCommandShape(self):
        state_path = self.write_state()

        def runner(argv, cwd):
            import subprocess

            class Result:
                returncode = 0
                stdout = "ok"
                stderr = ""

            return Result()

        build = foundry.run_build(state_path, runner=runner)
        test = foundry.run_test(state_path, runner=runner)
        self.assertEqual(build["receipt_command"]["exit_code"], 0)
        self.assertIn("command", build["receipt_command"])
        self.assertIn("duration_ms", build["receipt_command"])
        self.assertEqual(test["receipt_command"]["exit_code"], 0)

    def prepare_rework_state(self, **overrides):
        state_path = self.write_state(
            current_step="implement.validate",
            steps={
                "plan.graph": {"status": "completed", "human_approved": True},
                "implement.build": {"status": "completed"},
                "implement.validate": {"status": "in_progress"},
            },
            **overrides,
        )
        self.seed_graph(state_path)
        return state_path

    def test_ValidatorReworkTransition_IncrementsStateRework(self):
        state_path = self.prepare_rework_state()
        run_config = state_path.parent / "config.json"
        complete_worker_step(
            state_path,
            run_config,
            agent="implementation-validator",
            mode="validate",
            next_state="implement.build",
        )
        foundry.transition(
            state_path,
            "implement.build",
            config_path=str(run_config),
            flow_path=None,
            evidence=None,
            decision="critical_findings",
            assignments=[],
        )
        saved = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["rework"]["validator_loops"], 1)
        self.assertEqual(saved["current_step"], "implement.build")

    def test_ValidatorReworkThreshold_BlocksTransition(self):
        state_path = self.prepare_rework_state(
            rework={"validator_loops": 2, "builder_to_bugbot_loops": 0},
        )
        run_config = state_path.parent / "config.json"
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.transition(
                state_path,
                "implement.build",
                config_path=str(run_config),
                flow_path=None,
                evidence=None,
                decision="critical_findings",
                assignments=[],
            )
        self.assertEqual(caught.exception.error_code, "REWORK_THRESHOLD_EXCEEDED")

    def prepare_pre_pr_state(self, **overrides):
        state_path = self.write_state(
            current_step="implement.pre_pr_review",
            steps={
                "plan.graph": {"status": "completed", "human_approved": True},
                "implement.code_review": {"status": "completed", "human_approved": True},
                "implement.pre_pr_review": {
                    "status": "in_progress",
                    "report": "received",
                    "gate_presented": True,
                    "gate_decision": "fix_findings",
                    "gate_outcome": "fix_findings",
                },
            },
            **overrides,
        )
        self.seed_graph(state_path)
        return state_path

    def test_PrePrReworkTransition_IncrementsBuilderToBugbotLoops(self):
        state_path = self.prepare_pre_pr_state()
        run_config = state_path.parent / "config.json"
        complete_worker_step(
            state_path,
            run_config,
            agent="devops-builder",
            mode="pre_pr_review",
            next_state="implement.build",
        )
        foundry.transition(
            state_path,
            "implement.build",
            config_path=str(run_config),
            flow_path=None,
            evidence=None,
            decision="fix_findings",
            assignments=[],
        )
        saved = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["rework"]["builder_to_bugbot_loops"], 1)
        self.assertEqual(saved["current_step"], "implement.build")

    def test_PrePrReworkThreshold_BlocksTransition(self):
        state_path = self.prepare_pre_pr_state(
            rework={"validator_loops": 0, "builder_to_bugbot_loops": 2},
        )
        run_config = state_path.parent / "config.json"
        config = foundry.deep_merge(
            foundry.load_config(None),
            {
                "foundry": {
                    **self.config["foundry"],
                    "worker": {
                        **self.config["foundry"]["worker"],
                        "builder_to_bugbot_loop_threshold": 2,
                    },
                }
            },
        )
        run_config.write_text(json.dumps(config), encoding="utf-8")
        state_path.write_text(
            json.dumps(
                {
                    **json.loads(state_path.read_text(encoding="utf-8")),
                    "resolved_profile_hash": foundry.profile_hash(config),
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaises(foundry.FoundryError) as caught:
            foundry.transition(
                state_path,
                "implement.build",
                config_path=str(run_config),
                flow_path=None,
                evidence=None,
                decision="fix_findings",
                assignments=[],
            )
        self.assertEqual(caught.exception.error_code, "REWORK_THRESHOLD_EXCEEDED")


if __name__ == "__main__":
    unittest.main()
