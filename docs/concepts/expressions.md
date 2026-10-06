# Expression language (v1 — superseded)

Status: **superseded** by [predicate-language.md](predicate-language.md) for new work.

The v1 grammar remains documented here for reference while the implementation flow and engine catch up. New predicates SHOULD use v2 collection expressions and derived state per the predicate language spec.

---

## v1 summary

The optional top-level `expression` object declared namespaces and operators. Connection `when` conditions and check `when` bodies used a minimal postfix grammar with `config`, `state`, `visit`, and `history` namespaces and required history functions (`count`, `last`, `events`, `visits`).

See the archived v1 rules in git history of this file, or [predicate-language.md](predicate-language.md) for the full v2 replacement including:

- typed compile-time validation against `state_schema`;
- collection methods (`filter`, `exists`, `none`, …) over state arrays;
- elimination of routing scalars such as `open_clarifying_questions_count`;
- explicit evaluation error semantics (no silent `false`).

**Migration:** replace v1 `when` strings with v2 equivalents and set `expression.version: 2` on the flow document.
