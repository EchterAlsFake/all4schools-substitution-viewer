from __future__ import annotations

import base64
import json
from dataclasses import replace
from datetime import datetime

from backend.database import Database
from backend.schemas import UpstreamSubstitution
from backend.upstream import (
    BERLIN,
    PlanSynchronizer,
    UpstreamError,
    _teacher_names,
    normalize_entries,
    query_window,
    redact_teacher_text,
    school_year,
)


def sample_entry(**changes):
    payload = {
        "id": 123,
        "type": 1,
        "start": "2026-08-24T07:45:00+02:00",
        "end": "2026-08-24T08:30:00+02:00",
        "oldSubject": "CHE",
        "newSubject": None,
        "oldRooms": [{"id": 1, "name": "A415"}],
        "newRooms": [{"id": 2, "name": None}],
        "oldTeachers": [{"id": 7, "name": "LiGyDe.Abc"}],
        "newTeachers": [],
        "oldClasses": [{"id": 8, "name": "12_CHE1"}],
        "newClasses": [],
        "comment": "Aufgaben von Abc; Rückfrage bei LiGyDe.Abc.",
    }
    payload.update(changes)
    return UpstreamSubstitution.model_validate(payload)


def test_query_window_skips_weekend():
    start, end = query_window(datetime(2026, 8, 21, 12, tzinfo=BERLIN))

    assert start.isoformat() == "2026-08-21T00:00:00"
    assert end.isoformat() == "2026-08-24T23:59:59"


def test_normalization_removes_all_teacher_objects_and_ids():
    entry = sample_entry(newClasses=[{"id": 9, "name": "12_CHE2"}])
    normalized, courses = normalize_entries([entry], {"LiGyDe.Abc", "Abc"})
    serialized = json.dumps(normalized)

    assert courses == {"12_CHE1", "12_CHE2"}
    assert "teacher" not in serialized.casefold()
    assert "LiGyDe.Abc" not in serialized
    assert '"id": 7' not in serialized
    assert normalized[0]["comment"] == "Aufgaben von Lehrkraft; Rückfrage bei Lehrkraft."
    assert normalized[0]["newRooms"] == []
    assert normalized[0]["classes"] == ["12_CHE1", "12_CHE2"]

    same_public_entry, _ = normalize_entries(
        [sample_entry(id=999, newClasses=[{"id": 77, "name": "12_CHE2"}])],
        {"LiGyDe.Abc", "Abc"},
    )
    assert same_public_entry[0]["id"] == normalized[0]["id"]


def test_teacher_redaction_handles_titles_and_known_names():
    value = redact_teacher_text(
        "Frau Dr. Anne Beispiel und Testperson übernehmen.", {"Testperson"}
    )
    assert value == "Lehrkraft und Lehrkraft übernehmen."


def test_structured_teacher_names_also_redact_short_codes_and_subjects():
    entry = sample_entry(
        oldTeachers=[
            {"id": 7, "name": "LiGyDe.Qxz"},
            {"id": 8, "name": "LiGyDe.Vwp"},
        ],
        oldSubject="Vertretung LiGyDe.Qxz",
        comment="Qxz und Vwp in B204.",
    )
    names = _teacher_names([entry])
    normalized, _ = normalize_entries([entry], names)

    assert normalized[0]["oldSubject"] == "Vertretung Lehrkraft"
    assert normalized[0]["comment"] == "Lehrkraft und Lehrkraft in B204."


def test_teacher_codes_are_learned_from_strong_free_text_contexts():
    entry = sample_entry(
        oldTeachers=[{"id": 7, "name": "Frau Dr. Beispielperson"}],
        newTeachers=[],
        comment=(
            "Aufgaben von Abc; Qxz und Vwp in B204; "
            "Rückfrage bei LiGyDe.Rst und Beispielperson."
        ),
    )

    names = _teacher_names([entry])
    normalized, _ = normalize_entries([entry], names)

    assert {
        "Abc",
        "Qxz",
        "Vwp",
        "LiGyDe.Rst",
        "Rst",
        "Frau Dr. Beispielperson",
        "Beispielperson",
    }.issubset(names)
    assert normalized[0]["comment"] == (
        "Aufgaben von Lehrkraft; Lehrkraft und Lehrkraft in B204; "
        "Rückfrage bei Lehrkraft und Lehrkraft."
    )


