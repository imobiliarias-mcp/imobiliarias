"""Tests for central_mcp config and error hierarchy."""

import pytest
from central_mcp.config import AppConfig
from central_mcp.errors import ProviderError, ProviderErrorCode


def test_provider_error_attributes_and_string():
    err = ProviderError(
        provider="alecorretoramg",
        code=ProviderErrorCode.TIMEOUT,
        message="Process timed out after 30s",
    )
    assert err.provider == "alecorretoramg"
    assert err.code == "timeout"
    assert "alecorretoramg" in str(err)
    assert "timeout" in str(err)
    assert "Process timed out" in str(err)


def test_provider_error_invalid_code_rejected():
    with pytest.raises(ValueError, match="Invalid error code"):
        ProviderError(
            provider="test",
            code="non_existent_code",
            message="bad",
        )


def test_app_config_defaults():
    cfg = AppConfig.from_env({})
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 8000
    assert cfg.worker_timeout_seconds == 30.0
    assert cfg.max_concurrent_workers == 10
    assert cfg.rate_limit_per_minute == 60
    assert cfg.rate_limit_burst == 10
    assert cfg.trusted_proxies == ()
    assert cfg.stateless_http is True


def test_app_config_env_overrides():
    env = {
        "CENTRAL_MCP_HOST": "127.0.0.1",
        "CENTRAL_MCP_PORT": "9000",
        "CENTRAL_MCP_WORKER_TIMEOUT": "15.5",
        "CENTRAL_MCP_MAX_CONCURRENT_WORKERS": "5",
        "CENTRAL_MCP_RATE_LIMIT_PER_MINUTE": "120",
        "CENTRAL_MCP_RATE_LIMIT_BURST": "20",
        "CENTRAL_MCP_TRUSTED_PROXIES": "10.0.0.1, 10.0.0.2",
        "CENTRAL_MCP_STATELESS_HTTP": "false",
    }
    cfg = AppConfig.from_env(env)
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 9000
    assert cfg.worker_timeout_seconds == 15.5
    assert cfg.max_concurrent_workers == 5
    assert cfg.rate_limit_per_minute == 120
    assert cfg.rate_limit_burst == 20
    assert cfg.trusted_proxies == ("10.0.0.1", "10.0.0.2")
    assert cfg.stateless_http is False


def test_app_config_validation_invalid_port():
    with pytest.raises(ValueError, match="Port must be between 1 and 65535"):
        AppConfig.from_env({"CENTRAL_MCP_PORT": "70000"})


def test_app_config_validation_invalid_timeout():
    with pytest.raises(ValueError, match="worker_timeout_seconds must be positive"):
        AppConfig.from_env({"CENTRAL_MCP_WORKER_TIMEOUT": "-1"})
