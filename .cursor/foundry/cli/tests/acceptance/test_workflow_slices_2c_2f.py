"""Acceptance: workflow-02 slices 2C–2F reach deliver.stub."""

import pytest

from tests.unit.test_workflow_slices_2c_2f import (
    _stub_execute_commands,
    test_full_path_reaches_deliver_stub_with_handoff,
)

pytestmark = pytest.mark.usefixtures("_stub_execute_commands")
