"""Auto-generate JSON Schema from live API responses using genson."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from genson import SchemaBuilder


def infer_schema(response_body: Any) -> dict[str, Any]:
    """Infer a JSON Schema from a response payload."""
    builder = SchemaBuilder()
    if isinstance(response_body, list):
        for item in response_body[:20]:  # Sample first 20 for arrays
            builder.add_object(item)
        return {"type": "array", "items": builder.to_schema()}
    else:
        builder.add_object(response_body)
        return builder.to_schema()


def infer_and_save(response_body: Any, output_path: str | Path) -> dict[str, Any]:
    """Infer a schema and write it to disk as JSON."""
    schema = infer_schema(response_body)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(schema, f, indent=2)
    return schema