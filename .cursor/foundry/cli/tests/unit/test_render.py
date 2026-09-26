"""Unit tests for foundry_cli.render."""

from __future__ import annotations

from foundry_cli.render import render_context_markdown

STEP_CONTEXT: dict = {
    "run_id": "porcelain-0007",
    "visit_id": "v-001",
    "node_id": "shape.intake",
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
        "state": ["state.nodes.shape.intake.*"],
        "files": {
            "write": [
                {
                    "uri": "run:ticket.json",
                    "resolved_path": "/tmp/runs/porcelain-0007/ticket.json",
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
                "resolved_uri": "run:artifacts/v-001/ticket.json",
            }
        ],
        "options": [],
    },
    "receipts": [
        "registry:schemas/intake-receipt.schema.json",
        "registry:schemas/agent-receipt.schema.json",
    ],
    "instructions": "registry:nodes/shape.intake/instructions.md",
    "instructions_path": "/tmp/foundry/nodes/shape.intake/instructions.md",
    "worker": {
        "mode": "shape",
        "prompt": "registry:workers/intake-checker.shape/prompt.md",
        "contract": "registry:workers/intake-checker.shape/contract.yaml",
        "prompt_path": "/tmp/foundry/workers/intake-checker.shape/prompt.md",
        "contract_path": "/tmp/foundry/workers/intake-checker.shape/contract.yaml",
    },
}

INSTRUCTIONS_TEXT = """# Shape intake

## Goal

Publish the `ticket` artifact.
"""

GATE_CONTEXT: dict = {
    "run_id": "porcelain-0007",
    "visit_id": "v-002",
    "node_id": "shape.examine.gate",
    "kind": "gate",
    "lifecycle": "opened",
    "title": "Examination ready — present plan or continue questioning",
    "reads": {"config": {}, "state": {}, "artifacts": [], "files": []},
    "allow": {
        "cli": [],
        "state": ["state.nodes.shape.examine.gate.*"],
        "files": {"write": []},
        "agents": [],
        "user": {"ask": False, "decide": True},
    },
    "produces": {"artifacts": [], "options": ["present", "continue"]},
    "receipts": [],
    "instructions": "",
    "instructions_path": "",
}


def test_render_context_markdown_includes_core_sections() -> None:
    markdown = render_context_markdown(STEP_CONTEXT, INSTRUCTIONS_TEXT)

    assert "# Steward context — shape.intake (v-001)" in markdown
    assert "## Position" in markdown
    assert "run_id: `porcelain-0007`" in markdown
    assert "## Allow" in markdown
    assert "### CLI" in markdown
    assert "`artifact.publish`" in markdown
    assert "## Worker" in markdown
    assert "| subagent_type | intake-checker.shape |" in markdown
    assert "| mode | shape |" in markdown
    assert "## Instructions" in markdown
    assert "<!-- inlined from registry:nodes/shape.intake/instructions.md -->" in markdown
    assert "# Shape intake" in markdown


def test_render_context_markdown_preserves_placeholders_verbatim() -> None:
    instructions = 'visit state patch --run "{run_id}" --visit "{visit_id}"'
    markdown = render_context_markdown(STEP_CONTEXT, instructions)

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
    markdown = render_context_markdown(context, INSTRUCTIONS_TEXT)

    assert "## Warnings" in markdown
    assert "lifecycle is 'examined'" in markdown


def test_render_context_markdown_gate_omits_worker() -> None:
    markdown = render_context_markdown(GATE_CONTEXT, "")

    assert "## Worker" not in markdown
    assert "kind: `gate`" in markdown
    assert "### Options" in markdown
    assert "`present`" in markdown
