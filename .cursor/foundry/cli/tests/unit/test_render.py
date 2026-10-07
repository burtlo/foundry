"""Unit tests for foundry_cli.render."""

from __future__ import annotations

from pathlib import Path

from foundry_cli.render import render_context_markdown
from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import (
    NODE_SHAPE_EXAMINE_GATE,
    NODE_SHAPE_INTAKE,
    REGISTRY_INTAKE_JUDGMENT,
    REGISTRY_INTAKE_OPERATIONS,
    REGISTRY_AGENT_RECEIPT_SCHEMA,
    REGISTRY_INTAKE_RECEIPT_SCHEMA,
    RUN_PORCELAIN_0007,
    VISIT_V001,
    VISIT_V002,
)

VERIFY_COMPLETE_GATE_INSTRUCTIONS = (
    FOUNDRY_ROOT / "nodes" / "verify.complete.gate" / "instructions.md"
)

STEP_CONTEXT: dict = {
    "run_id": RUN_PORCELAIN_0007,
    "visit_id": VISIT_V001,
    "node_id": NODE_SHAPE_INTAKE,
    "kind": "step",
    "lifecycle": "opened",
    "title": "Shape intake — publish ticket and seal receipts",
    "reads": {
        "config": {"workspace": "."},
        "state": {"ticket": None, "app_folder": None},
        "artifacts": [],
        "files": [],
    },
    "allow": {
        "cli": [
            "visit.intake.complete",
            "visit.state_patch",
        ],
        "state": [f"state.nodes.{NODE_SHAPE_INTAKE}.*"],
        "files": {
            "write": [
                {
                    "uri": "run:ticket.json",
                    "resolved_path": f"/tmp/runs/{RUN_PORCELAIN_0007}/ticket.json",
                },
            ]
        },
        "agents": [],
        "user": {"ask": False, "decide": False},
    },
    "produces": {
        "artifacts": [
            {
                "id": "ticket",
                "uri": "run:artifacts/{visit_id}/ticket.json",
                "resolved_uri": f"run:artifacts/{VISIT_V001}/ticket.json",
            }
        ],
        "options": [],
    },
    "receipts": [
        REGISTRY_INTAKE_RECEIPT_SCHEMA,
        REGISTRY_AGENT_RECEIPT_SCHEMA,
    ],
    "instructions": REGISTRY_INTAKE_JUDGMENT,
    "instructions_path": f"/tmp/foundry/nodes/{NODE_SHAPE_INTAKE}/judgment.md",
    "operations": REGISTRY_INTAKE_OPERATIONS,
    "operations_path": f"/tmp/foundry/nodes/{NODE_SHAPE_INTAKE}/operations.yaml",
}

JUDGMENT_TEXT = """# Shape intake - judgment

## Scope confirmation (judgment only)
"""

OPERATIONS_TEXT = """version: 1
node_id: shape.intake
"""

GATE_CONTEXT: dict = {
    "run_id": RUN_PORCELAIN_0007,
    "visit_id": VISIT_V002,
    "node_id": NODE_SHAPE_EXAMINE_GATE,
    "kind": "gate",
    "lifecycle": "opened",
    "title": "Open questions remain — present anyway or continue examination",
    "reads": {"config": {}, "state": {}, "artifacts": [], "files": []},
    "allow": {
        "cli": [],
        "state": [f"state.nodes.{NODE_SHAPE_EXAMINE_GATE}.*"],
        "files": {"write": []},
        "agents": [],
        "user": {"ask": False, "decide": True},
    },
    "produces": {"artifacts": [], "options": ["accept", "reject"]},
    "receipts": [],
    "instructions": "",
    "instructions_path": "",
    "prompt": "Examination still has open clarifying questions.",
}


