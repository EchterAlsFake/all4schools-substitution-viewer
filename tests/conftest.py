from __future__ import annotations

from pathlib import Path

import pytest

from backend.config import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        base_dir=tmp_path,
        api_url="https://example.invalid/api",
        api_refresh_url="https://example.invalid/api/refresh",
        api_auth_url="https://example.invalid/api/auth",
        api_token="test-token",
        api_username="test-user",
        api_password="test-password",
        school_id=999,
        gate_answers=("ROOM42", "42"),
        public_host="testserver",
        trust_cloudflare_ip=False,
        secure_cookie=False,
        upgrade_insecure_requests=True,
        sync_enabled=False,
        sync_interval_seconds=300,
        request_timeout_seconds=5,
        max_response_bytes=1024 * 1024,
        database_path=tmp_path / "vplan.db",
        cache_path=tmp_path / "plan-cache.json",
        configuration_errors=(),
    )


@pytest.fixture
def anyio_backend():
    return "asyncio"
