# CLI test suite — measure-first speed plan

Status: **proposed** (2026-10-07).  
**Audience:** implementers improving local iteration and CI wall clock for [`.cursor/foundry/cli`](../../.cursor/foundry/cli).  
**Parent context:** ~530 pytest cases (`tests/unit` + Gherkin `tests/acceptance`); default developer entrypoints `foundry dev unit`, `foundry dev acceptance`, `foundry dev all` ([`foundry_cli/dev.py`](../../.cursor/foundry/cli/foundry_cli/dev.py)).

**Principle:** Do not optimize blindly. Establish a **baseline**, rank **hot spots** with evidence, then ship changes in **small slices** with before/after timings recorded in this doc (§Metrics log).

---

## A. Problem statement

| Pain | Cause (hypothesis — confirm in Phase 0) |
| --- | --- |
| Slow `dev all` | Sequential unit then acceptance; each leg spawns a **new** `python -m pytest` subprocess with captured stdout/stderr |
| Slow unit collection | Root [`tests/conftest.py`](../../.cursor/foundry/cli/tests/conftest.py) registers **all** acceptance `pytest_plugins` step modules even when running `tests/unit` only |
| Slow integration unit tests | Per-test `tmp_path` workspaces, `git` subprocesses, `shutil.copytree(FOUNDRY_ROOT)`, repeated `load_registry` |
| Slow acceptance | One `foundry.py` subprocess per step via [`invoke_foundry`](../../.cursor/foundry/cli/tests/acceptance/helpers.py); multi-step advance chains; job host readiness polling |
| Slow catalog tests / `catalog build` | Full-flow `build_catalog` scans every `.feature` file per node ([`collect_node_tests`](../../.cursor/foundry/cli/foundry_cli/catalog.py)) |

**Non-goals for this plan:**

- Replacing pytest or pytest-bdd
- Removing subprocess-based acceptance tests (they are the contract for the CLI surface)
- Parallelizing acceptance against `workspace is the repository root` scenarios without isolation design
- Speeding up tests by weakening assertions or deleting scenario coverage without an explicit tradeoff note

---

## B. Phase 0 — Measure (required before implementation)

### B.1 Baseline commands

Run from `.cursor/foundry/cli` with the project venv. Record machine/OS and git SHA in §Metrics log.

```bash
# Collection cost (imports only)
.venv/bin/python -m pytest --collect-only -q

# Unit — wall clock + slowest tests
.venv/bin/python -m pytest tests/unit -q --durations=25

# Acceptance (default dev filter)
.venv/bin/python -m pytest tests/acceptance -q -k "not dev_commands" --durations=25

# Optional: repeat unit with import profiling
.venv/bin/python -X importtime -m pytest tests/unit --collect-only -q 2> /tmp/pytest-importtime.txt
```

Also capture `foundry dev unit` and `foundry dev acceptance` wall clock (includes extra Python startup vs raw pytest).

### B.2 Classify each top-N slow test

For every item in `--durations=25`, assign **one primary bucket**:

| Bucket | Signals | Example areas |
| --- | --- | --- |
| **SUBPROCESS_CLI** | `subprocess`, `invoke_foundry`, `foundry.py` in stack | Acceptance features, `test_user_cli_*`, `implementation_flow_helpers.invoke_foundry_cli` |
| **GIT** | `git init`, `git commit`, hook validators | `git_workspace.py`, `test_hooks.py`, execute commit boundary |
| **HOST** | `foundry_cli.host`, `Popen`, sleep poll | `job_host.feature`, `test_host_integration.py` |
| **IO_COPY** | `copytree(FOUNDRY_ROOT)` | `test_registry_refs.py`, `test_catalog.py` |
| **REGISTRY_PARSE** | `load_registry`, `build_catalog`, `build_node_index` | `flow` fixture users, catalog unit tests |
| **FEATURE_SCAN** | `collect_node_tests`, glob `*.feature` | Full `build_catalog` |
| **ENGINE_INPROC** | `advance_run`, executors without CLI | Many `test_*_complete.py` — usually fast; note if slow |

Export a short table: `test_id | duration_s | bucket | notes`.

### B.3 Acceptance vs unit share

Compute:

- `T_unit`, `T_acceptance`, `T_all ≈ T_unit + T_acceptance` (sequential `dev all`)
- `% time in top 5 tests` and `% time in top bucket`

**Exit criterion for Phase 0:** §Metrics log has one baseline row and a ranked hotspot table (minimum 15 rows or all tests &gt; 0.5s).

---

## C. Phase 1 — Design from hot spots

