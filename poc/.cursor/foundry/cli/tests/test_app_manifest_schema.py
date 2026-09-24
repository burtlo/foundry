"""Validate the Foundry app-manifest v1 schema fixture corpus."""

import json
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


FOUNDRY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = FOUNDRY_ROOT / "schemas" / "app-manifest.schema.json"
FIXTURES_DIR = FOUNDRY_ROOT / "schemas" / "fixtures"


def _load_yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain a YAML object")
    return value


def _error_path(error) -> str:
    path = ".".join(str(part) for part in error.absolute_path)
    return path or "root"


class AppManifestSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        cls.validator = Draft202012Validator(schema)

    def test_valid_fixtures_pass(self) -> None:
        fixture = _load_yaml(FIXTURES_DIR / "app-manifest.valid.yaml")
        for case in fixture["cases"]:
            with self.subTest(case=case["name"]):
                errors = sorted(
                    self.validator.iter_errors(case["manifest"]),
                    key=lambda error: list(error.absolute_path),
                )
                self.assertEqual(errors, [])

    def test_invalid_fixtures_fail_at_expected_path(self) -> None:
        fixture = _load_yaml(FIXTURES_DIR / "app-manifest.invalid.yaml")
        for case in fixture["cases"]:
            with self.subTest(case=case["name"]):
                errors = list(self.validator.iter_errors(case["manifest"]))
                self.assertTrue(errors, "fixture unexpectedly passed validation")
                self.assertIn(
                    case["expected_path"],
                    {_error_path(error) for error in errors},
                )


if __name__ == "__main__":
    unittest.main()
