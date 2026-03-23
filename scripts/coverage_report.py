#!/usr/bin/env python3
"""
Contract Coverage Report Generator.

Analyzes which endpoints and response codes defined in an OpenAPI spec
are covered by at least one test. Reports uncovered paths as warnings.

Usage:
    python scripts/coverage_report.py --spec contracts/petstore/v1.0.0.yaml --results coverage_data.json
    python scripts/coverage_report.py --spec contracts/petstore/v1.0.0.yaml --auto-discover
"""

import argparse
import json
import sys
from pathlib import Path

import yaml


def load_spec(spec_path: str) -> dict:
    """Load an OpenAPI spec from a YAML or JSON file."""
    path = Path(spec_path)
    if not path.exists():
        print(f"ERROR: Spec file not found: {spec_path}")
        sys.exit(1)

    with open(path, "r") as f:
        if path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(f)
        else:
            return json.load(f)


def extract_endpoints(spec: dict) -> list[dict]:
    """Extract all endpoints (method + path + response codes) from an OpenAPI spec."""
    endpoints = []
    paths = spec.get("paths", {})

    http_methods = {"get", "post", "put", "patch", "delete", "head", "options"}

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in http_methods:
                continue
            if not isinstance(operation, dict):
                continue

            responses = operation.get("responses", {})
            response_codes = list(responses.keys()) if responses else ["200"]

            endpoint = {
                "path": path,
                "method": method.upper(),
                "operation_id": operation.get("operationId", ""),
                "summary": operation.get("summary", ""),
                "response_codes": response_codes,
            }
            endpoints.append(endpoint)

    return endpoints


def load_coverage_data(results_path: str) -> list[dict]:
    """
    Load coverage data from a JSON file.

    Expected format:
    [
        {"method": "GET", "path": "/pet/{petId}", "status_code": "200"},
        {"method": "POST", "path": "/pet", "status_code": "200"},
        ...
    ]
    """
    path = Path(results_path)
    if not path.exists():
        return []

    with open(path, "r") as f:
        return json.load(f)


def auto_discover_coverage(spec: dict) -> list[dict]:
    """
    Auto-discover coverage by scanning test files for endpoint references.
    Returns a list of likely-covered endpoints based on test file content.
    """
    covered = []
    tests_dir = Path("tests")

    if not tests_dir.exists():
        return covered

    paths = spec.get("paths", {})
    test_files = list(tests_dir.glob("test_*.py"))

    for test_file in test_files:
        content = test_file.read_text()

        for path in paths:
            # Normalize path for matching - replace {param} patterns
            search_path = path.replace("{", "").replace("}", "")
            # Also check the raw path
            if path in content or search_path in content:
                path_item = paths[path]
                for method in path_item:
                    if method.lower() in {
                        "get", "post", "put", "patch", "delete",
                    }:
                        covered.append(
                            {
                                "method": method.upper(),
                                "path": path,
                                "status_code": "200",
                                "source": str(test_file),
                            }
                        )

    return covered


def normalize_path(path: str) -> str:
    """Normalize a path for comparison by replacing specific IDs with parameter placeholders."""
    import re
    # Replace numeric path segments that look like IDs
    normalized = re.sub(r"/\d+(/|$)", "/{id}\\1", path)
    return normalized


