# Python app-manifest reference

This factory-local fixture is the cross-platform implementation reference for
Foundry protocol 2.2. Its commands are executable `python` argv lists, so
Windows and Linux factory CI can run `run init`, `build`, `test`, and
`verification.implementation` without a language toolchain beyond CPython.

The fixture is not an application repository. Real apps still commit their own
`.foundry/app.yaml` through `/foundry-app-bootstrap`.
