# Orchestration progress — cli-operator-ux

Status: **complete**

| Package | Implement | Verify | Notes |
|---------|-----------|--------|-------|
| P1 | completed | pass | Verdict-first `up`, `--verbose`, porcelain tests |
| P2 | completed | pass | `cmd_down`, idempotent stop host+bridge |
| P3 | completed | pass | help_catalog + curriculum root `-h` |
| P4 | completed | pass | `foundry help`, `-a`, `<cmd>` |
| P5 | completed | pass | `up` → host `auto_advance` wiring |
| P6 | completed | pass | intake-only shape + handoff output |
| P7 | completed | pass | `INTAKE_BLOCKED`, `INPUT_REQUIRED`, `--prompt` |
| P8 | completed | pass | `shape --attach` + shared stream |
| P9 | completed | pass | runbook + docgen from help_catalog |

## Package P1

### Implementer

- **Status:** completed
- **Files:** `readiness/formatting.py` (new), `foundry.py`, `parser.py` (`-v`/`--verbose` on `up`), `tests/unit/test_foundry_up_porcelain.py` (new)
- **Summary:** Verdict-first human `up` (“Foundry is ready” / not ready), `Next:` line, compact bridge/PID detail; dimension `ok=` lines only with `--verbose`. Not-ready human routed via porcelain formatter. `cmd_up` JSON unchanged.

### Verifier

- **Verdict:** pass
- **Checks:** Code inspection against AC 1–6 / D5; scope limited to P1 touchpoints; `up_commands.py` JSON path unchanged.
- **Orchestrator regression:** `pytest tests/unit/test_foundry_up*.py` + `test_foundry_up_porcelain.py` — **11 passed**.

## Package P2

### Implementer

- **Status:** completed
- **Files:** `up_commands.py` (`cmd_down`), `parser.py`, `foundry.py` (dispatch + `_format_down`), `readiness/formatting.py` (`format_down_human`), `tests/unit/test_foundry_down.py` (new, 6 tests)
- **Summary:** Top-level `foundry down` stops workspace host then judgment bridge; idempotent when already stopped; human + JSON `ok: true` envelopes.

### Verifier

- **Verdict:** pass
- **Checks:** Stop order, idempotency, parser/registry wiring, foreground `up` Ctrl+C path unchanged.
- **Orchestrator regression:** `pytest test_foundry_down.py test_foundry_up.py` — **8 passed**.

## Package P3

### Implementer

- **Status:** completed
- **Files:** `help_catalog.py` (new), `parser.py` (`_FoundryArgumentParser`, `required=False` subparsers), `test_foundry_root_help.py`, golden `fixtures/foundry_root_help.txt`
- **Summary:** Journey-section curriculum on bare `foundry` / `foundry -h`; listed commands only; subcommand `-h` unchanged; metadata ready for P4.

### Verifier

- **Verdict:** pass
- **Checks:** Sections match spec table; `host`/`run`/`tui` absent from root help; dispatch registration preserved; no P4 `help` command yet.
- **Orchestrator regression:** `pytest test_foundry_root_help.py test_parser.py` — **15 passed**.

## Package P4

### Implementer

- **Status:** completed
- **Files:** `help_commands.py` (`cmd_help`), `help_catalog.py` (`format_all_commands_help`, etc.), `parser.py`, `foundry.py`, `test_foundry_help_command.py`
- **Summary:** `foundry help` matches curated `-h`; `help -a` lists all top-level commands; `help <cmd>` delegates to subparser help; `help` is unlisted in default curriculum.

### Verifier

- **Verdict:** pass
- **Checks:** AC 11–12 delegation; flat parser (no nested help subcommands); P3 root help unchanged.
- **Orchestrator regression:** `pytest test_foundry_help_command.py test_foundry_root_help.py` — **11 passed**.

## Package P5

### Implementer

