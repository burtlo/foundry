---
step_id: deliver.ship
title: Commit, push, PR, and Jira transition
subagent: null
run_modes: [implementation]
delivery_gate: false
state_keys:
  - steps.deliver.ship.status
  - steps.deliver.ship.gate_decision
  - resolved_pr_title
  - pr_url
---

## Purpose

The only step that writes outside the working tree: commit, push, open the pull request, and transition the ticket. Terminal step of the implementation flow.

**Parent may run shell git/gh via Foundry fences only. No `Write`/`StrReplace` under `{app_folder}` except `{run_dir}`.** On tooling failure: `run block`.

## Inputs (from parent)

- FactoryConfig slice: `git.pr_title_pattern`, `jira_transitions`
- `feature_branch`, `issue_key`, ticket summary

## Parent actions

1. `git add` the intended paths, then seal the staged tree:

```foundry-invoke
deliver prepare --state "{state_path}" --factory-root "{factory_root}"
```

This runs the staged-secrets check and records the branch, base HEAD, and staged tree. Run it **after** staging and **before** committing.
2. Commit with a conventional-commit message (shell only).
3. Build the PR title:

```foundry-invoke
pr-title --issue-key {issue_key} --summary "{summary}"
```

The title is `{issue_key} - {brief description}` and must **not** carry a conventional-commit prefix.
4. Push, then `gh pr create`.
5. Verify the remote PR through the authenticated GitHub CLI:

```foundry-invoke
deliver pr-verify --state "{state_path}" --pr-url "{pr_url}" --pr-title "{resolved_pr_title}"
```

This fetches the authoritative URL, title, head branch, head SHA, commit list,
and head tree. The engine emits success evidence only when every value matches
the local delivery seal; parent-recorded PR attestations are rejected.
6. Transition the ticket per `jira_transitions.on_pr_ready`.
7. Present the PR URL and title, collect confirmation, resolve the gate, then:

```foundry-invoke
gate resolve --state "{state_path}" --config "{config_path}" --source human --decision approve
```

Write the required handoff and resume in a fresh steward session before completion.

```foundry-invoke
run complete --state "{state_path}" --pr-url "{pr_url}" --pr-title "{resolved_pr_title}"
```

`run complete` rejects branch/tree drift or missing authenticated `deliver
pr-verify` evidence and writes `learning_record.json` (offline; do not load
into the next steward chat).

**CI failure triage after the PR:** when checks fail, launch `devops-builder` in `investigate` mode (or the `ci-investigator` subagent) and treat fixes as rework back to `implement.build`. There is no separate step ID for this; the run stays on `deliver.ship`.

## Launch packet (pass to Task; not parent work)

None for shipping. For CI triage:

```text
Mode: investigate
PR: {pr_url}
Failed checks: {check names}
Return: root cause per check, minimal fix, whether the fix is code or workflow.
```

## State keys this step owns

- `steps.deliver.ship.status`
- `steps.deliver.ship.gate_decision`
- `resolved_pr_title`

## Gate

`human_confirm` (`confirm_pr`).

## Invalid transitions

- `require_delivery_check: true` — `transition --to deliver.ship` re-runs `delivery-check` and refuses on any failure. This is the hard stop the acceptance criteria call for.
- `run complete` requires a current delivery seal whose staged tree still matches the committed tree.
- Do not comment on the ticket here; that was `deliver.scope_comment`.
- Do not squash the staged-secrets check to save a turn.
