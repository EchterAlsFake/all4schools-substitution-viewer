from __future__ import annotations

import json
from dataclasses import replace

import httpx2
import pytest
from sqlalchemy import select

from backend.app import create_app
from backend.database import Database, Feedback


pytestmark = pytest.mark.anyio


def client_for(settings):
    return httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=create_app(settings)),
        base_url="http://testserver",
    )


def proxied_client_for(settings, client_address=("127.0.0.1", 123)):
    return httpx2.AsyncClient(
        transport=httpx2.ASGITransport(
            app=create_app(settings), client=client_address
        ),
        base_url="http://testserver",
    )


async def answer(client: httpx2.AsyncClient, value: str):
    return await client.post("/api/auth/answer", json={"answer": value})


async def test_three_wrong_answers_block_until_a_new_app_instance(settings):
    async with client_for(settings) as client:
        first = await answer(client, "wrong")
        second = await answer(client, "still-wrong")
        third = await answer(client, "again-wrong")

        assert first.status_code == 401
        assert first.json()["remainingAttempts"] == 2
        assert second.json()["remainingAttempts"] == 1
        assert third.status_code == 423
        assert third.json()["code"] == "ip_blocked"
        assert (await answer(client, "ROOM42")).status_code == 423

    async with client_for(settings) as restarted:
        assert (await answer(restarted, " room42 ")).status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"answer": "ROOM42", "extra": True},
        {"answer": 42},
        {"answer": ""},
        {"answer": "x" * 33},
        {"answer": "ROOM\n42"},
    ],
)
async def test_gate_rejects_invalid_json_schemas_without_counting_attempts(
    settings, payload
):
    async with client_for(settings) as client:
        invalid = await client.post("/api/auth/answer", json=payload)
        status = await client.get("/api/auth/status")

    assert invalid.status_code == 422
    assert invalid.json()["code"] == "invalid_request"
    assert status.json()["remainingAttempts"] == 3


async def test_gate_rejects_malformed_json(settings):
    async with client_for(settings) as client:
        invalid = await client.post(
            "/api/auth/answer",
            content=b"{",
            headers={"Content-Type": "application/json"},
        )

    assert invalid.status_code == 422
    assert invalid.json()["code"] == "invalid_request"


async def test_success_creates_httponly_session_and_protects_plan(settings):
    settings.cache_path.write_text(
        json.dumps(
            {
                "version": "abc",
                "lastSuccessfulFetchAt": "2026-08-22T10:00:00+00:00",
                "sourceFrom": "2026-08-22T00:00:00",
                "sourceTo": "2026-08-24T23:59:59",
                "schoolYear": "2026-2027",
                "learnedCourseCodes": [],
                "days": [],
            }
        ),
        encoding="utf-8",
    )
    async with client_for(settings) as client:
        assert (await client.get("/api/plan")).status_code == 401
        response = await answer(client, "42")

        assert response.status_code == 200
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "SameSite=strict" in response.headers["set-cookie"]
        plan = await client.get("/api/plan")
        assert plan.status_code == 200
        assert plan.headers["cache-control"] == "no-store"
        assert plan.json()["version"] == "abc"


async def test_logout_revokes_the_memory_session(settings):
    async with client_for(settings) as client:
        assert (await answer(client, "ROOM42")).status_code == 200

        assert (await client.post("/api/auth/logout")).status_code == 200
        assert (await client.get("/api/plan")).status_code == 401


