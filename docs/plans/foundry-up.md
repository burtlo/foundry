# Foundry Up

Given that the foundry CLI has been set up (just setup)
and the project has the foundry configuration files
and the required Cursor credential is available

When I run `foundry up`

Then I expect:

- the correct application workspace is resolved
- the judgment bridge starts
- the host starts
- the host is configured to use that bridge
- both processes are healthy
- the command reports that Foundry is ready

And:
  foundry shape --input-file plans/foundry-up.md

successfully reaches judgment.
