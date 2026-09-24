"""Local markdown ticket intake for Foundry (no Jira)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

# Free-form local ids: AUTH-001, feat-refresh, etc.
LOCAL_ISSUE_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
JIRA_ISSUE_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]+-\d+$")
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)
TICKET_SCHEMA_VERSION = "1.0.0"
VALID_TICKET_SOURCES = frozenset({"local_file", "paste", "jira"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class TicketError(Exception):
    def __init__(self, error_code: str, message: str, *, required_input: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.required_input = required_input


def resolve_tickets_root(
    *,
    app_folder: str | Path | None,
    factory_root: str | Path | None,
    tickets_root: str | None,
) -> Path:
    """Resolve tickets directory. Relative paths are under app_folder, else factory_root."""
    raw = (tickets_root or "tickets").strip() or "tickets"
    path = Path(raw)
    if path.is_absolute():
        return path
    base: Path | None = None
    if app_folder:
        base = Path(app_folder).resolve()
    elif factory_root:
        base = Path(factory_root).resolve()
    if base is None:
        raise TicketError(
            "MISSING_TICKETS_ROOT",
            "Pass --app-folder or --factory-root to resolve a relative tickets root.",
            required_input="appFolder",
        )
    return (base / path).resolve()


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    if yaml is None:
        raise TicketError(
            "MISSING_YAML",
            "PyYAML is required to parse ticket frontmatter. pip install -r .cursor/foundry/cli/requirements.txt",
        )
    meta = yaml.safe_load(match.group(1)) or {}
    if not isinstance(meta, dict):
        raise TicketError("INVALID_TICKET", "Ticket frontmatter must be a YAML mapping.")
    return meta, match.group(2)


def _extract_title(body: str, meta: dict[str, Any]) -> str:
    if isinstance(meta.get("title"), str) and meta["title"].strip():
        return meta["title"].strip()
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return re.sub(r"^#+\s*", "", stripped).strip()
    return ""


def _acceptance_criteria(body: str) -> list[str]:
    lines = body.splitlines()
    collecting = False
    items: list[str] = []
    for line in lines:
        if re.match(r"^##+\s+Acceptance criteria\b", line, re.IGNORECASE):
            collecting = True
            continue
        if collecting and re.match(r"^##+\s+", line):
            break
        if collecting:
            m = re.match(r"^\s*[-*]\s+(?:\[[ xX]\]\s*)?(.+)$", line)
            if m:
                items.append(m.group(1).strip())
    return items


def load_ticket_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise TicketError("MISSING_TICKET", f"Ticket file not found: {path}", required_input="ticketFile")
    if path.suffix.lower() != ".md":
        raise TicketError("INVALID_TICKET", f"Ticket file must be markdown (.md): {path}")
    stem = path.stem
    if not LOCAL_ISSUE_KEY_RE.match(stem):
        raise TicketError(
            "INVALID_ISSUE_KEY",
            f"Filename stem {stem!r} is not a valid ticket id.",
            required_input="issueKey",
        )
    text = path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(text)
    meta_id = meta.get("id")
    if meta_id is not None and str(meta_id).strip() != stem:
        raise TicketError(
            "TICKET_ID_MISMATCH",
            f"Frontmatter id {meta_id!r} does not match filename stem {stem!r}.",
            required_input="issueKey",
        )
    title = _extract_title(body, meta)
    # Id must appear in title or body (description).
    haystack = f"{title}\n{body}"
    if stem not in haystack:
        raise TicketError(
            "TICKET_ID_MISSING_IN_BODY",
            f"Ticket id {stem!r} must appear in the title or body.",
            required_input="ticketFile",
        )
    if not title:
        raise TicketError(
            "INVALID_TICKET",
            "Ticket must have a title (frontmatter title or markdown H1).",
            required_input="ticketFile",
        )
    issue_type = meta.get("type") or meta.get("issue_type")
    if not issue_type or not str(issue_type).strip():
        raise TicketError(
            "INVALID_TICKET",
            "Ticket frontmatter must include type (e.g. Story).",
            required_input="ticketFile",
        )
    labels = meta.get("labels") or []
    if isinstance(labels, str):
        labels = [labels]
    if not isinstance(labels, list):
        raise TicketError("INVALID_TICKET", "labels must be a list or string.")
    app_hint = meta.get("app") or meta.get("app_folder")
    ac = _acceptance_criteria(body)
    return {
        "ticket_source": "local",
        "issue_key": stem,
        "summary": title,
        "description": body.strip(),
        "issue_type": str(issue_type).strip(),
        "labels": [str(x) for x in labels],
        "acceptance_criteria": ac,
        "app_hint": str(app_hint) if app_hint else None,
        "path": str(path.resolve()),
        "frontmatter": {k: v for k, v in meta.items() if k not in ("id",)},
    }


def to_sealed_ticket(
    packet: dict[str, Any],
    *,
    source: str,
    source_path: str | None = None,
) -> dict[str, Any]:
    """Normalize a load/ingest packet into the sealed ticket.json shape."""
    if source not in VALID_TICKET_SOURCES:
        raise TicketError("INVALID_TICKET_SOURCE", f"source must be one of {sorted(VALID_TICKET_SOURCES)}")
    ticket_id = str(packet.get("issue_key") or packet.get("id") or "").strip()
    if not ticket_id or not LOCAL_ISSUE_KEY_RE.match(ticket_id):
        raise TicketError("INVALID_ISSUE_KEY", f"Ticket id {ticket_id!r} is malformed.", required_input="issueKey")
    title = str(packet.get("summary") or packet.get("title") or "").strip()
    if not title:
        raise TicketError("INVALID_TICKET", "Sealed ticket requires a non-empty title.")
    issue_type = str(packet.get("issue_type") or packet.get("type") or "").strip()
    if not issue_type:
        raise TicketError("INVALID_TICKET", "Sealed ticket requires type.")
    body = str(packet.get("description") or packet.get("body") or "")
    ac = packet.get("acceptance_criteria") or []
    if not isinstance(ac, list):
        raise TicketError("INVALID_TICKET", "acceptance_criteria must be a list.")
    labels = packet.get("labels") or []
    if not isinstance(labels, list):
        raise TicketError("INVALID_TICKET", "labels must be a list.")
    app = packet.get("app") or packet.get("app_hint")
    path = source_path or packet.get("path") or packet.get("source_path")
    sealed = {
        "schema_version": TICKET_SCHEMA_VERSION,
        "id": ticket_id,
        "title": title,
        "summary": title,
        "type": issue_type,
        "body": body,
        "acceptance_criteria": [str(x) for x in ac],
        "labels": [str(x) for x in labels],
        "app": str(app) if app else None,
        "app_hint": str(app) if app else None,
        "source": source,
        "source_path": str(path) if path else None,
        "sealed_at": _now_iso(),
    }
    validate_sealed_ticket(sealed)
    return sealed


def validate_sealed_ticket(sealed: dict[str, Any]) -> None:
    required = ("schema_version", "id", "title", "type", "body", "acceptance_criteria", "source")
    for key in required:
        if key not in sealed:
            raise TicketError("INVALID_TICKET", f"Sealed ticket missing required field {key!r}.")
    if sealed.get("schema_version") != TICKET_SCHEMA_VERSION:
        raise TicketError("INVALID_TICKET", f"Unsupported ticket schema_version {sealed.get('schema_version')!r}.")
    if sealed.get("source") not in VALID_TICKET_SOURCES:
        raise TicketError("INVALID_TICKET_SOURCE", f"Invalid source {sealed.get('source')!r}.")
    if not str(sealed.get("title") or "").strip():
        raise TicketError("INVALID_TICKET", "title must be non-empty.")
    if not str(sealed.get("type") or "").strip():
        raise TicketError("INVALID_TICKET", "type must be non-empty.")
    if not isinstance(sealed.get("acceptance_criteria"), list):
        raise TicketError("INVALID_TICKET", "acceptance_criteria must be a list.")
    ticket_id = str(sealed.get("id") or "")
    if not LOCAL_ISSUE_KEY_RE.match(ticket_id):
        raise TicketError("INVALID_ISSUE_KEY", f"Ticket id {ticket_id!r} is malformed.")
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "packets" / "ticket.schema.json"
    if schema_path.is_file():
        try:
            from jsonschema import Draft202012Validator
        except ImportError:  # pragma: no cover
            return
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errors = sorted(Draft202012Validator(schema).iter_errors(sealed), key=str)
        if errors:
            messages = [
                f"{'/'.join(str(p) for p in error.absolute_path) or '<root>'}: {error.message}"
                for error in errors
            ]
            raise TicketError("INVALID_TICKET", f"ticket.schema.json: {'; '.join(messages)}")


def seal_ticket_to_run(run_directory: Path, sealed: dict[str, Any]) -> Path:
    validate_sealed_ticket(sealed)
    run_directory.mkdir(parents=True, exist_ok=True)
    path = run_directory / "ticket.json"
    path.write_text(json.dumps(sealed, indent=2) + "\n", encoding="utf-8")
    return path


def load_sealed_ticket(run_directory: Path) -> dict[str, Any] | None:
    path = run_directory / "ticket.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TicketError("INVALID_TICKET", "ticket.json is not a JSON object.")
    validate_sealed_ticket(data)
    return data


def parse_ticket_markdown(text: str, *, default_id: str | None = None) -> dict[str, Any]:
    """Parse pasted or file markdown into a load-shaped packet (not yet sealed)."""
    meta, body = _parse_frontmatter(text)
    meta_id = meta.get("id")
    ticket_id = str(meta_id).strip() if meta_id is not None else (default_id or "")
    if not ticket_id:
        raise TicketError(
            "INVALID_ISSUE_KEY",
            "Paste/ingest requires frontmatter id or --issue-key.",
            required_input="issueKey",
        )
    if not LOCAL_ISSUE_KEY_RE.match(ticket_id):
        raise TicketError("INVALID_ISSUE_KEY", f"Ticket id {ticket_id!r} is malformed.", required_input="issueKey")
    title = _extract_title(body, meta)
    if not title:
        raise TicketError("INVALID_TICKET", "Ticket must have a title (frontmatter title or markdown H1).")
    issue_type = meta.get("type") or meta.get("issue_type")
    if not issue_type or not str(issue_type).strip():
        raise TicketError("INVALID_TICKET", "Ticket frontmatter must include type (e.g. Story).")
    haystack = f"{title}\n{body}"
    if ticket_id not in haystack:
        raise TicketError(
            "TICKET_ID_MISSING_IN_BODY",
            f"Ticket id {ticket_id!r} must appear in the title or body.",
        )
    labels = meta.get("labels") or []
    if isinstance(labels, str):
        labels = [labels]
    if not isinstance(labels, list):
        raise TicketError("INVALID_TICKET", "labels must be a list or string.")
    app_hint = meta.get("app") or meta.get("app_folder")
    return {
        "ticket_source": "paste",
        "issue_key": ticket_id,
        "summary": title,
        "description": body.strip(),
        "issue_type": str(issue_type).strip(),
        "labels": [str(x) for x in labels],
        "acceptance_criteria": _acceptance_criteria(body),
        "app_hint": str(app_hint) if app_hint else None,
        "path": None,
        "frontmatter": {k: v for k, v in meta.items() if k not in ("id",)},
    }


def ingest_ticket(
    *,
    file: Path | None = None,
    text: str | None = None,
    issue_key: str | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    """Validate markdown from file or paste and return a sealed ticket packet."""
    if file is not None and text is not None:
        raise TicketError("INVALID_TICKET", "Pass either --file or --text/--stdin, not both.")
    if file is not None:
        packet = load_ticket_file(file)
        sealed_source = source or "local_file"
        return to_sealed_ticket(packet, source=sealed_source, source_path=str(file.resolve()))
    if text is None or not str(text).strip():
        raise TicketError("INVALID_TICKET", "Provide --file or ticket markdown text.", required_input="ticketText")
    packet = parse_ticket_markdown(text, default_id=issue_key)
    sealed_source = source or "paste"
    return to_sealed_ticket(packet, source=sealed_source, source_path=None)


def render_ticket_markdown(sealed: dict[str, Any]) -> str:
    validate_sealed_ticket(sealed)
    labels = sealed.get("labels") or []
    app = sealed.get("app") or sealed.get("app_hint")
    fm: dict[str, Any] = {
        "id": sealed["id"],
        "title": sealed["title"],
        "type": sealed["type"],
    }
    if labels:
        fm["labels"] = labels
    if app:
        fm["app"] = app
    if yaml is None:
        raise TicketError("MISSING_YAML", "PyYAML is required to save tickets.")
    front = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip()
    lines = [f"---", front, "---", "", f"# {sealed['id']} — {sealed['title']}", "", sealed.get("body") or ""]
    ac = sealed.get("acceptance_criteria") or []
    if ac:
        lines.extend(["", "## Acceptance criteria", ""])
        for item in ac:
            lines.append(f"- [ ] {item}")
    lines.append("")
    return "\n".join(lines)


def save_ticket(
    sealed_or_packet: dict[str, Any],
    *,
    tickets_root: Path,
    filename: str | None = None,
) -> dict[str, Any]:
    """Write markdown under tickets_root. Accepts sealed ticket or load packet."""
    if sealed_or_packet.get("schema_version") == TICKET_SCHEMA_VERSION:
        sealed = sealed_or_packet
    else:
        source = "local_file"
        sealed = to_sealed_ticket(sealed_or_packet, source=source)
    tickets_root.mkdir(parents=True, exist_ok=True)
    name = filename or f"{sealed['id']}.md"
    if not name.endswith(".md"):
        name = f"{name}.md"
    path = tickets_root / name
    if path.stem != sealed["id"]:
        raise TicketError(
            "TICKET_ID_MISMATCH",
            f"Filename stem {path.stem!r} must match ticket id {sealed['id']!r}.",
        )
    path.write_text(render_ticket_markdown(sealed), encoding="utf-8")
    return {"path": str(path.resolve()), "issue_key": sealed["id"], "ticket": sealed}


def list_tickets(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        raise TicketError("MISSING_TICKETS_ROOT", f"Tickets root not found: {root}", required_input="ticketsRoot")
    items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for path in sorted(root.glob("*.md")):
        try:
            packet = load_ticket_file(path)
            items.append(
                {
                    "issue_key": packet["issue_key"],
                    "summary": packet["summary"],
                    "issue_type": packet["issue_type"],
                    "path": packet["path"],
                    "labels": packet["labels"],
                }
            )
        except TicketError as exc:
            errors.append({"path": str(path), "errorCode": exc.error_code, "message": exc.message})
    return {
        "tickets_root": str(root.resolve()),
        "count": len(items),
        "tickets": items,
        "errors": errors,
    }


def format_pick_list(listed: dict[str, Any]) -> str:
    lines = [
        f"## Local tickets ({listed.get('count', 0)})",
        f"Root: `{listed.get('tickets_root')}`",
        "",
    ]
    for idx, ticket in enumerate(listed.get("tickets") or [], start=1):
        labels = ", ".join(ticket.get("labels") or []) or "—"
        lines.append(
            f"{idx}. **{ticket['issue_key']}** — {ticket.get('summary') or '(no title)'} "
            f"({ticket.get('issue_type')}; labels: {labels})"
        )
    if listed.get("errors"):
        lines.append("")
        lines.append("### Skipped (invalid)")
        for err in listed["errors"]:
            lines.append(f"- `{err['path']}`: {err['errorCode']} — {err['message']}")
    lines.append("")
    lines.append("Pick a number or issue id to continue.")
    return "\n".join(lines)


def pick_ticket(root: Path, selection: str | int | None = None) -> dict[str, Any]:
    listed = list_tickets(root)
    payload = {**listed, "markdown": format_pick_list(listed)}
    if selection is None or selection == "":
        return payload
    tickets = listed["tickets"]
    chosen: dict[str, Any] | None = None
    raw = str(selection).strip()
    if raw.isdigit():
        idx = int(raw)
        if idx < 1 or idx > len(tickets):
            raise TicketError("INVALID_SELECTION", f"Pick number must be 1..{len(tickets)}.", required_input="selection")
        chosen = tickets[idx - 1]
    else:
        for ticket in tickets:
            if ticket["issue_key"] == raw:
                chosen = ticket
                break
        if chosen is None:
            raise TicketError("INVALID_SELECTION", f"No ticket with id {raw!r}.", required_input="selection")
    packet = load_ticket_file(Path(chosen["path"]))
    return {**payload, "selected": packet}


def validate_issue_key_for_source(
    issue_key: str | None,
    *,
    ticket_source: str,
    pattern: str | None = None,
) -> None:
    if issue_key is None:
        return
    if pattern:
        if not re.match(pattern, issue_key):
            raise TicketError(
                "INVALID_ISSUE_KEY",
                f"Issue key {issue_key!r} does not match pattern {pattern!r}.",
                required_input="issueKey",
            )
        return
    if ticket_source == "jira":
        if not JIRA_ISSUE_KEY_RE.match(issue_key):
            raise TicketError(
                "INVALID_ISSUE_KEY",
                f"Issue key {issue_key!r} is not a Jira key.",
                required_input="issueKey",
            )
        return
    if not LOCAL_ISSUE_KEY_RE.match(issue_key):
        raise TicketError(
            "INVALID_ISSUE_KEY",
            f"Issue key {issue_key!r} is malformed.",
            required_input="issueKey",
        )
