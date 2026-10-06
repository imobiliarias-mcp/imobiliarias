"""Tests for LocalVenvAdapter using worker process."""

from pathlib import Path
import pytest

from central_mcp.errors import ProviderError, ProviderErrorCode
from central_mcp.providers.venv_adapter import LocalVenvAdapter


def _setup_fake_agency(path: Path, class_name: str, method_body: str) -> None:
    scripts_dir = path / "scripts" / "mcp"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    tools_file = scripts_dir / "tools.py"
    tools_file.write_text(
        f"class {class_name}:\n"
        f"    @classmethod\n"
        f"    def create_default(cls):\n"
        f"        return cls()\n"
        f"{method_body}\n"
    )


def test_adapter_successful_call(tmp_path: Path):
    agency = tmp_path / "agency_a"
    _setup_fake_agency(
        agency,
        "AdapterA",
        "    def search_rentals(self, **kwargs):\n"
        "        return {'agency': 'A', 'params': kwargs}\n",
    )
    adapter = LocalVenvAdapter(agency, "AdapterA", provider_name="agency_a")
    result = adapter.search_rentals(city="Fabriciano", page=2)
    assert result["agency"] == "A"
    assert result["params"]["city"] == "Fabriciano"
    assert result["params"]["page"] == 2


def test_adapter_timeout_raises_provider_error(tmp_path: Path):
    agency = tmp_path / "agency_hang"
    _setup_fake_agency(
        agency,
        "AdapterHang",
        "    def search_rentals(self, **kwargs):\n"
        "        import time\n"
        "        time.sleep(5)\n"
        "        return {}\n",
    )
    adapter = LocalVenvAdapter(
        agency,
        "AdapterHang",
        provider_name="agency_hang",
        timeout_seconds=0.3,
    )
    with pytest.raises(ProviderError) as exc_info:
        adapter.search_rentals()
    assert exc_info.value.code == ProviderErrorCode.TIMEOUT
    assert exc_info.value.provider == "agency_hang"


def test_adapter_upstream_error_raises_provider_error(tmp_path: Path):
    agency = tmp_path / "agency_fail"
    _setup_fake_agency(
        agency,
        "AdapterFail",
        "    def search_rentals(self, **kwargs):\n"
        "        raise RuntimeError('Database exploded')\n",
    )
    adapter = LocalVenvAdapter(agency, "AdapterFail", provider_name="agency_fail")
    with pytest.raises(ProviderError) as exc_info:
        adapter.search_rentals()
    assert exc_info.value.code == ProviderErrorCode.UPSTREAM_ERROR
    assert "Database exploded" in exc_info.value.message


def test_adapter_output_too_large(tmp_path: Path):
    agency = tmp_path / "agency_large"
    _setup_fake_agency(
        agency,
        "AdapterLarge",
        "    def search_rentals(self, **kwargs):\n"
        "        return {'data': 'x' * 5000}\n",
    )
    adapter = LocalVenvAdapter(
        agency,
        "AdapterLarge",
        provider_name="agency_large",
        max_output_bytes=1000,
    )
    with pytest.raises(ProviderError) as exc_info:
        adapter.search_rentals()
    assert exc_info.value.code == ProviderErrorCode.OUTPUT_TOO_LARGE


def test_two_agencies_isolated_scripts(tmp_path: Path):
    agency1 = tmp_path / "agency1"
    agency2 = tmp_path / "agency2"

    _setup_fake_agency(
        agency1,
        "SharedName",
        "    def get_provider_info(self):\n"
        "        return {'agency': 1}\n",
    )
    _setup_fake_agency(
        agency2,
        "SharedName",
        "    def get_provider_info(self):\n"
        "        return {'agency': 2}\n",
    )

    adapter1 = LocalVenvAdapter(agency1, "SharedName", provider_name="agency1")
    adapter2 = LocalVenvAdapter(agency2, "SharedName", provider_name="agency2")

    assert adapter1.get_provider_info()["agency"] == 1
    assert adapter2.get_provider_info()["agency"] == 2