def test_render_context_markdown_includes_core_sections() -> None:
    markdown = render_context_markdown(
        STEP_CONTEXT, JUDGMENT_TEXT, operations_text=OPERATIONS_TEXT
    )

    assert f"# Steward context — {NODE_SHAPE_INTAKE} ({VISIT_V001})" in markdown
    assert "## Position" in markdown
    assert f"run_id: `{RUN_PORCELAIN_0007}`" in markdown
    assert "## Allow" in markdown
    assert "### CLI" in markdown
    assert "`visit.intake.complete`" in markdown
    assert "## Worker" not in markdown
    assert "## Operations" in markdown
    assert "## Judgment" in markdown
    assert f"<!-- inlined from {REGISTRY_INTAKE_OPERATIONS} -->" in markdown
    assert f"<!-- inlined from {REGISTRY_INTAKE_JUDGMENT} -->" in markdown
    assert "# Shape intake - judgment" in markdown


def test_render_context_markdown_engine_owned_intake_note() -> None:
    engine_context = {
        **STEP_CONTEXT,
        "instructions": "",
        "operations": "",
    }
    engine_context.pop("instructions_path", None)
    engine_context.pop("operations_path", None)
    markdown = render_context_markdown(engine_context, "", operations_text="")
    assert "## Intake" in markdown
    assert "visit intake complete" in markdown
    assert "## Judgment" not in markdown


def test_render_context_markdown_preserves_placeholders_verbatim() -> None:
    instructions = 'visit state patch --run "{run_id}" --visit "{visit_id}"'
    markdown = render_context_markdown(STEP_CONTEXT, instructions, operations_text="")

    assert '"{run_id}"' in markdown
    assert '"{visit_id}"' in markdown


def test_render_context_markdown_includes_warnings() -> None:
    context = {
        **STEP_CONTEXT,
        "lifecycle": "examined",
        "warnings": [
            "Visit lifecycle is 'examined'; steward work should proceed only when lifecycle is 'opened'."
        ],
    }
    markdown = render_context_markdown(context, JUDGMENT_TEXT, operations_text=OPERATIONS_TEXT)

    assert "## Warnings" in markdown
    assert "lifecycle is 'examined'" in markdown


def test_render_context_markdown_execute_branch_engine_owned_blurb() -> None:
    context = {
        **STEP_CONTEXT,
        "node_id": "execute.branch",
        "title": "Create the feature branch",
        "instructions": "",
        "operations": "",
    }
    context.pop("instructions_path", None)
    context.pop("operations_path", None)
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Feature branch" in markdown
    assert "run advance" in markdown
    assert "git checkout" in markdown.lower()
    assert "## Judgment" not in markdown
    assert "## Instructions" not in markdown


def test_render_context_markdown_execute_test_engine_owned_blurb() -> None:
    context = {
        **STEP_CONTEXT,
        "node_id": "execute.test",
        "title": "Run repo verification and repair loop",
        "instructions": "",
        "operations": "",
    }
    context.pop("instructions_path", None)
    context.pop("operations_path", None)
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Execute test" in markdown
    assert "run advance" in markdown
    assert "execute.test.gate" in markdown
    assert "## Judgment" not in markdown
    assert "## Instructions" not in markdown


def test_render_context_markdown_execute_commit_engine_owned_blurb() -> None:
    context = {
        **STEP_CONTEXT,
        "node_id": "execute.commit",
        "title": "Final summarizing commit on feature branch",
        "instructions": "",
        "operations": "",
    }
    context.pop("instructions_path", None)
    context.pop("operations_path", None)
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Execute commit" in markdown
    assert "run advance" in markdown
    assert "commit-agent" in markdown
    assert "## Judgment" not in markdown
    assert "## Instructions" not in markdown


def test_render_context_markdown_execute_commit_gate_evidence() -> None:
    context = {
        **STEP_CONTEXT,
        "node_id": "execute.commit.gate",
        "kind": "gate",
        "title": "Execute commit recorded",
        "decider": "engine",
        "reads": {
            "reverify_loop": {"reverify_count": 0, "limit": 2, "within_limit": True},
            "state": {"final_commit_sha": "deadbeef", "execute_commit_message": "wip"},
            "commit_receipt": {
                "visit_id": "v-ec",
                "status": "completed",
                "receipt_id": "r-1",
                "resolved_path": None,
                "commands": [],
            },
        },
        "produces": {"options": ["pass"]},
    }
    context.pop("instructions", None)
    context.pop("instructions_path", None)
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Re-verify loop" in markdown
    assert "## Commit evidence" in markdown
    assert "`deadbeef`" in markdown
    assert "run advance" in markdown
    assert "## Instructions" not in markdown


