# Engine procedure

This document defines the engine procedure pseudocode. Visit lifecycle states and hooks are in [visits-lifecycle.md](visits-lifecycle.md). Check evaluation and actions are in [control-plane.md](control-plane.md). Ledger events and ordering are in [run-record.md](run-record.md). Connection selection rules are in [graph.md](graph.md#selection).

---

```text
enter(node_id, source_visit_id, connection_id):
  visit = new Visit(node_id, lifecycle=null)
  append visit.admitted
  set_lifecycle(examined)

  if run_hook(on_examine) does not proceed: return
  if run_hook(on_open) does not proceed: return

  set_lifecycle(opened)
  if node is gate:
    append gate.presented
    authorized decider records a declared decision
    append gate.resolved
    close_request(visit)
  else:
    steward performs work, publishes outputs, and requests close

close_request(visit):
  require lifecycle == opened
  if run_hook(on_close) does not proceed: return
  verify declared output is complete
  set_lifecycle(closed)
  if run_hook(on_seal) does not proceed: return
  seal visit as completed

run_hook(hook):
  for check in declaration order:
    result = evaluate check
    append check.recorded
    action = explicit policy or default policy
    append policy.applied
    perform action
    if action stops the hook: return action disposition
  return proceed

seal(visit, outcome, reason=null):
  set_lifecycle(sealed)
  append visit.sealed
  if node is terminal:
    set run status completed
    append run.completed
  else:
    select exactly one eligible connection
    append connection.taken
    enter connection.to with a new visit id

set_lifecycle(to):
  append lifecycle.changed(visit.lifecycle → to)
  update visit lifecycle in the same atomic operation
```

No routing occurs before seal.
