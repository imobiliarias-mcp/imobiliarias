"""Worker process executing agency MCP tools in an isolated process context."""

from __future__ import annotations

import importlib
import json
import sys
from typing import Any

ALLOWED_METHODS = frozenset(
    {"search_rentals", "get_property_detail", "get_facets", "get_provider_info"}
)


def _read_request() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        sys.stderr.write("Empty request on stdin\n")
        sys.exit(1)
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        sys.stderr.write(f"Invalid JSON on stdin: {exc}\n")
        sys.exit(1)
    if not isinstance(data, dict):
        sys.stderr.write("Request payload must be a JSON object\n")
        sys.exit(1)
    return data


def _validate_method(method: str) -> None:
    if method not in ALLOWED_METHODS:
        sys.stderr.write(f"Disallowed method: {method}\n")
        sys.exit(2)


def _load_adapter(class_name: str) -> Any:
    module = importlib.import_module("scripts.mcp.tools")
    cls = getattr(module, class_name)
    if hasattr(cls, "create_default"):
        return cls.create_default()
    return cls()


def _execute(adapter: Any, method: str, kwargs: dict[str, Any]) -> Any:
    fn = getattr(adapter, method)
    return fn(**kwargs)


def _write_response(result: Any) -> None:
    payload = json.dumps(result, default=str)
    sys.stdout.write(payload)
    sys.stdout.flush()


def main() -> None:
    """Run worker loop for a single tool execution."""
    req = _read_request()
    method = str(req.get("method", ""))
    _validate_method(method)
    class_name = str(req.get("adapter_class", ""))
    kwargs = req.get("kwargs", {})
    try:
        adapter = _load_adapter(class_name)
        result = _execute(adapter, method, kwargs)
        _write_response(result)
    except (RuntimeError, OSError, ValueError, KeyError, AttributeError, TypeError, ImportError) as exc:
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
