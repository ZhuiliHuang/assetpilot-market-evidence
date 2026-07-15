"""Validate untrusted AI analysis candidates against published evidence."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

from market_evidence.package_builder import sha256_hex
from market_evidence.schema_validation import EvidenceValidationError, validate_document


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DIRECT_TRADING_TERMS = (
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "下单",
    "仓位",
    "止损",
    "止盈",
    "buy",
    "sell",
    "add position",
    "trim position",
    "place an order",
    "stop loss",
    "take profit",
)


class CandidateValidationError(ValueError):
    """Raised when an untrusted candidate cannot be promoted."""


@dataclass(frozen=True)
class ValidatedCandidate:
    evidence_version: str
    direction_ids: tuple[str, ...]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CandidateValidationError(f"invalid evidence document: {path.name}") from error
    if not isinstance(value, dict):
        raise CandidateValidationError(f"invalid evidence document: {path.name}")
    return value


def _known_direction_ids() -> set[str]:
    registry = _load_json(REPOSITORY_ROOT / "config" / "directions.json")
    return {
        direction["id"]
        for category in registry["categories"]
        for direction in category["directions"]
    }


def _iter_text(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _iter_text(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_text(child)


def _reject_trading_language(candidate: dict[str, Any]) -> None:
    for text in _iter_text(candidate):
        normalized = text.casefold()
        if "http://" in normalized or "https://" in normalized:
            raise CandidateValidationError("url text is not allowed; cite published source evidence")
        if any(term.casefold() in normalized for term in DIRECT_TRADING_TERMS):
            raise CandidateValidationError("trading language is not allowed in an AI candidate")


def _load_direction_packages(public_root: Path, manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    packages: dict[str, dict[str, Any]] = {}
    for category_entry in manifest["categories"]:
        category = _load_json(public_root / category_entry["package_path"])
        if sha256_hex(category) != category_entry["sha256"]:
            raise CandidateValidationError("hash mismatch in published category evidence")
        try:
            validate_document("market-category", category)
        except EvidenceValidationError as error:
            raise CandidateValidationError(f"invalid published category evidence: {error}") from error
        for direction_entry in category["directions"]:
            direction = _load_json(public_root / direction_entry["detail_path"])
            if sha256_hex(direction) != direction_entry["sha256"]:
                raise CandidateValidationError("hash mismatch in published direction evidence")
            try:
                validate_document("market-direction", direction)
            except EvidenceValidationError as error:
                raise CandidateValidationError(f"invalid published direction evidence: {error}") from error
            packages[direction["direction_id"]] = direction
    return packages


def _resolve_json_pointer(document: Any, pointer: str) -> Any:
    current = document
    for raw_part in pointer.split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and re.fullmatch(r"0|[1-9][0-9]*", part):
            index = int(part)
            if index >= len(current):
                raise KeyError(part)
            current = current[index]
        else:
            raise KeyError(part)
    return current


def _evidence_references(item: dict[str, Any]) -> Iterable[str]:
    for key in ("supporting_evidence_refs", "counter_evidence_refs", "evidence_refs"):
        yield from item.get(key, [])


def _validate_references(candidate: dict[str, Any], packages: dict[str, dict[str, Any]]) -> None:
    for item in (*candidate["focus_opportunities"], *candidate["risks"]):
        direction_id = item["direction_id"]
        package = packages.get(direction_id)
        if package is None:
            raise CandidateValidationError(f"unknown direction: {direction_id}")
        expected_prefix = f"directions/{direction_id}#/"
        references = tuple(_evidence_references(item))
        if item in candidate["focus_opportunities"]:
            if not any("/source_evidence/" in ref and ref.endswith("/url") for ref in references):
                raise CandidateValidationError("focus item requires a published source url reference")
            if not any("/source_evidence/" in ref and ref.endswith("/as_of") for ref in references):
                raise CandidateValidationError("focus item requires a published source date reference")
        for reference in references:
            if not reference.startswith(expected_prefix):
                raise CandidateValidationError(
                    f"reference must point to the same direction: {direction_id}"
                )
            pointer = reference[len(expected_prefix) :]
            try:
                resolved = _resolve_json_pointer(package, pointer)
            except (KeyError, TypeError) as error:
                raise CandidateValidationError(f"unresolved evidence reference: {reference}") from error
            if reference.endswith("/url"):
                parsed = urlsplit(resolved) if isinstance(resolved, str) else None
                if (
                    parsed is None
                    or parsed.scheme != "https"
                    or not parsed.hostname
                    or parsed.username is not None
                    or parsed.password is not None
                ):
                    raise CandidateValidationError(f"unsafe source url reference: {reference}")
            if reference.endswith("/as_of"):
                try:
                    date.fromisoformat(resolved)
                except (TypeError, ValueError) as error:
                    raise CandidateValidationError(f"invalid source date reference: {reference}") from error


def validate_candidate(candidate: dict[str, Any], public_root: Path) -> ValidatedCandidate:
    """Bind a candidate to the exact current manifest and resolve every citation."""

    try:
        validate_document("market-analysis-candidate", candidate)
    except EvidenceValidationError as error:
        message = str(error)
        if "private" in message:
            raise CandidateValidationError(f"private field rejected: {message}") from error
        raise CandidateValidationError(f"invalid AI candidate: {message}") from error

    public_root = public_root.resolve()
    manifest = _load_json(public_root / "manifest.json")
    try:
        validate_document("market-data-manifest", manifest)
    except EvidenceValidationError as error:
        raise CandidateValidationError(f"invalid published manifest: {error}") from error

    if candidate["evidence_version"] != manifest["evidence_version"]:
        raise CandidateValidationError("candidate evidence version is not current")
    if candidate["evidence_manifest_sha256"] != sha256_hex(manifest):
        raise CandidateValidationError("candidate manifest hash does not match current evidence")

    known_directions = _known_direction_ids()
    items = (*candidate["focus_opportunities"], *candidate["risks"])
    for item in items:
        if item["direction_id"] not in known_directions:
            raise CandidateValidationError(f"unknown direction: {item['direction_id']}")

    _reject_trading_language(candidate)
    packages = _load_direction_packages(public_root, manifest)
    _validate_references(candidate, packages)

    direction_ids = tuple(dict.fromkeys(item["direction_id"] for item in items))
    return ValidatedCandidate(manifest["evidence_version"], direction_ids)
