# Foundry Up — operator GWT (seed)

Given that the foundry CLI has been set up (`just setup`)
and the project has the foundry configuration files
and the required Cursor credential is available

When I run `foundry up`

Then I expect it to show:

```
Foundry is ready for workspace: C:\Users\lynnv\src\foundry

host pid: 37780
bridge: http://127.0.0.1:8791/v1/agent

Next:
  foundry shape PLANFILE.md
```

When I run `foundry shape PLANFILE.md`
Then I expect to start a workflow (the same as `foundry shape --input-file`)

When I run `foundry shape "an idea to shape"`
Then I expect to start a workflow (the same as `foundry shape --input`)

When I `foundry shape` with a file or text
Then I expect it to show:

```
Started run `foundry-0006` with shape request

Next:
  foundry attach foundry-0006  # attach to the run
  foundry status foundry-0006  # check on the status
```

When I run `foundry attach ID`
Then I expect to see a well formatted response that displays the markdown in a well formatted output and the user can scroll through the rendered output. Maybe a summation of the other commands. Really what I'm looking for is an interactive console where the user can move the viewport around like that would be available in some other cli tooling that provide the ability to approximate the chat interface of cursor or other product chat interfaces.

---

Design investigation: [cli-operator-ux/retro.md](cli-operator-ux/retro.md) (2026-10-15 session). Canonical bundle scenario: [foundry-up/gwt-scenario.md](foundry-up/gwt-scenario.md).
