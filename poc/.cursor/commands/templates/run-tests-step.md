# Run Tests

Discover and run all test projects in the solution.

---

## Find All Test Projects

List projects in the solution (`dotnet sln list` or `*.csproj` under `*.Tests` / `*.UnitTests` / `*.IntegrationTests` / `*.E2E.Tests`).

---

## Run All Tests

Run the suite via the factory CLI using the immutable run snapshot:

```text
python "{factory_root}/.cursor/foundry/cli/foundry.py" test --state "{state_path}"
```

Use the JSON `exitCode`, `command`, and `outputTail`. Do not invent a
`dotnet test` argv when the snapshot omits the command; stop and report the
manifest contract error.

---

## Handle Test Results

### If Tests Fail

1. Identify the failing test(s)
2. Display the error message and stack trace
3. Work with the developer to fix the issue
4. Re-run tests until all pass

**Common failure patterns:**
- Missing mock setup
- Incorrect expected values
- Database connection issues
- Missing configuration

### If Tests Pass

> "✅ All tests passed. Ready to proceed with documentation updates."

---

## Test Output Interpretation

| Exit Code | Meaning |
|-----------|---------|
| 0 | All tests passed |
| 1 | One or more tests failed |
| Other | Build or configuration error |

---

## Proceed to Update Docs

After all tests pass, proceed to Update Docs to update documentation.

