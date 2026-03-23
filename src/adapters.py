"""Adapters for bridging Playwright responses into openapi-core validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse


@dataclass
class OpenAPIRequest:
    """Lightweight request object satisfying the openapi-core request protocol."""

    host_url: str
    path: str
    method: str = "GET"
    body: Optional[str] = None
    mimetype: str = "application/json"
    content_type: str = "application/json"
    _query: dict[str, list[str]] = field(default_factory=dict)
    _headers: dict[str, str] = field(default_factory=dict)
    _cookies: dict[str, str] = field(default_factory=dict)

    @property
    def parameters(self) -> dict:
        return {
            "query": self._query,
            "header": self._headers,
            "cookie": self._cookies,
            "path": {},
        }

    @classmethod
    def from_url(
        cls,
        full_url: str,
        server_url: str,
        method: str = "GET",
        body: Any = None,
    ) -> "OpenAPIRequest":
        parsed = urlparse(full_url)
        server_parsed = urlparse(server_url)

        # Strip the server path prefix to get the spec-relative path
        server_path = server_parsed.path.rstrip("/")
        path = parsed.path
        if path.startswith(server_path):
            path = path[len(server_path) :]
        if not path.startswith("/"):
            path = "/" + path

        query = parse_qs(parsed.query)

        return cls(
            host_url=f"{server_parsed.scheme}://{server_parsed.netloc}{server_path}",
            path=path,
            method=method.lower(),
            body=json.dumps(body) if body is not None else None,
            _query=query,
        )


@dataclass
class OpenAPIResponse:
    """Lightweight response object satisfying the openapi-core response protocol."""

    data: bytes
    status_code: int = 200
    mimetype: str = "application/json"
    content_type: str = "application/json"
    headers: dict[str, str] = field(default_factory=lambda: {"Content-Type": "application/json"})

    @classmethod
    def from_playwright(cls, pw_response: Any) -> "OpenAPIResponse":
        """Build from a Playwright APIResponse."""
        ct = pw_response.headers.get("content-type", "application/json")
        return cls(
            data=pw_response.body(),
            status_code=pw_response.status,
            mimetype=ct.split(";")[0].strip(),
            content_type=ct,
            headers=dict(pw_response.headers),
        )