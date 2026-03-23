"""
Contract tests for JSONPlaceholder API.

Validates live API responses against expected schemas.
Docs: https://jsonplaceholder.typicode.com
"""

import pytest
from conftest import (
    record_coverage,
    validate_object_schema,
)


# ──────────────────────────────────────────────────────────────
# Schema definitions
# ──────────────────────────────────────────────────────────────

POST_SCHEMA = {
    "type": "object",
    "required": ["userId", "id", "title", "body"],
    "properties": {
        "userId": {"type": "integer"},
        "id": {"type": "integer"},
        "title": {"type": "string"},
        "body": {"type": "string"},
    },
}

USER_ADDRESS_SCHEMA = {
    "type": "object",
    "required": ["street", "suite", "city", "zipcode", "geo"],
    "properties": {
        "street": {"type": "string"},
        "suite": {"type": "string"},
        "city": {"type": "string"},
        "zipcode": {"type": "string"},
        "geo": {
            "type": "object",
            "required": ["lat", "lng"],
            "properties": {
                "lat": {"type": "string"},
                "lng": {"type": "string"},
            },
        },
    },
}

USER_COMPANY_SCHEMA = {
    "type": "object",
    "required": ["name", "catchPhrase", "bs"],
    "properties": {
        "name": {"type": "string"},
        "catchPhrase": {"type": "string"},
        "bs": {"type": "string"},
    },
}

USER_REQUIRED_FIELDS = {
    "id": int,
    "name": str,
    "username": str,
    "email": str,
}

USER_NESTED_FIELDS = {
    "address": dict,
    "company": dict,
}


# ──────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────


class TestGetPosts:
    """GET /posts — List all posts."""

    def test_returns_array_of_100_posts(self, api_context, jsonplaceholder_url):
        """Response is an array of 100 post objects."""
        response = api_context.get(f"{jsonplaceholder_url}/posts")
        assert response.status == 200
        record_coverage("GET", "/posts", response.status)

        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 100

    def test_each_post_has_required_fields(self, api_context, jsonplaceholder_url):
        """Each post has id (int), title (string), body (string), userId (int)."""
        response = api_context.get(f"{jsonplaceholder_url}/posts")
        body = response.json()

        for post in body[:5]:  # Validate first 5 for speed
            errors = validate_object_schema(
                post,
                required_fields={
                    "userId": int,
                    "id": int,
                    "title": str,
                    "body": str,
                },
            )
            assert not errors, f"Post {post.get('id')} validation failed: {errors}"

    def test_post_ids_are_sequential(self, api_context, jsonplaceholder_url):
        """Post IDs should be sequential from 1 to 100."""
        response = api_context.get(f"{jsonplaceholder_url}/posts")
        body = response.json()
        ids = [post["id"] for post in body]
        assert ids == list(range(1, 101))


class TestCreatePost:
    """POST /posts — Create a new post (synthesised response)."""

    def test_create_post_returns_expected_schema(
        self, api_context, jsonplaceholder_url
    ):
        """Creating a post returns a synthesised object with id=101."""
        payload = {
            "title": "Contract Test Post",
            "body": "This is a test body for contract testing.",
            "userId": 1,
        }

        response = api_context.post(
            f"{jsonplaceholder_url}/posts",
            data=payload,
        )
        assert response.status == 201
        record_coverage("POST", "/posts", response.status)

        body = response.json()
        assert "id" in body
        assert body["id"] == 101  # JSONPlaceholder always returns 101

    def test_create_post_echoes_fields(self, api_context, jsonplaceholder_url):
        """Created post should echo back the submitted fields."""
        payload = {
            "title": "Echo Test",
            "body": "Test body content",
            "userId": 42,
        }

        response = api_context.post(
            f"{jsonplaceholder_url}/posts",
            data=payload,
        )
        body = response.json()

        assert body["title"] == payload["title"]
        assert body["body"] == payload["body"]
        assert body["userId"] == payload["userId"]


class TestGetUser:
    """GET /users/{id} — Complex nested object validation."""

    def test_user_has_required_fields(self, api_context, jsonplaceholder_url):
        """User object has id, name, username, email."""
        response = api_context.get(f"{jsonplaceholder_url}/users/1")
        assert response.status == 200
        record_coverage("GET", "/users/{id}", response.status)

        body = response.json()
        errors = validate_object_schema(body, USER_REQUIRED_FIELDS)
        assert not errors, f"User validation failed: {errors}"

    def test_user_has_nested_address(self, api_context, jsonplaceholder_url):
        """User address contains street, suite, city, zipcode, geo."""
        response = api_context.get(f"{jsonplaceholder_url}/users/1")
        body = response.json()

        assert "address" in body
        address = body["address"]

        for field in ["street", "suite", "city", "zipcode"]:
            assert field in address, f"Missing address field: {field}"
            assert isinstance(address[field], str)

        assert "geo" in address
        geo = address["geo"]
        assert "lat" in geo
        assert "lng" in geo

    def test_user_has_nested_company(self, api_context, jsonplaceholder_url):
        """User company contains name, catchPhrase, bs."""
        response = api_context.get(f"{jsonplaceholder_url}/users/1")
        body = response.json()

        assert "company" in body
        company = body["company"]

        for field in ["name", "catchPhrase", "bs"]:
            assert field in company, f"Missing company field: {field}"
            assert isinstance(company[field], str)

    def test_user_email_format(self, api_context, jsonplaceholder_url):
        """User email should contain @ symbol."""
        response = api_context.get(f"{jsonplaceholder_url}/users/1")
        body = response.json()

        assert "@" in body["email"], f"Invalid email format: {body['email']}"

    def test_all_users_valid(self, api_context, jsonplaceholder_url):
        """All 10 users should have valid structure."""
        response = api_context.get(f"{jsonplaceholder_url}/users")
        assert response.status == 200
        record_coverage("GET", "/users", response.status)

        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 10

        for user in body:
            errors = validate_object_schema(user, USER_REQUIRED_FIELDS)
            assert not errors, (
                f"User {user.get('id')} validation failed: {errors}"
            )
            # Verify nested objects exist
            assert isinstance(user.get("address"), dict)
            assert isinstance(user.get("company"), dict)


class TestGetComments:
    """GET /comments — Additional endpoint coverage."""

    def test_comments_have_required_fields(self, api_context, jsonplaceholder_url):
        """Comments should have postId, id, name, email, body."""
        response = api_context.get(f"{jsonplaceholder_url}/comments?postId=1")
        assert response.status == 200
        record_coverage("GET", "/comments", response.status)

        body = response.json()
        assert isinstance(body, list)
        assert len(body) > 0

        for comment in body:
            errors = validate_object_schema(
                comment,
                required_fields={
                    "postId": int,
                    "id": int,
                    "name": str,
                    "email": str,
                    "body": str,
                },
            )
            assert not errors, (
                f"Comment {comment.get('id')} validation failed: {errors}"
            )