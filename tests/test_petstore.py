"""
Contract tests for Swagger Petstore API (OpenAPI 3.0).

Validates live API responses against expected schemas.
Spec: https://github.com/swagger-api/swagger-petstore/blob/master/src/main/resources/openapi.yaml
Live: https://petstore3.swagger.io/api/v3
"""

import pytest
from conftest import (
    record_coverage,
    validate_object_schema,
)


# ──────────────────────────────────────────────────────────────
# Expected schemas
# ──────────────────────────────────────────────────────────────

PET_REQUIRED_FIELDS = {
    "id": int,
    "name": str,
}

PET_OPTIONAL_FIELDS = {
    "status": str,
    "photoUrls": list,
    "tags": list,
}

VALID_PET_STATUSES = {"available", "pending", "sold"}


# ──────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────


class TestCreatePet:
    """POST /pet — Create a pet."""

    def test_create_pet_response_schema(self, api_context, petstore_url):
        """Response body matches Pet schema after creation."""
        payload = {
            "id": 99001,
            "name": "ContractTestDog",
            "status": "available",
            "photoUrls": ["https://example.com/photo.jpg"],
            "tags": [{"id": 1, "name": "test"}],
            "category": {"id": 1, "name": "Dogs"},
        }

        response = api_context.post(
            f"{petstore_url}/pet",
            data=payload,
        )
        assert response.status == 200
        record_coverage("POST", "/pet", response.status)

        body = response.json()
        errors = validate_object_schema(body, PET_REQUIRED_FIELDS, PET_OPTIONAL_FIELDS)
        assert not errors, f"Pet creation response validation failed: {errors}"

    def test_create_pet_id_is_integer(self, api_context, petstore_url):
        """Pet id should be an integer."""
        payload = {
            "id": 99002,
            "name": "IntegerTestPet",
            "status": "available",
            "photoUrls": [],
        }

        response = api_context.post(f"{petstore_url}/pet", data=payload)
        body = response.json()
        assert isinstance(body["id"], int), f"id should be int, got {type(body['id'])}"

    def test_create_pet_status_is_valid_enum(self, api_context, petstore_url):
        """Pet status should be one of: available, pending, sold."""
        payload = {
            "id": 99003,
            "name": "EnumTestPet",
            "status": "available",
            "photoUrls": [],
        }

        response = api_context.post(f"{petstore_url}/pet", data=payload)
        body = response.json()

        if "status" in body and body["status"] is not None:
            assert body["status"] in VALID_PET_STATUSES, (
                f"Invalid status: {body['status']}"
            )


class TestGetPetById:
    """GET /pet/{petId} — Retrieve a pet."""

    @pytest.fixture(autouse=True)
    def _create_test_pet(self, api_context, petstore_url):
        """Ensure a test pet exists before retrieval tests."""
        payload = {
            "id": 99010,
            "name": "RetrieveTestPet",
            "status": "available",
            "photoUrls": ["https://example.com/pet.jpg"],
        }
        api_context.post(f"{petstore_url}/pet", data=payload)

    def test_get_pet_returns_correct_schema(self, api_context, petstore_url):
        """Retrieved pet has all required fields."""
        response = api_context.get(f"{petstore_url}/pet/99010")
        assert response.status == 200
        record_coverage("GET", "/pet/{petId}", response.status)

        body = response.json()
        errors = validate_object_schema(body, PET_REQUIRED_FIELDS)
        assert not errors, f"Get pet validation failed: {errors}"

    def test_get_pet_has_name_string(self, api_context, petstore_url):
        """Pet name should be a string."""
        response = api_context.get(f"{petstore_url}/pet/99010")
        body = response.json()
        assert isinstance(body["name"], str)

    def test_get_pet_not_found(self, api_context, petstore_url):
        """Requesting a non-existent pet returns 404."""
        response = api_context.get(f"{petstore_url}/pet/999999999")
        assert response.status == 404
        record_coverage("GET", "/pet/{petId}", response.status)


class TestFindPetsByStatus:
    """GET /pet/findByStatus — Find pets by status."""

    def test_find_available_pets_returns_array(self, api_context, petstore_url):
        """Response is an array of Pet objects."""
        response = api_context.get(
            f"{petstore_url}/pet/findByStatus?status=available"
        )
        assert response.status == 200
        record_coverage("GET", "/pet/findByStatus", response.status)

        body = response.json()
        assert isinstance(body, list)

    def test_find_by_status_all_match(self, api_context, petstore_url):
        """All returned pets should have the requested status."""
        response = api_context.get(
            f"{petstore_url}/pet/findByStatus?status=sold"
        )
        body = response.json()

        for pet in body[:10]:  # Check first 10
            if "status" in pet:
                assert pet["status"] == "sold", (
                    f"Pet {pet.get('id')} has status '{pet['status']}', expected 'sold'"
                )

    def test_find_by_status_each_pet_valid(self, api_context, petstore_url):
        """Each pet in the results has valid schema."""
        response = api_context.get(
            f"{petstore_url}/pet/findByStatus?status=pending"
        )
        body = response.json()

        for pet in body[:5]:
            errors = validate_object_schema(pet, PET_REQUIRED_FIELDS)
            assert not errors, (
                f"Pet {pet.get('id')} validation failed: {errors}"
            )


class TestSchemaRegression:
    """Schema regression tests — diff v1.0.0 → v1.1.0."""

    def test_no_breaking_changes_in_contracts(self):
        """Verify stored contract versions have no breaking changes."""
        from scripts.diff_contracts import analyze_diff
        from conftest import load_contract

        try:
            v1 = load_contract("petstore", "v1.0.0")
            v1_1 = load_contract("petstore", "v1.1.0")
        except Exception:
            pytest.skip("Petstore v1.0.0 and v1.1.0 contracts not available")

        report = analyze_diff(v1, v1_1)
        assert report["is_backward_compatible"], (
            f"Breaking changes found: {report['breaking_changes']}"
        )