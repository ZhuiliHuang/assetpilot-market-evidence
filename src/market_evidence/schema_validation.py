"""Strict validation for public market-evidence documents."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


SCHEMAS_DIRECTORY = Path(__file__).resolve().parents[2] / "schemas"

FORBIDDEN_KEYS = {
    "portfolio" + "_id",
    "account" + "_id",
    "cost" + "_basis",
    "position" + "_quantity",
    "asset" + "_total",
    "transaction" + "_id",
    "insurance" + "_details",
    "ocr" + "_text",
}


class EvidenceValidationError(ValueError):
    """Raised when a public evidence document violates its contract or privacy boundary."""


@lru_cache(maxsize=8)
def load_schema(schema_name: str) -> dict[str, Any]:
    if not schema_name or any(character not in "abcdefghijklmnopqrstuvwxyz-" for character in schema_name):
        raise EvidenceValidationError(f"unknown schema name: {schema_name!r}")
    schema_path = SCHEMAS_DIRECTORY / f"{schema_name}.schema.json"
    if not schema_path.is_file():
        raise EvidenceValidationError(f"unknown schema: {schema_name}")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def reject_forbidden_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for raw_key, child in value.items():
            key = str(raw_key).strip().lower()
            child_path = f"{path}.{raw_key}"
            if key in FORBIDDEN_KEYS:
                raise EvidenceValidationError(f"forbidden private field at {child_path}")
            reject_forbidden_keys(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_forbidden_keys(child, f"{path}[{index}]")


def validate_document(schema_name: str, document: dict[str, Any]) -> None:
    if not isinstance(document, dict):
        raise EvidenceValidationError("evidence document must be a JSON object")

    reject_forbidden_keys(document)
    validator = Draft202012Validator(load_schema(schema_name))
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.absolute_path))
    if not errors:
        return

    first_error = errors[0]
    location = "$"
    if first_error.absolute_path:
        location += "".join(
            f"[{part}]" if isinstance(part, int) else f".{part}"
            for part in first_error.absolute_path
        )
    raise EvidenceValidationError(f"{schema_name} invalid at {location}: {first_error.message}")