class FakeResponse:
    def __init__(self, payload, *, status_code=200, headers=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.payload = payload
        self.content = json.dumps(payload).encode()
        self.text = self.content.decode()

    def json(self):
        return self.payload


def fake_jwt(subject: str = "vplan-test") -> str:
    def encode(payload: dict[str, str]) -> str:
        return base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":")).encode()
        ).decode().rstrip("=")

    return f"{encode({'alg': 'HS256', 'typ': 'JWT'})}.{encode({'sub': subject})}.c2ln"


def test_http3_is_tried_before_http2_fallback(settings):
    database = Database(settings.database_path)
    database.initialize()
    synchronizer = PlanSynchronizer(settings, database)
    calls: list[tuple[dict, str]] = []

    def request(payload, http_version):
        calls.append((payload, http_version))
        if http_version == "v3":
            raise UpstreamError("transport_error_v3")
        return FakeResponse([sample_entry().model_dump(mode="json")])

    synchronizer._request = request  # type: ignore[method-assign]
    result = synchronizer.fetch()

    assert result["status"] == "updated"
    assert result["protocol"] == "h2_fallback"
    assert [version for _, version in calls] == ["v3", "v2"]
    assert calls[0][0]["schoolIds"] == [999]
    cache = settings.cache_path.read_text(encoding="utf-8")
    assert "LiGyDe.Abc" not in cache
    assert "oldTeachers" not in cache


def test_expired_token_is_refreshed_persisted_and_retried_once(settings):
    database = Database(settings.database_path)
    database.initialize()
    synchronizer = PlanSynchronizer(settings, database)
    env_path = settings.base_dir / ".env"
    env_path.write_text(
        "VPLAN_API_TOKEN=test-token\nVPLAN_SCHOOL_ID=999\n", encoding="utf-8"
    )
    refreshed_token = fake_jwt()
    plan_tokens: list[str] = []
    refresh_calls: list[tuple[str, str]] = []

    def request(payload, http_version):
        plan_tokens.append(synchronizer._api_token)
        if len(plan_tokens) == 1:
            raise UpstreamError("upstream_http_401")
        return FakeResponse([sample_entry().model_dump(mode="json")])

    def refresh_request(token, http_version):
        refresh_calls.append((token, http_version))
        return FakeResponse({"accessToken": refreshed_token})

    synchronizer._request = request  # type: ignore[method-assign]
    synchronizer._refresh_request = refresh_request  # type: ignore[method-assign]

    result = synchronizer.fetch()

    assert result["status"] == "updated"
    assert result["tokenRefreshed"] is True
    assert plan_tokens == ["test-token", refreshed_token]
    assert refresh_calls == [("test-token", "v3")]
    persisted = env_path.read_text(encoding="utf-8")
    assert f"VPLAN_API_TOKEN='{refreshed_token}'" in persisted
    assert "VPLAN_SCHOOL_ID=999" in persisted
    assert "test-token" not in persisted


def test_invalid_refreshed_token_is_not_persisted_or_retried(settings):
    database = Database(settings.database_path)
    database.initialize()
    synchronizer = PlanSynchronizer(settings, database)
    env_path = settings.base_dir / ".env"
    original_env = "VPLAN_API_TOKEN=test-token\nVPLAN_SCHOOL_ID=999\n"
    env_path.write_text(original_env, encoding="utf-8")
    plan_requests = 0

    def request(payload, http_version):
        nonlocal plan_requests
        plan_requests += 1
        raise UpstreamError("upstream_http_401")

    synchronizer._request = request  # type: ignore[method-assign]
    synchronizer._refresh_request = (  # type: ignore[method-assign]
        lambda token, version: FakeResponse({"token": "not-a-jwt"})
    )

    def fail_session_auth():
        raise UpstreamError("session_auth_upstream_http_401")

    synchronizer._authenticate_new_session = fail_session_auth  # type: ignore[method-assign]

    result = synchronizer.fetch()

    assert result == {
        "status": "error",
        "code": "session_auth_upstream_http_401",
        "refreshCode": "token_refresh_invalid_refreshed_token",
        "tokenRefreshAttempted": True,
        "sessionAuthAttempted": True,
    }
    assert plan_requests == 1
    assert env_path.read_text(encoding="utf-8") == original_env


