"""
Contract tests for OpenBreweryDB API.

Validates live API responses against the stored OpenAPI contract.
Docs: https://www.openbrewerydb.org/documentation
"""

import pytest
from conftest import (
    load_contract,
    get_schema_component,
    record_coverage,
    validate_against_schema,
    validate_object_schema,
)


# ──────────────────────────────────────────────────────────────
# Expected schema for inline validation
# ──────────────────────────────────────────────────────────────

BREWERY_REQUIRED_FIELDS = {
    "id": str,
    "name": str,
    "brewery_type": str,
}

BREWERY_NULLABLE_FIELDS = {
    "city": str,
    "state_province": str,
    "country": str,
    "longitude": str,
    "latitude": str,
    "phone": str,
    "website_url": str,
    "address_1": str,
    "postal_code": str,
    "state": str,
    "street": str,
}

VALID_BREWERY_TYPES = {
    "micro", "nano", "regional", "brewpub", "large",
    "planning", "bar", "contract", "proprietor", "closed",
}


# ──────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────


class TestListBreweries:
    """GET /breweries — Paginated brewery list."""

    def test_returns_array(self, api_context, openbrewerydb_url):
        """Response is an array of brewery objects."""
        response = api_context.get(f"{openbrewerydb_url}/breweries")
        assert response.status == 200
        record_coverage("GET", "/breweries", response.status)

        body = response.json()
        assert isinstance(body, list)
        assert len(body) > 0

    def test_each_brewery_has_required_fields(
        self, api_context, openbrewerydb_url
    ):
        """Each brewery has id, name, brewery_type."""
        response = api_context.get(f"{openbrewerydb_url}/breweries")
        body = response.json()

        for brewery in body[:5]:
            errors = validate_object_schema(brewery, BREWERY_REQUIRED_FIELDS)
            assert not errors, (
                f"Brewery {brewery.get('id')} failed: {errors}"
            )

    def test_brewery_type_is_valid_enum(self, api_context, openbrewerydb_url):
        """brewery_type should be one of the allowed values."""
        response = api_context.get(f"{openbrewerydb_url}/breweries")
        body = response.json()

        for brewery in body:
            btype = brewery.get("brewery_type")
            assert btype in VALID_BREWERY_TYPES, (
                f"Invalid brewery_type: '{btype}' for brewery {brewery.get('id')}"
            )

    def test_pagination(self, api_context, openbrewerydb_url):
        """Pagination with per_page parameter should limit results."""
        response = api_context.get(
            f"{openbrewerydb_url}/breweries?per_page=5"
        )
        assert response.status == 200

        body = response.json()
        assert isinstance(body, list)
        assert len(body) <= 5

    def test_validates_against_contract(self, api_context, openbrewerydb_url):
        """Validate response against stored OpenAPI contract schema."""
        contract = load_contract("openbrewerydb")
        brewery_schema = get_schema_component(contract, "Brewery")

        response = api_context.get(
            f"{openbrewerydb_url}/breweries?per_page=3"
        )
        body = response.json()

        for brewery in body:
            errors = validate_against_schema(brewery, brewery_schema)
            assert not errors, (
                f"Brewery {brewery.get('id')} contract validation failed: {errors}"
            )


class TestGetBreweryById:
    """GET /breweries/{id} — Single brewery."""

    def test_single_brewery_response(self, api_context, openbrewerydb_url):
        """Fetching a single brewery returns a valid object."""
        # First get a valid ID from the list
        list_response = api_context.get(
            f"{openbrewerydb_url}/breweries?per_page=1"
        )
        breweries = list_response.json()
        assert len(breweries) > 0

        brewery_id = breweries[0]["id"]

        response = api_context.get(
            f"{openbrewerydb_url}/breweries/{brewery_id}"
        )
        assert response.status == 200
        record_coverage("GET", "/breweries/{id}", response.status)

        body = response.json()
        errors = validate_object_schema(body, BREWERY_REQUIRED_FIELDS)
        assert not errors, f"Single brewery validation failed: {errors}"

    def test_latitude_longitude_format(self, api_context, openbrewerydb_url):
        """Latitude and longitude should be numeric strings or null."""
        response = api_context.get(
            f"{openbrewerydb_url}/breweries?per_page=10"
        )
        body = response.json()

        for brewery in body:
            lat = brewery.get("latitude")
            lon = brewery.get("longitude")

            if lat is not None:
                assert isinstance(lat, (str, float, int)), (
                    f"latitude should be string or number, got {type(lat)}"
                )
                try:
                    float(lat)
                except (ValueError, TypeError):
                    pytest.fail(
                        f"latitude '{lat}' is not a valid numeric value"
                    )

            if lon is not None:
                assert isinstance(lon, (str, float, int)), (
                    f"longitude should be string or number, got {type(lon)}"
                )
                try:
                    float(lon)
                except (ValueError, TypeError):
                    pytest.fail(
                        f"longitude '{lon}' is not a valid numeric value"
                    )


