# App-manifest validation (factory-only)

Factory Windows/Linux CI (`.github/workflows/foundry-flow-check.yml`) owns
schema, semantic, capability, routing, and **reference** manifests
(`python-reference`, `iot-reference`, `analysis-reference`).

Foundry does **not** publish a reusable app-repo validator workflow.

Apps validate during `/foundry-app-bootstrap` via `app init` and `app validate`.
See [foundry-app-bootstrap](../../skills/foundry-app-bootstrap/SKILL.md).

App-repository CI is optional and outside this contract.

Porcelain is proven from a clean app-only checkout at delivery, not by factory
CI.

Rollback means reverting the factory release. There is no silent fallback to
`AGENTS.md`, `.sln`, Makefile, or `projectType` inference. Bootstrap detectors
stay advisory authoring helpers; they never run during a Foundry run. Protocol
cutover: [protocol-2.2-cutover.md](protocol-2.2-cutover.md). Plan:
[foundry-app-manifest-plan.md](../../../docs/foundry-app-manifest-plan.md).
