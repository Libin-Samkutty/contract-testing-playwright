"""
Shared fixtures for contract testing.

Provides Playwright API request context, schema loaders,
validation helpers, and coverage tracking.
"""

import json
import os
from pathlib import Path

import pytest
import yaml
from playwright.sync_api import Playwright


# ──────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────

CONTRACTS_DIR = Path(__file__).parent.parent / "contracts"

API_URLS = {
    "petstore_v3": "https://petstore3.swagger.io/api/v3",
    "petstore_v2": "https://petstore.swagger.io/v2",
    "realworld": "https://api.realworld.io/api",
    "jsonplaceholder": "https://jsonplaceholder.typicode.com",
    "openbrewerydb": "https://api.openbrewerydb.org/v1",
}


# ──────────────────────────────────────────────────────────────
# Coverage tracking
# ──────────────────────────────────────────────────────────────

_coverage_data: list[dict] = []


def record_coverage(method: str, path: str, status_code: int) -> None:
    """Record an endpoint that was tested for coverage reporting."""
    _coverage_data.append(
        {
            "method": method.upper(),
            "path": path,
            "status_code": str(status_code),
        }
    )


@pytest.fixture(scope="session", autouse=True)
def save_coverage_data():
    """Save coverage data to a JSON file after all tests complete."""
    yield
    if _coverage_data:
        output_path = Path("coverage_data.json")
        with open(output_path, "w") as f:
            json.dump(_coverage_data, f, indent=2)


# ──────────────────────────────────────────────────────────────
# Schema loading helpers
# ──────────────────────────────────────────────────────────────


def load_contract(api_name: str, version: str = None) -> dict:
    """
    Load an OpenAPI/JSON Schema contract from the contracts directory.

    Args:
        api_name: Name of the API (e.g., 'petstore', 'realworld')
        version: Version string (e.g., 'v1.0.0'). If None, loads latest.

    Returns:
        Parsed schema dict.
    """
    api_dir = CONTRACTS_DIR / api_name

    if not api_dir.exists():
        pytest.skip(f"No contracts found for API: {api_name}")

    if version:
        for ext in (".yaml", ".yml", ".json"):
            path = api_dir / f"{version}{ext}"
            if path.exists():
                return _load_file(path)
        pytest.skip(f"Contract version not found: {api_name}/{version}")
    else:
        # Load the latest version (highest semver)
        files = sorted(api_dir.glob("v*.yaml")) + sorted(api_dir.glob("v*.yml"))
        if not files:
            pytest.skip(f"No versioned contracts in {api_dir}")
        return _load_file(files[-1])


def _load_file(path: Path) -> dict:
    """Load a YAML or JSON file."""
    with open(path, "r") as f:
        if path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(f)
        return json.load(f)


def get_schema_component(contract: dict, component_name: str) -> dict:
    """
    Extract a named schema from the components/schemas section.

    Works with both OpenAPI 3.x and Swagger 2.x formats.
    """
    # OpenAPI 3.x
    schemas = contract.get("components", {}).get("schemas", {})
    if component_name in schemas:
        return schemas[component_name]

    # Swagger 2.x
    definitions = contract.get("definitions", {})
    if component_name in definitions:
        return definitions[component_name]

    available = list(schemas.keys()) + list(definitions.keys())
    raise KeyError(
        f"Schema '{component_name}' not found. Available: {available}"
    )


# ──────────────────────────────────────────────────────────────
# Validation helpers
# ──────────────────────────────────────────────────────────────


def _normalize_openapi_schema(schema: dict) -> dict:
    """Convert OpenAPI 3.0 nullable:true to JSON Schema null types."""
    if not isinstance(schema, dict):
        return schema
    result = {}
    for key, value in schema.items():
        if key == "properties" and isinstance(value, dict):
            result[key] = {k: _normalize_openapi_schema(v) for k, v in value.items()}
        elif key in ("items", "additionalProperties") and isinstance(value, dict):
            result[key] = _normalize_openapi_schema(value)
        elif key in ("oneOf", "anyOf", "allOf") and isinstance(value, list):
            result[key] = [_normalize_openapi_schema(v) for v in value]
        else:
            result[key] = value
    if result.pop("nullable", False):
        if "type" in result and isinstance(result["type"], str):
            result["type"] = [result["type"], "null"]
        elif "oneOf" in result:
            result["oneOf"] = result["oneOf"] + [{"type": "null"}]
        elif "anyOf" in result:
            result["anyOf"] = result["anyOf"] + [{"type": "null"}]
    return result


def validate_against_schema(instance: dict | list, schema: dict) -> list[str]:
    """
    Validate a response payload against a JSON Schema.

    Returns a list of validation error messages (empty if valid).
    """
    import jsonschema

    normalized = _normalize_openapi_schema(schema)
    validator = jsonschema.Draft7Validator(normalized)
    errors = list(validator.iter_errors(instance))
    return [f"{e.json_path}: {e.message}" for e in errors]


def validate_object_schema(
    obj: dict,
    required_fields: dict[str, type],
    optional_fields: dict[str, type] | None = None,
) -> list[str]:
    """
    Quick structural validation of a dict.

    Args:
        obj: The dict to validate
        required_fields: Mapping of field_name → expected Python type
        optional_fields: Mapping of field_name → expected Python type (if present)

    Returns:
        List of error messages (empty if valid).
    """
    errors = []

    for field, expected_type in required_fields.items():
        if field not in obj:
            errors.append(f"Missing required field: '{field}'")
        elif obj[field] is not None and not isinstance(obj[field], expected_type):
            errors.append(
                f"Field '{field}' expected {expected_type.__name__}, "
                f"got {type(obj[field]).__name__}"
            )

    if optional_fields:
        for field, expected_type in optional_fields.items():
            if field in obj and obj[field] is not None:
                if not isinstance(obj[field], expected_type):
                    errors.append(
                        f"Optional field '{field}' expected {expected_type.__name__}, "
                        f"got {type(obj[field]).__name__}"
                    )

    return errors


# ──────────────────────────────────────────────────────────────
# Playwright fixtures
# ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def api_context(playwright: Playwright):
    """Create a Playwright API request context for all tests."""
    context = playwright.request.new_context(
        extra_http_headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    )
    yield context
    context.dispose()


@pytest.fixture(scope="session")
def petstore_url():
    """Petstore v3 base URL."""
    return API_URLS["petstore_v3"]


@pytest.fixture(scope="session")
def realworld_url():
    """RealWorld (Conduit) base URL."""
    return API_URLS["realworld"]


@pytest.fixture(scope="session")
def jsonplaceholder_url():
    """JSONPlaceholder base URL."""
    return API_URLS["jsonplaceholder"]


@pytest.fixture(scope="session")
def openbrewerydb_url():
    """OpenBreweryDB base URL."""
    return API_URLS["openbrewerydb"]