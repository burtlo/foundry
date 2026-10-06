"""Agent task connection (requests, adapters, submit)."""

from foundry_cli.engine.agent.adapter import AgentAdapter, StubAgentAdapter, get_adapter
from foundry_cli.engine.agent.submit import submit_agent_result
from foundry_cli.engine.agent.tasks import (
    EXAMINATION_RESULT_SCHEMA,
    SHAPE_EXAMINE_TASK_ID,
    load_task_definition,
)

__all__ = [
    "AgentAdapter",
    "StubAgentAdapter",
    "EXAMINATION_RESULT_SCHEMA",
    "SHAPE_EXAMINE_TASK_ID",
    "get_adapter",
    "load_task_definition",
    "submit_agent_result",
]
