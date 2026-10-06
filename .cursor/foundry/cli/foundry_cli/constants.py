"""Named constants for the Foundry CLI command layer."""

from __future__ import annotations

# Visit lifecycle states
LIFECYCLE_EXAMINED = "examined"
LIFECYCLE_OPENED = "opened"
LIFECYCLE_CLOSED = "closed"
LIFECYCLE_SEALED = "sealed"

# Run status values
RUN_STATUS_NEW = "new"
RUN_STATUS_RUNNING = "running"

# Node kinds
KIND_STEP = "step"
KIND_GATE = "gate"

# Ledger event types
EVENT_RUN_STATUS_CHANGED = "run.status_changed"
EVENT_VISIT_ADMITTED = "visit.admitted"
EVENT_VISIT_SEALED = "visit.sealed"
EVENT_CHECK_RECORDED = "check.recorded"
EVENT_POLICY_APPLIED = "policy.applied"
EVENT_ARTIFACT_LINKED = "artifact.linked"
EVENT_RECEIPT_LINKED = "receipt.linked"
EVENT_EXECUTE_AUTHORIZATION_RECORDED = "execute.authorization.recorded"
EVENT_OPERATOR_ACTION = "operator.action"

# CLI capability IDs
CAP_VISIT_STATE_PATCH = "visit.state_patch"
CAP_VISIT_INTAKE_COMPLETE = "visit.intake.complete"
CAP_VISIT_EXAMINE_COMPLETE = "visit.examine.complete"
CAP_VISIT_PRESENT_COMPLETE = "visit.present.complete"
CAP_VISIT_RECORD_COMPLETE = "visit.record.complete"
CAP_VISIT_PLAN_COMPLETE = "visit.plan.complete"
CAP_RUN_AGENT_SUBMIT = "run.agent.submit"
CAP_ARTIFACT_PUBLISH = "artifact.publish"
CAP_RECEIPT_LINK = "receipt.link"
CAP_TRANSITION = "transition"

# Defaults
DEFAULT_FLOW_ID = "implementation"
DEFAULT_ENTRY_NODE_ID = "shape.intake"

# Steps with no registry judgment file; mechanism is host-owned (see intake_executor / execute_step_executor).
ENGINE_OWNED_STEP_NODE_IDS: frozenset[str] = frozenset(
    {
        "shape.intake",
        "shape.examine",
        "shape.present",
        "shape.record",
        "execute.intake",
        "execute.branch",
        "execute.plan",
        "execute.build",
        "execute.test",
    }
)