def test_failed_request_after_token_refresh_is_reported(settings):
    database = Database(settings.database_path)
    database.initialize()
    synchronizer = PlanSynchronizer(settings, database)
    (settings.base_dir / ".env").write_text(
        "VPLAN_API_TOKEN=test-token\n", encoding="utf-8"
    )
    requests_count = 0

    def request(payload, http_version):
        nonlocal requests_count
        requests_count += 1
        raise UpstreamError(
            "upstream_http_401" if requests_count == 1 else "upstream_http_500"
        )

    synchronizer._request = request  # type: ignore[method-assign]
    synchronizer._refresh_request = (  # type: ignore[method-assign]
        lambda token, version: FakeResponse(fake_jwt("retry-failure"))
    )

    result = synchronizer.fetch()

    assert result == {
        "status": "error",
        "code": "after_token_refresh_upstream_http_500",
        "tokenRefreshAttempted": True,
    }
    assert requests_count == 2


def test_refresh_endpoint_uses_current_bearer_and_chrome_http3(settings):
    database = Database(settings.database_path)
    database.initialize()
    synchronizer = PlanSynchronizer(settings, database)
    captured: dict[str, object] = {}

    class RecordingSession:
        def post(self, url, **options):
            captured["url"] = url
            captured.update(options)
            return FakeResponse(fake_jwt())

        def get(self, url, **options):
            raise AssertionError("GET fallback was not expected")

        def close(self):
            pass

    synchronizer._session.close()
    synchronizer._session = RecordingSession()

    synchronizer._refresh_request("current-token", "v3")

    assert captured["url"] == settings.api_refresh_url
    assert captured["headers"] == {
        "Authorization": "Bearer current-token",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    assert captured["impersonate"] == "chrome"
    assert captured["http_version"] == "v3"


def test_refresh_failure_falls_back_to_session_authentication(settings):
    database = Database(settings.database_path)
    database.initialize()
    synchronizer = PlanSynchronizer(settings, database)
    plan_requests = 0
    session_auth_calls = 0

    def request(payload, http_version):
        nonlocal plan_requests
        plan_requests += 1
        if plan_requests == 1:
            raise UpstreamError("upstream_http_401")
        return FakeResponse([sample_entry().model_dump(mode="json")])

    def fail_refresh():
        raise UpstreamError("token_refresh_upstream_http_401")

    def authenticate():
        nonlocal session_auth_calls
        session_auth_calls += 1

    synchronizer._request = request  # type: ignore[method-assign]
    synchronizer._refresh_api_token = fail_refresh  # type: ignore[method-assign]
    synchronizer._authenticate_new_session = authenticate  # type: ignore[method-assign]

    result = synchronizer.fetch()

    assert result["status"] == "updated"
    assert result["sessionReauthenticated"] is True
    assert "tokenRefreshed" not in result
    assert plan_requests == 2
    assert session_auth_calls == 1


def test_jwt_auth_creates_new_session_and_uses_exact_payload(settings, monkeypatch):
    sessions = []
    login_calls: list[tuple[str, dict]] = []
    plan_headers: list[dict[str, str]] = []

    class RecordingSession:
        def __init__(self, **options):
            self.cookies: dict[str, str] = {}
            self.closed = False
            sessions.append(self)

        def post(self, url, **options):
            if url == settings.api_auth_url:
                login_calls.append((url, options))
                self.cookies["official-session"] = "test-cookie"
                return FakeResponse({"ok": True})
            plan_headers.append(options["headers"])
            return FakeResponse([])

        def close(self):
            self.closed = True

    monkeypatch.setattr("backend.upstream.requests.Session", RecordingSession)
    database = Database(settings.database_path)
    database.initialize()
    synchronizer = PlanSynchronizer(settings, database)
    original_session = synchronizer._session

    synchronizer._authenticate_new_session()
    synchronizer._request({"schoolIds": [999]}, "v3")

    assert len(sessions) == 2
    assert original_session.closed is True
    assert synchronizer._session is sessions[1]
    assert login_calls[0][0] == settings.api_auth_url
    assert login_calls[0][1]["json"] == {
        "Username": "test-user",
        "Password": "test-password",
        "Pin": None,
    }
    assert login_calls[0][1]["impersonate"] == "chrome"
    assert login_calls[0][1]["http_version"] == "v3"
    assert "Authorization" not in plan_headers[0]


def test_jwt_auth_accepts_authorization_header_and_persists_token(
    settings, monkeypatch
):
    refreshed_token = fake_jwt("session-login")

    class HeaderSession:
        def __init__(self, **options):
            self.cookies = {}

        def post(self, url, **options):
            return FakeResponse(
                {"ok": True},
                headers={"Authorization": f"Bearer {refreshed_token}"},
            )

        def close(self):
            pass

    monkeypatch.setattr("backend.upstream.requests.Session", HeaderSession)
    database = Database(settings.database_path)
    database.initialize()
    synchronizer = PlanSynchronizer(settings, database)
    env_path = settings.base_dir / ".env"
    env_path.write_text("VPLAN_API_TOKEN=test-token\n", encoding="utf-8")

    synchronizer._authenticate_new_session()

    assert synchronizer._api_token == refreshed_token
    assert synchronizer._send_bearer is True
    assert f"VPLAN_API_TOKEN='{refreshed_token}'" in env_path.read_text(
        encoding="utf-8"
    )


def test_session_auth_rejects_missing_credentials_without_network(settings):
    settings_without_credentials = replace(
        settings,
        api_username="",
        api_password="",
    )
    database = Database(settings.database_path)
    database.initialize()
    synchronizer = PlanSynchronizer(settings_without_credentials, database)

    try:
        synchronizer._authenticate_new_session()
    except UpstreamError as error:
        assert str(error) == "session_auth_credentials_unavailable"
    else:
        raise AssertionError("Missing credentials must fail closed")


def test_unchanged_fetch_does_not_rewrite_cache(settings, monkeypatch):
    database = Database(settings.database_path)
    database.initialize()
    synchronizer = PlanSynchronizer(settings, database)
    response = FakeResponse([sample_entry().model_dump(mode="json")])
    synchronizer._request = lambda payload, version: response  # type: ignore[method-assign]

    assert synchronizer.fetch()["status"] == "updated"
    first_mtime = settings.cache_path.stat().st_mtime_ns
    assert synchronizer.fetch()["status"] == "unchanged"
    assert settings.cache_path.stat().st_mtime_ns == first_mtime


def test_learning_is_scoped_to_school_year(settings):
    database = Database(settings.database_path)
    database.initialize()
    database.learn("2025-2026", {"12_OLD"}, {"LiGyDe.Old"})
    database.learn("2026-2027", {"12_NEW"}, {"LiGyDe.New"})
    database.learn("2026-2027", {"11_KEEP"}, {"LiGyDe.Keep"})

    assert database.learned_courses("2025-2026") == []
    assert database.learned_courses("2026-2027") == ["11_KEEP", "12_NEW"]
    assert school_year(datetime(2026, 8, 1).date()) == "2026-2027"


def test_maintenance_prunes_old_learning_even_without_a_successful_fetch(settings):
    database = Database(settings.database_path)
    database.initialize()
    database.learn("2025-2026", {"12_OLD"}, {"LiGyDe.Old"})

    database.cleanup("2026-2027")

    assert database.learned_courses("2025-2026") == []
    assert database.learned_teacher_names("2025-2026") == []


def test_failed_refresh_keeps_last_valid_plan_and_marks_it_stale(settings):
    database = Database(settings.database_path)
    database.initialize()
    synchronizer = PlanSynchronizer(settings, database)
    synchronizer._request = lambda payload, version: FakeResponse(  # type: ignore[method-assign]
        [sample_entry().model_dump(mode="json")]
    )
    assert synchronizer.fetch()["status"] == "updated"

    def fail_request(payload, version):
        raise UpstreamError("transport_error_v3" if version == "v3" else "offline")

    synchronizer._request = fail_request  # type: ignore[method-assign]
    assert synchronizer.fetch()["status"] == "error"
    cached = synchronizer.public_plan()

    assert cached is not None
    assert cached["stale"] is True
    assert cached["days"]
