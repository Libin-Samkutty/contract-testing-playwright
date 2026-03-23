"""Load, resolve, and manage versioned OpenAPI contract files."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import prance
import yaml


class ContractManager:
    """Manages versioned OpenAPI contracts stored on disk."""

    def __init__(self, contracts_dir: str = "contracts") -> None:
        self.contracts_dir = Path(contracts_dir)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_spec(self, api_name: str, version: str) -> dict[str, Any]:
        """Load and fully resolve an OpenAPI spec (all $refs inlined)."""
        path = self._spec_path(api_name, version)
        parser = prance.ResolvingParser(str(path), strict=False)
        return parser.specification

    def load_spec_raw(self, api_name: str, version: str) -> dict[str, Any]:
        """Load a spec without resolving $refs."""
        path = self._spec_path(api_name, version)
        with open(path) as f:
            return yaml.safe_load(f)

    # ------------------------------------------------------------------
    # Version discovery
    # ------------------------------------------------------------------

    def list_versions(self, api_name: str) -> list[str]:
        """Return sorted version strings for an API (e.g. ['v1.0.0', 'v1.1.0'])."""
        api_dir = self.contracts_dir / api_name
        if not api_dir.is_dir():
            return []
        versions = []
        for f in api_dir.iterdir():
            if f.suffix in (".yaml", ".yml", ".json"):
                versions.append(f.stem)
        return sorted(versions, key=self._semver_key)

    def get_latest_version(self, api_name: str) -> str | None:
        versions = self.list_versions(api_name)
        return versions[-1] if versions else None

    def get_previous_version(self, api_name: str, current: str) -> str | None:
        versions = self.list_versions(api_name)
        if current in versions:
            idx = versions.index(current)
            return versions[idx - 1] if idx > 0 else None
        return None

    # ------------------------------------------------------------------
    # Spec metadata
    # ------------------------------------------------------------------

    def list_endpoints(self, spec: dict[str, Any]) -> list[tuple[str, str]]:
        """Return [(method, path), …] for every operation in the spec."""
        endpoints: list[tuple[str, str]] = []
        http_methods = {"get", "post", "put", "patch", "delete", "head", "options"}
        for path, path_item in spec.get("paths", {}).items():
            for method in path_item:
                if method.lower() in http_methods:
                    endpoints.append((method.upper(), path))
        return sorted(endpoints)

    def list_response_codes(
        self, spec: dict[str, Any], path: str, method: str
    ) -> list[str]:
        """Return defined response status codes for an operation."""
        op = spec.get("paths", {}).get(path, {}).get(method.lower(), {})
        return list(op.get("responses", {}).keys())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _spec_path(self, api_name: str, version: str) -> Path:
        for ext in (".yaml", ".yml", ".json"):
            p = self.contracts_dir / api_name / f"{version}{ext}"
            if p.exists():
                return p
        raise FileNotFoundError(
            f"Contract not found: {api_name}/{version} in {self.contracts_dir}"
        )

    @staticmethod
    def _semver_key(version: str) -> tuple[int, ...]:
        nums = re.findall(r"\d+", version)
        return tuple(int(n) for n in nums)