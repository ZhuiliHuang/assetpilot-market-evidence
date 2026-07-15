from __future__ import annotations

import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PUBLIC_FILES = {
    Path("README.md"),
    Path(".gitignore"),
    Path("pyproject.toml"),
    Path("src/market_evidence/__init__.py"),
    Path(".github/workflows/ci.yml"),
}

FORBIDDEN_PATH_PARTS = {
    "assetpilot.sqlite3",
    "backend/data",
    "screenshots",
    "private-logs",
}

FORBIDDEN_TEXT_KEYS = {
    "portfolio_id",
    "account_id",
    "cost_basis",
    "position_quantity",
    "asset_total",
    "wind_api_key",
    "openai_api_key",
}

SECRET_PATTERNS = {
    "GitHub token": re.compile(r"(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{20,}"),
    "OpenAI token": re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    "assigned secret": re.compile(
        r"(?i)(?:openai|wind|github)[_-]?(?:api[_-]?)?(?:key|token)\s*[:=]\s*[^\s$][^\s]*"
    ),
}

TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}

IGNORED_TOP_LEVEL = {".git", ".pytest_cache", ".venv", "build", "dist", "tests"}


def public_repository_files() -> list[Path]:
    return [
        path
        for path in REPOSITORY_ROOT.rglob("*")
        if path.is_file()
        and not set(path.relative_to(REPOSITORY_ROOT).parts) & IGNORED_TOP_LEVEL
    ]


def test_required_public_repository_skeleton_exists() -> None:
    missing = sorted(
        str(path) for path in REQUIRED_PUBLIC_FILES if not (REPOSITORY_ROOT / path).is_file()
    )

    assert not missing, f"missing required public files: {missing}"


def test_public_repository_paths_do_not_contain_private_artifacts() -> None:
    violations: list[str] = []
    for path in public_repository_files():
        normalized = path.relative_to(REPOSITORY_ROOT).as_posix().lower()
        for forbidden in FORBIDDEN_PATH_PARTS:
            if forbidden in normalized:
                violations.append(f"{normalized}: contains forbidden path marker {forbidden!r}")

    assert not violations, "\n".join(violations)


def test_public_repository_text_does_not_contain_private_fields_or_secrets() -> None:
    violations: list[str] = []
    for path in public_repository_files():
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        content = path.read_text(encoding="utf-8").lower()
        relative_path = path.relative_to(REPOSITORY_ROOT).as_posix()
        for forbidden in FORBIDDEN_TEXT_KEYS:
            if forbidden in content:
                violations.append(f"{relative_path}: contains forbidden field {forbidden!r}")
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                violations.append(f"{relative_path}: contains a possible {label}")

    assert not violations, "\n".join(violations)
