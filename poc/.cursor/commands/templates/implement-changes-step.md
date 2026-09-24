# Implement the Code Changes

Work with the developer to implement the required changes.

---

## Important Guidelines

**This step is for CODE CHANGES ONLY.**

| Action | Allowed |
|--------|---------|
| Make code changes | ✅ DO |
| Build the solution to verify it compiles | ✅ DO |
| Run tests | ❌ DO NOT (handled in Add Tests and Run Tests steps) |
| Update documentation | ❌ DO NOT (that's Update Docs step) |
| Generate PRD | ❌ DO NOT (that's Generate PRD step) |

---

## Before Making Changes

1. **Review the relevant AGENTS.md files** for the projects being modified
2. **Follow documented patterns and conventions**
3. **Respect layer boundaries and architectural rules**

---

## Throughout Implementation

- Explain each change being made
- Ask for developer input on design decisions
- Keep changes focused on the ticket requirements
- Reference the acceptance criteria to ensure all requirements are addressed

---

## Verify the Build

After making changes, verify the build:

```text
python "{factory_root}/.cursor/foundry/cli/foundry.py" build --state "{state_path}"
```

Do not invent `dotnet build`. The CLI executes the command frozen in the run
snapshot. Do **not** run tests in this step.

---

## Verify Ready to Proceed

**After implementation is complete and the build succeeds, confirm with the developer:**

> "📝 **Implementation Complete - Ready for Review**
> 
> I've made the following code changes:
> - {list of files modified/created}
> - {brief summary of changes}
> 
> ✅ **Build Status:** Successful
> 
> **Acceptance Criteria Status:**
> - [ ] {Criterion 1} - {Addressed/Not Yet}
> - [ ] {Criterion 2} - {Addressed/Not Yet}
> 
> Are you ready to proceed with adding tests, or would you like to:
> - **Review changes** - I can show you any file or explain any change
> - **Make adjustments** - Tell me what needs to be modified
> - **Proceed to tests** - Continue to Add Tests"

---

## Wait for Confirmation

**⏸️ STOP: WAIT for explicit developer confirmation before proceeding to Add Tests.**

