# Foundry developer tasks — run `just` (default) or `just help` for commands.
# Requires: https://github.com/casey/just

# Default on Windows is `sh` (Git Bash). Use cmd on Windows; sh on macOS/Linux.
[unix]
set shell := ["sh", "-cu"]

[windows]
set shell := ["cmd.exe", "/C"]

cli_dir := ".cursor/foundry/cli"
entry := cli_dir + "/foundry.py"
workspace := "."
fixture_app := ".cursor/foundry/fixtures/apps/foundry-test"

bootstrap_python := if os() == "windows" { "python" } else { "python3" }
venv_python := if os() == "windows" {
    cli_dir + "/.venv/Scripts/python.exe"
} else {
    cli_dir + "/.venv/bin/python"
}

# Default recipe: show help
default: help

# List all recipes with descriptions
help:
    @echo Foundry — developer tasks (https://github.com/casey/just)
    @echo.
    @echo   Setup
    @echo     just setup              Create CLI venv and install requirements
    @echo.
    @echo   Tests
    @echo     just unit               Run unit tests (pytest tests/unit)
    @echo     just acceptance         Run acceptance tests (Gherkin; excludes dev_commands)
    @echo     just test               Run unit then acceptance (alias: all)
    @echo     just acceptance-meta    Acceptance including dev_commands.feature
    @echo.
    @echo   Docs and catalog
    @echo     just docs               Build catalog indexes and regenerate docs/
    @echo     just smoke              Fast doc check (shape.intake only)
    @echo     just catalog            Generate catalog index YAML only
    @echo     just doc                Generate documentation only (doc build)
    @echo.
    @echo   CI / maintenance
    @echo     just check              docs + test + fail if docs/ has uncommitted drift
    @echo     just fixtures           Regenerate porcelain run fixtures
    @echo     just resolve            Print resolved bundle and cli_path (bootstrap smoke)
    @echo     just validate-app       config validate on foundry-test fixture app
    @echo.
    @echo   Pass-through
    @echo     just foundry ARGS...    Any foundry CLI command (workspace = repo root)
    @echo     just foundry-ws WS ARGS Workspace + foundry CLI
    @echo.
    @echo Recipes (just --list):
    @just --list --unsorted

# Bootstrap the CLI virtualenv and install Python dependencies
setup:
    {{ bootstrap_python }} -m venv {{ cli_dir }}/.venv
    {{ venv_python }} -m pip install -r {{ cli_dir }}/requirements.txt

# Invoke foundry.py from the repository root workspace
foundry *ARGS:
    {{ venv_python }} {{ entry }} --workspace {{ workspace }} {{ ARGS }}

# Invoke foundry.py with an explicit workspace path
foundry-ws WS *ARGS:
    {{ venv_python }} {{ entry }} --workspace {{ WS }} {{ ARGS }}

# Run unit tests
unit *ARGS:
    just foundry dev unit {{ ARGS }}

# Run acceptance tests (dev_commands.feature excluded by default)
acceptance *ARGS:
    just foundry dev acceptance {{ ARGS }}

# Run unit tests then acceptance tests
test *ARGS:
    just foundry dev all {{ ARGS }}

alias all := test

# Run acceptance tests including dev_commands.feature (meta; not for nested CI)
acceptance-meta *ARGS:
    just foundry dev all --include-dev-scenarios {{ ARGS }}

# Build catalog indexes and regenerate docs/
docs *ARGS:
    just foundry dev docs {{ ARGS }}

# Fast documentation smoke (shape.intake only)
smoke *ARGS:
    just foundry dev docs --smoke {{ ARGS }}

# Generate catalog index YAML under docs/catalog/
catalog *ARGS:
    just foundry catalog build {{ ARGS }}

# Generate documentation from the flow registry (catalog build runs inside doc pipeline when using dev docs)
doc *ARGS:
    just foundry doc build {{ ARGS }}

# Regenerate docs, run tests, and fail if docs/ changed on disk
check:
    just docs
    just test --quiet
    git diff --exit-code -- docs

# Regenerate porcelain run fixtures under .cursor/foundry/fixtures/runs/
fixtures:
    {{ venv_python }} {{ cli_dir }}/scripts/build_porcelain_run_fixtures.py

# Print resolved registry bundle and CLI path
resolve:
    just foundry cli resolve

# Validate foundry.yaml on the test fixture application workspace
validate-app:
    just foundry-ws {{ fixture_app }} config validate
