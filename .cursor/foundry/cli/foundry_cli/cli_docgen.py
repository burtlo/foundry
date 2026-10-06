"""Generate CLI self-documentation from argparse and capability annotations."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from foundry_cli.docgen import rel_link

# Dest names for argparse routing actions — skipped when listing command flags.
_PARSER_SKIP_DESTS = frozenset({"help", "command"})


def collect_subparser_dests(parser: argparse.ArgumentParser) -> frozenset[str]:
    """Collect all subparser dest names from an argparse tree."""
    dests: set[str] = set(_PARSER_SKIP_DESTS)
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            dests.add(action.dest)
            for subparser in action.choices.values():
                dests |= collect_subparser_dests(subparser)
    return frozenset(dests)


# Author annotations for implemented commands (supplements argparse help text).
CLI_CAPABILITIES: dict[str, dict[str, Any]] = {
    "run.context": {
        "command": "run context",
        "summary": (
            "Assemble the steward context packet for a visit: reads, allow grants, "
            "artifact declarations, worker binding, and instructions path. "
            "Use `--json` for the context-packet envelope or `--markdown` for a single "
            "steward document with inlined step instructions."
        ),
        "schema": "registry:schemas/context-packet.schema.json",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/run_context.feature",
        "status": "implemented",
        "extra_sections": [
            {
                "title": "Output modes",
                "body": (
                    "| Mode | Flag | Audience | Contents |\n"
                    "|---|---|---|---|\n"
                    "| JSON | `--json` | Programs, schema validation | "
                    "`context-packet.schema.json` envelope; includes `instructions_path` "
                    "but not inlined instruction text |\n"
                    "| Markdown | `--markdown` | Phase stewards | Single document with "
                    "metadata sections and step instructions inlined verbatim |\n"
                    "\n"
                    "`--json` and `--markdown` are mutually exclusive. Stewards SHOULD use "
                    "`--markdown` and follow one document. Step files under "
                    "`.cursor/foundry/nodes/` remain the authoring source; the CLI is a "
                    "renderer. The Worker block lists registry paths only — stewards launch "
                    "workers separately.\n"
                    "\n"
                    "See [capabilities.md](../../concepts/capabilities.md#steward-context) "
                    "for steward-context semantics."
                ),
            },
            {
                "title": "Sample invocations",
                "body": (
                    "```bash\n"
                    "foundry run context --run-dir .cursor/foundry/fixtures/runs/porcelain-0007-v001 "
                    "--markdown\n"
                    "foundry run context --run-dir .cursor/foundry/fixtures/runs/porcelain-0007-v001 "
                    "--json\n"
                    "```"
                ),
            },
            {
                "title": "Sample markdown output (abbreviated)",
                "body": (
                    "```markdown\n"
                    "# Steward context — shape.intake (v-001)\n"
                    "\n"
                    "_Shape intake — publish ticket and seal receipts_\n"
                    "\n"
                    "## Position\n"
                    "\n"
                    "- run_id: `porcelain-0007`\n"
                    "- visit_id: `v-001`\n"
                    "- node_id: `shape.intake`\n"
                    "- kind: `step`\n"
                    "- lifecycle: `opened`\n"
                    "\n"
                    "## Reads\n"
                    "\n"
                    "### Config\n"
                    "| Key | Value |\n"
                    "|---|---|\n"
                    "| workspace | . |\n"
                    "\n"
                    "## Allow\n"
                    "\n"
                    "### CLI\n"
                    "- `artifact.publish`\n"
                    "- `transition`\n"
                    "\n"
                    "## Produces\n"
                    "\n"
                    "### Artifacts\n"
                    "| ID | URI | Resolved URI |\n"
                    "|---|---|---|\n"
                    "| ticket | `run:artifacts/{visit_id}/ticket.json` | "
                    "`run:artifacts/v-001/ticket.json` |\n"
                    "\n"
                    "## Worker\n"
                    "\n"
                    "| Key | Value |\n"
                    "|---|---|\n"
                    "| subagent_type | intake-checker.shape |\n"
                    "| mode | shape |\n"
                    "| prompt | registry:workers/intake-checker.shape/prompt.md |\n"
                    "\n"
                    "---\n"
                    "\n"
                    "## Instructions\n"
                    "\n"
                    "<!-- inlined from registry:nodes/shape.intake/instructions.md -->\n"
                    "\n"
                    "# Shape intake\n"
                    "\n"
                    "## Goal\n"
                    "\n"
                    "Publish the `ticket` artifact.\n"
                    "```"
                ),
            },
        ],
    },
    "catalog.build": {
        "command": "catalog build",
        "summary": "Generate machine-readable node index YAML files from the flow registry.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/catalog_build.feature",
        "status": "implemented",
    },
    "doc.build": {
        "command": "doc build",
        "summary": (
            "Generate flow, node, worker, and CLI documentation under the docs directory "
            "from factory-flow.yaml, registry artifacts, and this CLI's command surface."
        ),
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/doc_build.feature",
        "status": "implemented",
    },
    "dev.docs": {
        "command": "dev docs",
        "summary": "Build catalog indexes and regenerate all node, worker, and CLI documentation.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/dev_commands.feature",
        "status": "implemented",
    },
    "dev.unit": {
        "command": "dev unit",
        "summary": "Run the Foundry CLI unit test suite (pytest tests/unit).",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/dev_commands.feature",
        "status": "implemented",
    },
    "dev.acceptance": {
        "command": "dev acceptance",
        "summary": "Run the Foundry CLI Gherkin acceptance suite (pytest tests/acceptance).",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/dev_commands.feature",
        "status": "implemented",
    },
    "dev.all": {
        "command": "dev all",
        "summary": "Run unit tests then acceptance tests.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/dev_commands.feature",
        "status": "implemented",
    },
    "cli.resolve": {
        "command": "cli resolve",
        "summary": (
            "Resolve foundry bundle paths (registry root, workspace, registry_source, "
            "foundry_config_path, and cli_path). Resolution order: --registry, "
            "FOUNDRY_REGISTRY, .foundry/foundry.yaml, workspace bundle walk."
        ),
        "status": "implemented",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/foundry_config.feature",
    },
    "run.create": {
        "command": "run create",
        "summary": "Create a new run, admit the flow entry visit, and run engine admission hooks.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/shape_intake.feature",
        "status": "implemented",
    },
    "visit.state.patch": {
        "command": "visit state patch",
        "summary": "Patch allowed run state fields on an opened visit.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/shape_intake.feature",
        "status": "implemented",
    },
    "visit.transition": {
        "command": "visit transition",
        "summary": "Request close on an opened visit; run on_close and on_seal hooks and route when sealed.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/shape_intake.feature",
        "status": "implemented",
    },
    "ledger.show": {
        "command": "ledger show",
        "summary": "Read ledger events from the run snapshot (read-only).",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/shape_intake.feature",
        "status": "implemented",
    },
    "artifact.publish": {
        "command": "artifact publish",
        "summary": "Validate and publish a declared artifact for the active visit.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/shape_intake.feature",
        "status": "implemented",
    },
    "receipt.seal": {
        "command": "receipt seal",
        "summary": "Validate a receipt draft, fill provenance, and append receipt.linked (capability receipt.link).",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/shape_intake.feature",
        "status": "implemented",
    },
    "gate.decide": {
        "command": "gate decide",
        "summary": (
            "Record the authorized decision on an opened user gate and request close. "
            "Appends gate.resolved, seals the visit, and routes by connection on.decisions."
        ),
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/shape_examine_gate.feature",
        "status": "implemented",
    },
    "app.discover": {
        "command": "app discover",
        "summary": (
            "Inspect the workspace repository and emit a proposed `.foundry/app.yaml` "
            "manifest draft without writing files. First step of `/craft-init`."
        ),
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/app_bootstrap.feature",
        "status": "implemented",
    },
    "app.init": {
        "command": "app init",
        "summary": (
            "Write `.foundry/app.yaml` from a validated manifest input file. "
            "Hard block on validation failure unless `--dry-run`."
        ),
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/app_bootstrap.feature",
        "status": "implemented",
    },
    "app.validate": {
        "command": "app validate",
        "summary": (
            "Validate `.foundry/app.yaml` against `app-manifest.schema.json`. "
            "Read-only probe used by the `validate-manifest` catalog check."
        ),
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/app_bootstrap.feature",
        "status": "implemented",
    },
    "config.validate": {
        "command": "config validate",
        "summary": (
            "Validate `.foundry/foundry.yaml` against `foundry-config.schema.json` "
            "and verify the registry path resolves to a bundle."
        ),
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/foundry_config.feature",
        "status": "implemented",
    },
    "config.init": {
        "command": "config init",
        "summary": (
            "Write `.foundry/foundry.yaml` with a registry pointer to the Foundry bundle. "
            "Defaults to probing `../foundry/.cursor/foundry` from the workspace."
        ),
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/foundry_config.feature",
        "status": "implemented",
    },
    "run.archive": {
        "command": "run archive",
        "summary": (
            "Move a workspace run into the Foundry repo `runs/` store with a sequential "
            "archive slug (`{app_id}-NNNN`), preserving the original engine run_id in "
            "`archive/manifest.json`. Optionally attach transcript and evaluation review."
        ),
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/run_archive.feature",
        "status": "implemented",
    },
    "shape": {
        "command": "shape",
        "summary": "Create a run from a shape request and advance into Shape (Phase 5 user CLI).",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/user_cli.feature",
        "status": "implemented",
    },
    "runs": {
        "command": "runs",
        "summary": "List workspace runs with status, active node, and wait kind.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/user_cli.feature",
        "status": "implemented",
    },
    "status": {
        "command": "status",
        "summary": "Show run snapshot summary; default run when exactly one active run.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/user_cli.feature",
        "status": "implemented",
    },
    "attach": {
        "command": "attach",
        "summary": "Stream ledger events for supervision; detach leaves the run running.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/user_cli.feature",
        "status": "implemented",
    },
    "answer": {
        "command": "answer",
        "summary": "Submit clarifying answers when wait.kind is user_input.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/user_cli.feature",
        "status": "implemented",
    },
    "decide": {
        "command": "decide",
        "summary": "Submit a user gate decision when wait.kind is decision.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/user_cli.feature",
        "status": "implemented",
    },
    "start": {
        "command": "start",
        "summary": (
            "Explicit Shape → Execute authorization at execute.start; records "
            "execute.authorization.recorded and advances into execute.intake."
        ),
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/user_cli.feature",
        "status": "implemented",
    },
    "retry": {
        "command": "retry",
        "summary": "Retry a halted, execution_error, paused, or operator-wait run.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/user_cli.feature",
        "status": "implemented",
    },
    "cancel": {
        "command": "cancel",
        "summary": "Halt a non-terminal run with a required --reason recorded in the ledger.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/user_cli.feature",
        "status": "implemented",
    },
    "host.start": {
        "command": "host start",
        "summary": "Start the background job host for this workspace.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/job_host.feature",
        "status": "implemented",
    },
    "host.status": {
        "command": "host status",
        "summary": "Report whether the job host is running.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/job_host.feature",
        "status": "implemented",
    },
    "host.stop": {
        "command": "host stop",
        "summary": "Stop the background job host.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/job_host.feature",
        "status": "implemented",
    },
    "host.run": {
        "command": "host run",
        "summary": "Run the job host in the foreground (tests).",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/job_host.feature",
        "status": "implemented",
    },
    "run.get": {
        "command": "run get",
        "summary": "Inspect run snapshot summary via host or disk.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/job_host.feature",
        "status": "implemented",
    },
    "run.list": {
        "command": "run list",
        "summary": "List workspace runs.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/job_host.feature",
        "status": "implemented",
    },
    "run.events": {
        "command": "run events",
        "summary": "Return ledger events after a sequence number.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/job_host.feature",
        "status": "implemented",
    },
    "run.advance": {
        "command": "run advance",
        "summary": "Bounded durable advancement until wait or step budget.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/job_host.feature",
        "status": "implemented",
    },
    "run.recover": {
        "command": "run recover",
        "summary": "Reload snapshot and advance (crash-safe resume).",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/job_host.feature",
        "status": "implemented",
    },
    "run.agent.submit": {
        "command": "run agent submit",
        "summary": "Submit a validated agent result for the active agent wait.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/shape_examine.feature",
        "status": "implemented",
    },
    "visit.intake.complete": {
        "command": "visit intake complete",
        "summary": "Complete shape intake with work prompt (engine hook).",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/shape_intake.feature",
        "status": "implemented",
    },
    "visit.examine.complete": {
        "command": "visit examine complete",
        "summary": "Seal agent receipt and transition after accepted examination judgment.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/shape_examine.feature",
        "status": "implemented",
    },
    "visit.present.complete": {
        "command": "visit present complete",
        "summary": "Publish presentation and transition after accepted presentation judgment.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/shape_present.feature",
        "status": "implemented",
    },
    "visit.record.complete": {
        "command": "visit record complete",
        "summary": "Publish plan and transition after accepted record judgment.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/shape_record.feature",
        "status": "implemented",
    },
    "visit.plan.complete": {
        "command": "visit plan complete",
        "summary": "Publish execution graph and brief after accepted plan judgment.",
        "acceptance": ".cursor/foundry/cli/tests/acceptance/features/execute_plan.feature",
        "status": "implemented",
    },
}


@dataclass(frozen=True)
class CommandSpec:
    """One leaf CLI subcommand discovered from argparse."""

    parts: tuple[str, ...]
    prog: str
    help: str
    arguments: tuple[dict[str, str], ...] = field(default_factory=tuple)

    @property
    def capability_id(self) -> str:
        return ".".join(self.parts)

    @property
    def slug(self) -> str:
        return "-".join(self.parts)


def capability_id_for_parts(parts: tuple[str, ...]) -> str:
    return ".".join(parts)


def _format_args(
    action: argparse.Action,
    *,
    skip_dests: frozenset[str],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    option_strings = action.option_strings or [action.dest]
    flags = ", ".join(f"`{opt}`" for opt in option_strings if opt != action.dest)
    if not flags and action.dest not in skip_dests:
        flags = f"`{action.dest}`"
    required = "yes" if action.required else "no"
    default = action.default
    if default is None or default == argparse.SUPPRESS:
        default_text = "—"
    elif isinstance(default, bool):
        default_text = str(default).lower()
    else:
        default_text = str(default)
    rows.append(
        {
            "flags": flags or "—",
            "required": required,
            "default": default_text,
            "help": str(action.help or "").replace("|", "\\|"),
        }
    )
    return rows


def _subparser_choice_help(action: argparse._SubParsersAction, name: str) -> str:
    for choice_action in getattr(action, "_choices_actions", []) or []:
        if getattr(choice_action, "dest", None) == name:
            return str(getattr(choice_action, "help", "") or "")
    return ""


def _collect_leaf_commands(
    parser: argparse.ArgumentParser,
    prefix: tuple[str, ...] = (),
    *,
    choice_help: str = "",
    skip_dests: frozenset[str] | None = None,
) -> Iterator[CommandSpec]:
    resolved_skip_dests = skip_dests if skip_dests is not None else collect_subparser_dests(parser)
    subparsers_actions = [
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    ]
    if not subparsers_actions:
        arguments: list[dict[str, str]] = []
        for action in parser._actions:
            if action.dest in resolved_skip_dests:
                continue
            if isinstance(action, argparse._SubParsersAction):
                continue
            if action.option_strings == ["-h", "--help"]:
                continue
            arguments.extend(_format_args(action, skip_dests=resolved_skip_dests))
        description = str(parser.description or choice_help or "")
        yield CommandSpec(
            parts=prefix,
            prog=parser.prog,
            help=description,
            arguments=tuple(arguments),
        )
        return

    for action in subparsers_actions:
        for name, subparser in sorted(action.choices.items()):
            help_text = _subparser_choice_help(action, name)
            yield from _collect_leaf_commands(
                subparser,
                prefix + (name,),
                choice_help=help_text,
                skip_dests=resolved_skip_dests,
            )


def collect_command_specs(parser: argparse.ArgumentParser) -> list[CommandSpec]:
    skip_dests = collect_subparser_dests(parser)
    specs: list[CommandSpec] = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, subparser in sorted(action.choices.items()):
                specs.extend(
                    _collect_leaf_commands(subparser, (name,), skip_dests=skip_dests)
                )
    return specs


def _global_flags_table(parser: argparse.ArgumentParser) -> str:
    skip_dests = collect_subparser_dests(parser)
    rows = ["| Flag | Required | Default | Description |", "|---|:---:|:---:|---|"]
    for action in parser._actions:
        if not action.option_strings or action.option_strings == ["-h", "--help"]:
            continue
        if action.dest in skip_dests:
            continue
        for row in _format_args(action, skip_dests=skip_dests):
            rows.append(
                f"| {row['flags']} | {row['required']} | {row['default']} | {row['help'] or '—'} |"
            )
    return "\n".join(rows) + "\n"


def _command_flags_table(spec: CommandSpec) -> str:
    if not spec.arguments:
        return "_No command-specific flags._\n"
    rows = ["| Flag | Required | Default | Description |", "|---|:---:|:---:|---|"]
    for row in spec.arguments:
        rows.append(
            f"| {row['flags']} | {row['required']} | {row['default']} | {row['help'] or '—'} |"
        )
    return "\n".join(rows) + "\n"


def _capability_meta(capability_id: str) -> dict[str, Any]:
    return CLI_CAPABILITIES.get(capability_id, {})


def build_cli_command_doc(
    spec: CommandSpec,
    *,
    repo_root: Path,
    from_file: Path,
    root_parser: argparse.ArgumentParser,
) -> str:
    meta = _capability_meta(spec.capability_id)
    command = meta.get("command") or " ".join(spec.parts)
    summary = meta.get("summary") or spec.help or "—"
    status = meta.get("status", "implemented")

    lines = [
        f"# `{command}`",
        "",
        f"Status: **{status}**",
        "",
        summary,
        "",
        "## Invocation",
        "",
        "```bash",
        f"foundry {command} [flags]",
        "```",
        "",
        "Global flags (`--workspace`, `--registry`, `--json`) are documented in "
        f"{rel_link(from_file, from_file.parent / 'index.md', 'cli/index.md')}.",
        "",
        "## Command flags",
        "",
        _command_flags_table(spec),
    ]

    for section in meta.get("extra_sections") or []:
        title = section.get("title")
        body = section.get("body")
        if title and body:
            lines.extend(["", f"## {title}", "", str(body).strip(), ""])

    schema_ref = meta.get("schema")
    if schema_ref:
        schema_path = repo_root / ".cursor" / "foundry" / str(schema_ref).removeprefix("registry:")
        if schema_path.is_file():
            lines.extend(
                [
                    "## Schema",
                    "",
                    rel_link(from_file, schema_path, str(schema_ref)),
                    "",
                ]
            )

    acceptance = meta.get("acceptance")
    if acceptance:
        acceptance_path = repo_root / acceptance
        if acceptance_path.is_file():
            lines.extend(
                [
                    "## Acceptance",
                    "",
                    rel_link(from_file, acceptance_path, acceptance_path.name),
                    "",
                ]
            )

    impl = meta.get("implementation")
    if impl:
        impl_path = repo_root / impl
        if impl_path.is_file():
            lines.extend(
                [
                    "## Implementation",
                    "",
                    rel_link(from_file, impl_path, impl),
                    "",
                ]
            )
    else:
        default_impl = repo_root / ".cursor" / "foundry" / "cli" / "foundry.py"
        if default_impl.is_file():
            lines.extend(
                [
                    "## Implementation",
                    "",
                    rel_link(from_file, default_impl, ".cursor/foundry/cli/foundry.py"),
                    "",
                ]
            )

    return "\n".join(lines)


def build_cli_index(
    specs: list[CommandSpec],
    *,
    repo_root: Path,
    output_dir: Path,
    root_parser: argparse.ArgumentParser,
) -> str:
    from_file = output_dir / "cli" / "index.md"
    cli_entry = repo_root / ".cursor" / "foundry" / "cli" / "foundry.py"
    lines = [
        "# Foundry CLI reference",
        "",
        "Generated from `foundry doc build` / `foundry dev docs`. "
        "Mechanical flags come from argparse; summaries and links are annotated in "
        "`foundry_cli/cli_docgen.py`.",
        "",
        f"Entry point: {rel_link(from_file, cli_entry, 'foundry.py')}",
        "",
        "## Global flags",
        "",
        _global_flags_table(root_parser),
        "",
        "## Commands",
        "",
        "| Capability | Command | Status | Reference |",
        "|---|---|---|---|",
    ]
    for spec in sorted(specs, key=lambda item: item.capability_id):
        meta = _capability_meta(spec.capability_id)
        command = meta.get("command") or " ".join(spec.parts)
        status = meta.get("status", "implemented")
        doc_path = output_dir / "cli" / f"{spec.slug}.md"
        lines.append(
            f"| `{spec.capability_id}` | `{command}` | {status} | "
            f"{rel_link(from_file, doc_path, spec.slug)} |"
        )
    concepts_index = repo_root / "docs" / "concepts" / "README.md"
    engine_doc = repo_root / "docs" / "concepts" / "engine.md"
    run_record_doc = repo_root / "docs" / "concepts" / "run-record.md"
    capabilities_doc = repo_root / "docs" / "concepts" / "capabilities.md"
    lines.extend(
        [
            "",
            "## See also",
            "",
            f"- {rel_link(from_file, concepts_index, 'Workflow concepts index')}",
            f"- {rel_link(from_file, engine_doc, 'Engine procedure')}",
            f"- {rel_link(from_file, run_record_doc, 'Ledger and run persistence')}",
            f"- {rel_link(from_file, capabilities_doc, 'Reads and allow (steward capabilities)')}",
            "",
        ]
    )
    return "\n".join(lines)


def write_cli_docs(
    *,
    parser: argparse.ArgumentParser,
    repo_root: Path,
    output_dir: Path,
) -> list[Path]:
    output_dir = output_dir.resolve()
    cli_dir = output_dir / "cli"
    cli_dir.mkdir(parents=True, exist_ok=True)

    specs = collect_command_specs(parser)
    written: list[Path] = []

    index_doc = build_cli_index(
        specs,
        repo_root=repo_root,
        output_dir=output_dir,
        root_parser=parser,
    )
    index_path = cli_dir / "index.md"
    index_path.write_text(index_doc, encoding="utf-8")
    written.append(index_path)

    for spec in specs:
        doc = build_cli_command_doc(
            spec,
            repo_root=repo_root,
            from_file=cli_dir / f"{spec.slug}.md",
            root_parser=parser,
        )
        path = cli_dir / f"{spec.slug}.md"
        path.write_text(doc, encoding="utf-8")
        written.append(path)

    return written
