"""
Tests for the Contract Diff Engine.

Validates that the diff engine correctly classifies breaking
vs. non-breaking changes between schema versions.
"""

import pytest
from scripts.diff_contracts import analyze_diff, classify_change


# ──────────────────────────────────────────────────────────────
# Base schemas for testing
# ──────────────────────────────────────────────────────────────

BASE_SCHEMA = {
    "openapi": "3.0.3",
    "info": {"title": "Test API", "version": "1.0.0"},
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "summary": "List all pets",
                "responses": {
                    "200": {
                        "description": "A list of pets",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {
                                        "$ref": "#/components/schemas/Pet",
                                    },
                                },
                            },
                        },
                    },
                },
            },
            "post": {
                "operationId": "createPet",
                "summary": "Create a pet",
                "responses": {
                    "201": {"description": "Pet created"},
                },
            },
        },
        "/pets/{petId}": {
            "get": {
                "operationId": "getPet",
                "summary": "Get a pet by ID",
                "parameters": [
                    {
                        "name": "petId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    },
                ],
                "responses": {
                    "200": {
                        "description": "A pet",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/Pet",
                                },
                            },
                        },
                    },
                    "404": {"description": "Pet not found"},
                },
            },
        },
    },
    "components": {
        "schemas": {
            "Pet": {
                "type": "object",
                "required": ["id", "name"],
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["available", "pending", "sold"],
                    },
                    "tag": {"type": "string"},
                },
            },
        },
    },
}


def _deep_copy(d: dict) -> dict:
    """Simple deep copy for nested dicts."""
    import copy
    return copy.deepcopy(d)


# ──────────────────────────────────────────────────────────────
# Tests: Non-Breaking Changes
# ──────────────────────────────────────────────────────────────


class TestNonBreakingChanges:
    """Changes that should be classified as non-breaking."""

    def test_add_optional_field(self):
        """Adding a new optional field to a schema is non-breaking."""
        previous = _deep_copy(BASE_SCHEMA)
        current = _deep_copy(BASE_SCHEMA)
        current["components"]["schemas"]["Pet"]["properties"]["color"] = {
            "type": "string",
        }

        report = analyze_diff(previous, current)
        assert report["is_backward_compatible"] is True
        assert report["total_breaking"] == 0
        assert report["total_non_breaking"] > 0
        assert report["compatibility_score"] == 100

    def test_add_new_endpoint(self):
        """Adding a new endpoint is non-breaking."""
        previous = _deep_copy(BASE_SCHEMA)
        current = _deep_copy(BASE_SCHEMA)
        current["paths"]["/pets/search"] = {
            "get": {
                "operationId": "searchPets",
                "summary": "Search pets",
                "responses": {"200": {"description": "Search results"}},
            },
        }

        report = analyze_diff(previous, current)
        assert report["is_backward_compatible"] is True
        assert report["total_breaking"] == 0

    def test_change_description(self):
        """Changing a description is non-breaking."""
        previous = _deep_copy(BASE_SCHEMA)
        current = _deep_copy(BASE_SCHEMA)
        current["info"]["description"] = "Updated API description"

        report = analyze_diff(previous, current)
        assert report["is_backward_compatible"] is True

    def test_add_optional_parameter(self):
        """Adding an optional query parameter is non-breaking."""
        previous = _deep_copy(BASE_SCHEMA)
        current = _deep_copy(BASE_SCHEMA)
        current["paths"]["/pets"]["get"]["parameters"] = [
            {
                "name": "limit",
                "in": "query",
                "required": False,
                "schema": {"type": "integer"},
            },
        ]

        report = analyze_diff(previous, current)
        assert report["is_backward_compatible"] is True

    def test_make_required_field_optional(self):
        """Making a required field optional is non-breaking."""
        previous = _deep_copy(BASE_SCHEMA)
        current = _deep_copy(BASE_SCHEMA)
        # Remove 'name' from required list (was ['id', 'name'], now ['id'])
        current["components"]["schemas"]["Pet"]["required"] = ["id"]

        report = analyze_diff(previous, current)
        assert report["is_backward_compatible"] is True

    def test_no_changes(self):
        """Identical schemas should produce no changes."""
        previous = _deep_copy(BASE_SCHEMA)
        current = _deep_copy(BASE_SCHEMA)

        report = analyze_diff(previous, current)
        assert report["is_backward_compatible"] is True
        assert report["total_breaking"] == 0
        assert report["total_non_breaking"] == 0
        assert report["compatibility_score"] == 100


# ──────────────────────────────────────────────────────────────
# Tests: Breaking Changes
# ──────────────────────────────────────────────────────────────


