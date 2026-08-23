from __future__ import annotations

from pathlib import Path

import pytest

from backend.config import Settings


def configure_required_environment(monkeypatch) -> None:
    for name in ("VPLAN_DATA_DIR", "VPLAN_DATABASE_PATH", "VPLAN_CACHE_PATH"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("VPLAN_API_TOKEN", "test-token")
    monkeypatch.setenv("VPLAN_SCHOOL_ID", "999")
    monkeypatch.setenv("VPLAN_GATE_ANSWERS", " Room 42 , 42 ")
    monkeypatch.setenv("VPLAN_API_URL", "https://example.invalid/api")
    monkeypatch.setenv(
        "VPLAN_API_REFRESH_URL", "https://example.invalid/api/refresh"
    )
    monkeypatch.setenv("VPLAN_API_AUTH_URL", "https://example.invalid/api/auth")
    monkeypatch.setenv("VPLAN_UPGRADE_INSECURE_REQUESTS", "true")
    monkeypatch.setenv("USERNAME", "test-user")
    monkeypatch.setenv("PASSWORD", "test-password")


def test_settings_normalize_answers_and_resolve_local_paths(
    tmp_path: Path, monkeypatch
):
    configure_required_environment(monkeypatch)
    monkeypatch.setenv("VPLAN_DATA_DIR", "runtime")
    monkeypatch.setenv("VPLAN_DATABASE_PATH", "private/database.sqlite")

    settings = Settings.load(tmp_path)

    assert settings.configuration_errors == ()
    assert settings.gate_answers == ("ROOM42", "42")
    assert settings.api_username == "test-user"
    assert settings.api_password == "test-password"
    assert settings.upgrade_insecure_requests is True
    assert "test-token" not in repr(settings)
    assert "test-user" not in repr(settings)
    assert "test-password" not in repr(settings)
    assert settings.database_path == (tmp_path / "private/database.sqlite").resolve()
    assert settings.cache_path == (tmp_path / "runtime/plan-cache.json").resolve()


def test_insecure_api_url_fails_closed(tmp_path: Path, monkeypatch):
    configure_required_environment(monkeypatch)
    monkeypatch.setenv("VPLAN_API_URL", "http://example.invalid/api")

    settings = Settings.load(tmp_path)

    assert "invalid_api_url" in settings.configuration_errors


def test_insecure_api_refresh_url_fails_closed(tmp_path: Path, monkeypatch):
    configure_required_environment(monkeypatch)
    monkeypatch.setenv("VPLAN_API_REFRESH_URL", "http://example.invalid/api/refresh")

    settings = Settings.load(tmp_path)

    assert "invalid_api_refresh_url" in settings.configuration_errors


def test_insecure_api_auth_url_fails_closed(tmp_path: Path, monkeypatch):
    configure_required_environment(monkeypatch)
    monkeypatch.setenv("VPLAN_API_AUTH_URL", "http://example.invalid/api/auth")

    settings = Settings.load(tmp_path)

    assert "invalid_api_auth_url" in settings.configuration_errors


@pytest.mark.parametrize(
    ("variable", "expected_error"),
    (
        ("VPLAN_API_URL", "missing_api_url"),
        ("VPLAN_API_REFRESH_URL", "missing_api_refresh_url"),
        ("VPLAN_API_AUTH_URL", "missing_api_auth_url"),
    ),
)
def test_missing_api_urls_fail_closed(
    tmp_path: Path, monkeypatch, variable: str, expected_error: str
):
    configure_required_environment(monkeypatch)
    monkeypatch.delenv(variable)

    settings = Settings.load(tmp_path)

    assert expected_error in settings.configuration_errors


def test_login_credentials_are_read_from_local_dotenv(tmp_path: Path, monkeypatch):
    configure_required_environment(monkeypatch)
    monkeypatch.setenv("USERNAME", "external-user")
    monkeypatch.setenv("PASSWORD", "external-password")
    (tmp_path / ".env").write_text(
        "USERNAME=dotenv-user\nPASSWORD=dotenv-password\n", encoding="utf-8"
    )

    settings = Settings.load(tmp_path)

    assert settings.api_username == "dotenv-user"
    assert settings.api_password == "dotenv-password"


def test_sync_interval_is_never_shorter_than_five_minutes(tmp_path: Path, monkeypatch):
    configure_required_environment(monkeypatch)
    monkeypatch.setenv("VPLAN_SYNC_INTERVAL_SECONDS", "120")

    settings = Settings.load(tmp_path)

    assert settings.sync_interval_seconds == 300


def test_upgrade_insecure_requests_can_be_disabled(tmp_path: Path, monkeypatch):
    configure_required_environment(monkeypatch)
    monkeypatch.setenv("VPLAN_UPGRADE_INSECURE_REQUESTS", "false")

    settings = Settings.load(tmp_path)

    assert settings.upgrade_insecure_requests is False
