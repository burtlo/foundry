"""Structural transcript lint for Foundry process violations."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def load_transcript_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        item = json.loads(stripped)
        if isinstance(item, dict):
            records.append(item)
    return records


def flatten_transcript_text(records: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for record in records:
        role = record.get("role")
        message = record.get("message")
        if isinstance(message, dict):
            for block in message.get("content") or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    chunks.append(block["text"])
                if block.get("type") == "tool_use":
                    name = block.get("name")
                    if isinstance(name, str):
                        chunks.append(name)
                    input_payload = block.get("input")
                    if isinstance(input_payload, dict):
                        chunks.append(json.dumps(input_payload))
        for key in ("content", "text", "output"):
            value = record.get(key)
            if isinstance(value, str):
                chunks.append(value)
    return "\n".join(chunks)


def extract_tool_uses(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    uses: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if record.get("role") != "assistant":
            continue
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        for block in message.get("content") or []:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            uses.append(
                {
                    "record_index": index,
                    "id": block.get("id"),
                    "name": block.get("name"),
                    "input": block.get("input") if isinstance(block.get("input"), dict) else {},
                }
            )
    return uses


def structural_findings(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    tool_uses = extract_tool_uses(records)
    for index, tool in enumerate(tool_uses):
        name = str(tool.get("name") or "").rsplit(".", 1)[-1]
        input_payload = tool.get("input") if isinstance(tool.get("input"), dict) else {}

        if name in ("Write", "ApplyPatch", "StrReplace"):
            path_value = str(input_payload.get("path") or input_payload.get("file_path") or input_payload)
            if re.search(r"[/\\]receipts[/\\].*\.json", path_value, re.I):
                findings.append(
                    {
                        "rule_id": "RECEIPT_BACKFILL",
                        "severity": "process_violation",
                        "description": "Parent wrote a receipt file directly instead of observability subagent complete",
                        "match": path_value,
                        "record_index": tool["record_index"],
                    }
                )

        if name == "Shell":
            command = str(input_payload.get("command") or "")
            if re.search(r"(?:^|[;&]\s*)dotnet\s+(?:build|test)\b", command, re.I):
                findings.append(
                    {
                        "rule_id": "RAW_DOTNET_ORCHESTRATOR",
                        "severity": "process_violation",
                        "description": "Orchestrator ran raw dotnet build/test instead of Foundry mechanics",
                        "match": command[:240],
                        "record_index": tool["record_index"],
                    }
                )

        if name in ("StrReplace", "Write", "ApplyPatch", "EditNotebook"):
            path_value = str(input_payload.get("path") or input_payload.get("target_notebook") or "")
            if re.search(r"\.(cs|csproj|razor|tsx|jsx)$", path_value, re.I):
                launched_before = any(
                    str(prior.get("name") or "").rsplit(".", 1)[-1] in ("Task", "Subagent")
                    for prior in tool_uses[:index]
                    if prior["record_index"] <= tool["record_index"]
                )
                launch_logged = any(
                    str(prior.get("name") or "").rsplit(".", 1)[-1] == "Shell"
                    and "worker launch-packet" in str(prior.get("input", {}).get("command") or "")
                    and "--work-item" in str(prior.get("input", {}).get("command") or "")
                    for prior in tool_uses[: index + 1]
                )
                if not launched_before and not launch_logged:
                    findings.append(
                        {
                            "rule_id": "INLINE_IMPLEMENT_BUILD",
                            "severity": "process_violation",
                            "description": "Parent edited implementation files without delegating a builder subagent",
                            "match": path_value,
                            "record_index": tool["record_index"],
                        }
                    )

        if name == "Shell" and "worker launch-packet" in str(input_payload.get("command") or ""):
            has_task_after = any(
                str(later.get("name") or "").rsplit(".", 1)[-1] in ("Task", "Subagent")
                for later in tool_uses[index + 1 : index + 8]
            )
            if not has_task_after:
                findings.append(
                    {
                        "rule_id": "LAUNCH_WITHOUT_TASK",
                        "severity": "process_violation",
                        "description": "Generated worker launch has no matching Task delegation nearby",
                        "match": str(input_payload.get("command") or "")[:240],
                        "record_index": tool["record_index"],
                    }
                )

    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, int, str]] = set()
    for finding in findings:
        key = (
            str(finding.get("rule_id")),
            int(finding.get("record_index") or 0),
            str(finding.get("match") or ""),
        )
        if key not in seen:
            seen.add(key)
            unique.append(finding)
    return unique


def analyze_transcript_file(
    path: Path,
    rules: list[dict[str, Any]],
) -> dict[str, Any]:
    records = load_transcript_records(path)
    text = flatten_transcript_text(records)
    regex_findings: list[dict[str, Any]] = []
    for rule in rules:
        for pattern in rule["patterns"]:
            for match in pattern.finditer(text):
                regex_findings.append(
                    {
                        "rule_id": rule["id"],
                        "severity": rule["severity"],
                        "description": rule["description"],
                        "match": match.group(0),
                        "offset": match.start(),
                    }
                )
    structural = structural_findings(records)
    findings = regex_findings + structural
    return {
        "finding_count": len(findings),
        "findings": findings,
        "rules_checked": [rule["id"] for rule in rules],
        "structural_finding_count": len(structural),
        "record_count": len(records),
    }
