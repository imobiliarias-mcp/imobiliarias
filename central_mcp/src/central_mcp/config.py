"""Application configuration and validation for Central MCP."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    """Runtime limits and server settings."""

    host: str = "0.0.0.0"
    port: int = 8000
    worker_timeout_seconds: float = 30.0
    max_worker_stdout_bytes: int = 10 * 1024 * 1024
    max_concurrent_workers: int = 10
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 10
    trusted_proxies: tuple[str, ...] = ()
    allowed_hosts: tuple[str, ...] = ("localhost", "127.0.0.1", "*")
    allowed_origins: tuple[str, ...] = ("*",)
    stateless_http: bool = True
    provider_min_interval_seconds: float = 1.0
    web_enabled: bool = True
    static_dir: str | None = None
    enrich_concurrency: int = 5
    detail_cache_ttl_seconds: float = 900.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> AppConfig:
        """Parse configuration from environment mapping or os.environ."""
        source = os.environ if env is None else env
        cfg = cls._build_from_mapping(source)
        cfg._validate()
        return cfg

    @classmethod
    def _build_from_mapping(cls, source: Mapping[str, str]) -> AppConfig:
        host = source.get("CENTRAL_MCP_HOST", "0.0.0.0")
        port = int(source.get("CENTRAL_MCP_PORT", "8000"))
        timeout = float(source.get("CENTRAL_MCP_WORKER_TIMEOUT", "30.0"))
        max_workers = int(source.get("CENTRAL_MCP_MAX_CONCURRENT_WORKERS", "10"))
        rate_limit = int(source.get("CENTRAL_MCP_RATE_LIMIT_PER_MINUTE", "60"))
        burst = int(source.get("CENTRAL_MCP_RATE_LIMIT_BURST", "10"))
        proxies = cls._parse_csv(source.get("CENTRAL_MCP_TRUSTED_PROXIES", ""))
        stateless = source.get("CENTRAL_MCP_STATELESS_HTTP", "true").lower() == "true"
        web_enabled = source.get("CENTRAL_MCP_WEB_ENABLED", "true").lower() == "true"
        static_dir = source.get("CENTRAL_MCP_STATIC_DIR") or None
        enrich_concurrency = int(source.get("CENTRAL_MCP_ENRICH_CONCURRENCY", "5"))
        detail_cache_ttl = float(source.get("CENTRAL_MCP_DETAIL_CACHE_TTL", "900"))
        return cls(
            host=host,
            port=port,
            worker_timeout_seconds=timeout,
            max_concurrent_workers=max_workers,
            rate_limit_per_minute=rate_limit,
            rate_limit_burst=burst,
            trusted_proxies=proxies,
            stateless_http=stateless,
            web_enabled=web_enabled,
            static_dir=static_dir,
            enrich_concurrency=enrich_concurrency,
            detail_cache_ttl_seconds=detail_cache_ttl,
        )

    @staticmethod
    def _parse_csv(raw: str) -> tuple[str, ...]:
        parts = [item.strip() for item in raw.split(",") if item.strip()]
        return tuple(parts)

    def _validate(self) -> None:
        if not (1 <= self.port <= 65535):
            raise ValueError(f"Port must be between 1 and 65535, got {self.port}")
        if self.worker_timeout_seconds <= 0:
            raise ValueError("worker_timeout_seconds must be positive")
        if self.max_concurrent_workers <= 0:
            raise ValueError("max_concurrent_workers must be positive")
        if self.rate_limit_per_minute <= 0 or self.rate_limit_burst <= 0:
            raise ValueError("rate limit parameters must be positive")
        if self.enrich_concurrency <= 0:
            raise ValueError("enrich_concurrency must be positive")
        if self.detail_cache_ttl_seconds < 0:
            raise ValueError("detail_cache_ttl_seconds must not be negative")
