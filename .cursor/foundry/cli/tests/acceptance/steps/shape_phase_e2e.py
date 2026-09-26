"""Step definitions specific to shape_phase_e2e.feature."""

from __future__ import annotations

import json

from pytest_bdd import when

from tests.acceptance.helpers import active_visit_id, invoke_foundry, run_dir


@when("I patch present state for active visit")
def patch_present_state(acceptance) -> None:
    run_dir_path = run_dir(acceptance)
    visit_id = active_visit_id(run_dir_path)
    patch = json.dumps(
        {
            "presented_ac": "E2E presented AC.",
            "presentation_artifact_path": f"run:artifacts/{visit_id}/presentation.md",
        }
    )
    acceptance["command"] = "visit state patch"
    acceptance["json_output"] = True
    acceptance["extra_argv"] = ["--set", patch]
    invoke_foundry(acceptance)


@when("I publish presentation artifact for active visit")
def publish_presentation_artifact(acceptance) -> None:
    run_dir_path = run_dir(acceptance)
    visit_id = active_visit_id(run_dir_path)
    acceptance["command"] = "artifact publish"
    acceptance["json_output"] = True
    acceptance["extra_argv"] = [
        "--artifact",
        "presentation",
        "--source",
        f"run:artifacts/{visit_id}/presentation.md",
    ]
    invoke_foundry(acceptance)


@when("I patch record state for active visit")
def patch_record_state(acceptance) -> None:
    run_dir_path = run_dir(acceptance)
    visit_id = active_visit_id(run_dir_path)
    patch = json.dumps(
        {
            "approved_ac": "E2E approved AC.",
            "approved_ac_version": 1,
            "approved_ac_digest": "sha256:e2eabc",
            "plan_path": f"run:artifacts/{visit_id}/plan.md",
            "plan_version": 1,
        }
    )
    acceptance["command"] = "visit state patch"
    acceptance["json_output"] = True
    acceptance["extra_argv"] = ["--set", patch]
    invoke_foundry(acceptance)


@when("I publish plan artifact for active visit")
def publish_plan_artifact(acceptance) -> None:
    run_dir_path = run_dir(acceptance)
    visit_id = active_visit_id(run_dir_path)
    acceptance["command"] = "artifact publish"
    acceptance["json_output"] = True
    acceptance["extra_argv"] = [
        "--artifact",
        "plan",
        "--source",
        f"run:artifacts/{visit_id}/plan.md",
    ]
    invoke_foundry(acceptance)