Use Phase 0 buckets to pick **slices** below. Implement only slices whose bucket appears in the top 40% of measured time **or** whose fix is trivial with low risk.

### C.1 Slice priority matrix (default order)

| Slice | Targets bucket | Risk | Expected win |
| --- | --- | --- | --- |
| **S1** Import hygiene | Collection / REGISTRY_PARSE (import side) | Low | Faster `tests/unit` collection |
| **S2** Unit parallelism | All unit buckets | Medium | Near-linear wall clock on multi-core |
| **S3** Session registry fixture | REGISTRY_PARSE | Low–medium | Many tests share one `load_registry` |
| **S4** Lighter bundle copies | IO_COPY | Low | Faster catalog/registry unit tests |
| **S5** Catalog feature index cache | FEATURE_SCAN | Low | Faster `build_catalog` + catalog unit tests |
| **S6** `dev` runner ergonomics | SUBPROCESS_CLI (wrapper only) | Low | Faster feedback loops; optional in-proc unit pytest |
| **S7** Acceptance CI sharding | SUBPROCESS_CLI | Medium | CI parallelism without shared repo_root races |
| **S8** Host test fixture | HOST | Medium | Fewer process spawns / shorter polls |
| **S9** Coverage dedup review | SUBPROCESS_CLI + maintenance | High (product) | Fewer redundant scenarios — **only** after metrics show duplicate cost |

Re-order slices after Phase 0 if a different bucket dominates.

---

## D. Phase 2 — Implementation slices (spec)

### S1 — Move acceptance `pytest_plugins` to acceptance conftest

**Today:** [`tests/conftest.py`](../../.cursor/foundry/cli/tests/conftest.py) lists all BDD step modules in `pytest_plugins`.

**Change:**

- Keep env defaults (`FOUNDRY_ALLOW_STUB_ADAPTER`, etc.) in root `tests/conftest.py`.
- Move `pytest_plugins = [...]` to [`tests/acceptance/conftest.py`](../../.cursor/foundry/cli/tests/acceptance/conftest.py).
- Update [acceptance README](../../.cursor/foundry/cli/tests/acceptance/README.md) registration note.

**Verify:** `pytest tests/unit --collect-only` no longer imports `tests.acceptance.steps.*`; acceptance suite still collects all scenarios.

**Metrics:** Compare `pytest tests/unit --collect-only` time before/after.

---

### S2 — `pytest-xdist` for unit tests

**Change:**

- Add `pytest-xdist` to [`.cursor/foundry/cli/requirements.txt`](../../.cursor/foundry/cli/requirements.txt).
- Extend `foundry dev unit` with optional parallelism, e.g. `--parallel` or pass-through `pytest_args` documented as:
  - `foundry dev unit -- -n auto`
- Document in [docs/cli/dev-unit.md](../cli/dev-unit.md) and [dev-all.md](../cli/dev-all.md).
- CI (when present): run unit with `-n auto` on multi-core runners.

**Guardrails:**

- Do **not** enable `-n` for acceptance by default.
- If a test flakes under xdist, fix isolation or mark `serial` (xdist group) — do not disable xdist globally.

**Metrics:** `T_unit` before/after on same machine.

---

### S3 — Session-scoped `bundle` / `flow` fixtures

**Change:** In [`tests/unit/conftest.py`](../../.cursor/foundry/cli/tests/unit/conftest.py), add session-scoped fixtures (e.g. `session_bundle`, `session_flow`) used by tests that only **read** registry data.

**Guardrails:**

- Tests that mutate bundle files on disk must keep `tmp_path` bundles.
- Document in [unit README](../../.cursor/foundry/cli/tests/unit/README.md).

**Metrics:** Re-run `--durations` on registry-heavy modules (`test_engine_gates.py`, `test_advance.py`, context `*_context.py`).

---

### S4 — Prefer minimal bundle stubs over full `copytree`

**Change:**

- Audit `shutil.copytree(FOUNDRY_ROOT, ...)` in unit tests; switch to [`bundle_with_step_stubs`](../../.cursor/foundry/cli/tests/unit/registry_test_helpers.py) where the test does not need the full nodes tree.
- Leave full copy only for tests that assert real instruction paths across the implementation flow.

**Metrics:** Time for `test_catalog.py` + `test_registry_refs.py` modules.

---

### S5 — Cache `collect_node_tests` in catalog build

**Change:** In [`foundry_cli/catalog.py`](../../.cursor/foundry/cli/foundry_cli/catalog.py):

- One pass over `feature_dir/*.feature` → map `node_id` → list of feature paths (tags + conservative text match, same semantics as today).
- `build_node_index` reads from the map instead of re-reading every feature per node.

