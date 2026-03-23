#!/usr/bin/env python3
"""
Contract Diff Engine.

Compares two versions of an OpenAPI/JSON Schema contract and classifies
changes as breaking or non-breaking.

Usage:
    python scripts/diff_contracts.py --previous contracts/petstore/v1.0.0.yaml --current contracts/petstore/v1.1.0.yaml
    python scripts/diff_contracts.py --previous v1.0.0 --current v1.1.0 --api petstore
"""

import argparse
import json
import re
import sys
from pathlib import Path

import yaml
from deepdiff import DeepDiff


# ──────────────────────────────────────────────────────────────
# Classification helpers
# ──────────────────────────────────────────────────────────────

BREAKING_PATTERNS = [
    # Paths / endpoints removed
    re.compile(r"root\['paths'\]\['.+'\]\['(get|post|put|patch|delete)'\]"),
    # Required fields added to request parameters
    re.compile(r"root\['paths'\].+\['parameters'\]"),
    # Schema required array changed
    re.compile(r"root\['components'\]\['schemas'\].+\['required'\]"),
    # Response schema properties removed
    re.compile(r"root\['components'\]\['schemas'\].+\['properties'\]\['.+'\]"),
    # Path-level removal
    re.compile(r"root\['paths'\]\['.+'\]$"),
]

NON_BREAKING_PATTERNS = [
    # New paths added
    re.compile(r"root\['paths'\]\['.+'\]"),
    # New optional properties added
    re.compile(r"root\['components'\]\['schemas'\].+\['properties'\]\['.+'\]"),
    # Description / summary changes
    re.compile(r".*\['description'\]"),
    re.compile(r".*\['summary'\]"),
    # Info block changes
    re.compile(r"root\['info'\]"),
]


def load_schema(path: str) -> dict:
    """Load a YAML or JSON schema file."""
    file_path = Path(path)
    if not file_path.exists():
        print(f"ERROR: File not found: {path}")
        sys.exit(1)

    with open(file_path, "r") as f:
        if file_path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(f)
        else:
            return json.load(f)


def resolve_path(version: str, api: str | None = None) -> str:
    """Resolve a version tag to a file path."""
    if Path(version).exists():
        return version

    if api:
        # Try contracts/{api}/{version}.yaml
        candidates = [
            f"contracts/{api}/{version}.yaml",
            f"contracts/{api}/{version}.yml",
            f"contracts/{api}/{version}.json",
        ]
        for candidate in candidates:
            if Path(candidate).exists():
                return candidate

    print(f"ERROR: Cannot resolve path for version '{version}'")
    sys.exit(1)


def classify_change(path: str, change_type: str) -> str:
    """
    Classify a single change as 'breaking' or 'non-breaking'.

    Rules:
    - dictionary_item_removed in paths/schemas → breaking
    - type_changes in schema properties → breaking
    - dictionary_item_added in paths → non-breaking
    - values_changed in descriptions → non-breaking
    """
    if change_type == "dictionary_item_removed":
        # Anything removed is potentially breaking
        for pattern in BREAKING_PATTERNS:
            if pattern.search(path):
                return "breaking"
        return "breaking"  # Default: removals are breaking

    if change_type == "type_changes":
        return "breaking"

    if change_type == "dictionary_item_added":
        return "non-breaking"

    if change_type == "values_changed":
        # Check if it's a type change in properties
        if "'type'" in path:
            return "breaking"
        # Description or metadata changes are non-breaking
        for pattern in NON_BREAKING_PATTERNS:
            if pattern.search(path):
                return "non-breaking"
        return "non-breaking"

    if change_type == "iterable_item_added":
        return "non-breaking"

    if change_type == "iterable_item_removed":
        # Removed items from arrays (e.g., required fields removed → non-breaking,
        # enum values removed → breaking)
        if "'required'" in path:
            return "non-breaking"  # Making a required field optional is non-breaking
        if "'enum'" in path:
            return "breaking"  # Removing an enum value is breaking
        return "breaking"

    return "non-breaking"


def get_breaking_penalty(path: str, change_type: str) -> tuple[str, int]:
    """
    Return (severity_label, score_penalty) for a breaking change.

    Severity tiers:
      endpoint_removed     -20  (highest — removes entire surface area)
      type_changed         -15  (high — client parsing will break)
      required_field       -10  (medium — new required param or enum removal)
      other                -10  (default)
    """
    # Endpoint removed
    if change_type == "dictionary_item_removed" and re.search(
        r"root\['paths'\]\['.+'\]$", path
    ):
        return "endpoint_removed", 20

    # Type changed (DeepDiff type_changes, or values_changed on a 'type' key)
    if change_type == "type_changes" or (
        change_type == "values_changed" and "'type'" in path
    ):
        return "type_changed", 15

    # Required field changed (added to request or removed from enum)
    if "'required'" in path or "'enum'" in path:
        return "required_field", 10

    return "breaking", 10


