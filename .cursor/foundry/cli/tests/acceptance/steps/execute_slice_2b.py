"""Step definitions for execute_slice_2b.feature."""

from __future__ import annotations

import os

from pytest_bdd import given


@given("execute stub verification passes")
def execute_stub_verification_passes() -> None:
    os.environ["FOUNDRY_EXECUTE_STUB"] = "1"
    os.environ.pop("FOUNDRY_EXECUTE_TEST_EXIT_CODE", None)
    os.environ.pop("FOUNDRY_EXECUTE_BUILD_EXIT_CODE", None)
