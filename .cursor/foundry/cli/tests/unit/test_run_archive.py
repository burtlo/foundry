"""Unit tests for run archive helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from foundry_cli.run_archive import allocate_archive_slug, archive_run


def test_allocate_archive_slug_increments(tmp_path: Path) -> None:
    (tmp_path / "porcelain-0001").mkdir()
    (tmp_path / "porcelain-0002").mkdir()
    assert allocate_archive_slug(tmp_path, "porcelain") == "porcelain-0003"


def test_archive_run_dry_run(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    runs = workspace / ".foundry" / "runs" / "porcelain-0001"
    runs.mkdir(parents=True)
    (workspace / ".foundry").mkdir(parents=True, exist_ok=True)
    (workspace / ".foundry" / "app.yaml").write_text(
        """schema_version: 1
id: porcelain
commands:
  build:
    default:
      argv: ["make", "build"]
      cwd: "."
      timeout_seconds: 600
verification:
  implementation:
    - build
builders:
  default_owner: general-builder
  routes:
    - id: default
      owner: general-builder
      priority: 0
      globs:
        - "**/*"
""",
        encoding="utf-8",
    )
    snapshot = {
        "run_id": "porcelain-0001",
        "run_uuid": "uuid-1",
        "flow_id": "implementation",
        "visits": [],
        "state": {},
    }
    (runs / "snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")
    (runs / "ticket.json").write_text(
        json.dumps({"raw_input": "rename virtual models"}),
        encoding="utf-8",
    )

    bundle = tmp_path / "foundry" / ".cursor" / "foundry"
    from tests.flow_registry_stubs import write_stub_flow_registry

    write_stub_flow_registry(bundle)
    archive_root = tmp_path / "foundry" / "runs"
    (archive_root / "porcelain-0001").mkdir(parents=True)

    result = archive_run(
        source_run_dir=runs,
        foundry_bundle=bundle,
        archive_root=archive_root,
        dry_run=True,
    )
    assert result["dry_run"] is True
    assert result["archive_slug"] == "porcelain-0002"
    assert result["run_id"] == "porcelain-0001"
    assert runs.exists()


def test_archive_run_moves_and_writes_manifest(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    runs = workspace / ".foundry" / "runs" / "porcelain-0001"
    runs.mkdir(parents=True)
    (workspace / ".foundry").mkdir(parents=True, exist_ok=True)
    (workspace / ".foundry" / "app.yaml").write_text(
        """schema_version: 1
id: porcelain
commands:
  build:
    default:
      argv: ["make", "build"]
      cwd: "."
      timeout_seconds: 600
verification:
  implementation:
    - build
builders:
  default_owner: general-builder
  routes:
    - id: default
      owner: general-builder
      priority: 0
      globs:
        - "**/*"
""",
        encoding="utf-8",
    )
    (workspace / "plan.md").write_text("# plan\n", encoding="utf-8")
    snapshot = {
        "run_id": "porcelain-0001",
        "run_uuid": "uuid-1",
        "flow_id": "implementation",
        "active_visit": {"id": "v-007", "node_id": "execute.start", "kind": "gate", "lifecycle": "opened"},
        "visits": [],
        "state": {"approved_ac_digest": "sha256:abc"},
    }
    (runs / "snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")

    bundle = tmp_path / "foundry" / ".cursor" / "foundry"
    from tests.flow_registry_stubs import write_stub_flow_registry

    write_stub_flow_registry(bundle)
    archive_root = tmp_path / "foundry" / "runs"

    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text('{"role":"user"}\n', encoding="utf-8")
    review = tmp_path / "review.md"
    review.write_text("# review\n", encoding="utf-8")

    result = archive_run(
        source_run_dir=runs,
        foundry_bundle=bundle,
        archive_root=archive_root,
        transcript_path=transcript,
        review_path=review,
    )
    dest = Path(result["archive_path"])
    assert result["archive_slug"] == "porcelain-0001"
    assert not runs.exists()
    assert (dest / "snapshot.json").is_file()
    assert (dest / "archive" / "manifest.json").is_file()
    assert (dest / "archive" / "transcript.jsonl").is_file()
    assert (dest / "archive" / "review.md").is_file()
    assert (dest / "archive" / "workspace-plan.md").is_file()
    manifest = json.loads((dest / "archive" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == "porcelain-0001"
    assert manifest["archive_slug"] == "porcelain-0001"


def test_archive_run_rejects_missing_snapshot(tmp_path: Path) -> None:
    bundle = tmp_path / "foundry" / ".cursor" / "foundry"
    from tests.flow_registry_stubs import write_stub_flow_registry

    write_stub_flow_registry(bundle)
    missing = tmp_path / "missing"
    missing.mkdir()
    with pytest.raises(FileNotFoundError):
        archive_run(source_run_dir=missing, foundry_bundle=bundle, archive_root=tmp_path / "runs")
