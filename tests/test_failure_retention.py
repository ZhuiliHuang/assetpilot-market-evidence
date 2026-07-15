from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_total_failure_does_not_change_last_valid_publication(tmp_path: Path) -> None:
    from scripts.update_market_data import update_public_tree

    destination = tmp_path / "public"
    update_public_tree(
        destination,
        now=datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc),
        fixture_mode=True,
    )
    before = digest(destination / "manifest.json")

    changed = update_public_tree(
        destination,
        now=datetime(2026, 7, 16, 12, 30, tzinfo=timezone.utc),
        fixture_mode=True,
        total_failure=True,
    )

    assert changed is False
    assert digest(destination / "manifest.json") == before


def test_invalid_staged_tree_is_rejected_without_replacing_destination(tmp_path: Path) -> None:
    from scripts.publish_data_branch import PublicationError, publish_validated_tree
    from scripts.update_market_data import update_public_tree

    destination = tmp_path / "public"
    update_public_tree(
        destination,
        now=datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc),
        fixture_mode=True,
    )
    before = digest(destination / "manifest.json")
    invalid = tmp_path / "invalid"
    invalid.mkdir()

    try:
        publish_validated_tree(invalid, destination)
    except PublicationError:
        pass
    else:
        raise AssertionError("invalid tree should not publish")

    assert digest(destination / "manifest.json") == before
