from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from market_evidence.analysis_publisher import publish_candidate


COMMIT_SHA = re.compile(r"^[a-f0-9]{40}$")
CANDIDATE_PATH = re.compile(r"^ai-inbox/[0-9]{4}-[0-9]{2}-[0-9]{2}\.json$")


class CandidateDiscoveryError(RuntimeError):
    """Raised when a candidate commit changes anything outside its one allowed file."""


def discover_candidate(repository: Path, head_sha: str) -> Path:
    repository = repository.resolve()
    if not COMMIT_SHA.fullmatch(head_sha):
        raise CandidateDiscoveryError("invalid candidate commit hash")

    completed = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "diff-tree",
            "--root",
            "--no-commit-id",
            "--name-status",
            "-r",
            "-z",
            head_sha,
        ],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise CandidateDiscoveryError("cannot inspect candidate commit")
    parts = completed.stdout.split(b"\0")
    if parts and parts[-1] == b"":
        parts.pop()
    if len(parts) != 2:
        raise CandidateDiscoveryError("candidate commit must change exactly one file")
    try:
        status = parts[0].decode("ascii")
        relative_path = parts[1].decode("utf-8")
    except UnicodeDecodeError as error:
        raise CandidateDiscoveryError("candidate commit path is invalid") from error
    if status not in {"A", "M"} or not CANDIDATE_PATH.fullmatch(relative_path):
        raise CandidateDiscoveryError("candidate commit may change only ai-inbox/YYYY-MM-DD.json")

    candidate = (repository / relative_path).resolve()
    try:
        candidate.relative_to(repository)
    except ValueError as error:
        raise CandidateDiscoveryError("candidate path escapes its repository") from error
    if not candidate.is_file():
        raise CandidateDiscoveryError("candidate file is missing")
    return candidate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and stage one untrusted AI candidate.")
    parser.add_argument("--candidate-repository", type=Path, required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candidate = discover_candidate(args.candidate_repository, args.head_sha)
    output = args.output.resolve()
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(args.public_root.resolve(), output)
    publish_candidate(candidate, output, published_at=datetime.now(timezone.utc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