**Tests:** Existing `test_catalog.py` and acceptance `catalog_build.feature` must pass unchanged.

**Metrics:** Time for `test_build_catalog_writes_index_files` and full `build_catalog` CLI acceptance scenarios.

---

### S6 — Developer command ergonomics

**Changes (pick based on Phase 0 wrapper overhead):**

| Item | Description |
| --- | --- |
| **Quiet CI profile** | Document `foundry dev unit --quiet` / `pytest -q --tb=line` for CI |
| **In-process unit pytest** | Optional `run_pytest` path using `pytest.main()` for `dev unit` only, retaining `FOUNDRY_DEV_PYTEST_ACTIVE` guard in [`dev.py`](../../.cursor/foundry/cli/foundry_cli/dev.py) |
| **Targeted recipes** | Add a short table to unit/acceptance README: node tag → `-m node.<id>`, module → file path |

**Metrics:** Compare `foundry dev unit` vs raw `pytest tests/unit -q` startup delta.

---

### S7 — Acceptance CI sharding (optional, after S2–S5)

**Design:**

- Shard by pytest marker (`node.*`, `foundry.*`, `cli.user`) or by feature file list.
- Each job uses **temporary workspaces** for scenarios that today use `repo_root`; keep one job for `workspace is the repository root` if needed.

**Deliverable:** Document shard commands in this plan’s §Metrics log appendix; no requirement to change default local `dev acceptance` until stable.

---

### S8 — Job host test efficiency (if HOST bucket is hot)

**Candidates:**

- Session-scoped host for `job_host.feature` + `run_storage.feature` only, with strict teardown.
- Reduce readiness poll interval / max wait if flakiness allows (measure in Phase 0).

**Guardrails:** Do not share host across tests that stop/start host in steps.

---

### S9 — Redundant coverage review (optional, explicit tradeoff)

If `run_context.feature` and `test_*_context.py` dominate duration with overlapping assertions:

- Produce a **coverage overlap matrix** (scenario ↔ unit module).
- Propose demotions (e.g. unit-only goldens for markdown, acceptance for CLI envelope only) in a follow-up PR — not silent deletion.

---

## E. Phase 3 — Validation and regression guards

After each slice:

1. `foundry dev unit` and `foundry dev acceptance` (default `-k "not dev_commands"`) pass.
2. Record before/after timings in §Metrics log.
3. If S2 landed: run unit twice — single-process and `-n auto` — on CI or locally before merge.

**Evidence gates** (align with [implementation-flow-runtime.md](../features/implementation-flow-runtime.md)):

- No change to scenario semantics without updating the matching `.feature` or documented intentional dedup (S9).
- Catalog/doc contract changes require `catalog build` / `doc build` only when S5 touches catalog semantics (S5 should not).

---

## F. Metrics log (fill during execution)

| Date | Git SHA | Machine | T_collect | T_unit | T_acceptance | T_dev_unit | T_dev_acceptance | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-07 | _baseline_ | _TBD_ | ~0.16s collect / 530 tests | _run Phase 0_ | _run Phase 0_ | _run Phase 0_ | _run Phase 0_ | Plan created; no optimizations landed yet |

### Hot spot table (template)

| Rank | Test / module | Duration (s) | Bucket | Slice |
| --- | --- | --- | --- | --- |
| 1 | | | | |
| 2 | | | | |

---

## G. Deliverables checklist

- [ ] Phase 0 baseline captured in §F
- [ ] S1 — `pytest_plugins` scoped to acceptance
- [ ] S2 — xdist + documented `dev unit` parallel invocation
- [ ] S3 — session registry fixtures (where safe)
- [ ] S4 — reduced full-bundle `copytree` in unit tests
- [ ] S5 — catalog feature index cache
- [ ] S6 — dev command / README targeting docs
- [ ] S7 — CI shard design (optional)
- [ ] S8 — host fixture tuning (optional, metrics-driven)
- [ ] [README.md](README.md) index row for this plan

---

## H. References

| Resource | Role |
| --- | --- |
| [tests/unit/README.md](../../.cursor/foundry/cli/tests/unit/README.md) | Unit layout and naming |
| [tests/acceptance/README.md](../../.cursor/foundry/cli/tests/acceptance/README.md) | Gherkin contracts and tags |
| [pytest.ini](../../.cursor/foundry/cli/pytest.ini) | Markers for sharding (`node.*`, `foundry.*`) |
| [implementation-flow-runtime.md](../features/implementation-flow-runtime.md) | T1–T10 scenario map — do not speed up by dropping evidence scenarios |