def test_render_context_markdown_execute_build_engine_owned_blurb() -> None:
    context = {
        **STEP_CONTEXT,
        "node_id": "execute.build",
        "title": "Run manifest build commands (host-owned)",
        "instructions": "",
        "operations": "",
    }
    context.pop("instructions_path", None)
    context.pop("operations_path", None)
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Execute build" in markdown
    assert "run advance" in markdown
    assert "execute_build_boundary" in markdown
    assert "## Judgment" not in markdown
    assert "## Instructions" not in markdown


def test_render_context_markdown_execute_intake_engine_owned_blurb() -> None:
    context = {
        **STEP_CONTEXT,
        "node_id": "execute.intake",
        "title": "Execute intake — plan alignment and clean git tree",
        "instructions": "",
        "operations": "",
    }
    context.pop("instructions_path", None)
    context.pop("operations_path", None)
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Execute intake" in markdown
    assert "run advance" in markdown
    assert "intake-checker.execute" in markdown
    assert "## Judgment" not in markdown
    assert "## Instructions" not in markdown


def test_render_context_markdown_verify_intake_gate_evidence() -> None:
    context = {
        **STEP_CONTEXT,
        "node_id": "verify.intake.gate",
        "kind": "gate",
        "title": "Verify intake blocked check",
        "decider": "engine",
        "reads": {
            "config": {},
            "state": {},
            "artifacts": [],
            "files": [],
            "intake_receipt": {
                "visit_id": "v-vi",
                "status": "passed",
                "receipt_id": "r-vi",
                "resolved_path": None,
            },
        },
        "produces": {"options": ["pass"]},
    }
    context.pop("instructions", None)
    context.pop("instructions_path", None)
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Verify intake evidence" in markdown
    assert "**verify.intake**" in markdown
    assert "`passed`" in markdown
    assert "run advance" in markdown
    assert "## Instructions" not in markdown


def test_render_context_markdown_verify_intake_engine_owned_blurb() -> None:
    context = {
        **STEP_CONTEXT,
        "node_id": "verify.intake",
        "title": "Verify intake — branch diff, receipts, and plan alignment",
        "instructions": "",
        "operations": "",
    }
    context.pop("instructions_path", None)
    context.pop("operations_path", None)
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Verify intake" in markdown
    assert "run advance" in markdown
    assert "intake-checker.verify" in markdown
    assert "## Judgment" not in markdown
    assert "## Instructions" not in markdown


def test_render_context_markdown_verify_acceptance_gate_evidence() -> None:
    context = {
        **STEP_CONTEXT,
        "node_id": "verify.acceptance.gate",
        "kind": "gate",
        "title": "Acceptance result routing",
        "decider": "engine",
        "reads": {
            "config": {},
            "state": {},
            "artifacts": [],
            "files": [],
            "verify_findings": {
                "visit_id": "v-acc",
                "gate_decision": "pass",
                "evidence_ok": True,
                "verdict": "pass",
            },
            "acceptance_receipt": {
                "visit_id": "v-acc",
                "status": "completed",
                "receipt_id": "r-acc",
                "resolved_path": None,
            },
        },
        "produces": {"options": ["pass", "replan", "reshape", "rework_execute"]},
    }
    context.pop("instructions", None)
    context.pop("instructions_path", None)
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Acceptance evidence" in markdown
    assert "**verify.acceptance**" in markdown
    assert "`pass`" in markdown
    assert "evidence_ok" in markdown
    assert "run advance" in markdown
    assert "## Instructions" not in markdown


