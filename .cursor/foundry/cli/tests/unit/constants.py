"""Shared constants for Foundry CLI unit tests."""

from __future__ import annotations

from tests.conftest import FOUNDRY_ROOT, REPO_ROOT

# Flow and run identifiers
IMPLEMENTATION_FLOW = "implementation"
RUN_PORCELAIN_0007 = "porcelain-0007"
FIXTURE_PORCELAIN_0007_V001 = "porcelain-0007-v001"

# Shape phase node IDs
NODE_SHAPE_INTAKE = "shape.intake"
NODE_SHAPE_EXAMINE = "shape.examine"
NODE_SHAPE_EXAMINE_GATE = "shape.examine.gate"
NODE_SHAPE_PRESENT = "shape.present"
NODE_SHAPE_RECORD = "shape.record"
NODE_DELIVER_STUB = "deliver.stub"

# Visit IDs used across engine and render tests
VISIT_V001 = "v-001"
VISIT_V002 = "v-002"
VISIT_V003 = "v-003"
VISIT_V005 = "v-005"
VISIT_V006 = "v-006"
VISIT_V007 = "v-007"

# Registry URIs
REGISTRY_INTAKE_JUDGMENT = "registry:nodes/shape.intake/judgment.md"
REGISTRY_INTAKE_OPERATIONS = "registry:nodes/shape.intake/operations.yaml"
REGISTRY_SCRIBE_AGENT = "registry:agents/scribe.md"
REGISTRY_INTAKE_RECEIPT_SCHEMA = "registry:schemas/intake-receipt.schema.json"
REGISTRY_AGENT_RECEIPT_SCHEMA = "registry:schemas/agent-receipt.schema.json"
REGISTRY_TICKET_SCHEMA = "registry:schemas/ticket.schema.json"

# Ledger event types
EVENT_RECEIPT_LINKED = "receipt.linked"
EVENT_VISIT_SEALED = "visit.sealed"

# Gate / engine error codes
ERROR_INVALID_FLAGS = "INVALID_FLAGS"
ERROR_GATE_USE_DECIDE = "GATE_USE_DECIDE"
ERROR_INVALID_GATE_DECISION = "INVALID_GATE_DECISION"
ERROR_NODE_NOT_FOUND = "NODE_NOT_FOUND"

# When expressions
OPEN_CLARIFYING_QUESTIONS_ZERO = "state.open_clarifying_questions_count == 0"
OPEN_CLARIFYING_QUESTIONS_NONZERO = "state.open_clarifying_questions_count != 0"
APPROVED_AC_RECORDED = "state.approved_ac_version >= 1"

# Paths
FIXTURES_ROOT = FOUNDRY_ROOT / "fixtures" / "runs"
FIXTURE_RUN_DIR = FIXTURES_ROOT / FIXTURE_PORCELAIN_0007_V001
ACCEPTANCE_FEATURES_DIR = FOUNDRY_ROOT / "cli" / "tests" / "acceptance" / "features"
RUN_CONTEXT_FEATURE = ".cursor/foundry/cli/tests/acceptance/features/run_context.feature"
DOCS_DIR = REPO_ROOT / "docs"
DOCS_NODES_DIR = DOCS_DIR / "nodes"
DOCS_CLI_RUN_CONTEXT = DOCS_DIR / "cli" / "run-context.md"

# Catalog
CATALOG_NODE_COUNT = 29
