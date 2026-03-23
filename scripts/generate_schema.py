#!/usr/bin/env python3
"""
Auto-Generate JSON Schema from Live API Responses.

Uses genson to infer a JSON Schema from a live API response,
then stores it as a baseline contract.

Usage:
    python scripts/generate_schema.py --url https://jsonplaceholder.typicode.com/posts --output contracts/jsonplaceholder/v1.0.0.yaml
    python scripts/generate_schema.py --url https://api.openbrewerydb.org/v1/breweries --output contracts/openbrewerydb/generated.yaml
"""

import argparse
import json
import sys
from pathlib import Path

import requests
import yaml

try:
    from genson import SchemaBuilder
except ImportError:
    print("ERROR: genson is required. Install with: pip install genson")
    sys.exit(1)


def fetch_response(url: str) -> dict | list:
    """Fetch a JSON response from a URL."""
    print(f"Fetching: {url}")
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"ERROR: Failed to fetch {url}: {e}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"ERROR: Response from {url} is not valid JSON")
        sys.exit(1)


def infer_schema(response_body: dict | list) -> dict:
    """Use genson to infer a JSON Schema from a response body."""
    builder = SchemaBuilder()

    if isinstance(response_body, list):
        # For arrays, add multiple objects to get a more complete schema
        for item in response_body[:20]:  # Sample first 20 items
            builder.add_object(item)
        # Wrap in array schema
        item_schema = builder.to_schema()
        return {
            "type": "array",
            "items": item_schema,
        }
    else:
        builder.add_object(response_body)
        return builder.to_schema()


def schema_to_openapi(
    schema: dict,
    url: str,
    title: str = "Auto-Generated API Spec",
) -> dict:
    """Wrap a JSON Schema in a minimal OpenAPI 3.0 document."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    path = parsed.path or "/"
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    # Determine response schema name
    path_parts = [p for p in path.strip("/").split("/") if p]
    schema_name = "".join(p.capitalize() for p in path_parts) if path_parts else "Root"

    openapi_doc = {
        "openapi": "3.0.3",
        "info": {
            "title": title,
            "version": "1.0.0",
            "description": f"Auto-generated from {url}",
        },
        "servers": [{"url": base_url}],
        "paths": {
            path: {
                "get": {
                    "operationId": f"get{schema_name}",
                    "summary": f"Get {schema_name}",
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": schema,
                                },
                            },
                        },
                    },
                },
            },
        },
    }

    return openapi_doc


def save_schema(schema: dict, output_path: str, as_openapi: bool = True) -> None:
    """Save schema to file as YAML or JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        if path.suffix in (".yaml", ".yml"):
            yaml.dump(schema, f, default_flow_style=False, sort_keys=False)
        else:
            json.dump(schema, f, indent=2)

    print(f"Schema saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Auto-generate JSON Schema from live API responses"
    )
    parser.add_argument(
        "--url",
        required=True,
        help="URL to fetch the API response from",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output file path for the generated schema",
    )
    parser.add_argument(
        "--title",
        default="Auto-Generated API Spec",
        help="Title for the generated OpenAPI document",
    )
    parser.add_argument(
        "--raw-schema",
        action="store_true",
        help="Output raw JSON Schema instead of OpenAPI wrapper",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        default=True,
        help="Pretty-print output",
    )
    args = parser.parse_args()

    response_body = fetch_response(args.url)
    schema = infer_schema(response_body)

    print("\nInferred Schema:")
    print(json.dumps(schema, indent=2))
    print()

    if args.raw_schema:
        save_schema(schema, args.output, as_openapi=False)
    else:
        openapi_doc = schema_to_openapi(schema, args.url, args.title)
        save_schema(openapi_doc, args.output, as_openapi=True)

    print("Done!")


if __name__ == "__main__":
    main()