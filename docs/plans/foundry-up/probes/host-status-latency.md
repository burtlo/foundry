# Host status latency probe (D11)

Record human `foundry host status` wall time in three scenarios before tightening CI caps:

| Scenario | Setup | Provisional cap |
|----------|--------|-----------------|
| Bridge absent | Stop bridge; host may be down | ≤ 3s |
| Bridge + host ready | After successful `foundry up` | ≤ 5s |
| Stale discovery | Truncate or corrupt bridge `state.json` while PID dead | ≤ 8s |

Health RPC uses `STATUS_HOST_CLIENT_TIMEOUT_SECONDS` (5s) in `host/timeout_policy.py`.

Example (PowerShell, from app workspace):

```powershell
Measure-Command { foundry host status }
```

Python probe (from registry `cli/` directory, after preparing each scenario):

```powershell
python scripts/probe_host_status_latency.py --workspace C:\path\to\app --scenario absent
python scripts/probe_host_status_latency.py --workspace C:\path\to\app --scenario ready
python scripts/probe_host_status_latency.py --workspace C:\path\to\app --scenario stale
```

## Recorded baselines (fixture / CI)

These medians are **placeholders from the mocked probe unit test** (`test_host_status_latency_probe.py`); they are not yet measured on a real app workspace. Replace with manual probe medians when recorded.

| Scenario | Median (fixture) | Provisional cap |
|----------|------------------|-----------------|
| Bridge absent | 0.05s | ≤ 3s |
| Bridge + host ready | 0.12s | ≤ 5s |
| Stale discovery | 0.20s | ≤ 8s |

Commit updated medians here after running `probe_host_status_latency.py` on a prepared environment.
