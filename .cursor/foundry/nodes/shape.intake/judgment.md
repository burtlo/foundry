# Shape intake - judgment

## Scope confirmation (judgment only)

When `reads.state.app_folder` is unset or differs from the application repo the user intends, confirm the correct root before running deterministic intake.

Default `app_folder` to `reads.config.workspace` when unset (engine applies this on `visit intake complete`).

## Boundaries

- Do **not** invoke **intake-checker.shape** on the happy path. Capture, ticket publication, evidence, seal, and transition are engine operations (`visit intake complete` — see **Operations**).
- When intake is **blocked** (missing work request), help the user supply input and re-run `visit intake complete`; do not publish a ticket or call `visit transition` manually while the intake receipt is blocked.
