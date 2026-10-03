"""Isolated virtualenv adapter executing agency tools in their own environment."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class LocalVenvAdapter:
    """Executes agency MCP tools within that agency's dedicated virtual environment."""

    def __init__(self, agency_dir: Path, adapter_class_name: str) -> None:
        """Initialize with target agency directory and adapter class name."""
        self._agency_dir = agency_dir
        self._class_name = adapter_class_name

    def search_rentals(
        self,
        city: str = "",
        min_price: float = 0.0,
        max_price: float = 0.0,
        bedrooms: int = 0,
        property_type: str = "",
        page: int = 1,
    ) -> dict[str, Any]:
        """Execute search_rentals tool inside the agency venv."""
        kwargs = {
            "city": city,
            "min_price": min_price,
            "max_price": max_price,
            "bedrooms": bedrooms,
            "property_type": property_type,
            "page": page,
        }
        return self._invoke("search_rentals", kwargs)

    def get_property_detail(self, property_code: str) -> dict[str, Any]:
        """Execute get_property_detail tool inside the agency venv."""
        return self._invoke("get_property_detail", {"property_code": property_code})

    def get_facets(self) -> dict[str, Any]:
        """Execute get_facets tool inside the agency venv."""
        return self._invoke("get_facets", {})

    def get_provider_info(self) -> dict[str, Any]:
        """Execute get_provider_info tool inside the agency venv."""
        return self._invoke("get_provider_info", {})

    def _resolve_python(self) -> str:
        """Find virtualenv python binary or fall back to current executable."""
        venv_python = self._agency_dir / ".venv" / "bin" / "python"
        if venv_python.exists():
            return str(venv_python)
        return sys.executable

    def _build_script(self, method: str, kwargs: dict[str, Any]) -> str:
        """Generate safe invocation script."""
        payload_json = json.dumps(kwargs)
        return (
            f"import json, sys; from scripts.mcp.tools import {self._class_name}; "
            f"a = {self._class_name}.create_default(); "
            f"res = getattr(a, '{method}')(**{payload_json}); "
            f"sys.stdout.write(json.dumps(res))"
        )

    def _invoke(self, method: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Run subprocess in the agency directory and capture JSON output."""
        python_bin = self._resolve_python()
        script = self._build_script(method, kwargs)
        cmd = [python_bin, "-c", script]
        proc = subprocess.run(
            cmd,
            cwd=str(self._agency_dir),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if proc.returncode != 0:
            error_msg = proc.stderr.strip() or f"Process failed with code {proc.returncode}"
            return {"error": error_msg, "status": "error"}
        return json.loads(proc.stdout)
