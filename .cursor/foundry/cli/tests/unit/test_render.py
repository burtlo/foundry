"""Unit tests for foundry_cli.render."""

from __future__ import annotations

from foundry_cli.render import render_context_markdown
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
            "artifact.publish",
            "ledger.show",
            "receipt.link",
            "transition",
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
    "title": "Examination ready — present plan or continue questioning",
    "reads": {"config": {}, "state": {}, "artifacts": [], "files": []},
    "allow": {
        "cli": [],
        "state": [f"state.nodes.{NODE_SHAPE_EXAMINE_GATE}.*"],
        "files": {"write": []},
        "agents": [],
        "user": {"ask": False, "decide": True},
    },
    "produces": {"artifacts": [], "options": ["present", "continue"]},
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
    assert "`artifact.publish`" in markdown
    assert "## Worker" not in markdown
    assert "## Operations" in markdown
    assert "## Judgment" in markdown
    assert f"<!-- inlined from {REGISTRY_INTAKE_OPERATIONS} -->" in markdown
    assert f"<!-- inlined from {REGISTRY_INTAKE_JUDGMENT} -->" in markdown
    assert "# Shape intake - judgment" in markdown


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


def test_render_context_markdown_gate_omits_worker() -> None:
    markdown = render_context_markdown(GATE_CONTEXT, "")

    assert "## Worker" not in markdown
    assert "kind: `gate`" in markdown
    assert "### Options" in markdown
    assert "`present`" in markdown
    assert "## Gate prompt" in markdown
    assert "Examination still has open clarifying questions." in markdown
