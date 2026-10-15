# Operator experience — Foundry as its own workspace

Status: **open design investigation**. This account concerns the operator's attempt to use Foundry on the [`foundry up` plan](foundry-up.md). Code links locate the implementation inspected for this retro; they may move as the project changes.

## Purpose and experience

The operator started `shape --input-file docs/plans/foundry-up.md` after manually starting bridge and host. The command blocked during judgment, then returned when the run needed four clarifying answers. The run state could represent that wait, but the command line did not make the questions or the path to answering them clear. The operator tried `status`, `run context`, and `attach` to find the missing interaction. This is a gap between a correct state transition and a usable human workflow.

The conversation is a source for the operator's questions and expectations. Its advice about which command to try is not the subject of this retro.

## Feedback investigations

### 1. `shape` hands control back at the moment a conversation is needed

*Operator signal (paraphrased): Why does my `shape` command return here instead of showing me the questions?*

**Status:** open.

**Operator signal.** Why does `shape` block during judgment, then return at `user_input` without displaying the questions? The operator wanted either a command that detaches promptly and tells them where to return, or an interactive session that stays with them through the Q&A.

**Observed path.** `shape --input-file docs/plans/foundry-up.md` blocked for about 46 seconds and returned a one-line `user_input` summary. The run had four open questions. The duration and wait state matter because they set an expectation that the command would continue guiding the operator.

**System touchpoints.** [`cmd_shape`](../../.cursor/foundry/cli/foundry_cli/user_cli.py) creates then advances a run; [`_format_shape`](../../.cursor/foundry/cli/foundry.py) owns its human output; [`examination_state`](../../.cursor/foundry/cli/foundry_cli/engine/examination_state.py) creates the `user_input` wait. The [run record concept](../concepts/run-record.md) explains the durable state.

**Design interpretation.** The command behaves synchronously until it reaches a human handoff, then becomes a stateful background workflow without explicitly changing the interaction mode. The user has to infer that transition and discover another command.

**Directions to explore.** Offer two explicit modes: an interactive path that renders questions and accepts answers, and a detached path that returns immediately with run ID, wait location, and a precise resume command. A smaller improvement could render the questions before returning. The dual-mode design better fits both automation and hands-on use, but requires a clear shared view of the same run state. Test both modes with a judgment that takes time and one that immediately asks questions.

### 2. Questions exist in state but lack an obvious human-facing home

*Operator signal (paraphrased): Where do I see and answer the questions for my run?*

**Status:** open.

**Operator signal.** Why do `status` and `run context` not present the questions plainly? Why does `attach` show a ledger/checkpoint stream rather than become the place to answer?

**Observed path.** `status` and `run context` did not give the operator a readable question list in this session. `attach foundry-0001` produced a high-volume event stream, had no answer input, and ended with `error [None]: None` after Ctrl-C. The operator did not run `answer`.

**System touchpoints.** [`cmd_attach`](../../.cursor/foundry/cli/foundry_cli/user_cli.py) is a snapshot/event stream, not an interactive Q&A surface. [`open_clarifying_questions`](../../.cursor/foundry/cli/foundry_cli/tui/host_client.py) and the [`user_input` TUI branch](../../.cursor/foundry/cli/foundry_cli/tui/app.py) show that the application can derive and display questions, but this capability was not discoverable from the attempted CLI path.

**Design interpretation.** Several commands expose different slices of the same run, but none clearly claims responsibility for “what does the human need to do now?” The operator's exploration of these commands is evidence that the product's navigation model is unclear, not simply that they chose the wrong command.

**Directions to explore.** Make every human wait return a compact action card: question count and text, answer options, run ID, and one canonical command to continue. A dedicated `foundry questions RUN` could provide a stable non-interactive view; an interactive `attach` could own the full conversation. The dedicated command is scriptable but adds another concept; enriching `attach` reduces command count but complicates a stream-oriented tool. Decide which surface is canonical, then make `shape`, `status`, and TUI point to it.

### 3. Answer submission asks the human to write API-shaped JSON

*Operator signal (paraphrased): Can I answer these in a file or editor instead of shell-escaped JSON?*

**Status:** open.

**Operator signal.** The operator wanted to answer in a file or editor, in a format like a commit message, rather than compose shell-escaped JSON. The issue is not whether the engine can accept answers; it is whether the command respects the kind of writing the questions require.

**System touchpoints.** The [`answer` parser](../../.cursor/foundry/cli/foundry_cli/parser.py) requires `--answers` as a JSON object. [`cmd_answer`](../../.cursor/foundry/cli/foundry_cli/user_cli.py) parses it and submits it with an expected revision. The TUI already uses labeled input fields for the same wait, indicating another possible interaction model.

**Directions to explore.** Generate an answer template with each question and ID, open `$EDITOR`, validate the completed file, and submit with the current revision. Also support `--answers-file` for automation and reviewable changes. An editor flow improves long answers but must handle stale revisions and partially answered templates; a file option is simpler and can precede an editor UI. Probe with four substantive questions and deliberately stale run state to see whether recovery is comprehensible.

## Cross-cutting opportunity

Design the run around **human handoffs**, not only engine waits. At each wait, the product should show the exact material requiring attention and offer a clear continuation path. Run state and event streams remain valuable evidence; they should not be the primary interface a person must inspect to answer a question. The same design principle applies to gates and future workflow phases.

### Probes for next session

- Try `run context --markdown` at `user_input` and compare what it renders with the four questions in the snapshot.
- Try a question-and-answer template in a file with four substantive answers, including a stale revision, to test the recovery path.
- Compare a detached `shape` response with an interactive `shape` session at the same wait; ask which makes the next action clearest.

## Evidence and run locator

| Field | Value from the session |
|---|---|
| Run | [`foundry-0001`](../../.foundry/runs/foundry-0001/snapshot.json) in `.foundry/runs/foundry-0001/` |
| Evaluation | [Artifacts-only `/evaluate-run` summary](foundry-0001-run-evaluation.md) — engine pass for the current phase; operator information partial |
| Workspace / input | `/Users/lynnfrank/src/foundry`; `docs/plans/foundry-up.md` |
| State when recorded | Revision 4, `shape.examine` (`v-002`), `wait.kind=user_input`, four open clarifying questions |
| Questions | `up-lifecycle`, `judgment-success`, `verification-cursor`, `shape-input-path` |
| Commands tried | `shape --input-file docs/plans/foundry-up.md`; `status`; `run context`; `attach foundry-0001` |

The snapshot and [ledger](../../.foundry/runs/foundry-0001/ledger.jsonl) record the engine's state. The linked evaluation assesses the current phase and states its transcript limits. This retro focuses on what those records cannot say by themselves: the operator's attempted path, expectations, and the product choices behind the friction.
