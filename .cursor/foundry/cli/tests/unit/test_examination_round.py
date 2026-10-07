"""Examination invalidation after clarifying answers (F2)."""

from __future__ import annotations

import shutil

from foundry_cli.engine.agent.adapter import AgentAdapterEnvelope, StubAgentAdapter, default_stub_presentation_result
from foundry_cli.engine.agent.dispatch import visit_has_accepted_task_result
from foundry_cli.engine.agent.tasks import SHAPE_EXAMINE_TASK_ID
from foundry_cli.run_service import advance_run_durable, answer_run_durable
from foundry_cli.run_store import get_revision, load_snapshot, save_snapshot
from tests.conftest import FOUNDRY_ROOT
from tests.unit.shape_flow_helpers import intake_open_run, valid_examination_result

BUNDLE = FOUNDRY_ROOT


def test_answers_supersede_prior_examination_and_dispatch_new_round(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    shutil.copytree(
        BUNDLE / "fixtures" / "apps" / "foundry-test" / ".foundry",
        workspace / ".foundry",
    )
    run_dir, snapshot, _flow = intake_open_run(workspace, work_prompt="Round two")
    save_snapshot(run_dir, snapshot)
    first_result = valid_examination_result(
        draft_acceptance_criteria=["Initial AC before answers."],
        questions=[{"id": "q1", "text": "Which API?", "why_needed": "Scope"}],
    )
    stub = StubAgentAdapter(default_result=first_result)
    advance_run_durable(
        workspace=workspace,
        bundle=BUNDLE,
        run_dir=run_dir,
        expected_revision=get_revision(snapshot),
        agent_adapter=stub,
    )
    reloaded = load_snapshot(run_dir)
    wait = reloaded.get("wait")
    assert isinstance(wait, dict)
    assert wait.get("kind") == "user_input"
    examine_visit_id = str(wait.get("visit_id"))
    assert visit_has_accepted_task_result(
        reloaded,
        visit_id=examine_visit_id,
        task_id=SHAPE_EXAMINE_TASK_ID,
    )

    answer_outcome = answer_run_durable(
        workspace=workspace,
        bundle=BUNDLE,
        run_dir=run_dir,
        answers={"q1": "REST v2"},
        expected_revision=get_revision(reloaded),
    )
    assert answer_outcome.get("ok") is True
    after_answer = load_snapshot(run_dir)
    assert not visit_has_accepted_task_result(
        after_answer,
        visit_id=examine_visit_id,
        task_id=SHAPE_EXAMINE_TASK_ID,
    )
    wait = after_answer.get("wait")
    assert isinstance(wait, dict)
    assert wait.get("kind") == "agent"
    assert stub.invoke_count == 1

    second_result = valid_examination_result(
        draft_acceptance_criteria=["Revised AC after REST v2."],
        questions=[],
    )

    class _ExamineThenPresentStub(StubAgentAdapter):
        def invoke(self, request):  # type: ignore[no-untyped-def]
            if str(request.get("task_id")) == SHAPE_EXAMINE_TASK_ID:
                result = second_result
            else:
                result = default_stub_presentation_result()
            return AgentAdapterEnvelope(
                request_id=str(request["request_id"]),
                attempt=int(request.get("attempt") or 1),
                provider_request_id="stub_round2",
                raw_response_ref=None,
                usage={"input_tokens": 0, "output_tokens": 0},
                finish_reason="stop",
                result=result,
            )

    advance_run_durable(
        workspace=workspace,
        bundle=BUNDLE,
        run_dir=run_dir,
        expected_revision=get_revision(after_answer),
        agent_adapter=_ExamineThenPresentStub(),
    )
    final = load_snapshot(run_dir)
    assert final["state"]["draft_ac"] == "Revised AC after REST v2."
    assert final["active_visit"]["node_id"] == "shape.present.gate"
