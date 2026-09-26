"""Step definitions specific to shape_examine.feature."""

from __future__ import annotations

from pytest_bdd import then

from tests.acceptance.constants import SCHEMA_VERSION
from tests.acceptance.helpers import run_dir, write_json


@then("I write examine agent receipt draft to the run directory")
def write_examine_agent_receipt(acceptance) -> None:
    # Steward examination receipt: no shape-steward in agent-receipt.schema.json enum yet.
    agent = {
        "schema_version": SCHEMA_VERSION,
        "agent": {"name": "intake-checker", "mode": "shape"},
        "status": "completed",
        "outputs": {"summary_markdown": "Examination conversation complete."},
    }
    write_json(run_dir(acceptance) / "receipts" / "agent.json", agent)
