# Analysis app-manifest reference

This factory-local fixture is the analysis-mode reference for Foundry protocol
2.2. It has no build or test commands. A `run init --run-mode analysis` must
succeed and freeze a snapshot whose `commands` are empty.

The fixture is not an application repository. Real apps still commit their own
`.foundry/app.yaml` through `/foundry-app-bootstrap`.
