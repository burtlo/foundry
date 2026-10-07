# Foundry developer tasks — run `just` (default) or `just help` for commands.
# Requires: https://github.com/casey/just

# Use cmd on Windows; sh on macOS/Linux. Windows paths must use `.\` + backslashes only
# (cmd treats `.cursor/foo` as command `.cursor` and `/foo` as switches).
[unix]
set shell := ["sh", "-cu"]

[windows]
set shell := ["cmd.exe", "/C"]

cli_dir := if os() == "windows" {
    ".\\.cursor\\foundry\\cli"
} else {
    ".cursor/foundry/cli"
}

entry := if os() == "windows" {
    cli_dir + "\\foundry.py"
} else {
    cli_dir + "/foundry.py"
}

venv_dir := if os() == "windows" {
    cli_dir + "\\.venv"
} else {
    cli_dir + "/.venv"
}

requirements := if os() == "windows" {
    cli_dir + "\\requirements.txt"
} else {
    cli_dir + "/requirements.txt"
}

fixtures_script := if os() == "windows" {
    cli_dir + "\\scripts\\build_porcelain_run_fixtures.py"
} else {
    cli_dir + "/scripts/build_porcelain_run_fixtures.py"
}

workspace := "."
fixture_app := if os() == "windows" {
    ".\\.cursor\\foundry\\fixtures\\apps\\foundry-test"
} else {
    ".cursor/foundry/fixtures/apps/foundry-test"
}

bootstrap_python := if os() == "windows" { "python" } else { "python3" }
venv_python := if os() == "windows" {
    venv_dir + "\\Scripts\\python.exe"
} else {
    venv_dir + "/bin/python"
}

# Default recipe: show help
default: help

# List all recipes with descriptions
help:
    @echo Foundry — developer tasks (https://github.com/casey/just)
    @echo.
    @echo   Setup
    @echo     just setup              Create CLI venv and install requirements
    @echo     just repair-venv        Reinstall deps when venv Python vs wheels mismatch
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
    {{ bootstrap_python }} -m venv {{ venv_dir }}
    {{ venv_python }} -m pip install --upgrade pip
    {{ venv_python }} -m pip install -r {{ requirements }}
    {{ venv_python }} -c "from rpds import HashTrieMap"

# Reinstall deps with the venv interpreter (fixes wrong ABI wheels, e.g. rpds.cp314 in a 3.13 venv)
repair-venv:
    {{ venv_python }} -m pip install --upgrade pip
    {{ venv_python }} -m pip install --force-reinstall -r {{ requirements }}
    {{ venv_python }} -c "from rpds import HashTrieMap"

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
    {{ venv_python }} {{ fixtures_script }}

# Print resolved registry bundle and CLI path
resolve:
    just foundry cli resolve

# Validate foundry.yaml on the test fixture application workspace
validate-app:
    just foundry-ws {{ fixture_app }} config validate
