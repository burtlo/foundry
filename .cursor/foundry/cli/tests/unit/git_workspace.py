"""Initialize a clean git worktree for hook tests."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Foundry Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Foundry Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
    )
    return env


def init_clean_git_repo(workspace: Path) -> None:
    env = _git_env()
    subprocess.run(["git", "init", "-b", "main"], cwd=workspace, check=True, capture_output=True, env=env)
    (workspace / "README.md").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=workspace, check=True, capture_output=True, env=env)
    subprocess.run(
        ["git", "commit", "-m", "test fixture"],
        cwd=workspace,
        check=True,
        capture_output=True,
        env=env,
    )


def ensure_clean_git_workspace(workspace: Path) -> None:
    """Commit all tracked/untracked files so validate_git_clean_execute passes."""
    env = _git_env()
    if not (workspace / ".git").is_dir():
        init_clean_git_repo(workspace)
        return
    subprocess.run(["git", "add", "-A"], cwd=workspace, check=True, capture_output=True, env=env)
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    if status.stdout.strip():
        subprocess.run(
            ["git", "commit", "-m", "test fixture update"],
            cwd=workspace,
            check=True,
            capture_output=True,
            env=env,
        )
