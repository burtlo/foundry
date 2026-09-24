# Foundry protocol 2.2 cutover

Status: delivered  
Cutover phase: app-manifest plan Phase 3

Foundry protocol `2.2.0` introduces a required, immutable application-manifest
snapshot for every new run. The active runtime and artifact schemas now use
`2.2.0`; protocol `2.1.0` artifacts are rejected rather than upgraded.

## Compatibility boundary

A `2.2.0` run state must identify the snapshot with `app_manifest_id` and
`app_manifest_hash`, and its run directory must contain `app-manifest.json`.
Run-bound mechanics read that snapshot rather than the live
`.foundry/app.yaml`.

There is no in-place upgrade or manifest-rebase operation for `2.1.0` runs.
Before strict enforcement is released, every active `2.1.0` run must be:

1. completed with the `2.1.0` factory release; or
2. explicitly abandoned and restarted as a new `2.2.0` run.

Foundry continues to reject protocol versions other than the version supported
by the running release. It must not silently add a manifest snapshot to an old
run or infer missing application mechanics.

## Delivered release boundary

The protocol constant and runtime schemas moved to `2.2.0` after:

1. the validator and bootstrap tooling are available;
2. the initial application manifests are committed and pass factory validation;
3. active `2.1.0` runs have been completed or abandoned; and
4. the strict run-init, snapshot, state-bound execution, and drift checks ship
   together.

At cutover, a missing or invalid live manifest fails before a run directory is
created. Missing-manifest errors (`APP_MANIFEST_MISSING`) point operators to
`/foundry-app-bootstrap`. `build`, `test`, and `project-context` require
`--state` and read only the canonical snapshot. `build-step verify` executes
`verification.implementation` in declared order. Live-manifest drift blocks
integrity, handoff, and delivery with guidance to abandon and restart the run.

Rollback means reverting to the preceding factory release. It does not permit
new `2.2.0` runs to fall back to `AGENTS.md`, solution files, Makefiles,
language files, or `projectType`, and a `2.2.0` run is not downgraded to
`2.1.0`.

## Documentation boundary

Protocol `2.2.0` snapshots the selected documentation model and its
configuration. Registered factory-shipped backends are `iot-agents-prd` and
`feature-records`. Unknown models fail before run creation. App-provided
backends and a plugin/extension loader are out of scope.
