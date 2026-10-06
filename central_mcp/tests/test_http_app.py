"""Tests for Starlette HTTP combined application and rate limiting middleware."""

from starlette.testclient import TestClient

from central_mcp.config import AppConfig
from central_mcp.http_app import create_http_app
from central_mcp.server import create_mcp_server


def test_healthz_endpoint():
    cfg = AppConfig.from_env({})
    mcp_server = create_mcp_server()
    app = create_http_app(mcp_server, cfg)

    with TestClient(app) as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


def test_rate_limiting_middleware_429():
    cfg = AppConfig(rate_limit_per_minute=60, rate_limit_burst=2)
    mcp_server = create_mcp_server()
    app = create_http_app(mcp_server, cfg)

    with TestClient(app) as client:
        # Healthz is exempt
        for _ in range(5):
            h_resp = client.get("/healthz")
            assert h_resp.status_code == 200

        # First 2 requests pass burst
        r1 = client.post("/mcp", json={})
        assert r1.status_code != 429

        r2 = client.post("/mcp", json={})
        assert r2.status_code != 429

        # 3rd request exceeds burst
        r3 = client.post("/mcp", json={})
        assert r3.status_code == 429
        assert "retry-after" in r3.headers


def test_trusted_proxy_forwarded_for():
    cfg = AppConfig(
        rate_limit_per_minute=60,
        rate_limit_burst=1,
        trusted_proxies=("testclient",),
    )
    mcp_server = create_mcp_server()
    app = create_http_app(mcp_server, cfg)

    with TestClient(app) as client:
        # Client A consumes token
        res1 = client.post("/mcp", json={}, headers={"X-Forwarded-For": "203.0.113.195"})
        assert res1.status_code != 429

        # Client A again exceeds rate limit
        res2 = client.post("/mcp", json={}, headers={"X-Forwarded-For": "203.0.113.195"})
        assert res2.status_code == 429

        # Client B should still be allowed
        res3 = client.post("/mcp", json={}, headers={"X-Forwarded-For": "198.51.100.1"})
        assert res3.status_code != 429
