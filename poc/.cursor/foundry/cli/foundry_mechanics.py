"""
Foundry mechanical helpers — issue-key, git, build/test, config defaults, PRD sync.

Imported by foundry.py (call_shared). Prefer invoking via foundry.py CLI:

    python "{factory_root}/.cursor/foundry/cli/foundry.py" <command> ...

Stdout is JSON. Non-zero exit includes errorCode / message / recoverable.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

CONVENTIONAL_TITLE = re.compile(r"^(feat|fix|docs|refactor|test|chore)\(")
BROWSE_PATHS = [
    re.compile(r"/browse/([A-Z][A-Z0-9]+-\d+)(?:[/?#]|$)"),
    re.compile(r"/jira/software/projects/[^/]+/issues/([A-Z][A-Z0-9]+-\d+)(?:[/?#]|$)"),
    re.compile(r"/jira/browse/([A-Z][A-Z0-9]+-\d+)(?:[/?#]|$)"),
]
BARE_KEY = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
DEFAULT_PR_TITLE_PATTERN = "{issue_key} - {brief_description}"
DEFAULT_BRANCH_PATTERN = "{developer_first_name}/{issue_key}"
DEFAULT_STAGED_SECRETS_PATTERN = r"\.(env|key|pem)$|secrets\.json|creds\.md|\.env\."
OUTPUT_TAIL_CHARS = 4000

CONFIG_DEFAULTS: dict[str, Any] = {
    "devops": {
        "enabled": True,
        "run_before_pr": True,
        "auto_refresh_same_tag": True,
    },
    "review": {
        "enabled": True,
        "run_before_pr": True,
        "mode": "both",
        "diff": "branch changes",
    },
    "story_writer": {
        "enabled": True,
        "run_on_jira": True,
        "run_on_free_text": True,
        "require_full_ac_presentation": True,
    },
    "builders": {"enabled": True},
    "analysis": {"enabled": True},
    "jira": {"pick_list_max_results": 50, "enabled": True},
    "git": {
        "pr_title_pattern": DEFAULT_PR_TITLE_PATTERN,
        "feature_branch_pattern": DEFAULT_BRANCH_PATTERN,
        "default_branch": "",
        "staged_secrets_check": {
            "enabled": True,
            "pattern": None,
            "extra_patterns": [],
        },
    },
}

ROLE_KEYS: dict[str, list[str] | None] = {
    "parent": None,
    "backend-builder": [
        "templates.implement",
        "templates.add_tests",
        "templates.run_tests",
        "app_folder",
        "factory_root",
    ],
    "client-builder": [
        "templates.implement",
        "templates.add_tests",
        "templates.run_tests",
        "app_folder",
        "factory_root",
    ],
    "feature-builder": [
        "templates.implement",
        "templates.add_tests",
        "templates.run_tests",
        "app_folder",
        "factory_root",
    ],
    "devops-builder": ["devops", "org.display_name", "app_folder", "factory_root"],
    "documentation-writer": [
        "templates.documentation_workflow",
        "templates.sync_prd_caller",
        "templates.sync_prd_step",
        "templates.sync_prd_validate_script",
        "templates.sync_prd_validate_script_posix",
        "analysis",
        "app_folder",
        "factory_root",
    ],
    "story-writer": [
        "org.required_labels",
        "jira.project_key",
        "story_writer",
        "analysis",
        "bug_squash",
        "app_folder",
        "factory_root",
    ],
    "codebase-researcher": ["app_folder", "factory_root"],
    "implementation-validator": [
        "org.required_labels",
        "jira.project_key",
        "app_folder",
        "factory_root",
    ],
    "build-with-tests": [
        "templates.implement",
        "templates.add_tests",
        "templates.run_tests",
        "app_folder",
        "factory_root",
    ],
    # Slash commands — minimal slices via factory-bootstrap (see command-bootstrap.md)
    "ticket-workflow": [
        "atlassian",
        "jira",
        "git",
        "jira_transitions",
        "workspace",
        "templates.create_branch",
        "templates.implement",
        "templates.add_tests",
        "templates.run_tests",
        "templates.update_docs",
        "templates.generate_prd",
        "templates.code_review",
        "templates.commit_push",
        "app_folder",
        "factory_root",
    ],
    "documentation-workflow": [
        "workspace",
        "templates.documentation_workflow",
        "templates.generate_prd",
        "templates.update_docs",
        "templates.sync_prd_caller",
        "templates.sync_prd_step",
        "templates.sync_prd_validate_script",
        "templates.sync_prd_validate_script_posix",
        "app_folder",
        "factory_root",
    ],
}


class FactoryError(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        recoverable: bool = True,
        required_input: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.recoverable = recoverable
        self.required_input = required_input
        self.extra = extra or {}


def emit_success(payload: dict[str, Any]) -> int:
    out = {"success": True, **payload}
    sys.stdout.write(json.dumps(out, indent=2) + "\n")
    return 0


def emit_error(exc: FactoryError) -> int:
    payload: dict[str, Any] = {
        "success": False,
        "errorCode": exc.error_code,
        "message": exc.message,
        "recoverable": exc.recoverable,
    }
    if exc.required_input:
        payload["requiredInput"] = exc.required_input
    payload.update(exc.extra)
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return 1


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def extract_yaml_fence(markdown: str) -> str:
    match = re.search(r"```ya?ml\s*\n(.*?)```", markdown, re.DOTALL | re.IGNORECASE)
    if not match:
        raise FactoryError("INVALID_YAML", "No YAML fence found in team-variables.md.")
    return match.group(1)


def parse_team_variables_markdown(markdown: str) -> dict[str, Any]:
    if yaml is None:
        raise FactoryError(
            "MISSING_DEPENDENCY",
            "PyYAML is required. pip install -r .cursor/foundry/cli/requirements.txt",
            recoverable=True,
            required_input="pyyaml",
        )
    try:
        data = yaml.safe_load(extract_yaml_fence(markdown))
    except yaml.YAMLError as exc:
        raise FactoryError("INVALID_YAML", f"YAML parse failed: {exc}") from exc
    if not isinstance(data, dict):
        raise FactoryError("INVALID_YAML", "YAML fence did not contain a mapping.")
    return apply_defaults(data)


def apply_defaults(data: dict[str, Any]) -> dict[str, Any]:
    return deep_merge(CONFIG_DEFAULTS, data)


def nested_get(data: dict[str, Any], dotted: str) -> Any:
    current: Any = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def nested_set(target: dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    current = target
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def resolve_template_paths(data: dict[str, Any], factory_root: Path) -> dict[str, Any]:
    templates = data.get("templates")
    if not isinstance(templates, dict):
        return data
    resolve_from_org = nested_get(data, "workspace.resolve_templates_from_org")
    if resolve_from_org is False:
        return data
    resolved = dict(templates)
    for key, value in templates.items():
        if isinstance(value, str) and not os.path.isabs(value):
            resolved[key] = str((factory_root / value).resolve()) if (factory_root / value).exists() else str(factory_root / value)
    data = dict(data)
    data["templates"] = resolved
    return data


def locate_team_variables(factory_root: Path | None) -> Path:
    """Legacy markdown team-variables lookup (mechanics tests / bootstrap).

    Runtime Foundry config uses YAML profiles under `.cursor/foundry/profiles/`.
    """
    candidates: list[Path] = []
    if factory_root is not None:
        candidates.append(factory_root / ".cursor" / "foundry" / "team-variables.md")
        candidates.append(factory_root / ".cursor" / "factory" / "team-variables.md")
    env_name = os.environ.get("GITHUB_PRIVATE")
    if env_name:
        candidates.append(Path(env_name) / ".cursor" / "foundry" / "team-variables.md")
        candidates.append(Path(env_name) / ".cursor" / "factory" / "team-variables.md")
    here = Path(__file__).resolve()
    # cli -> foundry -> .cursor -> repo root
    plugin_root = here.parents[3]
    candidates.append(plugin_root / ".cursor" / "foundry" / "team-variables.md")
    candidates.append(plugin_root / ".cursor" / "factory" / "team-variables.md")
    for path in candidates:
        if path.is_file():
            return path
    raise FactoryError(
        "MISSING_TEAM_VARIABLES",
        "team-variables.md not found. Pass --factory-root or use a Foundry YAML profile.",
        required_input="factoryRoot",
    )


def slice_role(
    data: dict[str, Any],
    role: str,
    *,
    app_folder: str | None,
    factory_root: str | None,
) -> dict[str, Any]:
    if role not in ROLE_KEYS:
        raise FactoryError("UNKNOWN_ROLE", f"Unknown role: {role}", required_input="role")
    payload: dict[str, Any] = {"role": role}
    if app_folder:
        payload["app_folder"] = app_folder
    if factory_root:
        payload["factory_root"] = factory_root
    keys = ROLE_KEYS[role]
    if keys is None:
        merged = dict(data)
        payload.update(merged)
        payload["role"] = role
        if app_folder:
            payload["app_folder"] = app_folder
        if factory_root:
            payload["factory_root"] = factory_root
        return payload
    for dotted in keys:
        if dotted in ("app_folder", "factory_root"):
            continue
        value = nested_get(data, dotted)
        if value is not None:
            nested_set(payload, dotted, value)
    return payload


def config_get(factory_root: Path, role: str, app_folder: str | None) -> dict[str, Any]:
    path = locate_team_variables(factory_root)
    text = path.read_text(encoding="utf-8")
    data = parse_team_variables_markdown(text)
    data = resolve_template_paths(data, factory_root)
    return slice_role(
        data,
        role,
        app_folder=app_folder,
        factory_root=str(factory_root),
    )


def parse_issue_key(text: str, pattern: str | None) -> str:
    found: str | None = None
    for compiled in BROWSE_PATHS:
        match = compiled.search(text)
        if match:
            found = match.group(1)
            break
    if found is None:
        match = BARE_KEY.search(text)
        if match:
            found = match.group(1)
    if not found:
        raise FactoryError(
            "MISSING_ISSUE_KEY",
            "No Jira issue key found in the given text.",
            required_input="issueKey",
        )
    if pattern:
        if not re.search(pattern, found):
            raise FactoryError(
                "INVALID_ISSUE_KEY",
                f"Issue key {found} does not match pattern {pattern}.",
                required_input="issueKey",
            )
    return found


def brief_description(summary: str) -> str:
    text = summary.strip()
    if len(text) <= 72:
        return text
    clipped = text[:72]
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return clipped.rstrip(" .,;:")


def build_pr_title(
    *,
    issue_key: str | None,
    summary: str,
    pattern: str | None,
    jira_enabled: bool,
) -> str:
    if jira_enabled and not issue_key:
        raise FactoryError(
            "MISSING_ISSUE_KEY",
            "Jira mode requires an issue key before PR creation.",
            required_input="issueKey",
        )
    if not jira_enabled and not issue_key:
        title = summary.strip()
    else:
        resolved_pattern = pattern or DEFAULT_PR_TITLE_PATTERN
        title = resolved_pattern.replace("{issue_key}", issue_key or "").replace(
            "{brief_description}", brief_description(summary)
        )
    if CONVENTIONAL_TITLE.match(title) or re.search(
        r"^(feat|fix|docs|refactor|test|chore)\([^)]*\):", title
    ):
        raise FactoryError(
            "INVALID_CONVENTIONAL_COMMIT_TITLE",
            "PR title must not use a conventional-commit prefix. Rebuild from the Jira summary.",
            required_input="summary",
        )
    return title


def expand_branch_name(
    pattern: str,
    *,
    developer_first_name: str,
    issue_key: str,
) -> str:
    name = pattern.replace("{developer_first_name}", developer_first_name).replace(
        "{issue_key}", issue_key
    )
    return name


def last_path_segment(ref: str) -> str:
    return ref.rstrip("/").split("/")[-1]


GitRunner = Callable[[list[str], Path], subprocess.CompletedProcess[str]]


def default_git_runner(args: list[str], repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def git_default_branch(repo: Path, runner: GitRunner = default_git_runner) -> str:
    result = runner(["git", "rev-parse", "--abbrev-ref", "origin/HEAD"], repo)
    if result.returncode == 0 and result.stdout.strip():
        return last_path_segment(result.stdout.strip())
    for name in ("main", "master"):
        probe = runner(
            ["git", "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{name}"],
            repo,
        )
        if probe.returncode == 0:
            return name
    for name in ("main", "master"):
        probe = runner(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{name}"],
            repo,
        )
        if probe.returncode == 0:
            return name
    raise FactoryError(
        "DEFAULT_BRANCH_NOT_FOUND",
        "Could not resolve the default branch (origin/HEAD or local/remote main/master).",
        required_input="repo",
    )


def branch_create(
    repo: Path,
    name: str,
    runner: GitRunner = default_git_runner,
    *,
    start_point: str | None = None,
) -> dict[str, Any]:
    if not name:
        raise FactoryError("MISSING_BRANCH_NAME", "branch create requires --name.", required_input="name")
    base = (start_point or "").strip() or None
    default = base or git_default_branch(repo, runner)
    current = runner(["git", "branch", "--show-current"], repo)
    current_name = (current.stdout or "").strip()
    if current_name == name:
        head = runner(["git", "rev-parse", "HEAD"], repo)
        if head.returncode != 0:
            raise FactoryError("GIT_HEAD_FAILED", head.stderr.strip() or "git rev-parse HEAD failed")
        return {
            "branch": name,
            "default_branch": default,
            "head": head.stdout.strip(),
            "created": False,
            "already_checked_out": True,
            "start_point": base,
        }
    if current_name != default:
        checkout = runner(["git", "checkout", default], repo)
        if checkout.returncode != 0:
            raise FactoryError(
                "GIT_CHECKOUT_FAILED",
                checkout.stderr.strip() or f"git checkout {default} failed",
            )
    if base is None:
        pull = runner(["git", "pull", "origin", default], repo)
        if pull.returncode != 0:
            raise FactoryError(
                "GIT_PULL_FAILED",
                pull.stderr.strip() or f"git pull origin {default} failed",
            )
    create = runner(["git", "checkout", "-b", name], repo)
    if create.returncode != 0:
        raise FactoryError(
            "GIT_BRANCH_CREATE_FAILED",
            create.stderr.strip() or f"git checkout -b {name} failed",
        )
    head = runner(["git", "rev-parse", "HEAD"], repo)
    if head.returncode != 0:
        raise FactoryError("GIT_HEAD_FAILED", head.stderr.strip() or "git rev-parse HEAD failed")
    return {
        "branch": name,
        "default_branch": default,
        "head": head.stdout.strip(),
        "created": True,
        "already_checked_out": False,
        "start_point": base,
    }


def git_snapshot(repo: Path, runner: GitRunner = default_git_runner) -> dict[str, str]:
    commands = {
        "branch": ["git", "branch", "--show-current"],
        "head": ["git", "rev-parse", "HEAD"],
        "index_tree": ["git", "write-tree"],
    }
    result: dict[str, str] = {}
    for key, argv in commands.items():
        completed = runner(argv, repo)
        if completed.returncode != 0 or not completed.stdout.strip():
            raise FactoryError(
                "GIT_SNAPSHOT_FAILED",
                completed.stderr.strip() or f"{' '.join(argv)} failed",
                extra={"field": key},
            )
        result[key] = completed.stdout.strip()
    return result


def load_factory_data(factory_root: Path) -> dict[str, Any]:
    path = locate_team_variables(factory_root)
    return parse_team_variables_markdown(path.read_text(encoding="utf-8"))


def staged_secrets_config(data: dict[str, Any]) -> dict[str, Any]:
    git = data.get("git")
    if not isinstance(git, dict):
        return dict(CONFIG_DEFAULTS["git"]["staged_secrets_check"])
    check = git.get("staged_secrets_check")
    if not isinstance(check, dict):
        return dict(CONFIG_DEFAULTS["git"]["staged_secrets_check"])
    return deep_merge(CONFIG_DEFAULTS["git"]["staged_secrets_check"], check)


def compile_staged_secrets_patterns(
    config: dict[str, Any],
    *,
    pattern_override: str | None = None,
) -> list[re.Pattern[str]]:
    if pattern_override:
        raw_patterns = [pattern_override]
    elif config.get("pattern"):
        raw_patterns = [str(config["pattern"])]
    else:
        raw_patterns = [DEFAULT_STAGED_SECRETS_PATTERN]
        extras = config.get("extra_patterns") or []
        if not isinstance(extras, list):
            raise FactoryError(
                "INVALID_CONFIG",
                "git.staged_secrets_check.extra_patterns must be a list.",
            )
        raw_patterns.extend(str(pattern) for pattern in extras if pattern)

    compiled: list[re.Pattern[str]] = []
    for pattern in raw_patterns:
        try:
            compiled.append(re.compile(pattern))
        except re.error as exc:
            raise FactoryError(
                "INVALID_REGEX",
                f"Invalid staged-secrets pattern {pattern!r}: {exc}",
            ) from exc
    return compiled


def git_staged_secrets_check(
    repo: Path,
    factory_root: Path,
    *,
    pattern_override: str | None = None,
    runner: GitRunner = default_git_runner,
) -> dict[str, Any]:
    config = staged_secrets_config(load_factory_data(factory_root))
    if config.get("enabled") is False:
        return {"passed": True, "skipped": True, "reason": "git.staged_secrets_check.enabled is false"}

    compiled = compile_staged_secrets_patterns(config, pattern_override=pattern_override)
    result = runner(["git", "diff", "--cached", "--name-only"], repo)
    if result.returncode != 0:
        raise FactoryError(
            "GIT_DIFF_FAILED",
            result.stderr.strip() or "git diff --cached --name-only failed",
        )

    staged = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    blocked = [path for path in staged if any(pattern.search(path) for pattern in compiled)]
    if blocked:
        raise FactoryError(
            "STAGED_SECRETS",
            "Blocked: commit includes sensitive staged paths: " + ", ".join(blocked),
            extra={"blockedPaths": blocked, "stagedCount": len(staged)},
        )

    return {
        "passed": True,
        "stagedCount": len(staged),
        "patternCount": len(compiled),
        "usedDefault": pattern_override is None and not config.get("pattern"),
    }


def delivery_check(state: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []

    def require(cond: bool, code: str, message: str) -> None:
        if not cond:
            failures.append(f"{code}: {message}")

    require(state.get("step6_approved") is True, "STEP6", "Human must approve implementation for documentation + ship.")
    require(
        state.get("step7_doc_change_report") == "received" and state.get("step7_human_approved") is True,
        "STEP7",
        "DocChangeReport must be received and human-approved.",
    )
    if state.get("prd_created_or_updated"):
        require(state.get("sync_prd_ok") is True, "SYNC_PRD", "prd-sync validate must exit 0 when a PRD was created or updated.")
    if state.get("devops_enabled") and state.get("devops_run_before_pr"):
        require(
            state.get("step7b_report") == "received" and state.get("step7b_approved") is True,
            "STEP7B",
            "devops-builder pre_pr_review must complete and be approved.",
        )
    if state.get("review_enabled") and state.get("review_run_before_pr"):
        require(
            state.get("step7c_report") == "received" and state.get("step7c_approved") is True,
            "STEP7C",
            "Pre-PR review report must be received and approved.",
        )
    require(state.get("feature_branch_ok") is True, "FEATURE_BRANCH", "Feature branch must be checked out (not the default branch).")
    require(isinstance(state.get("pr_extras_register"), list), "PR_EXTRAS", "pr_extras_register must be an array (empty allowed).")

    if failures:
        raise FactoryError(
            "DELIVERY_GATES_FAILED",
            "Delivery gates failed: " + "; ".join(failures),
            recoverable=True,
            required_input="state",
        )
    return {"passed": True, "gates": ["step6", "step7", "sync_prd", "step7b", "step7c", "feature_branch", "pr_extras"]}


def prd_sync_validate(repo: Path, factory_root: Path) -> dict[str, Any]:
    scripts = factory_root / ".cursor" / "foundry" / "scripts"
    if os.name == "nt":
        script = scripts / "validate-sync-prd-caller.ps1"
        args = ["powershell", "-NoProfile", "-File", str(script)]
    else:
        script = scripts / "validate-sync-prd-caller.sh"
        args = ["bash", str(script)]
    if not script.is_file():
        raise FactoryError("MISSING_PRD_SYNC_SCRIPT", f"Validator not found: {script}")
    result = subprocess.run(args, cwd=repo, capture_output=True, text=True, check=False)
    ok = result.returncode == 0
    payload = {
        "exitCode": result.returncode,
        "command": args,
        "outputTail": ((result.stdout or "") + (result.stderr or ""))[-OUTPUT_TAIL_CHARS:],
    }
    if not ok:
        raise FactoryError(
            "PRD_SYNC_INVALID",
            payload["outputTail"] or "validate-sync-prd-caller failed",
            extra=payload,
        )
    payload["passed"] = True
    return payload


def run_manifest_command(
    app_folder: Path,
    command_name: str,
    command: dict[str, Any],
    runner: Callable[[list[str], Path], subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, Any]:
    argv = command.get("argv")
    cwd_value = command.get("cwd")
    timeout_seconds = command.get("timeout_seconds")
    if not isinstance(argv, list) or not argv or not all(
        isinstance(part, str) and part for part in argv
    ):
        raise FactoryError(
            "APP_MANIFEST_SNAPSHOT_INVALID",
            f"Snapshot command {command_name!r} has invalid argv.",
        )
    if not isinstance(cwd_value, str) or not cwd_value:
        raise FactoryError(
            "APP_MANIFEST_SNAPSHOT_INVALID",
            f"Snapshot command {command_name!r} has invalid cwd.",
        )
    if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool):
        raise FactoryError(
            "APP_MANIFEST_SNAPSHOT_INVALID",
            f"Snapshot command {command_name!r} has invalid timeout_seconds.",
        )
    root = app_folder.resolve()
    cwd = (root / cwd_value).resolve()
    try:
        cwd.relative_to(root)
    except ValueError as exc:
        raise FactoryError(
            "APP_MANIFEST_CWD_UNSAFE",
            f"Snapshot command {command_name!r} resolves outside the app folder.",
        ) from exc
    started = time.perf_counter()
    try:
        if runner is None:
            result = subprocess.run(
                argv,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
                shell=False,
            )
        else:
            result = runner(argv, cwd)
    except subprocess.TimeoutExpired as exc:
        raise FactoryError(
            "COMMAND_TIMEOUT",
            f"Manifest command {command_name!r} exceeded {timeout_seconds} seconds.",
            extra={
                "commandName": command_name,
                "argv": argv,
                "cwd": str(cwd),
                "timeoutSeconds": timeout_seconds,
            },
        ) from exc
    duration_ms = int((time.perf_counter() - started) * 1000)
    combined = (result.stdout or "") + (result.stderr or "")
    payload = {
        "command": shlex.join(argv),
        "commandName": command_name,
        "argv": argv,
        "cwd": str(cwd),
        "timeoutSeconds": timeout_seconds,
        "exitCode": result.returncode,
        "durationMilliseconds": duration_ms,
        "outputTail": combined[-OUTPUT_TAIL_CHARS:],
        "warnings": [],
    }
    if result.returncode != 0:
        raise FactoryError(
            "COMMAND_FAILED",
            payload["outputTail"]
            or f"{command_name} failed with exit {result.returncode}",
            extra=payload,
        )
    return payload


def load_state(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FactoryError("INVALID_STATE", f"Could not read run-state JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise FactoryError("INVALID_STATE", "Run-state must be a JSON object.")
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="foundry.py", description="Factory parent CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    cfg = sub.add_parser("config")
    cfg_sub = cfg.add_subparsers(dest="config_command", required=True)
    cfg_get = cfg_sub.add_parser("get")
    cfg_get.add_argument("--factory-root", required=True)
    cfg_get.add_argument("--role", required=True)
    cfg_get.add_argument("--app-folder", default=None)

    issue = sub.add_parser("issue-key")
    issue_sub = issue.add_subparsers(dest="issue_command", required=True)
    issue_parse = issue_sub.add_parser("parse")
    issue_parse.add_argument("--text", required=True)
    issue_parse.add_argument("--pattern", default=None)

    pr = sub.add_parser("pr-title")
    pr.add_argument("--issue-key", default=None)
    pr.add_argument("--summary", required=True)
    pr.add_argument("--pattern", default=None)
    pr.add_argument(
        "--jira-enabled",
        default="true",
        choices=("true", "false"),
        help="true (default) requires --issue-key; false uses --summary as the full title",
    )

    git = sub.add_parser("git")
    git_sub = git.add_subparsers(dest="git_command", required=True)
    git_db = git_sub.add_parser("default-branch")
    git_db.add_argument("--repo", required=True)
    git_secrets = git_sub.add_parser("staged-secrets-check")
    git_secrets.add_argument("--repo", required=True)
    git_secrets.add_argument("--factory-root", required=True)
    git_secrets.add_argument(
        "--pattern",
        default=None,
        help="Replace team-variables patterns (tests/debug only)",
    )

    branch_name = sub.add_parser("branch-name")
    branch_name.add_argument("--pattern", required=True)
    branch_name.add_argument("--developer-first-name", required=True)
    branch_name.add_argument("--issue-key", required=True)

    branch = sub.add_parser("branch")
    branch_sub = branch.add_subparsers(dest="branch_command", required=True)
    branch_create_p = branch_sub.add_parser("create")
    branch_create_p.add_argument("--repo", required=True)
    branch_create_p.add_argument("--name", required=True)
    branch_create_p.add_argument(
        "--start-point",
        default=None,
        help="Create the feature branch from this ref instead of the detected default branch. Skips pull.",
    )

    delivery = sub.add_parser("delivery-check")
    delivery.add_argument("--state", required=True)

    prd = sub.add_parser("prd-sync")
    prd_sub = prd.add_subparsers(dest="prd_command", required=True)
    prd_val = prd_sub.add_parser("validate")
    prd_val.add_argument("--repo", required=True)
    prd_val.add_argument("--factory-root", required=True)

    return parser


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "config" and args.config_command == "get":
        return config_get(Path(args.factory_root), args.role, args.app_folder)
    if args.command == "issue-key" and args.issue_command == "parse":
        key = parse_issue_key(args.text, args.pattern)
        return {"issue_key": key}
    if args.command == "pr-title":
        title = build_pr_title(
            issue_key=args.issue_key,
            summary=args.summary,
            pattern=args.pattern,
            jira_enabled=args.jira_enabled == "true",
        )
        return {"title": title}
    if args.command == "git" and args.git_command == "default-branch":
        branch = git_default_branch(Path(args.repo))
        return {"default_branch": branch}
    if args.command == "git" and args.git_command == "staged-secrets-check":
        return git_staged_secrets_check(
            Path(args.repo),
            Path(args.factory_root),
            pattern_override=args.pattern,
        )
    if args.command == "branch-name":
        name = expand_branch_name(
            args.pattern,
            developer_first_name=args.developer_first_name,
            issue_key=args.issue_key,
        )
        return {"branch": name}
    if args.command == "branch" and args.branch_command == "create":
        return branch_create(
            Path(args.repo),
            args.name,
            start_point=getattr(args, "start_point", None),
        )
    if args.command == "delivery-check":
        return delivery_check(load_state(Path(args.state)))
    if args.command == "prd-sync" and args.prd_command == "validate":
        return prd_sync_validate(Path(args.repo), Path(args.factory_root))
    raise FactoryError("UNKNOWN_COMMAND", f"Unhandled command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = dispatch(args)
        return emit_success(payload)
    except FactoryError as exc:
        return emit_error(exc)


if __name__ == "__main__":
    sys.exit(main())