def analyze_diff(previous: dict, current: dict) -> dict:
    """
    Perform a deep diff between two schema versions and classify changes.

    Returns a report dict with breaking and non-breaking changes.
    """
    diff = DeepDiff(previous, current, ignore_order=True, verbose_level=2)

    breaking_changes = []
    non_breaking_changes = []

    change_types = [
        "dictionary_item_removed",
        "dictionary_item_added",
        "type_changes",
        "values_changed",
        "iterable_item_added",
        "iterable_item_removed",
    ]

    for change_type in change_types:
        changes = diff.get(change_type, {})
        if isinstance(changes, dict):
            items = changes.items()
        elif isinstance(changes, set):
            items = [(item, None) for item in changes]
        else:
            continue

        for path, detail in items:
            classification = classify_change(str(path), change_type)
            change_entry = {
                "path": str(path),
                "change_type": change_type,
                "detail": str(detail) if detail else None,
                "classification": classification,
            }

            if classification == "breaking":
                severity, penalty = get_breaking_penalty(str(path), change_type)
                change_entry["severity"] = severity
                change_entry["penalty"] = penalty
                breaking_changes.append(change_entry)
            else:
                non_breaking_changes.append(change_entry)

    # Severity-weighted compatibility score
    total_penalty = sum(c["penalty"] for c in breaking_changes)
    score = max(0, 100 - total_penalty)

    return {
        "breaking_changes": breaking_changes,
        "non_breaking_changes": non_breaking_changes,
        "total_breaking": len(breaking_changes),
        "total_non_breaking": len(non_breaking_changes),
        "compatibility_score": score,
        "is_backward_compatible": len(breaking_changes) == 0,
    }


def print_report(report: dict, previous_label: str, current_label: str) -> None:
    """Print a human-readable diff report."""
    print("=" * 70)
    print("CONTRACT DIFF REPORT")
    print(f"Previous: {previous_label}")
    print(f"Current:  {current_label}")
    print("=" * 70)
    print()

    score = report["compatibility_score"]
    if score == 100:
        indicator = "✅"
    elif score >= 40:
        indicator = "⚠️"
    else:
        indicator = "❌"

    print(f"Compatibility Score: {indicator} {score}/100")
    print(
        f"Breaking Changes:     {report['total_breaking']}"
    )
    print(
        f"Non-Breaking Changes: {report['total_non_breaking']}"
    )
    print()

    if report["breaking_changes"]:
        print("🔴 BREAKING CHANGES:")
        print("-" * 50)
        for change in report["breaking_changes"]:
            severity = change.get("severity", "breaking")
            penalty = change.get("penalty", 0)
            print(f"  ❌ [{severity}] -{penalty}pts  {change['path']}")
            if change["detail"]:
                detail_str = str(change["detail"])
                if len(detail_str) > 120:
                    detail_str = detail_str[:120] + "..."
                print(f"     Detail: {detail_str}")
        print()

    if report["non_breaking_changes"]:
        print("🟢 NON-BREAKING CHANGES:")
        print("-" * 50)
        for change in report["non_breaking_changes"]:
            print(f"  ✅ [{change['change_type']}] {change['path']}")
            if change["detail"]:
                detail_str = str(change["detail"])
                if len(detail_str) > 120:
                    detail_str = detail_str[:120] + "..."
                print(f"     Detail: {detail_str}")
        print()

    if report["is_backward_compatible"]:
        print("✅ RESULT: Backward compatible — safe to deploy")
    else:
        print("❌ RESULT: BREAKING CHANGES DETECTED — deployment blocked")

    print("=" * 70)


def save_report(report: dict, output_path: str) -> None:
    """Save the diff report as JSON."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Report saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Contract Diff Engine")
    parser.add_argument(
        "--previous",
        required=True,
        help="Previous schema version (file path or version tag)",
    )
    parser.add_argument(
        "--current",
        required=True,
        help="Current schema version (file path or version tag)",
    )
    parser.add_argument(
        "--api",
        help="API name (for resolving version tags to file paths)",
    )
    parser.add_argument(
        "--output",
        help="Output file path for JSON report",
    )
    parser.add_argument(
        "--fail-on-breaking",
        action="store_true",
        default=True,
        help="Exit with non-zero status on breaking changes (default: True)",
    )
    args = parser.parse_args()

    previous_path = resolve_path(args.previous, args.api)
    current_path = resolve_path(args.current, args.api)

    previous_schema = load_schema(previous_path)
    current_schema = load_schema(current_path)

    report = analyze_diff(previous_schema, current_schema)
    print_report(report, args.previous, args.current)

    if args.output:
        save_report(report, args.output)

    if args.fail_on_breaking and report["total_breaking"] > 0:
        sys.exit(1)

    return report


if __name__ == "__main__":
    main()