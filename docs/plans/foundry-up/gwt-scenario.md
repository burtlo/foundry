# Foundry Up — Given/When/Then

Given that the foundry CLI has been set up (`just setup`)
and the project has the foundry configuration files
and the required Cursor credential is available

When I run `foundry up`

Then I expect:

- the correct application workspace is resolved
- the judgment bridge starts
- the host starts
- the host is configured to use that bridge
- both processes are healthy
- the command reports that Foundry is ready for that workspace

And human stdout resembles:

```
Foundry is ready for workspace: <absolute workspace path>

host pid: <pid>
bridge: http://127.0.0.1:<port>/v1/agent

Next:
  foundry shape PLANFILE.md
```

When I run `foundry shape PLANFILE.md` or `foundry shape "an idea to shape"`
Then I expect the same workflow as `--input-file` / `--input` respectively.

When shape succeeds
Then I expect intake acknowledgment, a started run id, and **Next:** hints for `attach` and `status`.

When I run `foundry attach <run-id>`
Then I expect a scrollable, human-readable view of steward markdown and progress—not raw ledger JSON—until I detach.

Legacy flat copy: [../foundry-up.md](../foundry-up.md).
