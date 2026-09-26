# Expression language

The optional top-level `expression` object declares the expression capabilities required by a registry document. Connection `when` conditions and check `when` bodies use this language. History functions read the ledger defined in [run-record.md](run-record.md). Semantic validation of expressions is in [validation.md](validation.md).

---

```yaml
expression:
  namespaces: [config, state, visit, history]
  operators: ["!", "&&", "||", "==", "!=", "<", "<=", ">", ">=", "in"]
```

When present, every namespace and operator used by a check or connection condition MUST be declared. An engine MUST reject a registry whose declared capabilities it does not support. Omission requests only the minimum language defined by this specification.

Available namespaces:

- `config.*` — immutable run configuration;
- `state.*` — current mutable domain-state snapshot;
- `visit.*` — current visit snapshot;
- `history.*` — append-only ledger queries.

Required operators:

```text
!  &&  ||  ==  !=  <  <=  >  >=  in  ( )
```

Required literals are booleans, null, strings, numbers, and list literals.

The minimum grammar is:

```text
expression     = or_expression ;
or_expression = and_expression, { "||", and_expression } ;
and_expression = comparison, { "&&", comparison } ;
comparison     = unary, [ ("==" | "!=" | "<" | "<=" | ">" | ">=" | "in"), unary ] ;
unary          = [ "!" ], postfix ;
postfix        = atom, { ".", identifier | "(", [ arguments ], ")" } ;
atom           = literal | identifier | list | "(", expression, ")" ;
arguments      = argument, { ",", argument } ;
argument       = [ identifier, "=" ], expression ;
list           = "[", [ expression, { ",", expression } ], "]" ;
literal        = "true" | "false" | "null" | string | number ;
```

Strings MAY use single or double quotes. The single `=` token is valid only between a named function argument and its value; equality uses `==`.

Required history functions:

| Function | Result |
|---|---|
| `history.count(event_type, filters...)` | Number of matching events |
| `history.last(event_type, filters...)` | Most recent matching event or `null` |
| `history.events(event_type, filters...)` | Matching events in sequence order |
| `history.visits(node_id)` | Visit ids for a node in admission order |

Expression evaluation MUST be side-effect free. Unknown names, invalid types, or evaluation failures are errors; they do not coerce to `false`.

Connection conditions evaluate after seal and can read the sealed visit's `outcome` and `decision`.

History `event_type` is an exact string such as `'visit.sealed'`. A named filter matches an event-envelope field when its name is one of `seq`, `at`, `run_id`, `visit_id`, `node_id`, or `type`; all other filter names match payload fields. `payload.<name>` MAY be used to make payload access explicit. A missing field does not match. Projecting a field from `null` is an evaluation error; authors MUST compare a nullable function result to `null` before projection.