async def test_feedback_validation_and_storage(settings):
    async with client_for(settings) as unauthorized_client:
        unauthorized = await unauthorized_client.post(
            "/api/feedback",
            headers={"X-VPlan-Request": "feedback"},
            json={"message": "Eine anonyme Testmeldung.", "privacy_confirmed": True},
        )
        assert unauthorized.status_code == 401

    async with client_for(settings) as client:
        await answer(client, "ROOM42")

        invalid = await client.post(
            "/api/feedback",
            headers={"X-VPlan-Request": "feedback"},
            json={
                "message": "Kontakt unter test@example.com bitte.",
                "privacy_confirmed": True,
            },
        )
        injection = await client.post(
            "/api/feedback",
            headers={"X-VPlan-Request": "feedback"},
            json={
                "message": "Anzeige bei Kurs ' OR 1=1 -- funktioniert nicht.",
                "privacy_confirmed": True,
            },
        )

        assert invalid.status_code == 400
        assert invalid.json()["code"] == "contact_data_not_allowed"
        assert injection.status_code == 200

    database = Database(settings.database_path)
    with database.session() as database_session:
        messages = list(database_session.scalars(select(Feedback.message)))
    assert messages == ["Anzeige bei Kurs ' OR 1=1 -- funktioniert nicht."]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"message": "Gültige Meldung.", "privacy_confirmed": True, "extra": 1},
        {"message": 123, "privacy_confirmed": True},
        {"message": "zu kurz", "privacy_confirmed": True},
        {"message": "x" * 1_501, "privacy_confirmed": True},
        {"message": "Gültige Meldung.", "privacy_confirmed": "true"},
    ],
)
async def test_feedback_rejects_invalid_json_schemas(settings, payload):
    async with client_for(settings) as client:
        await answer(client, "ROOM42")
        invalid = await client.post(
            "/api/feedback",
            headers={"X-VPlan-Request": "feedback"},
            json=payload,
        )

    assert invalid.status_code == 422
    assert invalid.json()["code"] == "invalid_request"


async def test_feedback_global_rate_limit(settings):
    async with client_for(settings) as client:
        await answer(client, "ROOM42")
        responses = [
            await client.post(
                "/api/feedback",
                headers={"X-VPlan-Request": "feedback"},
                json={
                    "message": f"Anonyme Beschreibung Nummer {number}.",
                    "privacy_confirmed": True,
                },
            )
            for number in range(31)
        ]

        assert all(response.status_code == 200 for response in responses[:30])
        assert responses[30].status_code == 429
        assert responses[30].json()["code"] == "rate_limited"


async def test_security_headers_and_legacy_redirect(settings):
    async with client_for(settings) as client:
        health = await client.get("/healthz")
        redirect = await client.get("/vplan", follow_redirects=False)

        assert health.headers["x-frame-options"] == "DENY"
        assert "default-src 'self'" in health.headers["content-security-policy"]
        assert "upgrade-insecure-requests" in health.headers["content-security-policy"]
        assert redirect.status_code == 308
        assert redirect.headers["location"] == "/"


async def test_https_upgrade_can_be_disabled_for_local_http(settings):
    local_http = replace(settings, upgrade_insecure_requests=False)

    async with client_for(local_http) as client:
        health = await client.get("/healthz")

    assert "default-src 'self'" in health.headers["content-security-policy"]
    assert "upgrade-insecure-requests" not in health.headers["content-security-policy"]


async def test_cross_origin_mutations_are_rejected(settings):
    async with client_for(settings) as client:
        response = await client.post(
            "/api/auth/answer",
            headers={"Origin": "https://attacker.example"},
            json={"answer": "ROOM42"},
        )

        assert response.status_code == 403
        assert response.json()["code"] == "invalid_origin"


async def test_cloudflare_address_is_only_trusted_from_loopback(settings):
    proxied = replace(settings, trust_cloudflare_ip=True)
    async with proxied_client_for(proxied) as client:
        missing = await client.get("/api/auth/status")
        accepted = await client.get(
            "/api/auth/status", headers={"CF-Connecting-IP": "2001:db8::1"}
        )
        assert missing.status_code == 503
        assert accepted.status_code == 200

    async with proxied_client_for(
        proxied, client_address=("192.0.2.20", 123)
    ) as untrusted_proxy:
        spoofed = await untrusted_proxy.get(
            "/api/auth/status", headers={"CF-Connecting-IP": "2001:db8::1"}
        )
        assert spoofed.status_code == 503


async def test_missing_configuration_fails_closed(settings):
    unconfigured = replace(
        settings,
        api_token="",
        gate_answers=(),
        configuration_errors=("missing_api_token", "missing_gate_answers"),
    )
    async with client_for(unconfigured) as client:
        health = await client.get("/healthz")
        auth = await client.get("/api/auth/status")

        assert health.json() == {"ok": False, "configured": False}
        assert auth.status_code == 503
        assert auth.json()["code"] == "service_not_configured"


async def test_lifespan_cleans_up_tasks_when_startup_context_is_cancelled(settings):
    app = create_app(settings)

    with pytest.raises(RuntimeError, match="startup interrupted"):
        async with app.router.lifespan_context(app):
            raise RuntimeError("startup interrupted")

    assert app.state.stop_event.is_set()