- **Status:** completed
- **Files:** `up_commands.py` (`configure_host_start_for_up` call), `host_commands.py` (discovery state fallback for `auto_advance`), `test_foundry_up_auto_advance.py` (3 tests)
- **Summary:** `foundry up` starts host with `auto_advance=True` (2.0s interval); `host status` can surface `host.auto_advance` from discovery state.

### Verifier

- **Verdict:** pass (wiring); e2e shape→examine without `run advance` deferred to **P6**
- **Checks:** Helper + `cmd_up`→`cmd_host_start` args; no engine eligibility changes.
- **Orchestrator regression:** `pytest test_foundry_up_auto_advance.py` + up/host regressions — **6 passed**.

## Package P6

### Implementer

- **Status:** completed
- **Files:** `user_cli.py` (`cmd_shape`, `stop_after_advance_reason=intake_complete`), `advance.py`, `run_service.py`, `host/handlers.py`, `foundry.py` (`_format_shape`), `test_user_cli_shape.py` (rewritten intake scenario)
- **Summary:** Shape seals intake and exits; human ack + `run=` + attach/status hints; JSON `intake_status`, `intake_complete`, hint fields. No block through `shape.present.gate`.

### Verifier

- **Verdict:** pass (orchestrator confirmed tests; verifier static review **blocked** on pytest in Ask mode)
- **Checks:** Intake stop wired host + local; no P8 `--attach`; answer/decide paths preserved.
- **Orchestrator regression:** `pytest test_user_cli_shape.py test_shape_input_verbatim.py` + advance intake test — **9 passed**.
- **Note:** First scenario uses `--input` not `--input-file` (same resolver); AC 17 e2e still relies on P5 + future smoke updates.

## Package P7

### Implementer

- **Status:** completed
- **Files:** `user_cli.py` (`_shape_intake_blocked_error`, input validation), `parser.py` (`--prompt` alias), `test_user_cli_shape_intake_validation.py` (new)
- **Summary:** Empty input → `INPUT_REQUIRED` non-zero; blocked intake → `INTAKE_BLOCKED` + `block_reason` in JSON; happy path unchanged.

### Verifier

- **Verdict:** pass
- **Checks:** Subprocess tests for empty input; mocked blocked intake; P6 happy path preserved; no P8 scope.
- **Orchestrator regression:** `pytest test_user_cli_shape_intake_validation.py test_user_cli_shape.py` — **10 passed**.

## Package P8

### Implementer

- **Status:** completed
- **Files:** `parser.py` (`--attach`), `user_cli.py` (`stream_run_attach`, `cmd_shape`/`cmd_attach`), `foundry.py` (handoff then stream), `test_shape_attach.py` (new)
- **Summary:** Same intake lines as default `shape`, then attach-style streaming; human question lines on `user_input`; detach does not cancel run.

### Verifier

- **Verdict:** pass
- **Checks:** Shared stream with standalone `attach` (default `human_questions=False`); AC 21–24 coverage in tests.
- **Orchestrator regression:** `pytest test_shape_attach.py test_user_cli_shape.py` — **11 passed, 2 skipped** (win32 subprocess detach).

## Package P9

### Implementer

- **Status:** completed
- **Files:** `docs/operator-runbook.md`, `cli_docgen.py`, `test_cli_docgen.py`, regenerated `docs/cli/*` (incl. `down.md`, `help.md`, curriculum in `index.md`)
- **Summary:** Runbook documents `down`, help curriculum, shape intake/`--attach`; docgen uses `help_catalog.LISTED_HELP_SECTIONS`.

### Verifier

- **Verdict:** pass
- **Checks:** Runbook sections present; docgen imports catalog; generated pages align with porcelain.
- **Orchestrator regression:** `pytest test_cli_docgen.py` — **5 passed**.
- **Note:** Curriculum table shape one-liner may still mirror argparse (“advance into Shape”) vs intake-only copy on `shape.md` — optional follow-up.
