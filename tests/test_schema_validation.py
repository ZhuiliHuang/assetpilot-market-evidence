from __future__ import annotations

import json
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VALID_FIXTURES = REPOSITORY_ROOT / "tests" / "fixtures" / "valid"
INVALID_FIXTURES = REPOSITORY_ROOT / "tests" / "fixtures" / "invalid"

EXPECTED_SCHEMAS = {
    "market-data-manifest",
    "market-category",
    "market-direction",
    "market-analysis-candidate",
    "market-analysis",
}


def load_fixture(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_all_public_contract_schemas_exist() -> None:
    schema_names = {
        path.name.removesuffix(".schema.json")
        for path in (REPOSITORY_ROOT / "schemas").glob("*.schema.json")
    }

    assert schema_names == EXPECTED_SCHEMAS


def test_valid_fixtures_pass_their_declared_schema() -> None:
    from market_evidence.schema_validation import validate_document

    fixtures = sorted(VALID_FIXTURES.glob("*.json"))
    assert fixtures, "valid schema fixtures are missing"
    for path in fixtures:
        document = load_fixture(path)
        validate_document(document.pop("_schema"), document)


def test_invalid_and_private_fixtures_are_rejected() -> None:
    from market_evidence.schema_validation import EvidenceValidationError, validate_document

    fixtures = sorted(INVALID_FIXTURES.glob("*.json"))
    assert fixtures, "invalid schema fixtures are missing"
    for path in fixtures:
        document = load_fixture(path)
        schema_name = document.pop("_schema")
        with pytest.raises(EvidenceValidationError, match=".+"):
            validate_document(schema_name, document)