def test_render_context_markdown_verify_acceptance_judgment_blurb() -> None:
    context = {
        **STEP_CONTEXT,
        "node_id": "verify.acceptance",
        "title": "Automated acceptance criteria validation",
        "instructions": "",
        "operations": "",
    }
    context.pop("instructions_path", None)
    context.pop("operations_path", None)
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Verify acceptance" in markdown
    assert "run agent submit" in markdown
    assert "implementation-validator" in markdown
    assert "verify.acceptance.gate" in markdown
    assert "## Instructions" not in markdown


def test_render_context_markdown_verify_code_quality_gate_evidence() -> None:
    context = {
        **STEP_CONTEXT,
        "node_id": "verify.code_quality.gate",
        "kind": "gate",
        "title": "Code quality result routing",
        "decider": "engine",
        "reads": {
            "config": {},
            "state": {},
            "artifacts": [],
            "files": [],
            "code_quality_receipt": {
                "visit_id": "v-cq",
                "status": "completed",
                "receipt_id": "r-cq",
                "resolved_path": None,
                "commands": [{"command": "make lint", "exit_code": 0}],
            },
        },
        "produces": {"options": ["pass", "repair"]},
    }
    context.pop("instructions", None)
    context.pop("instructions_path", None)
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Code quality evidence" in markdown
    assert "**verify.code_quality**" in markdown
    assert "make lint" in markdown
    assert "run advance" in markdown
    assert "## Instructions" not in markdown


def test_render_context_markdown_verify_code_quality_engine_owned_blurb() -> None:
    context = {
        **STEP_CONTEXT,
        "node_id": "verify.code_quality",
        "title": "Automated lint, Bugbot, and security review",
        "instructions": "",
        "operations": "",
    }
    context.pop("instructions_path", None)
    context.pop("operations_path", None)
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Verify code quality" in markdown
    assert "run advance" in markdown
    assert "verify.code_quality.gate" in markdown
    assert "not_applicable" in markdown
    assert "## Judgment" not in markdown
    assert "## Instructions" not in markdown


def test_render_context_markdown_verify_code_review_engine_owned_blurb() -> None:
    context = {
        **STEP_CONTEXT,
        "node_id": "verify.code_review",
        "title": "Human code review — single turn",
        "instructions": "",
        "operations": "",
    }
    context.pop("instructions_path", None)
    context.pop("operations_path", None)
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Verify code review" in markdown
    assert "run advance" in markdown
    assert "verify.code_review.gate" in markdown
    assert "verify-notes" in markdown
    assert "## Judgment" not in markdown
    assert "## Instructions" not in markdown


def test_render_context_markdown_verify_complete_engine_owned_blurb() -> None:
    context = {
        **STEP_CONTEXT,
        "node_id": "verify.complete",
        "title": "Verify phase complete",
        "instructions": "",
        "operations": "",
    }
    context.pop("instructions_path", None)
    context.pop("operations_path", None)
    markdown = render_context_markdown(context, "", operations_text="")
    assert "## Verify phase complete" in markdown
    assert "run advance" in markdown
    assert "verified_at" in markdown
    assert "verify.complete.gate" in markdown
    assert "## Judgment" not in markdown
    assert "## Instructions" not in markdown