class TestBreakingChanges:
    """Changes that should be classified as breaking."""

    def test_remove_field_from_schema(self):
        """Removing a field from a response schema is breaking."""
        previous = _deep_copy(BASE_SCHEMA)
        current = _deep_copy(BASE_SCHEMA)
        del current["components"]["schemas"]["Pet"]["properties"]["status"]

        report = analyze_diff(previous, current)
        assert report["is_backward_compatible"] is False
        assert report["total_breaking"] > 0

    def test_remove_endpoint(self):
        """Removing an endpoint is breaking."""
        previous = _deep_copy(BASE_SCHEMA)
        current = _deep_copy(BASE_SCHEMA)
        del current["paths"]["/pets/{petId}"]

        report = analyze_diff(previous, current)
        assert report["is_backward_compatible"] is False
        assert report["total_breaking"] > 0

    def test_remove_http_method(self):
        """Removing an HTTP method from a path is breaking."""
        previous = _deep_copy(BASE_SCHEMA)
        current = _deep_copy(BASE_SCHEMA)
        del current["paths"]["/pets"]["post"]

        report = analyze_diff(previous, current)
        assert report["is_backward_compatible"] is False

    def test_change_field_type(self):
        """Changing the type of a field is breaking."""
        previous = _deep_copy(BASE_SCHEMA)
        current = _deep_copy(BASE_SCHEMA)
        current["components"]["schemas"]["Pet"]["properties"]["id"]["type"] = "string"

        report = analyze_diff(previous, current)
        assert report["is_backward_compatible"] is False
        assert report["total_breaking"] > 0

    def test_remove_enum_value(self):
        """Removing an enum value is breaking."""
        previous = _deep_copy(BASE_SCHEMA)
        current = _deep_copy(BASE_SCHEMA)
        current["components"]["schemas"]["Pet"]["properties"]["status"]["enum"] = [
            "available",
            "pending",
        ]  # Removed 'sold'

        report = analyze_diff(previous, current)
        assert report["is_backward_compatible"] is False


# ──────────────────────────────────────────────────────────────
# Tests: Compatibility Score
# ──────────────────────────────────────────────────────────────


class TestCompatibilityScore:
    """Tests for the backward compatibility scoring system."""

    def test_perfect_score_no_breaking(self):
        """No breaking changes → score 100."""
        previous = _deep_copy(BASE_SCHEMA)
        current = _deep_copy(BASE_SCHEMA)
        current["components"]["schemas"]["Pet"]["properties"]["color"] = {
            "type": "string",
        }

        report = analyze_diff(previous, current)
        assert report["compatibility_score"] == 100

    def test_reduced_score_with_breaking(self):
        """Breaking changes should reduce the score."""
        previous = _deep_copy(BASE_SCHEMA)
        current = _deep_copy(BASE_SCHEMA)
        del current["components"]["schemas"]["Pet"]["properties"]["status"]

        report = analyze_diff(previous, current)
        assert report["compatibility_score"] < 100

    def test_low_score_many_breaking(self):
        """Multiple breaking changes should result in a low score."""
        previous = _deep_copy(BASE_SCHEMA)
        current = _deep_copy(BASE_SCHEMA)
        del current["components"]["schemas"]["Pet"]["properties"]["status"]
        del current["components"]["schemas"]["Pet"]["properties"]["tag"]
        del current["paths"]["/pets"]["post"]
        del current["paths"]["/pets/{petId}"]

        report = analyze_diff(previous, current)
        assert report["compatibility_score"] < 50
        assert report["total_breaking"] >= 3


# ──────────────────────────────────────────────────────────────
# Tests: classify_change function
# ──────────────────────────────────────────────────────────────


class TestClassifyChange:
    """Unit tests for the classify_change helper."""

    def test_removed_path_is_breaking(self):
        result = classify_change(
            "root['paths']['/pets/{petId}']",
            "dictionary_item_removed",
        )
        assert result == "breaking"

    def test_removed_method_is_breaking(self):
        result = classify_change(
            "root['paths']['/pets']['post']",
            "dictionary_item_removed",
        )
        assert result == "breaking"

    def test_type_change_is_breaking(self):
        result = classify_change(
            "root['components']['schemas']['Pet']['properties']['id']['type']",
            "type_changes",
        )
        assert result == "breaking"

    def test_added_path_is_non_breaking(self):
        result = classify_change(
            "root['paths']['/pets/search']",
            "dictionary_item_added",
        )
        assert result == "non-breaking"

    def test_description_change_is_non_breaking(self):
        result = classify_change(
            "root['paths']['/pets']['get']['description']",
            "values_changed",
        )
        assert result == "non-breaking"