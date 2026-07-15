from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def create_repository(tmp_path: Path, *, extra_file: bool = False) -> tuple[Path, str]:
    repository = tmp_path / "candidate-repository"
    repository.mkdir()
    git(repository, "init", "--initial-branch=chatgpt-inbox")
    git(repository, "config", "user.name", "candidate-test")
    git(repository, "config", "user.email", "candidate@example.invalid")
    inbox = repository / "ai-inbox"
    inbox.mkdir()
    (inbox / "2026-07-15.json").write_text("{}\n", encoding="utf-8")
    if extra_file:
        workflow = repository / ".github" / "workflows"
        workflow.mkdir(parents=True)
        (workflow / "attack.yml").write_text("name: untrusted\n", encoding="utf-8")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "candidate")
    return repository, git(repository, "rev-parse", "HEAD")


def test_discovery_accepts_one_date_named_candidate(tmp_path: Path) -> None:
    from scripts.validate_ai_candidate import discover_candidate

    repository, head_sha = create_repository(tmp_path)

    assert discover_candidate(repository, head_sha) == (
        repository / "ai-inbox" / "2026-07-15.json"
    ).resolve()


def test_discovery_rejects_candidate_commit_that_changes_workflow_code(tmp_path: Path) -> None:
    from scripts.validate_ai_candidate import CandidateDiscoveryError, discover_candidate

    repository, head_sha = create_repository(tmp_path, extra_file=True)

    with pytest.raises(CandidateDiscoveryError, match="exactly one"):
        discover_candidate(repository, head_sha)
