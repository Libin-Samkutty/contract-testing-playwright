#!/usr/bin/env python3
"""
Validate all OpenAPI spec files in the contracts directory.

Ensures each spec file is valid before it's used in testing.

Usage:
    python scripts/validate_specs.py
    python scripts/validate_specs.py --contracts-dir contracts
    python scripts/validate_specs.py --spec contracts/petstore/v1.0.0.yaml
"""

import argparse
import sys
from pathlib import Path

import yaml
from openapi_spec_validator import validate
from openapi_spec_validator.readers import read_from_filename


def validate_single_spec(spec_path: str) -> tuple[bool, str]:
    """
    Validate a single OpenAPI spec file.

    Returns (is_valid, message).
    """
    path = Path(spec_path)
    if not path.exists():
        return False, f"File not found: {spec_path}"

    try:
        spec_dict, _ = read_from_filename(str(path))
        validate(spec_dict)
        return True, f"✅ Valid: {spec_path}"
    except Exception as e:
        return False, f"❌ Invalid: {spec_path}\n   Error: {e}"


def find_all_specs(contracts_dir: str) -> list[str]:
    """Find all YAML/JSON spec files in the contracts directory."""
    contracts_path = Path(contracts_dir)
    if not contracts_path.exists():
        print(f"WARNING: Contracts directory not found: {contracts_dir}")
        return []

    specs = []
    for ext in ("*.yaml", "*.yml", "*.json"):
        specs.extend(str(p) for p in contracts_path.rglob(ext))

    return sorted(specs)


def main():
    parser = argparse.ArgumentParser(description="Validate OpenAPI Spec Files")
    parser.add_argument(
        "--contracts-dir",
        default="contracts",
        help="Directory containing contract spec files",
    )
    parser.add_argument(
        "--spec",
        help="Path to a single spec file to validate",
    )
    args = parser.parse_args()

    if args.spec:
        specs = [args.spec]
    else:
        specs = find_all_specs(args.contracts_dir)

    if not specs:
        print("No spec files found to validate.")
        sys.exit(0)

    print("=" * 60)
    print("OPENAPI SPEC VALIDATION")
    print("=" * 60)
    print()

    total = len(specs)
    valid_count = 0
    invalid_count = 0
    results = []

    for spec_path in specs:
        is_valid, message = validate_single_spec(spec_path)
        results.append((is_valid, message))
        print(message)
        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1

    print()
    print("-" * 60)
    print(f"Total: {total} | Valid: {valid_count} | Invalid: {invalid_count}")
    print("-" * 60)

    if invalid_count > 0:
        print("\n❌ VALIDATION FAILED — fix spec errors before proceeding")
        sys.exit(1)
    else:
        print("\n✅ ALL SPECS VALID")
        sys.exit(0)


if __name__ == "__main__":
    main()