def calculate_coverage(
    endpoints: list[dict],
    covered: list[dict],
) -> dict:
    """Calculate coverage statistics."""
    total_endpoints = len(endpoints)
    total_response_codes = sum(len(e["response_codes"]) for e in endpoints)

    covered_endpoints = set()
    covered_responses = set()

    for item in covered:
        covered_method = item["method"].upper()
        covered_path = item["path"]
        covered_status = str(item.get("status_code", "200"))

        for endpoint in endpoints:
            if (
                endpoint["method"] == covered_method
                and endpoint["path"] == covered_path
            ):
                covered_endpoints.add(
                    f"{endpoint['method']} {endpoint['path']}"
                )
                if covered_status in endpoint["response_codes"]:
                    covered_responses.add(
                        f"{endpoint['method']} {endpoint['path']} {covered_status}"
                    )

    uncovered_endpoints = []
    for endpoint in endpoints:
        key = f"{endpoint['method']} {endpoint['path']}"
        if key not in covered_endpoints:
            uncovered_endpoints.append(endpoint)

    uncovered_responses = []
    for endpoint in endpoints:
        for code in endpoint["response_codes"]:
            key = f"{endpoint['method']} {endpoint['path']} {code}"
            if key not in covered_responses:
                uncovered_responses.append(
                    {
                        "method": endpoint["method"],
                        "path": endpoint["path"],
                        "status_code": code,
                    }
                )

    endpoint_coverage = (
        (len(covered_endpoints) / total_endpoints * 100) if total_endpoints > 0 else 0
    )
    response_coverage = (
        (len(covered_responses) / total_response_codes * 100)
        if total_response_codes > 0
        else 0
    )

    return {
        "total_endpoints": total_endpoints,
        "covered_endpoints": len(covered_endpoints),
        "endpoint_coverage_pct": round(endpoint_coverage, 1),
        "total_response_codes": total_response_codes,
        "covered_response_codes": len(covered_responses),
        "response_coverage_pct": round(response_coverage, 1),
        "uncovered_endpoints": uncovered_endpoints,
        "uncovered_responses": uncovered_responses,
    }


def print_report(spec_path: str, coverage: dict) -> None:
    """Print a human-readable coverage report."""
    print("=" * 70)
    print("CONTRACT COVERAGE REPORT")
    print(f"Spec: {spec_path}")
    print("=" * 70)
    print()

    ep_pct = coverage["endpoint_coverage_pct"]
    print(
        f"Endpoint Coverage:  {coverage['covered_endpoints']}"
        f"/{coverage['total_endpoints']} ({ep_pct}%)"
    )

    resp_pct = coverage["response_coverage_pct"]
    print(
        f"Response Coverage:  {coverage['covered_response_codes']}"
        f"/{coverage['total_response_codes']} ({resp_pct}%)"
    )
    print()

    # Color-coded score
    if ep_pct >= 80:
        grade = "✅ GOOD"
    elif ep_pct >= 50:
        grade = "⚠️  MODERATE"
    else:
        grade = "❌ LOW"
    print(f"Grade: {grade}")
    print()

    if coverage["uncovered_endpoints"]:
        print("UNCOVERED ENDPOINTS (warnings):")
        print("-" * 40)
        for ep in coverage["uncovered_endpoints"]:
            summary = f" — {ep['summary']}" if ep.get("summary") else ""
            print(f"  ⚠️  {ep['method']} {ep['path']}{summary}")
        print()

    if coverage["uncovered_responses"]:
        print("UNCOVERED RESPONSE CODES:")
        print("-" * 40)
        for resp in coverage["uncovered_responses"][:20]:  # Limit output
            print(
                f"  ⚠️  {resp['method']} {resp['path']}"
                f" → {resp['status_code']}"
            )
        remaining = len(coverage["uncovered_responses"]) - 20
        if remaining > 0:
            print(f"  ... and {remaining} more")
        print()

    print("=" * 70)


def save_report(spec_path: str, coverage: dict, output_path: str) -> None:
    """Save coverage report as JSON."""
    report = {
        "spec": spec_path,
        "coverage": coverage,
    }
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"Report saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Contract Coverage Report Generator")
    parser.add_argument(
        "--spec",
        required=True,
        help="Path to the OpenAPI spec file",
    )
    parser.add_argument(
        "--results",
        help="Path to coverage data JSON file",
    )
    parser.add_argument(
        "--auto-discover",
        action="store_true",
        help="Auto-discover coverage from test files",
    )
    parser.add_argument(
        "--output",
        help="Output path for JSON report",
    )
    args = parser.parse_args()

    spec = load_spec(args.spec)
    endpoints = extract_endpoints(spec)

    if args.results:
        covered = load_coverage_data(args.results)
    elif args.auto_discover:
        covered = auto_discover_coverage(spec)
    else:
        covered = []

    coverage = calculate_coverage(endpoints, covered)
    print_report(args.spec, coverage)

    if args.output:
        save_report(args.spec, coverage, args.output)

    # Exit with non-zero if coverage is critically low
    if coverage["endpoint_coverage_pct"] < 20:
        print("CRITICAL: Coverage below 20% threshold")
        sys.exit(1)

    return coverage


if __name__ == "__main__":
    main()