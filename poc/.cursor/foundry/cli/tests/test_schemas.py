"""Validate Foundry v2 JSON schemas against example fixtures."""

import json
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

FOUNDRY_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = FOUNDRY_ROOT / "schemas"
EXAMPLES_DIR = SCHEMAS_DIR / "examples"
PROFILES_DIR = FOUNDRY_ROOT / "profiles"


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _validate(schema_name: str, fixture_name: str) -> None:
    schema = _load_json(SCHEMAS_DIR / schema_name)
    fixture = _load_json(EXAMPLES_DIR / fixture_name)
    Draft202012Validator(schema).validate(fixture)


class SchemaFixtureTests(unittest.TestCase):
    def test_run_state_implementation_example(self) -> None:
        _validate(
            "factory-run-state.schema.json",
            "run-state-implementation.example.json",
        )

    def test_execution_graph_iris_example(self) -> None:
        _validate(
            "execution-graph.schema.json",
            "execution-graph-iris.example.json",
        )

    def test_factory_config_profiles_validate_against_same_schema(self) -> None:
        schema = _load_json(SCHEMAS_DIR / "factory-config.schema.json")
        validator = Draft202012Validator(schema)
        for profile_name in ("default.yaml", "example-team.yaml"):
            profile = yaml.safe_load(
                (PROFILES_DIR / profile_name).read_text(encoding="utf-8")
            )
            errors = list(validator.iter_errors(profile))
            self.assertEqual(errors, [], profile_name)


if __name__ == "__main__":
    unittest.main()
