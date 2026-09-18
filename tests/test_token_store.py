import base64

import pytest

from backend.config import Settings
from backend.token_store import read_token, write_token
from backend.upstream import PlanSynchronizer, UpstreamError
from backend.database import Database


def jwt(subject="new"):
    payload = base64.urlsafe_b64encode(
        ('{"sub":"' + subject + '"}').encode()
    ).decode().rstrip("=")
    return f"eyJhbGciOiJIUzI1NiJ9.{payload}.c2ln"


def test_restart_uses_saved_token_over_stale_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("VPLAN_API_TOKEN", "bootstrap")
    monkeypatch.setenv("VPLAN_DATA_DIR", str(tmp_path / "private"))
    path = tmp_path / "private/api-token"
    write_token(path, jwt())
    settings = Settings.load(tmp_path)
    assert settings.api_token == jwt()
    assert settings.token_path == path
    assert path.stat().st_mode & 0o777 == 0o600
    assert not (tmp_path / ".env").exists()


@pytest.mark.parametrize("content", [b"", b"bad-token", b"a" * 20000, b"\xff"])
def test_invalid_saved_token_falls_back(tmp_path, monkeypatch, content):
    monkeypatch.setenv("VPLAN_API_TOKEN", "bootstrap")
    monkeypatch.setenv("VPLAN_DATA_DIR", str(tmp_path))
    (tmp_path / "api-token").write_bytes(content)
    assert Settings.load(tmp_path).api_token == "bootstrap"


def test_missing_token_uses_bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv("VPLAN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VPLAN_API_TOKEN", "bootstrap")
    assert Settings.load(tmp_path).api_token == "bootstrap"
    monkeypatch.delenv("VPLAN_API_TOKEN")
    assert "missing_api_token" in Settings.load(tmp_path).configuration_errors


def test_unreadable_saved_token_fails_closed(tmp_path, monkeypatch):
    def denied(path):
        raise PermissionError("secret-content-must-not-escape")
    monkeypatch.setattr("backend.config.read_token", denied)
    settings = Settings.load(tmp_path)
    assert "saved_api_token_unreadable" in settings.configuration_errors
    assert "secret-content" not in repr(settings)


def test_failed_atomic_replace_preserves_token_and_cleans_temp(tmp_path, monkeypatch):
    path = tmp_path / "api-token"
    write_token(path, jwt("old"))
    def denied(source, destination):
        raise PermissionError("write denied")
    monkeypatch.setattr("backend.token_store.os.replace", denied)
    with pytest.raises(PermissionError):
        write_token(path, jwt())
    assert read_token(path) == jwt("old")
    assert list(tmp_path.iterdir()) == [path]


def test_persist_failure_does_not_change_active_token(settings, monkeypatch):
    synchronizer = PlanSynchronizer(settings, Database(settings.database_path))
    def denied(path, token):
        raise PermissionError("secret-content-must-not-escape")
    monkeypatch.setattr("backend.upstream.write_token", denied)
    with pytest.raises(UpstreamError, match="^token_refresh_persist_error$"):
        synchronizer._persist_api_token(jwt(), "token_refresh_persist_error")
    assert synchronizer._api_token == "test-token"
