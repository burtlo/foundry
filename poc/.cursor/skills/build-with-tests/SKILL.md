---
name: build-with-tests
description: >-
  Implements a scoped feature with tests using project AGENTS.md conventions.
  Loads team variables via factory-bootstrap when run standalone; accepts
  FactoryConfig from Foundry builders when nested. Runs when
  backend-builder, client-builder, or feature-builder runs, or when the user
  asks to build, implement, or ship with tests.
disable-model-invocation: true
---

# Build with tests

## Variables contract (always first)

1. **FactoryConfig** — when the launch prompt includes FactoryConfig from a parent (`build-with-tests`, `backend-builder`, `client-builder`, or `feature-builder`), use it. Template paths are already resolved.
2. **Standalone** — when FactoryConfig is **not** provided, read and follow **[factory-bootstrap](../factory-bootstrap/SKILL.md)** with `{bootstrap_role}` = **`build-with-tests`**.
3. Work only under **`{app_folder}`** from FactoryConfig.
4. Read the **technical brief** and **ticket packet** (if provided)—stay in scope.

---

## Implementation phase (code only)

**If** `templates.implement` exists and the file is on disk, read and obey that path from FactoryConfig.

**Else** follow these generic rules:

- Review the AGENTS.md headings the parent listed before editing (Policy, Key Patterns, Authentication/Security, Data Contracts).
- Make focused changes; explain decisions when non-obvious.
- Run the project **build** via the factory CLI (do not invent `dotnet build` or scrape AGENTS.md for argv):

```text
python "{factory_root}/.cursor/foundry/cli/foundry.py" build --state "{state_path}"
```

- Do **not** run the full test suite in this phase unless the snapshot defines a
  single combined command.

## Test phase

**If** `templates.add_tests` and `templates.run_tests` exist, read and obey those files in order.

**Else**:

- Add or update tests matching existing project layout.
- Name every test **`Subject_Scenario_ExpectedOutcome`**; read sibling tests in the target project first.
- Prefer **one assertion per test** when verifying independent facts (see `add-tests-step.md` when available).
- Run tests via:

```text
python "{factory_root}/.cursor/foundry/cli/foundry.py" test --state "{state_path}"
```

- Report pass/fail from the CLI JSON (`success`, `exitCode`, `outputTail`).

## Finish

1. Re-run `foundry.py build` if code changed after tests.
2. Return a short summary:
   - Files changed
   - Patterns reused from the codebase
   - Build/test command results (from CLI JSON)
   - Acceptance criteria addressed (reference ticket packet or brief)
   - Suggested `AGENTS.md` rule additions (if any)

## Rules

- Do not refactor unrelated code.
- Do not add dependencies without explicit instruction in the brief.
- Do not edit files outside agreed scope.
- **Do not** update `AGENTS.md` or generate PRD here—the parent runs documentation after the critic cycle (`implement.documentation` / `documentation-workflow`).
- If tests fail and the brief forbids breaking a rule, stop and report the conflict.