def test_render_context_markdown_execute_start_includes_living_plan(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text("# Living plan\n\nExecute scope.", encoding="utf-8")
    context = {
        **GATE_CONTEXT,
        "node_id": "execute.start",
        "reads": {
            **GATE_CONTEXT["reads"],
            "artifacts": [
                {
                    "artifact": "shape.record.plan",
                    "from": "nearest_sealed_ancestor",
                    "resolved_uri": "run:artifacts/v-006/plan.md",
                    "resolved_path": str(plan),
                }
            ],
        },
    }
    markdown = render_context_markdown(context, "# Execute start gate\n")
    assert "## Living plan" in markdown
    assert "Execute scope." in markdown


def test_render_context_markdown_record_gate_includes_living_plan(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text("# Living plan\n\nScope details.", encoding="utf-8")
    context = {
        **GATE_CONTEXT,
        "node_id": "shape.record.gate",
        "reads": {
            **GATE_CONTEXT["reads"],
            "artifacts": [
                {
                    "artifact": "shape.record.plan",
                    "from": "nearest_sealed_ancestor",
                    "resolved_uri": "run:artifacts/v-006/plan.md",
                    "resolved_path": str(plan),
                }
            ],
        },
    }
    markdown = render_context_markdown(context, "# Gate step\n")
    assert "## Living plan" in markdown
    assert "# Living plan" in markdown
    assert "Scope details." in markdown


def test_render_context_markdown_verify_complete_gate_state_handoff() -> None:
    instructions_text = VERIFY_COMPLETE_GATE_INSTRUCTIONS.read_text(encoding="utf-8")
    context = {
        **GATE_CONTEXT,
        "node_id": "verify.complete.gate",
        "title": "Verify complete",
        "produces": {"artifacts": [], "options": ["accept"]},
        "reads": {
            "config": {},
            "state": {
                "verified_at": "2026-10-06T18:00:00Z",
                "feature_branch": "foundry/demo",
                "final_commit_sha": "sha9",
            },
            "artifacts": [],
            "files": [],
        },
        "prompt": "User accepts the implementation. Accept to end the verify phase and proceed to deliver.",
    }
    markdown = render_context_markdown(context, instructions_text)
    assert "### State" in markdown
    assert "sha9" in markdown
    assert "foundry/demo" in markdown
    assert "## Verify notes" not in markdown
    assert "## Instructions" in markdown
    assert "gate decide" in markdown
    assert "`accept`" in markdown


def test_render_context_markdown_code_review_gate_includes_verify_notes(tmp_path: Path) -> None:
    notes = tmp_path / "verify-notes.md"
    notes.write_text("# Verify notes\n\nBranch diff reviewed.", encoding="utf-8")
    context = {
        **GATE_CONTEXT,
        "node_id": "verify.code_review.gate",
        "reads": {
            **GATE_CONTEXT["reads"],
            "artifacts": [
                {
                    "artifact": "verify.code_review.verify-notes",
                    "from": "nearest_sealed_ancestor",
                    "resolved_uri": "run:artifacts/v-cr/verify-notes.md",
                    "resolved_path": str(notes),
                }
            ],
        },
    }
    markdown = render_context_markdown(context, "# Gate step\n")
    assert "## Verify notes" in markdown
    assert "Branch diff reviewed." in markdown
    assert "## Instructions" in markdown


def test_render_context_markdown_present_gate_includes_plan_presentation(tmp_path: Path) -> None:
    presentation = tmp_path / "presentation.md"
    presentation.write_text("# Plan body\n\nDetails here.", encoding="utf-8")
    context = {
        **GATE_CONTEXT,
        "node_id": "shape.present.gate",
        "reads": {
            **GATE_CONTEXT["reads"],
            "artifacts": [
                {
                    "artifact": "shape.present.presentation",
                    "from": "nearest_sealed_ancestor",
                    "resolved_uri": "run:artifacts/v-004/presentation.md",
                    "resolved_path": str(presentation),
                }
            ],
        },
    }
    markdown = render_context_markdown(context, "# Gate step\n")
    assert "## Plan presentation" in markdown
    assert "# Plan body" in markdown
    assert "Details here." in markdown


def test_render_context_markdown_gate_omits_worker() -> None:
    markdown = render_context_markdown(GATE_CONTEXT, "# Gate step\n")

    assert "## Worker" not in markdown
    assert "kind: `gate`" in markdown
    assert "### Options" in markdown
    assert "`accept`" in markdown
    assert "`reject`" in markdown
    assert "## Gate prompt" in markdown
    assert "Examination still has open clarifying questions." in markdown
    assert "## Instructions" in markdown
    assert "## Judgment" not in markdown
    assert "# Gate step" in markdown
