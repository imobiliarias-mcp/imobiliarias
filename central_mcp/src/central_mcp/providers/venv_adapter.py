"""Isolated process adapter executing agency tools in their own environment."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

from central_mcp.errors import ProviderError, ProviderErrorCode


class LocalVenvAdapter:
    """Executes agency MCP tools via central_mcp.worker in an isolated process."""

    def __init__(
        self,
        agency_dir: Path,
        adapter_class_name: str,
        provider_name: str = "",
        timeout_seconds: float = 30.0,
        max_output_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        self._agency_dir = agency_dir
        self._class_name = adapter_class_name
        self._provider_name = provider_name or agency_dir.name
        self._timeout_seconds = timeout_seconds
        self._max_output_bytes = max_output_bytes

    def search_rentals(
        self,
        city: str = "",
        min_price: float = 0.0,
        max_price: float = 0.0,
        bedrooms: int = 0,
        property_type: str = "",
        page: int = 1,
    ) -> dict[str, Any]:
        """Execute search_rentals tool inside the worker process."""
        kwargs = self._build_search_kwargs(
            city, min_price, max_price, bedrooms, property_type, page
        )
        return self._invoke("search_rentals", kwargs)

    def _build_search_kwargs(
        self,
        city: str,
        min_price: float,
        max_price: float,
        bedrooms: int,
        property_type: str,
        page: int,
    ) -> dict[str, Any]:
        if self._provider_name == "marcioimoveis":
            return {
                "locations": [city] if city else None,
                "min_price": min_price,
                "max_price": max_price,
                "bedrooms": bedrooms,
                "property_type": property_type,
                "page": page,
            }
        if self._provider_name == "imobiliariaportalmg":
            return {
                "city_id": city,
                "min_price": min_price,
                "max_price": max_price,
                "bedrooms": bedrooms,
                "page": page,
            }
        return {
            "city": city,
            "min_price": min_price,
            "max_price": max_price,
            "bedrooms": bedrooms,
            "property_type": property_type,
            "page": page,
        }

    def get_property_detail(self, property_code: str) -> dict[str, Any]:
        """Execute get_property_detail tool inside the worker process."""
        return self._invoke("get_property_detail", {"property_code": property_code})

    def get_facets(self) -> dict[str, Any]:
        """Execute get_facets tool inside the worker process."""
        return self._invoke("get_facets", {})

    def get_provider_info(self) -> dict[str, Any]:
        """Execute get_provider_info tool inside the worker process."""
        return self._invoke("get_provider_info", {})

    def _build_env(self) -> dict[str, str]:
        current_env = dict(os.environ)
        paths = [str(self._agency_dir), str(self._agency_dir / "src")]
        venv_sp = list(self._agency_dir.glob(".venv/lib/python*/site-packages"))
        paths.extend(str(sp) for sp in venv_sp)
        paths.extend(p for p in sys.path if p)
        current_env["PYTHONPATH"] = os.pathsep.join(paths)
        return current_env

    def _build_payload(self, method: str, kwargs: dict[str, Any]) -> bytes:
        payload = {
            "provider": self._provider_name,
            "adapter_class": self._class_name,
            "method": method,
            "kwargs": kwargs,
        }
        return json.dumps(payload).encode("utf-8")

    def _kill_process_group(self, proc: subprocess.Popen) -> None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass
        proc.wait()

    def _run_subprocess(self, payload: bytes) -> tuple[int, bytes, bytes]:
        cmd = [sys.executable, "-m", "central_mcp.worker"]
        env = self._build_env()
        proc = subprocess.Popen(
            cmd,
            cwd=str(self._agency_dir),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            start_new_session=True,
        )
        try:
            stdout, stderr = proc.communicate(input=payload, timeout=self._timeout_seconds)
            return proc.returncode, stdout, stderr
        except subprocess.TimeoutExpired:
            self._kill_process_group(proc)
            raise ProviderError(
                self._provider_name,
                ProviderErrorCode.TIMEOUT,
                f"Execution timed out after {self._timeout_seconds}s",
            )

    def _decode_output(self, stdout: bytes, stderr: bytes, code: int) -> dict[str, Any]:
        if len(stdout) > self._max_output_bytes:
            raise ProviderError(
                self._provider_name,
                ProviderErrorCode.OUTPUT_TOO_LARGE,
                f"Output length {len(stdout)} exceeded limit {self._max_output_bytes}",
            )
        if code != 0:
            err_msg = stderr.decode("utf-8", errors="replace").strip()
            raise ProviderError(
                self._provider_name,
                ProviderErrorCode.UPSTREAM_ERROR,
                err_msg or f"Worker exited with code {code}",
            )
        try:
            return json.loads(stdout.decode("utf-8"))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ProviderError(
                self._provider_name,
                ProviderErrorCode.INVALID_OUTPUT,
                f"Invalid JSON: {exc}",
            )

    def _invoke(self, method: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        payload = self._build_payload(method, kwargs)
        code, stdout, stderr = self._run_subprocess(payload)
        return self._decode_output(stdout, stderr, code)
