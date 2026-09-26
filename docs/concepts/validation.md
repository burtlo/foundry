# Validation

Validation has two layers: structural (JSON Schema) and semantic (`flow validate`). Graph invariants are in [graph.md](graph.md#graph-invariants). Expression parsing is in [expressions.md](expressions.md). Path rules are in [capabilities.md](capabilities.md#paths). A conforming registry example is in [registry.md](registry.md).

---

## Structural validation

JSON Schema validates:

- required fields and primitive types;
- closed field sets;
- enum values;
- check body shape;
- ordered lifecycle hook lists and check-reference shape;
- policy and action shape;
- artifact declaration and artifact-read shape;
- node, connection, worker, and capability object shape.

## Semantic validation

`flow validate` validates relationships JSON Schema cannot fully express:

- unique ids;
- valid entry, check, node, and connection references;
- entry reachability and a structural path from every node to a terminal node;
- node-kind and output compatibility;
- artifact-id uniqueness, URI-template validity, and completed-output evidence;
- artifact schema references, cardinality, consumer references, and ancestry selectors;
- gate decider and capability compatibility;
- gate option and connection-decision compatibility;
- non-empty, unique connection selectors and valid selector values;
- action validity for each hook;
- required reasons;
- expression parsing and namespace use;
- path roots;
- path-template use and exact correspondence between a templated artifact URI and its producing node's write capability;
- exactly one body per check;
- no outgoing connections from terminal nodes;
- at least one outgoing connection from non-terminal nodes;
- statically detectable missing or overlapping routes.

The engine repeats safety-critical semantic checks at runtime, especially exactly-one connection selection.
