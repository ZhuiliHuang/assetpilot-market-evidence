from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def workflow_text(name: str) -> str:
    return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


def test_candidate_receiver_is_read_only_and_cannot_publish() -> None:
    workflow = workflow_text("candidate-received.yml")

    assert "chatgpt-inbox" in workflow
    assert "ai-inbox/*.json" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "contents: write" not in workflow
    assert "secrets:" not in workflow
    assert "git push" not in workflow


def test_trusted_publisher_uses_workflow_run_and_never_executes_candidate_code() -> None:
    workflow = workflow_text("publish-ai-analysis.yml")

    assert "workflow_run:" in workflow
    assert 'workflows: ["Candidate received"]' in workflow
    assert "github.event.workflow_run.head_branch == 'chatgpt-inbox'" in workflow
    assert "github.event.workflow_run.conclusion == 'success'" in workflow
    assert "ref: main" in workflow
    assert "ref: ${{ github.event.workflow_run.head_sha }}" in workflow
    assert "contents: write" in workflow
    assert "python trusted/scripts/validate_ai_candidate.py" in workflow
    assert "python candidate-source/" not in workflow
