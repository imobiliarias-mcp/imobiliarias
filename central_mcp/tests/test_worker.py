"""Tests for central_mcp.worker process."""

import json
import subprocess
import sys
from pathlib import Path


def test_worker_disallowed_method_rejected(tmp_path: Path):
    request = {
        "provider": "dummy",
        "adapter_class": "DummyAdapter",
        "method": "evil_method",
        "kwargs": {},
    }
    proc = subprocess.run(
        [sys.executable, "-m", "central_mcp.worker"],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "Disallowed method" in proc.stderr


def test_worker_invalid_json_stdin():
    proc = subprocess.run(
        [sys.executable, "-m", "central_mcp.worker"],
        input="not-valid-json",
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "Invalid JSON" in proc.stderr


def test_worker_successful_invocation(tmp_path: Path):
    # Create fake agency with scripts/mcp/tools.py
    scripts_dir = tmp_path / "scripts" / "mcp"
    scripts_dir.mkdir(parents=True)
    tools_file = scripts_dir / "tools.py"
    tools_file.write_text(
        "class FakeTool:\n"
        "    @classmethod\n"
        "    def create_default(cls):\n"
        "        return cls()\n"
        "    def search_rentals(self, **kwargs):\n"
        "        return {'status': 'ok', 'results': [1, 2, 3]}\n"
    )

    request = {
        "provider": "fake",
        "adapter_class": "FakeTool",
        "method": "search_rentals",
        "kwargs": {"city": "Timóteo"},
    }

    env = {"PYTHONPATH": str(tmp_path)}
    proc = subprocess.run(
        [sys.executable, "-m", "central_mcp.worker"],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env={**dict(env), "PATH": "/usr/bin:/bin"},
        check=False,
    )
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out == {"status": "ok", "results": [1, 2, 3]}
