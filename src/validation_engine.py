"""Validate live API responses against stored OpenAPI / JSON Schema contracts."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from src.contract_manager import ContractManager


class ValidationEngine:
    """Validates response payloads against a resolved OpenAPI spec."""

    def __init__(self, spec: dict[str, Any]) -> None:
        self.spec = spec

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_response(
        self,
        path: str,
        method: str,
        status_code: int | str,
        body: Any,
    ) -> None:
        """Validate *body* against the response schema for the given operation.

        Raises ``jsonschema.ValidationError`` on mismatch.
        """
        schema = self.get_response_schema(path, method, str(status_code))
        adapted = self._openapi_schema_to_jsonschema(schema)
        jsonschema.validate(instance=body, schema=adapted)

    def get_response_schema(
        self, path: str, method: str, status_code: str
    ) -> dict[str, Any]:
        """Extract the JSON Schema for a specific response from the spec."""
        paths = self.spec.get("paths", {})
        if path not in paths:
            raise KeyError(f"Path '{path}' not found in spec. Available: {list(paths)}")

        operation = paths[path].get(method.lower())
        if operation is None:
            raise KeyError(f"Method '{method}' not found for path '{path}'")

        responses = operation.get("responses", {})
        resp = responses.get(status_code)
        if resp is None:
            # Try default response
            resp = responses.get("default")
        if resp is None:
            raise KeyError(
                f"Status {status_code} not found for {method.upper()} {path}. "
                f"Available: {list(responses)}"
            )

        content = resp.get("content", {})
        json_content = content.get("application/json")
        if json_content is None:
            raise KeyError(
                f"No application/json content for {method.upper()} {path} {status_code}"
            )
        return json_content["schema"]

    # ------------------------------------------------------------------
    # OpenAPI → JSON Schema adaptation
    # ------------------------------------------------------------------

    def _openapi_schema_to_jsonschema(self, schema: Any) -> Any:
        """Convert OpenAPI 3.0 schema extensions to valid JSON Schema draft-7+."""
        if not isinstance(schema, dict):
            return schema

        result: dict[str, Any] = {}
        nullable = schema.get("nullable", False)

        for key, value in schema.items():
            # Skip OpenAPI-only keywords that aren't part of JSON Schema
            if key in (
                "nullable",
                "discriminator",
                "readOnly",
                "writeOnly",
                "xml",
                "externalDocs",
                "example",
            ):
                continue

            if key == "properties" and isinstance(value, dict):
                result[key] = {
                    k: self._openapi_schema_to_jsonschema(v)
                    for k, v in value.items()
                }
            elif key == "items":
                result[key] = self._openapi_schema_to_jsonschema(value)
            elif key in ("allOf", "anyOf", "oneOf"):
                result[key] = [self._openapi_schema_to_jsonschema(s) for s in value]
            elif key == "additionalProperties" and isinstance(value, dict):
                result[key] = self._openapi_schema_to_jsonschema(value)
            else:
                result[key] = value

        # Convert nullable → JSON Schema union type
        if nullable and "type" in result:
            t = result["type"]
            if isinstance(t, list):
                if "null" not in t:
                    result["type"] = t + ["null"]
            else:
                result["type"] = [t, "null"]

        return result

    # ------------------------------------------------------------------
    # Spec self-validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate_spec_file(path: str | Path) -> None:
        """Validate that the spec file conforms to the OpenAPI meta-schema.

        Raises ``openapi_spec_validator.exceptions.OpenAPIValidationError`` on failure.
        """
        from openapi_spec_validator import validate

        with open(path) as f:
            spec_dict = yaml.safe_load(f)
        validate(spec_dict)

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_file(cls, path: str | Path) -> "ValidationEngine":
        import prance

        parser = prance.ResolvingParser(str(path), strict=False)
        return cls(parser.specification)

    @classmethod
    def from_contract(
        cls,
        api_name: str,
        version: str,
        contracts_dir: str = "contracts",
    ) -> "ValidationEngine":
        mgr = ContractManager(contracts_dir)
        spec = mgr.load_spec(api_name, version)
        return cls(spec)