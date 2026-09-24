"""iot-agents-prd documentation backend: .sln / AGENTS.md / generated PRD."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from foundry_docs import DocsError, git_changed_files, unsafe_relative_path

ENTRY_POINT_SUFFIXES = (
    ".Api",
    ".Functions",
    ".Web.Api",
    ".PWA",
    ".Admin",
    ".Web",
    ".Blazor",
    ".UI",
    ".Worker",
    ".Jobs",
    ".Processor",
    ".Listener",
    ".Console",
    ".CLI",
)
TEST_SUFFIXES = (".Tests", ".UnitTests", ".E2E.Tests", ".Test")
SLN_PROJECT_RE = re.compile(r'Project\("[^"]+"\)\s*=\s*"([^"]+)",\s*"([^"]+)"', re.IGNORECASE)

ROOT_AGENTS_AUDIT_FIELDS: list[tuple[str, str]] = [
    ("Application Name", "Application Metadata"),
    ("Description", "Application Metadata"),
    ("URL", "Application Metadata"),
    ("Tech Owner", "Ownership"),
    ("Business Owner", "Ownership"),
    ("Department", "Ownership"),
    ("Dev Team", "Ownership"),
    ("Products/Platforms", "Products & Platforms"),
    ("Features", "Products & Platforms"),
    ("Framework", "Technical Stack"),
    ("Programming Language", "Technical Stack"),
    ("Hosting Location", "Infrastructure"),
    ("Infrastructure", "Infrastructure"),
    ("Source Control", "Infrastructure"),
    ("Access Type", "Security & Compliance"),
    ("Authentication", "Security & Compliance"),
    ("Authorization", "Security & Compliance"),
    ("Compliance Requirements", "Security & Compliance"),
    ("Security Assessment - DAST", "Security & Compliance"),
    ("Security Assessment - SAST", "Security & Compliance"),
    ("Security Controls", "Security & Compliance"),
    ("Secret Management", "Security & Compliance"),
    ("Data Sensitivity", "Data Classification"),
    ("Data Type", "Data Classification"),
    ("Users per Month", "Business Impact"),
    ("Number of Users per Month", "Business Impact"),
    ("Revenue Impact", "Business Impact"),
    ("Criticality", "Business Impact"),
    ("External Services", "External Service Integrations"),
    ("Database Type", "Database"),
    ("Database Name", "Database"),
    ("Database Servers", "Database"),
    ("CI Platform", "CI/CD"),
    ("Platform", "CI/CD"),
    ("CI Workflows", "CI/CD"),
    ("CD Workflows", "CI/CD"),
    ("Deployment Environments", "CI/CD"),
    ("Artifacts", "CI/CD"),
    ("Test Harness", "Test Harness"),
    ("Store Data Source(s)", "Store Data Scope"),
    ("Store Data", "Store Data Scope"),
    ("Store Inclusion/Exclusion Rules", "Store Data Scope"),
    ("Environment Data Replication", "Environment Data Replication"),
]

PRD_VALIDATION_CHECKS: list[dict[str, str]] = [
    {"id": "1", "field": "Application Name", "prd_section": "1.1"},
    {"id": "2", "field": "Description", "prd_section": "1.1"},
    {"id": "3", "field": "Tech Owner", "prd_section": "1.1"},
    {"id": "4", "field": "Business Owner", "prd_section": "1.1"},
    {"id": "5", "field": "Department", "prd_section": "1.1"},
    {"id": "6", "field": "Dev Team", "prd_section": "1.1"},
    {"id": "7", "field": "Entry Point Index", "prd_section": "1.2", "section_heading": "Entry Point Index"},
    {"id": "8", "field": "Users per Month", "prd_section": "1.3", "alt_fields": ["Number of Users per Month"]},
    {"id": "9", "field": "Criticality", "prd_section": "1.3"},
    {"id": "10", "field": "Revenue Impact", "prd_section": "1.3"},
    {"id": "11", "field": "Framework", "prd_section": "2.1"},
    {"id": "12", "field": "Infrastructure", "prd_section": "2.2"},
    {"id": "13", "field": "External Interfaces", "prd_section": "3.1", "section_heading": "External Interfaces"},
    {"id": "14", "field": "External Service Integrations", "prd_section": "3.2", "section_heading": "External Service Integrations"},
    {"id": "15", "field": "Architecture", "prd_section": "2.3", "section_heading": "Architecture"},
    {"id": "16", "field": "Data Sensitivity", "prd_section": "4.1"},
    {"id": "17", "field": "Data Type", "prd_section": "4.1"},
    {"id": "18", "field": "Database Type", "prd_section": "4"},
    {"id": "19", "field": "Database Name", "prd_section": "4"},
    {"id": "20", "field": "Database Servers", "prd_section": "4", "section_heading": "Server Locations"},
    {"id": "21", "field": "Data Contracts", "prd_section": "4.2", "section_heading": "Data Contracts"},
    {"id": "22", "field": "Authentication", "prd_section": "5.1"},
    {"id": "23", "field": "Compliance Requirements", "prd_section": "5.2"},
    {"id": "24", "field": "Security Assessment - DAST", "prd_section": "5.2", "alt_fields": ["DAST"]},
    {"id": "25", "field": "Security Assessment - SAST", "prd_section": "5.2", "alt_fields": ["SAST"]},
    {"id": "26", "field": "Secret Management", "prd_section": "5.3"},
    {
        "id": "27",
        "field": "Component Architecture",
        "prd_section": "6",
        "section_heading": "Component Architecture",
        "alt_section_headings": ["Entry Point Index", "Repositories/Components"],
    },
    {"id": "28", "field": "Platform", "prd_section": "8", "alt_fields": ["CI Platform"]},
    {"id": "29", "field": "CI Workflows", "prd_section": "8", "section_heading": "Workflows"},
    {"id": "30", "field": "CD Workflows", "prd_section": "8", "section_heading": "CD Pipeline"},
    {"id": "31", "field": "Deployment Environments", "prd_section": "8"},
    {"id": "32", "field": "Test Harness", "prd_section": "9"},
    {"id": "33", "field": "Store Data", "prd_section": "4.4", "alt_fields": ["Store Data Source(s)"]},
    {"id": "34", "field": "Store Data Scope", "prd_section": "4.4", "section_heading": "Store Data Scope"},
    {
        "id": "35",
        "field": "Store Inclusion/Exclusion Rules",
        "prd_section": "4.4",
        "alt_fields": ["Store Data"],
        "section_heading": "Store Data Scope",
    },
    {"id": "36", "field": "Environment Data Replication", "prd_section": "4.5"},
    {"id": "37", "field": "Environment Data Replication", "prd_section": "4.5"},
    {"id": "38", "field": "Environment Data Replication", "prd_section": "4.5"},
    {"id": "39", "field": "Environment Data Replication", "prd_section": "4.5"},
    {"id": "40", "field": "Secret Management", "prd_section": "5.3"},
]

def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def value_in_prd(value: str, prd_text: str) -> bool:
    norm_prd = normalize_text(prd_text)
    norm_val = normalize_text(value)
    if norm_val in norm_prd:
        return True
    if norm_val in {"not applicable", "tbd", "n/a"}:
        return "not applicable" in norm_prd or "n/a" in norm_prd
    primary = normalize_text(value.split(",")[0].split("—")[0].strip())
    if len(primary) >= 4 and primary in norm_prd:
        return True
    tokens = [token for token in re.split(r"[\s,;/]+", primary) if len(token) >= 4]
    return any(token in norm_prd for token in tokens)


def extract_table_field(markdown: str, field_label: str) -> str | None:
    patterns = [
        rf"\|\s*\*?\*?{re.escape(field_label)}\*?\*?\s*\|\s*([^|\n]+)",
        rf"\*\*{re.escape(field_label)}\*\*\s*\|\s*([^|\n]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, markdown, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if value and value not in {"TBD", "—", "-", "N/A"}:
                return value
            if value:
                return value
    return None


def section_present(markdown: str, heading: str) -> bool:
    return bool(re.search(rf"^#{{1,6}}\s+{re.escape(heading)}\b", markdown, re.MULTILINE | re.IGNORECASE))


def classify_project(name: str, project_dir: Path | None = None) -> str:
    if any(name.endswith(suffix) for suffix in TEST_SUFFIXES):
        return "test"
    if any(token in name for token in ENTRY_POINT_SUFFIXES):
        return "entry_point"
    if name.endswith(".Http.Api") or ".Http." in name:
        return "entry_point"
    if project_dir is not None and (project_dir / "host.json").is_file():
        return "entry_point"
    return "library"


def parse_sln_projects(sln_path: Path) -> list[dict[str, str]]:
    text = sln_path.read_text(encoding="utf-8")
    projects: list[dict[str, str]] = []
    for name, rel_path in SLN_PROJECT_RE.findall(text):
        if rel_path.endswith(".csproj"):
            project_dir = (sln_path.parent / rel_path).parent
            projects.append(
                {
                    "name": name,
                    "path": rel_path.replace("\\", "/"),
                    "kind": classify_project(name, project_dir),
                }
            )
    return projects


def find_solution(app_folder: Path) -> Path | None:
    matches = sorted(app_folder.glob("*.sln"))
    return matches[0] if matches else None


def list_agents_files(app_folder: Path) -> list[Path]:
    return sorted(app_folder.glob("**/AGENTS.md"))


def agents_content_hash(app_folder: Path) -> str:
    digest = hashlib.sha256()
    for path in list_agents_files(app_folder):
        digest.update(path.relative_to(app_folder).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def find_prd_path(app_folder: Path) -> Path | None:
    candidates = sorted(app_folder.glob("Documentation/prd-*-generated.md"))
    if candidates:
        return candidates[0]
    candidates = sorted(app_folder.glob("docs/prd-*-generated.md"))
    return candidates[0] if candidates else None


def default_prd_path(app_folder: Path, app_name: str | None = None) -> Path:
    existing = find_prd_path(app_folder)
    if existing:
        return existing
    name = app_name or app_folder.name
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return app_folder / "Documentation" / f"prd-{slug}-generated.md"


def is_narrow_agents_diff(changed_files: list[str]) -> bool:
    if not changed_files:
        return True
    return all(path.endswith("AGENTS.md") for path in changed_files)


def canonical_audit_fields() -> list[tuple[str, str]]:
    seen: set[str] = set()
    fields: list[tuple[str, str]] = []
    for field, section in ROOT_AGENTS_AUDIT_FIELDS:
        if field in seen:
            continue
        seen.add(field)
        fields.append((field, section))
    return fields


def audit_agents_file(path: Path) -> dict[str, Any]:
    markdown = path.read_text(encoding="utf-8")
    missing: list[str] = []
    present: list[str] = []
    for field, section in canonical_audit_fields():
        value = extract_table_field(markdown, field)
        has_section = section_present(markdown, section) or section_present(markdown, field)
        if value or has_section:
            present.append(field)
        else:
            missing.append(field)
    return {
        "path": str(path),
        "exists": True,
        "present_count": len(present),
        "missing_fields": sorted(set(missing)),
        "complete": len(missing) <= 5,
    }


def docs_discover(app_folder: str) -> dict[str, Any]:
    root = Path(app_folder)
    if not root.is_dir():
        raise DocsError("INVALID_APP_FOLDER", f"App folder does not exist: {app_folder}")
    sln = find_solution(root)
    if sln is None:
        raise DocsError("SOLUTION_NOT_FOUND", f"No .sln file found under {app_folder}.")
    projects = parse_sln_projects(sln)
    entry_points = [p for p in projects if p["kind"] == "entry_point"]
    libraries = [p for p in projects if p["kind"] == "library"]
    tests = [p for p in projects if p["kind"] == "test"]
    agents_files = [str(p.relative_to(root)) for p in list_agents_files(root)]
    return {
        "app_folder": str(root),
        "solution": sln.name,
        "solution_path": str(sln),
        "entry_points": entry_points,
        "libraries": libraries,
        "tests": tests,
        "agents_files": agents_files,
        "entry_point_count": len(entry_points),
    }


def docs_audit(app_folder: str) -> dict[str, Any]:
    root = Path(app_folder)
    if not root.is_dir():
        raise DocsError("INVALID_APP_FOLDER", f"App folder does not exist: {app_folder}")
    discovery = docs_discover(app_folder)
    audits = [audit_agents_file(path) for path in list_agents_files(root)]
    missing_agents = []
    for entry in discovery["entry_points"]:
        rel = Path(entry["path"]).parent / "AGENTS.md"
        if not (root / rel).is_file() and not (root / "AGENTS.md").is_file():
            missing_agents.append(str(rel))
    return {
        "app_folder": str(root),
        "agents_audits": audits,
        "missing_agents_files": missing_agents,
        "prd_generator_exists": (root / "Documentation" / "prd-generator-prompt.md").is_file(),
        "prd_exists": find_prd_path(root) is not None,
        "summary": {
            "agents_file_count": len(audits),
            "incomplete_files": sum(1 for audit in audits if not audit["complete"]),
        },
    }


def compile_prd_markdown(app_folder: Path) -> str:
    root_agents = app_folder / "AGENTS.md"
    if not root_agents.is_file():
        raise DocsError("MISSING_ROOT_AGENTS", f"Root AGENTS.md not found in {app_folder}.")
    root_md = root_agents.read_text(encoding="utf-8")
    app_name = extract_table_field(root_md, "Application Name") or app_folder.name
    description = extract_table_field(root_md, "Description") or "TBD"
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry_agents = [path for path in list_agents_files(app_folder) if path.resolve() != root_agents.resolve()]

    lines = [
        f"# {app_name} - Product Requirements Document",
        "",
        f"Generated: {generated}",
        f"Source: AGENTS.md files from {app_folder.name} workspace",
        "",
        "---",
        "",
        "## 1. System Identity",
        "",
        "### 1.1 Overview",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| **System Name** | {app_name} |",
        f"| **Description** | {description} |",
    ]
    for label in ("URL", "Tech Owner", "Business Owner", "Department", "Dev Team"):
        value = extract_table_field(root_md, label)
        if value:
            lines.append(f"| **{label}** | {value} |")

    lines.extend(["", "### 1.2 Repositories/Components", "", "| Component | Path | Description |", "|-----------|------|-------------|"])
    for path in entry_agents:
        rel = path.parent.relative_to(app_folder)
        name = path.parent.name
        lines.append(f"| {name} | `{rel.as_posix()}/` | Entry point AGENTS.md |")
    if not entry_agents:
        lines.append(f"| {app_name} | `{app_folder.name}/` | Root application |")

    lines.extend(["", "### 1.3 Key Metrics", "", "| Metric | Value |", "|--------|-------|"])
    for label in ("Number of Users per Month", "Users per Month", "Criticality", "Revenue Impact"):
        value = extract_table_field(root_md, label)
        if value:
            metric = label.replace("Number of ", "")
            lines.append(f"| **{metric}** | {value} |")

    lines.extend(["", "### 1.4 Products & Platforms", ""])
    for label in ("Products/Platforms", "Features"):
        value = extract_table_field(root_md, label)
        if value:
            lines.append(f"- **{label}:** {value}")

    lines.extend(["", "---", "", "## 2. Technical Architecture", "", "### 2.1 Technology Stack", ""])
    for label in ("Framework", "Programming Language"):
        value = extract_table_field(root_md, label)
        if value:
            lines.append(f"- **{label}:** {value}")

    lines.extend(["", "### 2.2 Infrastructure", ""])
    for label in ("Hosting Location", "Infrastructure", "Source Control"):
        value = extract_table_field(root_md, label)
        if value:
            lines.append(f"- **{label}:** {value}")

    if section_present(root_md, "Architecture"):
        arch = re.search(
            r"### Architecture\s*\n+(.*?)(?=\n### |\n## |\Z)",
            root_md,
            re.DOTALL | re.IGNORECASE,
        )
        if arch:
            lines.extend(["", "### 2.3 Architecture Diagram", "", arch.group(1).strip(), ""])

    lines.extend(["", "---", "", "## 3. External Interfaces", ""])
    if section_present(root_md, "External Service Integrations"):
        block = re.search(
            r"## External Service Integrations\s*\n+(.*?)(?=\n## |\Z)",
            root_md,
            re.DOTALL | re.IGNORECASE,
        )
        if block:
            lines.append(block.group(1).strip())

    for path in entry_agents:
        entry_md = path.read_text(encoding="utf-8")
        if section_present(entry_md, "External Interfaces"):
            block = re.search(
                r"## External Interfaces\s*\n+(.*?)(?=\n## |\Z)",
                entry_md,
                re.DOTALL | re.IGNORECASE,
            )
            if block:
                lines.extend(["", f"### {path.parent.name}", "", block.group(1).strip()])

    lines.extend(["", "---", "", "## 4. Data Architecture", "", "### 4.1 Data Classification", ""])
    for label in ("Data Sensitivity", "Data Type"):
        value = extract_table_field(root_md, label)
        if value:
            lines.append(f"- **{label}:** {value}")

    if section_present(root_md, "Database"):
        block = re.search(r"## Database\s*\n+(.*?)(?=\n## |\Z)", root_md, re.DOTALL | re.IGNORECASE)
        if block:
            lines.extend(["", "### 4.2 Database", "", block.group(1).strip()])

    if section_present(root_md, "Store Data Scope"):
        block = re.search(
            r"## Store Data Scope\s*\n+(.*?)(?=\n## |\Z)",
            root_md,
            re.DOTALL | re.IGNORECASE,
        )
        if block:
            lines.extend(["", "### 4.4 Store Data Scope", "", block.group(1).strip()])

    if section_present(root_md, "Environment Data Replication"):
        block = re.search(
            r"## Environment Data Replication\s*\n+(.*?)(?=\n## |\Z)",
            root_md,
            re.DOTALL | re.IGNORECASE,
        )
        if block:
            lines.extend(["", "### 4.5 Environment Data Replication", "", block.group(1).strip()])

    lines.extend(["", "---", "", "## 5. Security & Compliance", ""])
    for heading in ("Authentication & Access", "Compliance", "Secret Management"):
        if section_present(root_md, heading):
            block = re.search(
                rf"### {heading}\s*\n+(.*?)(?=\n### |\n## |\Z)",
                root_md,
                re.DOTALL | re.IGNORECASE,
            )
            if block:
                lines.extend(["", f"### 5.x {heading}", "", block.group(1).strip()])

    lines.extend(["", "---", "", "## 6. Component Architecture", ""])
    if section_present(root_md, "Entry Point Index"):
        block = re.search(
            r"## Entry Point Index\s*\n+(.*?)(?=\n## |\Z)",
            root_md,
            re.DOTALL | re.IGNORECASE,
        )
        if block:
            lines.append(block.group(1).strip())
    for path in entry_agents:
        rel = path.relative_to(app_folder)
        lines.append(f"- `{rel.as_posix()}`")

    lines.extend(["", "---", "", "## 8. Deployment & Infrastructure", ""])
    if section_present(root_md, "CI/CD"):
        block = re.search(r"## CI/CD\s*\n+(.*?)(?=\n## |\Z)", root_md, re.DOTALL | re.IGNORECASE)
        if block:
            lines.append(block.group(1).strip())

    lines.extend(["", "---", "", "## 9. Development Guidelines", ""])
    for path in entry_agents:
        entry_md = path.read_text(encoding="utf-8")
        if section_present(entry_md, "Test Harness & Dev Tools"):
            block = re.search(
                r"## Test Harness & Dev Tools\s*\n+(.*?)(?=\n## |\Z)",
                entry_md,
                re.DOTALL | re.IGNORECASE,
            )
            if block:
                lines.extend([f"### {path.parent.name}", "", block.group(1).strip(), ""])

    return "\n".join(lines).rstrip() + "\n"


def prd_generate(
    app_folder: str,
    since: str | None = None,
    *,
    git_runner: Callable[..., Any] | None = None,
    write: bool = True,
) -> dict[str, Any]:
    root = Path(app_folder)
    if not root.is_dir():
        raise DocsError("INVALID_APP_FOLDER", f"App folder does not exist: {app_folder}")
    changed_files: list[str] = []
    if since:
        changed_files = git_changed_files(root, since, runner=git_runner)
        if changed_files and not is_narrow_agents_diff(changed_files):
            raise DocsError(
                "PRD_WIDE_DIFF",
                "Changes since the base commit are not limited to AGENTS.md; use documentation-writer for LLM PRD work.",
                extra={"changed_files": changed_files},
            )
        if not changed_files:
            existing = find_prd_path(root)
            if existing and existing.is_file():
                return {
                    "app_folder": str(root),
                    "skipped": True,
                    "reason": "no_agents_changes",
                    "method": "deterministic",
                    "prd_path": str(existing),
                    "created_or_updated": False,
                }

    content = compile_prd_markdown(root)
    prd_path = default_prd_path(root)
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    previous_hash = None
    if prd_path.is_file():
        previous_hash = hashlib.sha256(prd_path.read_bytes()).hexdigest()
        if previous_hash == content_hash:
            return {
                "app_folder": str(root),
                "skipped": True,
                "reason": "up_to_date",
                "method": "deterministic",
                "prd_path": str(prd_path),
                "created_or_updated": False,
                "agents_hash": agents_content_hash(root),
            }

    if write:
        prd_path.parent.mkdir(parents=True, exist_ok=True)
        prd_path.write_text(content, encoding="utf-8")

    return {
        "app_folder": str(root),
        "skipped": False,
        "method": "deterministic",
        "prd_path": str(prd_path),
        "created_or_updated": True,
        "agents_hash": agents_content_hash(root),
        "changed_files": changed_files,
        "previous_hash": previous_hash,
        "content_hash": content_hash,
    }


def _agents_sources(app_folder: Path) -> list[tuple[str, str]]:
    sources: list[tuple[str, str]] = []
    for path in list_agents_files(app_folder):
        sources.append((str(path.relative_to(app_folder)), path.read_text(encoding="utf-8")))
    return sources


def prd_validate(app_folder: str) -> dict[str, Any]:
    root = Path(app_folder)
    if not root.is_dir():
        raise DocsError("INVALID_APP_FOLDER", f"App folder does not exist: {app_folder}")
    prd_path = find_prd_path(root)
    if prd_path is None or not prd_path.is_file():
        raise DocsError("PRD_NOT_FOUND", f"No generated PRD found under {app_folder}.")
    prd_text = prd_path.read_text(encoding="utf-8")
    sources = _agents_sources(root)
    if not sources:
        raise DocsError("MISSING_AGENTS", f"No AGENTS.md files found under {app_folder}.")

    checks: list[dict[str, Any]] = []
    passed = 0
    for spec in PRD_VALIDATION_CHECKS:
        fields = [spec["field"]] + list(spec.get("alt_fields") or [])
        section_heading = spec.get("section_heading")
        section_headings = [section_heading] if section_heading else []
        section_headings.extend(spec.get("alt_section_headings") or [])
        expected_values: list[str] = []
        section_ok = False
        for rel, markdown in sources:
            for heading in section_headings:
                if heading and section_present(markdown, heading):
                    section_ok = True
            for field in fields:
                value = extract_table_field(markdown, field)
                if value:
                    expected_values.append(value)
                if section_present(markdown, field):
                    section_ok = True

        ok = False
        detail = "missing source evidence"
        if section_headings and section_ok:
            if any(heading and heading.lower() in normalize_text(prd_text) for heading in section_headings):
                ok = True
                detail = f"section {section_headings[0]} present"
        if not ok and expected_values:
            for value in expected_values:
                if value_in_prd(value, prd_text):
                    ok = True
                    detail = f"matched {fields[0]}"
                    break
        if not ok and section_ok and spec.get("prd_section"):
            section_token = f"## {spec['prd_section'][:1]}"
            if section_token.lower() in normalize_text(prd_text):
                ok = True
                detail = f"prd section {spec['prd_section']} present"
        if not ok and not expected_values and not section_ok:
            ok = True
            detail = "not applicable in source AGENTS.md"

        if ok:
            passed += 1
        checks.append(
            {
                "id": spec["id"],
                "field": spec["field"],
                "prd_section": spec["prd_section"],
                "passed": ok,
                "detail": detail,
            }
        )

    total = len(checks)
    payload = {
        "app_folder": str(root),
        "prd_path": str(prd_path),
        "passed": passed == total,
        "summary": {"passed": passed, "total": total, "failed": total - passed},
        "checks": checks,
    }
    if passed != total:
        failed = [check for check in checks if not check["passed"]]
        raise DocsError(
            "PRD_VALIDATION_FAILED",
            f"PRD validation failed: {len(failed)} of {total} checks did not pass.",
            extra=payload,
        )
    return payload


class IotAgentsPrdBackend:
    """Factory-shipped .NET/IoT AGENTS.md + PRD documentation model."""

    model = "iot-agents-prd"
    workflow = "iot-documentation-workflow"

    def validate_config(self, config: Any) -> None:
        if config is None:
            config = {}
        if not isinstance(config, dict):
            raise DocsError(
                "APP_MANIFEST_DOCUMENTATION_CONFIG_INVALID",
                "iot-agents-prd documentation.config must be an object.",
            )
        agents = config.get("agents")
        if agents is not None and (
            not isinstance(agents, list)
            or not all(isinstance(item, str) and item.strip() for item in agents)
        ):
            raise DocsError(
                "APP_MANIFEST_DOCUMENTATION_CONFIG_INVALID",
                "iot-agents-prd documentation.config.agents must be an array of relative paths.",
            )
        if isinstance(agents, list):
            for item in agents:
                if unsafe_relative_path(item):
                    raise DocsError(
                        "APP_MANIFEST_DOCUMENTATION_CONFIG_INVALID",
                        f"iot-agents-prd agents glob escapes the app folder: {item!r}.",
                    )
        generated = config.get("generated_prd")
        if generated is not None:
            if not isinstance(generated, str) or not generated.strip():
                raise DocsError(
                    "APP_MANIFEST_DOCUMENTATION_CONFIG_INVALID",
                    "iot-agents-prd documentation.config.generated_prd must be a relative path.",
                )
            if unsafe_relative_path(generated):
                raise DocsError(
                    "APP_MANIFEST_DOCUMENTATION_CONFIG_INVALID",
                    f"iot-agents-prd generated_prd escapes the app folder: {generated!r}.",
                )

    def discover(self, snapshot: dict[str, Any], app_folder: str) -> dict[str, Any]:
        payload = docs_discover(app_folder)
        payload["model"] = self.model
        payload["workflow"] = self.workflow
        payload["snapshot_id"] = (snapshot or {}).get("id")
        return payload

    def execute(
        self,
        snapshot: dict[str, Any],
        app_folder: str,
        since: str | None,
        *,
        git_runner: Callable[..., Any] | None = None,
    ) -> dict[str, Any]:
        from foundry_docs import common_result

        checks: list[str] = []
        blockers: list[str] = []
        artifacts: list[str] = []
        changed = False
        generated: dict[str, Any] | None = None
        validated: dict[str, Any] | None = None
        root = Path(app_folder)

        try:
            discovery = self.discover(snapshot, app_folder)
            checks.append("discover")
            artifacts.extend(discovery.get("agents_files") or [])
            if discovery.get("solution"):
                artifacts.append(str(discovery["solution"]))
        except DocsError as exc:
            blockers.append(f"{exc.error_code}: {exc.message}")
            return common_result(
                model=self.model,
                workflow=self.workflow,
                status="failed",
                artifacts=artifacts,
                changed=False,
                validation_passed=False,
                checks=checks,
                publication_required=False,
                publication_passed=True,
                blockers=blockers,
            )

        try:
            audit = docs_audit(app_folder)
            checks.append("audit")
            summary = audit.get("summary") or {}
            if summary.get("incomplete_files") or audit.get("missing_agents_files"):
                changed = True
            if audit.get("prd_exists"):
                existing = find_prd_path(root)
                if existing is not None:
                    artifacts.append(str(existing.relative_to(root)) if existing.is_relative_to(root) else str(existing))
        except DocsError as exc:
            blockers.append(f"{exc.error_code}: {exc.message}")

        try:
            generated = prd_generate(app_folder, since, git_runner=git_runner)
            checks.append("prd_generate")
            if generated.get("created_or_updated"):
                changed = True
            if generated.get("prd_path"):
                prd_path = Path(str(generated["prd_path"]))
                rel = (
                    str(prd_path.relative_to(root))
                    if prd_path.is_absolute() and prd_path.is_relative_to(root)
                    else str(generated["prd_path"])
                )
                if rel not in artifacts:
                    artifacts.append(rel)
        except DocsError as exc:
            if exc.error_code == "PRD_WIDE_DIFF":
                checks.append("prd_generate_skipped_wide_diff")
                changed = True
                generated = {
                    "skipped": True,
                    "reason": "wide_diff",
                    "created_or_updated": False,
                    "changed_files": (exc.extra or {}).get("changed_files") or [],
                }
            else:
                blockers.append(f"{exc.error_code}: {exc.message}")

        created_or_updated = bool(generated and generated.get("created_or_updated"))
        if since and not changed:
            try:
                changed_files = git_changed_files(root, since, runner=git_runner)
                if changed_files:
                    changed = True
            except DocsError:
                pass

        publication_required = created_or_updated
        publication_passed = not publication_required

        prd_path = find_prd_path(root)
        should_validate = prd_path is not None and (
            generated is None or generated.get("reason") != "wide_diff"
        )
        if should_validate:
            try:
                validated = prd_validate(app_folder)
                checks.append("prd_validate")
            except DocsError as exc:
                blockers.append(f"{exc.error_code}: {exc.message}")
                extra = exc.extra or {}
                if isinstance(extra.get("checks"), list):
                    validated = extra
        elif generated and generated.get("reason") == "wide_diff":
            checks.append("prd_validate_skipped_wide_diff")

        unique_artifacts: list[str] = []
        for item in artifacts:
            if item not in unique_artifacts:
                unique_artifacts.append(item)

        validation_passed = not blockers and (validated is None or validated.get("passed") is not False)
        return common_result(
            model=self.model,
            workflow=self.workflow,
            status="failed" if blockers else "completed",
            artifacts=unique_artifacts,
            changed=changed,
            validation_passed=validation_passed,
            checks=checks,
            publication_required=publication_required,
            publication_passed=publication_passed,
            blockers=blockers,
        )

    def validate_receipt(self, receipt: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
        from foundry_docs import validate_common_result

        return validate_common_result(receipt, snapshot, expected_model=self.model)

    def delivery_requirements(
        self,
        snapshot: dict[str, Any],
        step_evidence: dict[str, Any] | None,
    ) -> dict[str, bool]:
        evidence = step_evidence or {}
        result = evidence.get("documentation_result")
        publication = result.get("publication") if isinstance(result, dict) else None
        publication = publication if isinstance(publication, dict) else {}
        required = bool(publication.get("required")) or bool(evidence.get("prd_created_or_updated"))
        passed = bool(publication.get("passed")) or evidence.get("sync_prd_ok") is True
        if not required:
            passed = True
        return {"required": required, "passed": passed}
