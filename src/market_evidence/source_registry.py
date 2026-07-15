"""Validation and loading for audited public market-data sources."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_REGISTRY_PATH = REPOSITORY_ROOT / "config" / "sources.json"
DIRECTION_REGISTRY_PATH = REPOSITORY_ROOT / "config" / "directions.json"

SOURCE_ID_PATTERN = re.compile(r"^[a-z0-9_]+$")
ALLOWED_POLICIES = {"publish_raw", "publish_derived_only", "link_only", "blocked"}
ALLOWED_KINDS = {"official_metadata", "market_data"}


class SourceRegistryError(ValueError):
    """Raised when source coverage or redistribution boundaries are unsafe."""


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_source_registry(document: dict[str, Any]) -> None:
    if not isinstance(document, dict):
        raise SourceRegistryError("source registry must be a JSON object")
    for key in ("schema_version", "audit_version", "audited_at", "sources", "direction_sources"):
        if key not in document:
            raise SourceRegistryError(f"source registry missing {key}")

    sources: dict[str, dict[str, Any]] = {}
    for source in document["sources"]:
        source_id = source.get("id")
        if not isinstance(source_id, str) or not SOURCE_ID_PATTERN.fullmatch(source_id):
            raise SourceRegistryError(f"invalid source id: {source_id!r}")
        if source_id in sources:
            raise SourceRegistryError(f"duplicate source id: {source_id}")
        if source.get("kind") not in ALLOWED_KINDS:
            raise SourceRegistryError(f"{source_id} has invalid kind")
        if source.get("redistribution_policy") not in ALLOWED_POLICIES:
            raise SourceRegistryError(f"{source_id} has invalid redistribution policy")
        if not str(source.get("terms_url", "")).startswith("https://"):
            raise SourceRegistryError(f"{source_id} must have an HTTPS terms URL")
        if not 1 <= source.get("timeout_seconds", 0) <= 30:
            raise SourceRegistryError(f"{source_id} timeout is outside the safety bound")
        if not 1 <= source.get("max_attempts", 0) <= 3:
            raise SourceRegistryError(f"{source_id} retry count is outside the safety bound")
        sources[source_id] = source

    seen_directions: set[str] = set()
    for direction in document["direction_sources"]:
        direction_id = direction.get("direction_id")
        if not isinstance(direction_id, str) or not SOURCE_ID_PATTERN.fullmatch(direction_id):
            raise SourceRegistryError(f"invalid direction id: {direction_id!r}")
        if direction_id in seen_directions:
            raise SourceRegistryError(f"duplicate direction source entry: {direction_id}")
        seen_directions.add(direction_id)

        official_source_id = direction.get("official_source_id")
        if official_source_id not in sources:
            raise SourceRegistryError(f"{direction_id} references unknown official source")
        official_source = sources[official_source_id]
        if official_source["kind"] != "official_metadata":
            raise SourceRegistryError(f"{direction_id} official source has the wrong kind")
        if official_source["redistribution_policy"] != "link_only":
            raise SourceRegistryError(f"{direction_id} official metadata must remain link-only")
        if not str(direction.get("official_url", "")).startswith("https://"):
            raise SourceRegistryError(f"{direction_id} official URL must use HTTPS")

        chain = direction.get("data_source_chain")
        if not isinstance(chain, list) or len(chain) < 2:
            raise SourceRegistryError(f"{direction_id} needs at least two data fallbacks")
        if len(chain) != len(set(chain)):
            raise SourceRegistryError(f"{direction_id} data source chain contains duplicates")
        for source_id in chain:
            if source_id not in sources:
                raise SourceRegistryError(f"{direction_id} references unknown source {source_id}")
            source = sources[source_id]
            if source["kind"] != "market_data":
                raise SourceRegistryError(f"{direction_id} chain contains non-data source {source_id}")
            if source["redistribution_policy"] in {"blocked", "link_only"}:
                raise SourceRegistryError(f"{direction_id} chain contains unusable source {source_id}")


def audit_source_coverage(
    source_registry: dict[str, Any] | None = None,
    direction_registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_registry = source_registry or load_json(SOURCE_REGISTRY_PATH)
    direction_registry = direction_registry or load_json(DIRECTION_REGISTRY_PATH)
    validate_source_registry(source_registry)

    expected_ids = [
        direction["id"]
        for category in direction_registry["categories"]
        for direction in category["directions"]
    ]
    covered_ids = [entry["direction_id"] for entry in source_registry["direction_sources"]]
    if covered_ids != expected_ids:
        raise SourceRegistryError("source coverage order must exactly match the locked direction registry")

    proxy_codes = [
        direction["primary_proxy_code"]
        for category in direction_registry["categories"]
        for direction in category["directions"]
    ]
    if any(not code for code in proxy_codes) or len(proxy_codes) != len(set(proxy_codes)):
        raise SourceRegistryError("primary proxy codes must be present and unique")

    return {
        "directions": len(expected_ids),
        "sources": len(source_registry["sources"]),
        "minimum_fallbacks": min(
            len(entry["data_source_chain"]) for entry in source_registry["direction_sources"]
        ),
        "audit_version": source_registry["audit_version"],
    }
