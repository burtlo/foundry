"""Shared constants for acceptance tests."""

from __future__ import annotations

from tests.conftest import FOUNDRY_ROOT
from tests.unit.constants import (
    ERROR_GATE_USE_DECIDE as ERR_GATE_USE_DECIDE,
    ERROR_INVALID_GATE_DECISION as ERR_INVALID_GATE_DECISION,
    REGISTRY_AGENT_RECEIPT_SCHEMA as AGENT_RECEIPT_SCHEMA,
    REGISTRY_INTAKE_RECEIPT_SCHEMA as INTAKE_RECEIPT_SCHEMA,
)

SCHEMA_VERSION = "2.2.0"

FLOW_IMPLEMENTATION = "implementation"

CLI_RUN_CONTEXT = "run context"
CLI_RUN_CREATE = "run create"
CLI_VISIT_STATE_PATCH = "visit state patch"
CLI_VISIT_TRANSITION = "visit transition"
CLI_LEDGER_SHOW = "ledger show"
CLI_ARTIFACT_PUBLISH = "artifact publish"
CLI_RECEIPT_SEAL = "receipt seal"
CLI_GATE_DECIDE = "gate decide"

FIXTURE_APP = FOUNDRY_ROOT / "fixtures" / "apps" / "foundry-test" / ".foundry" / "app.yaml"

# Committed run fixtures under fixtures/runs/ (demo run_id porcelain-0007)
FIXTURE_EXAMINE = "porcelain-0007-v002-examine"
FIXTURE_EXAMINE_EXAMINED = "porcelain-0007-v002-examine-examined"
FIXTURE_EXAMINE_GATE = "porcelain-0007-v003-examine-gate"
FIXTURE_EXAMINE_GATE_EXAMINED = "porcelain-0007-v003-examine-gate-examined"
FIXTURE_PRESENT = "porcelain-0007-v004-present"
FIXTURE_PRESENT_EXAMINED = "porcelain-0007-v004-present-examined"
FIXTURE_PRESENT_GATE = "porcelain-0007-v005-present-gate"
FIXTURE_PRESENT_GATE_PRESENTED = "porcelain-0007-v005-present-gate-presented"
FIXTURE_RECORD = "porcelain-0007-v006-record"
FIXTURE_RECORD_EXAMINED = "porcelain-0007-v006-record-examined"
FIXTURE_RECORD_GATE = "porcelain-0007-v007-record-gate"
FIXTURE_RECORD_GATE_EXAMINED = "porcelain-0007-v007-record-gate-examined"

# Acceptance-only error codes
ERR_CAPABILITY_DENIED = "CAPABILITY_DENIED"
ERR_ARTIFACT_INCOMPLETE = "ARTIFACT_INCOMPLETE"
ERR_CHECK_FAILED = "CHECK_FAILED"
ERR_VISIT_NOT_OPENED = "VISIT_NOT_OPENED"
ERR_STATE_PATCH_DENIED = "STATE_PATCH_DENIED"
