"""Shared pytest fixtures for Foundry CLI unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from foundry_cli.parser import build_parser
from foundry_cli.paths import foundry_root
from foundry_cli.registry import load_registry
from tests.conftest import REPO_ROOT
from tests.unit.constants import IMPLEMENTATION_FLOW


@pytest.fixture
def parser():
    return build_parser()


@pytest.fixture
def bundle() -> Path:
    return foundry_root(REPO_ROOT)


@pytest.fixture
def flow(bundle: Path) -> dict:
    _, flow = load_registry(bundle, flow_id=IMPLEMENTATION_FLOW)
    return flow


@pytest.fixture
def flow_bundle(bundle: Path) -> tuple[dict, Path]:
    _, flow = load_registry(bundle, flow_id=IMPLEMENTATION_FLOW)
    return flow, bundle
