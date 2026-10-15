---
name: operator-onboarding-retro
description: >-
  Turn an operator's questions, frustrations, commands, and observed workflow
  into a product experience retrospective with implementation references and
  explored improvement options. Use for onboarding or dogfooding retros;
  evaluate-run handles run correctness and compliance.
---

# Operator experience retrospective

Write or update a durable retro in a **plan bundle** at `docs/plans/<bundle>/retro.md` from the operator's experience. Treat the user as a product tester and design collaborator. Help them continue the workflow when they ask how, while also examining what made that help necessary. The retro is a design investigation, not a support article, chat transcript audit, or list of complaints.

## Evidence and boundaries

- **Operator account:** Preserve the user's question, complaint, desired outcome, and impact in their terms. Quote briefly when exact wording matters; otherwise label a paraphrase. A question can reveal an expectation even when the command eventually works.
- **Observed interaction:** Record relevant commands, options, outputs, delays, retries, and transitions. Say whether each fact came from the user's account, a terminal, a run artifact, or code. Do not infer the full experience from the run alone.
- **Run evidence:** Record the run ID/path. When `run_path` is provided, either link an `/evaluate-run` output in the repository or chat, or write exactly: **“evaluate-run not run—engine verdict omitted.”** That workflow owns engine correctness, gates, judgment, and deliverable assessment. Include only the run state needed to explain the operator's experience; do not reproduce a scorecard or re-evaluate the run here. A steward chat transcript is not automatically stored in the live run directory.
- **System map:** Follow a complaint into the relevant command parser, formatter, host/bridge behavior, workflow node, documentation, or configuration. Use repository-relative links to specific files and name functions/objects where useful. Separate verified mechanism from suspected cause, and mark links as a snapshot of the current implementation.
- **Design analysis:** For each material feedback item, explain the expectation, friction, why it matters, plausible product changes, their tradeoffs, and a question or probe that would help choose. Do not stop at a workaround or a feature request. Explore workflow or structural changes when the local fix would leave the underlying friction intact.

Do not make advice from the conversation into the subject of the retro unless the user identifies that advice itself as product feedback. Avoid characterizing the operator's frustration as a complaint about the helper. Preserve corrections to factual claims without turning them into a transcript chronology.

## Signal block

Use this shape for each material investigation, adapting labels when needed. Lead with a brief first-person operator line. Use quotation marks only for the operator's actual words; use italics and label a paraphrase when reconstructing a question from notes.

```markdown
### <short product-facing title>

*Operator signal (paraphrased): Why does this step return before I can answer?*

- **Expected:** What the operator thought or wanted to happen.
- **Observed:** Command, option, output, timing, or transition; identify its source.
- **Friction cost:** Time, context switching, uncertainty, lost trust, or blocked progress.
- **Touchpoints:** Links to the relevant code and/or docs; name entrypoints and objects.
- **Interpretation:** What the mismatch reveals about the product; distinguish fact from hypothesis.
- **Options and tradeoffs:** At least one meaningful alternative and its downside; compare a local fix with a workflow change when useful.
- **Probe:** A concrete experiment or question that would choose between options.
- **Status:** open | mitigated | fixed-in-code (with evidence for the latter two).
```

## Suggested document shape

Adapt headings to the session; do not force a section with no evidence.

1. **Purpose and setting:** What the operator tried to accomplish, where, and with which run(s).
2. **Experience in the operator's terms:** A short account of the intended path and where momentum broke.
3. **Feedback investigations:** One subsection per distinct friction. Include operator signal, observed path, system touchpoints, design interpretation, options and tradeoffs, and an open question or recommended probe.
4. **Cross-cutting design opportunities:** Combine recurring causes and consider a better workflow, interface, or architecture. Prioritize by impact and uncertainty, not by a generic P0/P1 list alone.
5. **Evidence index:** Run/evaluation links, commands and outputs that matter, code/docs entrypoints, and any uncertainty or state that may change.

Prefer links at the point of analysis. Keep setup instructions or workarounds only when they explain the friction; link the maintained runbook for operational guidance.

## Working procedure

1. Read the full available conversation and attachments. Extract the operator's questions and comments before reading code so the implementation does not redefine the problem.
2. Reconstruct only the command/option sequence relevant to those signals. Inspect run artifacts or an existing evaluation for context, and inspect code/docs to trace the supporting systems.
3. Distinguish observation, code-backed explanation, and hypothesis. If the implementation has changed since the experience, keep the historical observation and say what changed.
4. Develop at least one meaningful design alternative for each material issue, including its cost or downside. Where useful, compare a narrow repair with a workflow redesign.
5. **Plan bundle:** Use `docs/plans/<bundle>/` (kebab-case). Create or update `retro.md` and a bundle `README.md` (see [retro-feature-interview](../retro-feature-interview/SKILL.md) bundle layout). Propose `<bundle>` in chat when not supplied on `/operator-onboarding-retro`. Legacy flat paths `docs/plans/operator-onboarding-<slug>-retro.md` are deprecated — prefer bundles for new work. Update [docs/plans/README.md](../../../docs/plans/README.md) when adding a bundle. Preserve useful first-person feedback and evidence while removing inaccurate attributions. Commit only when requested.

Before finishing, check: no section audits the helper's advice; each material signal has a first-person line, at least one code/doc link, and a design alternative; operational instructions are linked rather than pasted as a full runbook; and every supplied `run_path` has an evaluation link or the required omitted-verdict sentence.

The command entrypoint is [`.cursor/commands/operator-onboarding-retro.md`](../../commands/operator-onboarding-retro.md). Use [`.cursor/skills/foundry-run-evaluation/SKILL.md`](../foundry-run-evaluation/SKILL.md) only when run evaluation is explicitly in scope or needed to interpret an existing review.
