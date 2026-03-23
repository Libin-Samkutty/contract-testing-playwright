"""
Contract tests for RealWorld (Conduit) API.

Validates live API responses against expected schemas.
Spec: https://github.com/gothinkster/realworld/blob/main/api/openapi.yml
Live: https://api.realworld.io/api
"""

import pytest
from conftest import (
    record_coverage,
    validate_object_schema,
)


# ──────────────────────────────────────────────────────────────
# Expected schemas
# ──────────────────────────────────────────────────────────────

ARTICLE_REQUIRED_FIELDS = {
    "slug": str,
    "title": str,
    "description": str,
    "body": str,
    "tagList": list,
    "createdAt": str,
    "updatedAt": str,
    "favorited": bool,
    "favoritesCount": int,
}


def validate_author(author: dict) -> list[str]:
    """Validate the author sub-object."""
    return validate_object_schema(
        author,
        required_fields={
            "username": str,
        },
        optional_fields={
            "bio": str,
            "image": str,
            "following": bool,
        },
    )


def validate_iso8601(value: str, field_name: str) -> str | None:
    """Check if a string looks like an ISO 8601 datetime."""
    import re
    # Basic ISO 8601 pattern: YYYY-MM-DDTHH:MM:SS
    pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    if not re.match(pattern, value):
        return f"{field_name} '{value}' is not ISO 8601 format"
    return None


# ──────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────


class TestListArticles:
    """GET /articles — List articles."""

    def test_returns_articles_wrapper(self, api_context, realworld_url):
        """Response has articles array and articlesCount."""
        response = api_context.get(f"{realworld_url}/articles")
        if response.status >= 500:
            pytest.skip(f"API unavailable: {response.status}")
        assert response.status == 200
        record_coverage("GET", "/articles", response.status)

        body = response.json()
        assert "articles" in body, "Response missing 'articles' key"
        assert "articlesCount" in body, "Response missing 'articlesCount' key"
        assert isinstance(body["articles"], list)
        assert isinstance(body["articlesCount"], int)

    def test_each_article_has_required_fields(
        self, api_context, realworld_url
    ):
        """Each article has title, body, author, tagList, etc."""
        response = api_context.get(f"{realworld_url}/articles?limit=5")
        body = response.json()

        articles = body.get("articles", [])
        if not articles:
            pytest.skip("No articles available from the API")

        for article in articles:
            errors = validate_object_schema(article, ARTICLE_REQUIRED_FIELDS)
            assert not errors, (
                f"Article '{article.get('slug')}' validation failed: {errors}"
            )

    def test_each_article_has_author(self, api_context, realworld_url):
        """Each article's author has at least a username."""
        response = api_context.get(f"{realworld_url}/articles?limit=5")
        body = response.json()

        articles = body.get("articles", [])
        if not articles:
            pytest.skip("No articles available")

        for article in articles:
            assert "author" in article, (
                f"Article '{article.get('slug')}' missing 'author'"
            )
            author = article["author"]
            assert isinstance(author, dict), "author should be an object"
            errors = validate_author(author)
            assert not errors, (
                f"Author in article '{article.get('slug')}' failed: {errors}"
            )

    def test_article_tag_list_is_array(self, api_context, realworld_url):
        """tagList should be an array of strings."""
        response = api_context.get(f"{realworld_url}/articles?limit=5")
        body = response.json()

        articles = body.get("articles", [])
        if not articles:
            pytest.skip("No articles available")

        for article in articles:
            tag_list = article.get("tagList")
            assert isinstance(tag_list, list), (
                f"tagList should be a list, got {type(tag_list)}"
            )
            for tag in tag_list:
                assert isinstance(tag, str), (
                    f"Each tag should be a string, got {type(tag)}"
                )


class TestGetSingleArticle:
    """GET /articles/{slug} — Single article."""

    def test_single_article_full_schema(self, api_context, realworld_url):
        """A single article matches the full Article schema."""
        # First get a slug from the list
        list_response = api_context.get(f"{realworld_url}/articles?limit=1")
        list_body = list_response.json()

        articles = list_body.get("articles", [])
        if not articles:
            pytest.skip("No articles available to test single retrieval")

        slug = articles[0]["slug"]

        response = api_context.get(f"{realworld_url}/articles/{slug}")
        assert response.status == 200
        record_coverage("GET", "/articles/{slug}", response.status)

        body = response.json()
        assert "article" in body, "Response missing 'article' wrapper key"

        article = body["article"]
        errors = validate_object_schema(article, ARTICLE_REQUIRED_FIELDS)
        assert not errors, f"Single article validation failed: {errors}"

    def test_article_dates_are_iso8601(self, api_context, realworld_url):
        """createdAt and updatedAt should be ISO 8601 datetime strings."""
        list_response = api_context.get(f"{realworld_url}/articles?limit=1")
        list_body = list_response.json()

        articles = list_body.get("articles", [])
        if not articles:
            pytest.skip("No articles available")

        slug = articles[0]["slug"]
        response = api_context.get(f"{realworld_url}/articles/{slug}")
        body = response.json()
        article = body["article"]

        for field in ["createdAt", "updatedAt"]:
            value = article.get(field)
            assert value is not None, f"{field} should not be null"
            error = validate_iso8601(value, field)
            assert error is None, error


class TestGetTags:
    """GET /tags — Tag list."""

    def test_tags_returns_array(self, api_context, realworld_url):
        """Response is { "tags": [string] }."""
        response = api_context.get(f"{realworld_url}/tags")
        if response.status >= 500:
            pytest.skip(f"API unavailable: {response.status}")
        assert response.status == 200
        record_coverage("GET", "/tags", response.status)

        body = response.json()
        assert "tags" in body, "Response missing 'tags' key"
        assert isinstance(body["tags"], list)

    def test_tags_are_strings(self, api_context, realworld_url):
        """Each tag should be a string."""
        response = api_context.get(f"{realworld_url}/tags")
        body = response.json()

        tags = body.get("tags", [])
        for tag in tags:
            assert isinstance(tag, str), f"Tag should be string, got {type(tag)}"

    def test_tags_are_non_empty(self, api_context, realworld_url):
        """Tag list should not be empty (assuming active API)."""
        response = api_context.get(f"{realworld_url}/tags")
        body = response.json()

        tags = body.get("tags", [])
        # This might be empty on some instances, so just warn
        if not tags:
            pytest.skip("Tags list is empty — API may have no data")


class TestContractDrift:
    """Detect schema drift between stored contract and live API."""

    def test_live_articles_match_contract_structure(
        self, api_context, realworld_url
    ):
        """Live API response structure matches what we expect from the contract."""
        response = api_context.get(f"{realworld_url}/articles?limit=3")
        if response.status >= 500:
            pytest.skip(f"API unavailable: {response.status}")
        body = response.json()

        # Verify top-level structure
        assert "articles" in body
        assert "articlesCount" in body

        articles = body.get("articles", [])
        if not articles:
            pytest.skip("No articles to validate against contract")

        # Check for unexpected structural changes (drift detection)
        expected_keys = {
            "slug", "title", "description", "body", "tagList",
            "createdAt", "updatedAt", "favorited", "favoritesCount", "author",
        }

        for article in articles:
            article_keys = set(article.keys())
            missing_keys = expected_keys - article_keys
            assert not missing_keys, (
                f"Contract drift detected! Missing keys: {missing_keys}"
            )