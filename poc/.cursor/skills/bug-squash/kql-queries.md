# Bug squash — Azure Monitor KQL templates

Used by [SKILL.md](SKILL.md). Substitute `{lookback_hours}`, `{top_n}`, `{app_scope}`, and table names after verifying with `monitor_table_list`.

These templates are **app-agnostic**. Scope to the chosen solution via dedicated App Insights, `resource_id`, or `{app_scope}` — never bake a product name into the skill.

## Table names

Classic App Insights API often uses `exceptions` / `traces` / `requests`.

Workspace-based (Log Analytics) commonly uses:

| Classic | Workspace-style |
|---------|-----------------|
| `exceptions` | `AppExceptions` |
| `traces` | `AppTraces` |
| `requests` | `AppRequests` |
| `dependencies` | `AppDependencies` |

If a query fails with “Failed to resolve table”, list tables and switch naming.

When using Monitor MCP `monitor_workspace_log_query`, pass `hours: {lookback_hours}` (or equivalent) **and** keep a `ago()` filter in KQL so the window is explicit in the query text.

---

## App scope (required on shared workspaces)

Build `{app_scope}` from confirmed `role_filters` / `resource_id_filters` for this run. Omit the whole `| where` only when querying a **dedicated** App Insights resource (or an already resource-scoped MCP query).

**Single role substring:**

```kusto
| where AppRoleName has "{role_substring}"
```

**Multiple roles (OR):**

```kusto
| where AppRoleName has_any ("{role_1}", "{role_2}")
```

**Role or resource id:**

```kusto
| where AppRoleName has "{role_substring}" or _ResourceId has "{resource_substring}"
```

Classic App Insights API: use `cloud_RoleName` instead of `AppRoleName`.

### Discover roles (before first scoped top-N)

```kusto
AppExceptions
| where TimeGenerated > ago({lookback_hours}h)
| summarize Count = count() by AppRoleName
| order by Count desc
| take 30
```

Show the engineer this list; confirm which roles belong to `{app_folder}` before aggregating top errors.

---

## Top exceptions by type and message

```kusto
AppExceptions
| where TimeGenerated > ago({lookback_hours}h)
{app_scope}
| extend ErrorKey = strcat(tostring(ExceptionType), " | ", substring(tostring(OuterMessage), 0, 120))
| summarize
    Count = count(),
    DistinctOps = dcount(OperationId),
    FirstSeen = min(TimeGenerated),
    LastSeen = max(TimeGenerated),
    SampleProblemId = any(ProblemId),
    SampleRole = any(AppRoleName),
    SampleMessage = any(OuterMessage)
    by ErrorKey, ExceptionType
| order by Count desc
| take {top_n}
```

Classic variant: replace `AppExceptions` with `exceptions`, `TimeGenerated` with `timestamp`, `OuterMessage` with `outerMessage`, `ExceptionType` with `type`, `OperationId` with `operation_Id`, `ProblemId` with `problemId`, `AppRoleName` with `cloud_RoleName`.

---

## Sample stacks for one error group

Replace `{exception_type}` and `{message_prefix}` from the top-errors row. Keep the same `{app_scope}` as the top-N query.

```kusto
AppExceptions
| where TimeGenerated > ago({lookback_hours}h)
{app_scope}
| where ExceptionType == "{exception_type}"
| where OuterMessage startswith "{message_prefix}"
| project
    TimeGenerated,
    OperationId,
    OperationName,
    ExceptionType,
    OuterMessage,
    InnermostMessage,
    Details,
    ProblemId,
    AppRoleName,
    ClientType
| order by TimeGenerated desc
| take 3
```

---

## Failed requests (optional companion)

```kusto
AppRequests
| where TimeGenerated > ago({lookback_hours}h)
{app_scope}
| where Success == false
| summarize
    Count = count(),
    AvgDurationMs = avg(DurationMs),
    SampleResultCode = any(ResultCode)
    by Name, ResultCode
| order by Count desc
| take {top_n}
```

---

## Error-level traces (when exceptions are sparse)

```kusto
AppTraces
| where TimeGenerated > ago({lookback_hours}h)
{app_scope}
| where SeverityLevel >= 3
| extend MsgKey = substring(tostring(Message), 0, 160)
| summarize Count = count(), LastSeen = max(TimeGenerated) by MsgKey, SeverityLevel
| order by Count desc
| take {top_n}
```

---

## Correlate exception to request (one OperationId)

```kusto
let op = "{operation_id}";
AppExceptions
| where OperationId == op
| union (
    AppRequests
    | where OperationId == op
)
| project TimeGenerated, ItemType = $table, OperationName, Name, ExceptionType, OuterMessage, ResultCode, Success
| order by TimeGenerated asc
```

---

## CLI fallback examples

```bash
# Dedicated App Insights component (classic analytics API) — already app-scoped
az monitor app-insights query \
  --app "{app_insights_name}" \
  --resource-group "{resource_group}" \
  --offset "{lookback_hours}h" \
  --analytics-query "exceptions | where timestamp > ago({lookback_hours}h) | summarize Count=count() by type, bin(timestamp, 1d) | order by Count desc | take {top_n}"

# Shared Log Analytics workspace — include app scope in KQL
az monitor log-analytics query \
  --workspace "{workspace_customer_id}" \
  --timespan "PT{lookback_hours}H" \
  --analytics-query "AppExceptions | where TimeGenerated > ago({lookback_hours}h) | where AppRoleName has \"{role_substring}\" | summarize Count=count() by ExceptionType | order by Count desc | take {top_n}"
```
