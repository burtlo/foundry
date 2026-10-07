# Deferred contract slices (optional)

Status: **open** — only if acceptance or steward UX fails after the main contract revision (REL-001–REL-019).

Parent context: [implementation-flow-runtime.md](../features/implementation-flow-runtime.md). Node contracts: `docs/nodes/`, `.cursor/foundry/nodes/`.

---

## `shape.examine` — slice 7

Optional follow-ups (not required for shipped examine contract):

- Materialize `reads.artifacts` ticket in the context packet (`context.py` / artifact resolver).
- Implement `questions_asked_total` increment on new questions in `apply_examination_result` **only if** a downstream consumer needs it; otherwise delete from schema everywhere.
- Host protocol: ensure `run.examine.complete` alias if host prefers RPC symmetry with intake.

---

## `shape.present.gate` — slice 5

Optional shared follow-up:

- Use the same `nearest_sealed_ancestor` resolver for `shape.record` context and materialization (noted in present gate cleanup).
- `shape.record.gate` presentation parity audit (out of scope unless trivial reuse).