class TestSearchBreweries:
    """GET /breweries/search?query=... — Search endpoint."""

    def test_search_returns_array(self, api_context, openbrewerydb_url):
        """Search returns an array of matching breweries."""
        response = api_context.get(
            f"{openbrewerydb_url}/breweries/search?query=dog"
        )
        assert response.status == 200
        record_coverage("GET", "/breweries/search", response.status)

        body = response.json()
        assert isinstance(body, list)

    def test_search_results_have_valid_schema(
        self, api_context, openbrewerydb_url
    ):
        """Search results should have the same schema as regular brewery objects."""
        response = api_context.get(
            f"{openbrewerydb_url}/breweries/search?query=ale"
        )
        body = response.json()

        for brewery in body[:5]:
            errors = validate_object_schema(brewery, BREWERY_REQUIRED_FIELDS)
            assert not errors, (
                f"Search result {brewery.get('id')} validation failed: {errors}"
            )

    def test_search_with_no_results(self, api_context, openbrewerydb_url):
        """Search with nonsense query returns empty array."""
        response = api_context.get(
            f"{openbrewerydb_url}/breweries/search?query=zzzxxxyyy999"
        )
        assert response.status == 200

        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 0


class TestContractValidation:
    """Validate responses against the stored OpenAPI contract."""

    def test_contract_schema_is_valid(self):
        """Stored contract schema should be loadable and have expected structure."""
        contract = load_contract("openbrewerydb")
        assert "openapi" in contract
        assert "paths" in contract
        assert "/breweries" in contract["paths"]
        assert "components" in contract
        assert "Brewery" in contract["components"]["schemas"]

    def test_contract_version_is_semver(self):
        """Contract version follows semantic versioning."""
        contract = load_contract("openbrewerydb")
        import re
        version = contract["info"]["version"]
        assert re.match(r"^\d+\.\d+\.\d+", version), (
            f"Version '{version}' does not follow semver"
        )


class TestOpenBreweryDBEdgeCases:
    """Edge-case inputs against the OpenBreweryDB API."""

    def test_breweries_endpoint_handles_edge_inputs(self, api_context, openbrewerydb_url):
        """Test that /breweries handles various edge-case query parameters."""
        edge_cases = [
            {"per_page": "0"},
            {"per_page": "1"},
            {"per_page": "200"},
            {"by_city": ""},
            {"by_state": "california"},
            {"by_type": "micro"},
            {"by_type": "invalid_type"},
            {"page": "1", "per_page": "3"},
        ]

        for params in edge_cases:
            query_string = "&".join(f"{k}={v}" for k, v in params.items())
            response = api_context.get(
                f"{openbrewerydb_url}/breweries?{query_string}"
            )

            assert response.status < 500, (
                f"Server error with params {params}: {response.status}"
            )

            if response.status == 200:
                body = response.json()
                assert isinstance(body, list), (
                    f"Expected array for params {params}, got {type(body)}"
                )

    def test_search_handles_special_characters(self, api_context, openbrewerydb_url):
        """Search endpoint handles special characters without 500 errors."""
        special_queries = [
            "dog",
            "IPA",
            "craft beer",
            "o'hara",
            "",
            "a" * 100,
        ]

        for query in special_queries:
            response = api_context.get(
                f"{openbrewerydb_url}/breweries/search?query={query}"
            )
            assert response.status < 500, (
                f"Server error for query '{query}': {response.status}"
            )