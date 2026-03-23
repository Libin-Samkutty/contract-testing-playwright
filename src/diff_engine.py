"""Detect and classify breaking vs. non-breaking changes between two OpenAPI specs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from deepdiff import DeepDiff


class ChangeCategory(str, Enum):
    BREAKING = "breaking"
    NON_BREAKING = "non-breaking"


@dataclass
class SchemaChange:
    category: ChangeCategory
    change_type: str  # e.g. "field_removed", "type_changed", "endpoint_added"
    path: str  # DeepDiff path string
    description: str
    old_value: Any = None
    new_value: Any = None


@dataclass
class DiffReport:
    breaking: list[SchemaChange] = field(default_factory=list)
    non_breaking: list[SchemaChange] = field(default_factory=list)

    @property
    def score(self) -> int:
        """Backward-compatibility score (0–100). 100 = fully compatible."""
        n = len(self.breaking)
        if n == 0:
            return 100
        # Deduct 15 points per breaking change, floor at 0
        return max(0, 100 - n * 15)

    @property
    def is_breaking(self) -> bool:
        return len(self.breaking) > 0

    @property
    def should_fail_pipeline(self) -> bool:
        """Pipeline should fail when 3+ breaking changes (score drops sharply)."""
        return len(self.breaking) >= 3

    def summary(self) -> str:
        lines = [
            f"Compatibility score: {self.score}/100",
            f"Breaking changes:     {len(self.breaking)}",
            f"Non-breaking changes: {len(self.non_breaking)}",
        ]
        if self.breaking:
            lines.append("\n=== BREAKING CHANGES ===")
            for c in self.breaking:
                lines.append(f"  [{c.change_type}] {c.description}")
                lines.append(f"    Path: {c.path}")
                if c.old_value is not None:
                    lines.append(f"    Old:  {c.old_value}")
                if c.new_value is not None:
                    lines.append(f"    New:  {c.new_value}")
        if self.non_breaking:
            lines.append("\n--- Non-breaking changes ---")
            for c in self.non_breaking:
                lines.append(f"  [{c.change_type}] {c.description}")
        return "\n".join(lines)


class DiffEngine:
    """Compare two OpenAPI specs and classify every structural change."""

    def diff(
        self,
        old_spec: dict[str, Any],
        new_spec: dict[str, Any],
    ) -> DiffReport:
        deep = DeepDiff(old_spec, new_spec, ignore_order=True, verbose_level=2)
        report = DiffReport()

        # --- items removed ---
        for path_str, value in (deep.get("dictionary_item_removed") or {}).items():
            change = self._classify_removal(path_str, value)
            self._add(report, change)

        # --- items added ---
        for path_str, value in (deep.get("dictionary_item_added") or {}).items():
            change = self._classify_addition(path_str, value)
            self._add(report, change)

        # --- type changes ---
        for path_str, detail in (deep.get("type_changes") or {}).items():
            change = SchemaChange(
                category=ChangeCategory.BREAKING,
                change_type="type_changed",
                path=path_str,
                description=self._human_path(path_str) + " — type changed",
                old_value=repr(detail.get("old_value")),
                new_value=repr(detail.get("new_value")),
            )
            self._add(report, change)

        # --- value changes ---
        for path_str, detail in (deep.get("values_changed") or {}).items():
            change = self._classify_value_change(path_str, detail)
            self._add(report, change)

        # --- iterable item removed (e.g. enum value removed, required entry removed) ---
        for path_str, detail in (deep.get("iterable_item_removed") or {}).items():
            change = self._classify_iterable_removal(path_str, detail)
            self._add(report, change)

        # --- iterable item added ---
        for path_str, detail in (deep.get("iterable_item_added") or {}).items():
            change = self._classify_iterable_addition(path_str, detail)
            self._add(report, change)

        return report

    # ------------------------------------------------------------------
    # Classification helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_path(path_str: str) -> list[str]:
        """Extract key segments from a DeepDiff path like root['a']['b']."""
        return re.findall(r"\['([^']+)'\]", path_str)

    def _is_in_response(self, keys: list[str]) -> bool:
        return "responses" in keys

    def _is_in_request_body(self, keys: list[str]) -> bool:
        return "requestBody" in keys

    def _is_in_parameters(self, keys: list[str]) -> bool:
        return "parameters" in keys

    def _is_path_level(self, keys: list[str]) -> bool:
        """True when the change is at the paths→{path} or paths→{path}→{method} level."""
        if len(keys) < 2:
            return False
        return keys[0] == "paths" and len(keys) <= 3

    def _classify_removal(self, path_str: str, value: Any) -> SchemaChange:
        keys = self._parse_path(path_str)
        human = self._human_path(path_str)

        # Endpoint removed
        if self._is_path_level(keys):
            return SchemaChange(
                ChangeCategory.BREAKING,
                "endpoint_removed",
                path_str,
                f"Endpoint removed: {human}",
                old_value=value,
            )

        # Field removed from response schema
        if self._is_in_response(keys):
            return SchemaChange(
                ChangeCategory.BREAKING,
                "response_field_removed",
                path_str,
                f"Response field removed: {human}",
                old_value=value,
            )

        # Field removed from request body — generally non-breaking
        if self._is_in_request_body(keys):
            return SchemaChange(
                ChangeCategory.NON_BREAKING,
                "request_field_removed",
                path_str,
                f"Request field removed (server more permissive): {human}",
            )

        # Default: treat unknown removals as breaking
        return SchemaChange(
            ChangeCategory.BREAKING,
            "field_removed",
            path_str,
            f"Removed: {human}",
            old_value=value,
        )

    def _classify_addition(self, path_str: str, value: Any) -> SchemaChange:
        keys = self._parse_path(path_str)
        human = self._human_path(path_str)

        # New endpoint
        if self._is_path_level(keys):
            return SchemaChange(
                ChangeCategory.NON_BREAKING,
                "endpoint_added",
                path_str,
                f"New endpoint added: {human}",
            )

        # New optional field in response — non-breaking
        if self._is_in_response(keys):
            return SchemaChange(
                ChangeCategory.NON_BREAKING,
                "response_field_added",
                path_str,
                f"Response field added: {human}",
            )

        # New required field in request body — breaking
        if self._is_in_request_body(keys) and "required" in keys:
            return SchemaChange(
                ChangeCategory.BREAKING,
                "required_request_field_added",
                path_str,
                f"New required request field: {human}",
            )

        # Default addition: non-breaking
        return SchemaChange(
            ChangeCategory.NON_BREAKING,
            "field_added",
            path_str,
            f"Added: {human}",
        )

    def _classify_value_change(self, path_str: str, detail: Any) -> SchemaChange:
        keys = self._parse_path(path_str)
        human = self._human_path(path_str)

        old = detail.get("new_value") if isinstance(detail, dict) else detail
        new = detail.get("old_value") if isinstance(detail, dict) else None

        # Type field changed (e.g. "integer" → "string")
        if keys and keys[-1] == "type":
            return SchemaChange(
                ChangeCategory.BREAKING,
                "type_changed",
                path_str,
                f"Type changed: {human}",
                old_value=detail.get("old_value") if isinstance(detail, dict) else None,
                new_value=detail.get("new_value") if isinstance(detail, dict) else None,
            )

        # Other value changes in schema – generally breaking
        if self._is_in_response(keys) or self._is_in_request_body(keys):
            return SchemaChange(
                ChangeCategory.BREAKING,
                "value_changed",
                path_str,
                f"Value changed: {human}",
                old_value=detail.get("old_value") if isinstance(detail, dict) else None,
                new_value=detail.get("new_value") if isinstance(detail, dict) else None,
            )

        return SchemaChange(
            ChangeCategory.NON_BREAKING,
            "value_changed",
            path_str,
            f"Value changed: {human}",
        )

    def _classify_iterable_removal(self, path_str: str, detail: Any) -> SchemaChange:
        keys = self._parse_path(path_str)
        human = self._human_path(path_str)

        # Enum value removed — breaking
        if "enum" in keys:
            return SchemaChange(
                ChangeCategory.BREAKING,
                "enum_value_removed",
                path_str,
                f"Enum value removed: {human}",
                old_value=detail,
            )

        # Required field removed (field made optional) — non-breaking
        if "required" in keys and self._is_in_response(keys):
            return SchemaChange(
                ChangeCategory.NON_BREAKING,
                "required_made_optional",
                path_str,
                f"Required field made optional: {human}",
            )

        return SchemaChange(
            ChangeCategory.BREAKING,
            "iterable_item_removed",
            path_str,
            f"Item removed: {human}",
            old_value=detail,
        )

    def _classify_iterable_addition(self, path_str: str, detail: Any) -> SchemaChange:
        keys = self._parse_path(path_str)
        human = self._human_path(path_str)

        # New required field added to request — breaking
        if "required" in keys and self._is_in_request_body(keys):
            return SchemaChange(
                ChangeCategory.BREAKING,
                "required_field_added_to_request",
                path_str,
                f"New required request field: {human}",
                new_value=detail,
            )

        return SchemaChange(
            ChangeCategory.NON_BREAKING,
            "iterable_item_added",
            path_str,
            f"Item added: {human}",
            new_value=detail,
        )

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def _human_path(self, path_str: str) -> str:
        keys = self._parse_path(path_str)
        if not keys:
            return path_str
        # Condense to something readable
        return " → ".join(keys)

    @staticmethod
    def _add(report: DiffReport, change: SchemaChange) -> None:
        if change.category == ChangeCategory.BREAKING:
            report.breaking.append(change)
        else:
            report.non_breaking.append(change)