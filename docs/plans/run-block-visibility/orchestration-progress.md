# Orchestration progress — run-block-visibility

Status: **complete**

| Package | Implement | Verify | Notes |
|---------|-----------|--------|-------|
| P1 | completed | pass | `parked_run.py` + unit tests |
| P2 | completed | pass | status + `run.get` `parked` |
| P3 | completed | pass | history parked section; 1 repair |
| P4 | completed | pass | agent Needs **—** |
| P5 | completed | pass | TUI `#action-panel`; 2 test repairs |

## Package P1

### Implementer

- Added `build_parked_run_projection` in `.cursor/foundry/cli/foundry_cli/parked_run.py`
- Unit tests: `.cursor/foundry/cli/tests/unit/test_parked_run_projection.py` (11 cases)

### Verifier

- **Verdict:** pass
- Orchestrator pytest: 11 passed

## Package P2

### Implementer

- `get_run` + bundle → `parked`; host/local status paths; `_format_status` parked block
- Tests: `test_status_parked.py`

### Verifier

- **Verdict:** pass
- Orchestrator pytest: `test_status_parked.py` + `test_rel005_loop_history.py` — 10 passed

## Package P3

### Implementer

- `operator_history.py` parked section; dynamic heading in renderer
- Repair: halt fixture in `test_operator_history.py`

### Verifier

- **Verdict:** pass (after repair)
- Orchestrator pytest: 7 passed

## Package P4

### Implementer

- `run_labels.py`: `agent` → **—**; three `test_tui.py` updates

### Verifier

- **Verdict:** pass
- Orchestrator pytest: 3 label tests passed

## Package P5

### Implementer

- Removed `#wait-panel`; `#action-panel` after history; `HostClient.retry`
- Repairs: expanded `test_tui.py` for verifier brief (retry, verify intake, history text, `execution_error` index, `a` binding)

### Verifier

- **Verdict:** pass (after test repairs)
- Orchestrator pytest: 62 passed across `test_tui`, `test_parked_run_projection`, `test_status_parked`, `test_operator_history`
