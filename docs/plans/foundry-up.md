# Foundry Up

Given that the foundry CLI has been set up (just setup)
and the project has the foundry configuration files
and the required Cursor credential is available

When I run `foundry up`

Then I expect it to show:

```
Foundry is ready for workspace: C:\Users\lynnv\src\foundry

host pid: 37780
bridge: http://127.0.0.1:8791/v1/agent

Shape work
  foundry shape PLANFILE.md
```

When I run `foundry shape PLANFILE.md`
Then I expect to start a workflow (The same as foundry shape --input-file)
When I run `foundry shape "an idea to shape"`
Then I expect to start a workflow (The same as foundry shape --input)
