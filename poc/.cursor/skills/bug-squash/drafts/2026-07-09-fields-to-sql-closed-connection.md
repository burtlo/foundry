# Local bug-squash draft (NOT created in Jira)

| Field | Value |
|-------|--------|
| **Issue type** | Bug |
| **Project** | TICKET (would use on create) |
| **Labels** | `bug-squash` |
| **Sprint** | none (backlog only) |
| **App** | Example.Api |
| **Environment** | prod |
| **Lookback** | 168h (7d) ending ~2026-07-09 |
| **Telemetry** | `prod-ai-example-north` → `prod-la-shared-north` |
| **Role** | `prod-fa-exampleapi-north` |
| **Status** | Local preview only — do not create until Gate 2 approval |

---

## Summary

FieldsToSql fails with closed SqlConnection during Event Hub batch upserts (prod)

---

## Description

## User Story

As a platform engineer, I want `FieldsToSql` to keep a usable SQL connection (or recover cleanly) while processing an Event Hub batch, so that field upserts do not fail with `BeginExecuteNonQuery requires an open and available Connection` and field history stays current.

## General Information

**Repository:** Example.Api  
**Component:** `Example.Api.Rest` / `FieldsToSql`  
**Function:** `FieldsToSql` (Event Hub `fields`, consumer group `fields-zuul`)  
**Primary file:** `Example.Api.Rest/Fields/FieldsToSql.cs` (~line 77 `ExecuteNonQueryAsync`)

### Azure Monitor evidence (prod, last 7 days)

| Metric | Value |
|--------|--------|
| Exception | `System.InvalidOperationException` |
| Message | `BeginExecuteNonQuery requires an open and available Connection. The connection's current state is closed.` |
| Count | **1171** |
| Distinct operations | **144** |
| First seen | 2026-07-03 ~05:27 UTC |
| Last seen | 2026-07-09 ~19:51 UTC |
| Sample OperationId | `8253fd4599bee5ae269440075c26776a` |
| ProblemId | `System.InvalidOperationException at Example.Api.Rest.Fields.FieldsToSql+<Run>d__5.MoveNext` |

Stack (abbreviated): SqlClient `ValidateCommand` / `BeginExecuteNonQueryInternal` → SqlClient retry → **`FieldsToSql.Run` line 77**.

### Suspected cause

`Run` opens **one** `SqlConnection` for the entire `EventData[]` batch, then reuses it for every message. If a prior command/retry leaves the connection **closed** or **broken**, later rows in the same invocation still use that connection and throw. Related noise in the same window includes `BeginExecuteReader` (state open/broken) on `ThingsQuery` and occasional `SqlException` “connection was recovered…” from `FieldsToSql`.

### Proposed fix (for implementer)

**Do not** open a new `SqlConnection` per Event Hub message. High field volume would increase pool pressure, latency, and SQL load. Keep **one connection per function invocation / batch** (current shape).

1. Before each `ExecuteNonQueryAsync` (or in the catch path before the next message), ensure the **shared** connection is still `Open`. If `Closed` or `Broken`, reopen that same logical connection (or replace once and continue the batch) — recover mid-batch, do not recreate per row.
2. After SqlClient command retry exhausts or leaves a bad state, reset connection state once, then continue remaining messages on the recovered connection.
3. Treat `InvalidOperationException` for connection state similarly to `SqlException` for logging/continue-vs-fail so one bad row does not poison the rest of the batch without recovery.
4. Re-check prod `SqlResiliency__*` settings vs intended `FieldsToSql` command/connection retry providers (retry should not leave the shared connection unusable for later rows).
5. Avoid per-message or tiny-chunk connection lifetimes unless profiling proves pool reuse is the bottleneck — default remains batch-scoped connection with mid-batch recovery.

**Note:** Drafted by bug-squash from Azure Monitor. Review before any Jira create. No secrets included.

## Acceptance Criteria

- [ ] Reproducing a closed/broken connection mid-batch no longer surfaces `BeginExecuteNonQuery… state is closed` for subsequent messages in the same invocation (unit or integration coverage preferred).
- [ ] After a connection failure, remaining Event Hub messages in the batch either succeed on a recovered connection or fail with clear, per-message logging (no silent skip of the whole batch without logs).
- [ ] Existing `SqlResiliency` / SqlClient retry behavior for `FieldsToSql` remains intentional and documented (or updated) in code/comments or AGENTS.md.
- [ ] In prod App Insights / Azure Monitor (`prod-fa-exampleapi-north`), count of this exact exception message drops materially in the 7 days after release vs the pre-fix baseline (~1171 / 7d).
- [ ] Related `SqlException` “connection was recovered and rowcount…” from `FieldsToSql` is reviewed; either fixed by the same change or explicitly deferred with rationale.

## Out of scope (unless expanded)

- Gemini `ThingNotFoundException` volume on shared App Insights
- Broader `ThingsQuery` / EF pool issues (separate ticket unless confirmed same root cause)
- HttpContext disposed / TaskCanceledException noise
