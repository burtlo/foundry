# Commit and Push

**Only proceed after developer approval in Code Review.**

**Prerequisites:**
- `{DeveloperFirstName}` - Developer's first name
- `{JiraTicketNumber}` - The Jira ticket ID (e.g., TICKET-1234)

---

## Stage All Changes

```text
git add .
```

---

## Staged secrets check (required — hard stop)

**Previously** the Foundry plugin could intercept `git commit` via a Cursor session hook. **That hook is removed.** The parent agent **must** run this factory CLI check after `git add` and **before** `git commit`. Do not commit when it exits non-zero.

Patterns come from `git.staged_secrets_check` in FactoryConfig (built-in default blocks `.env`, `.key`, `.pem`, `secrets.json`, `creds.md`, and `.env.*` paths). Override with `pattern` (full replace) or `extra_patterns` (OR onto default).

```text
python "{factory_root}/.cursor/foundry/cli/foundry.py" git staged-secrets-check --repo "{app_folder}" --factory-root "{factory_root}"
```

If blocked, unstage or remove the sensitive paths, re-run `git add` as needed, then re-run the check.

---

## Create Commit

Use conventional commit format:

**PR title is separate from this commit message.** When you create the PR next, `--title` must **not** copy this subject line.

| Commit message (this step) | PR title (Step 8 / create-pr-step) |
|----------------------------|-------------------------------------|
| `feat(TICKET-2247): Upgrade Example.Api to .NET 10` | `TICKET-2247 - Upgrade Example.Api to .NET 10` |

See Step 12 in `ticket-workflow` or foundry `create-pr-step.md`.

Run **only** the fence that matches the current shell (PowerShell 5.1 on Windows; bash on macOS/Linux).

```powershell
git commit -m @"
feat({JiraTicketNumber}): Brief description of change

- List of key changes made
- Tests added/updated
- Documentation updated

Jira: {JiraTicketNumber}
"@
```

```bash
git commit -m "feat({JiraTicketNumber}): Brief description of change

- List of key changes made
- Tests added/updated
- Documentation updated

Jira: {JiraTicketNumber}"
```

### Commit Type Reference

| Type | Use When |
|------|----------|
| `feat` | New feature or enhancement |
| `fix` | Bug fix |
| `docs` | Documentation only changes |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `test` | Adding or modifying tests |
| `chore` | Maintenance tasks, dependency updates |

---

## Push to Remote

```text
git push -u origin {DeveloperFirstName}/{JiraTicketNumber}
```

---

## Confirmation

**Confirm with the developer:**

> "✅ Changes committed and pushed to branch `{DeveloperFirstName}/{JiraTicketNumber}`."

---

## Next Steps

After successful push:
- Proceed to create a Pull Request (Step 12 in full workflow)
- Or continue with additional development tasks

