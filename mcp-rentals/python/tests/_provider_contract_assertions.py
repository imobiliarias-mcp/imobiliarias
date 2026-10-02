"""Assertions matching provider results against the exported worker contract."""

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from rental_bridge import contracts
from rental_bridge.serialization.projection import clean_projection

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = PROJECT_ROOT / "dist/contracts/providers.json"
WORKER_SCHEMA = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))["worker_response"]


def assert_worker_response(provider_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = _normalized_response(payload)
    Draft202012Validator(WORKER_SCHEMA).validate(response)
    _validate_references(provider_id, response["display"])
    json.dumps(response, allow_nan=False)
    return response


def _normalized_response(payload: dict[str, Any]) -> dict[str, Any]:
    display = [clean_projection(item) for item in payload["display"]]
    return {"version": 1, "status": "ok", "native": payload["native"], "display": display}


def _validate_references(provider_id: str, display: list[dict[str, Any]]) -> None:
    specification_path = PROJECT_ROOT / "provider-specs" / f"{provider_id}.json"
    specification = json.loads(specification_path.read_text(encoding="utf-8"))
    reference_validator = Draft202012Validator(specification["reference"])
    for item in display:
        _validate_reference_if_present(reference_validator, item)
        _validate_url_if_present(provider_id, item)


def _validate_reference_if_present(validator: Draft202012Validator, item: dict[str, Any]) -> None:
    if "reference" in item:
        validator.validate(item["reference"])


def _validate_url_if_present(provider_id: str, item: dict[str, Any]) -> None:
    if "url" in item:
        contracts.validate_public_url(item["url"], provider_id)
