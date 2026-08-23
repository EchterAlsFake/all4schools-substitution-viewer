from __future__ import annotations

import asyncio
import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime, time as datetime_time, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .auth import COOKIE_NAME, AccessGate, ClientIdentityError
from .config import BASE_DIR, Settings
from .database import Database
from .schemas import FeedbackSubmission, GateAnswer
from .upstream import BERLIN, PlanSynchronizer, school_year


LOGGER = logging.getLogger("vplan")
CONTACT_RE = re.compile(
    r"(?:\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|https?://|www\.)",
    re.IGNORECASE,
)
PHONE_RE = re.compile(r"(?:\+?\d[\d\s()./-]{5,}\d)")
HTML_RE = re.compile(r"<[^>]+>")


def _json_error(code: str, status_code: int, **extra: object) -> JSONResponse:
    return JSONResponse({"ok": False, "code": code, **extra}, status_code=status_code)


def seconds_until_sync_window(now: datetime | None = None) -> float:
    current = (now or datetime.now(BERLIN)).astimezone(BERLIN)
    if 6 <= current.hour < 22:
        return 0.0
    resume_date = current.date() + (timedelta(days=1) if current.hour >= 22 else timedelta())
    resume_at = datetime.combine(resume_date, datetime_time(6), tzinfo=BERLIN)
    return max(
        0.0,
        (
            resume_at.astimezone(timezone.utc) - current.astimezone(timezone.utc)
        ).total_seconds(),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or Settings.load()
    database = Database(active_settings.database_path)
    database.initialize()
    gate = AccessGate(active_settings.gate_answers)
    synchronizer = PlanSynchronizer(active_settings, database)
    stop_event = asyncio.Event()

    async def background_sync() -> None:
        while not stop_event.is_set():
            quiet_period = seconds_until_sync_window()
            if quiet_period > 0:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=quiet_period)
                except TimeoutError:
                    pass
                continue
            try:
                result = await asyncio.to_thread(synchronizer.fetch)
                if result.get("status") == "error":
                    if result.get("sessionAuthAttempted"):
                        LOGGER.error(
                            "Plan synchronization failed after token refresh and "
                            "session authentication (refresh code %s, final code %s)",
                            result.get("refreshCode"),
                            result.get("code"),
                        )
                    elif result.get("tokenRefreshAttempted"):
                        LOGGER.error(
                            "Plan synchronization failed during or after automatic token "
                            "refresh with code %s",
                            result.get("code"),
                        )
                    else:
                        LOGGER.warning(
                            "Plan refresh failed with code %s", result.get("code")
                        )
            except Exception:
                LOGGER.exception("Unexpected VPlan synchronization error")
            try:
                await asyncio.wait_for(
                    stop_event.wait(), timeout=active_settings.sync_interval_seconds
                )
            except TimeoutError:
                pass

    async def maintenance() -> None:
        while not stop_event.is_set():
            current_school_year = school_year(datetime.now(BERLIN).date())
            await asyncio.to_thread(database.cleanup, current_school_year)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=3_600)
            except TimeoutError:
                pass

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        sync_task = (
            asyncio.create_task(background_sync())
            if active_settings.sync_enabled
            else None
        )
        maintenance_task = asyncio.create_task(maintenance())
        try:
            yield
        finally:
            stop_event.set()
            tasks = [maintenance_task]
            if sync_task is not None:
                tasks.append(sync_task)
            await asyncio.gather(*tasks, return_exceptions=True)
            synchronizer.close()

    app = FastAPI(
        title="VPlan",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.settings = active_settings
    app.state.database = database
    app.state.gate = gate
    app.state.synchronizer = synchronizer
    app.state.stop_event = stop_event
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[
            active_settings.public_host,
            "localhost",
            "127.0.0.1",
            "[::1]",
            "testserver",
        ],
    )
    content_security_policy = [
        "default-src 'self'",
        "base-uri 'self'",
        "connect-src 'self'",
        "font-src 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "img-src 'self' data:",
        "manifest-src 'self'",
        "object-src 'none'",
        "script-src 'self'",
        "style-src 'self'",
        "worker-src 'self'",
    ]
    if active_settings.upgrade_insecure_requests:
        content_security_policy.append("upgrade-insecure-requests")
    content_security_policy_header = "; ".join(content_security_policy)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            content_security_policy_header
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        if request.url.path.startswith("/api/") or request.url.path in {"/", "/index.html"}:
            response.headers["Cache-Control"] = "no-store"
        return response

    def identity(request: Request) -> str:
        try:
            return gate.client_key(request, active_settings)
        except ClientIdentityError as exc:
            raise HTTPException(status_code=503, detail="client_identity_unavailable") from exc

    def require_access(request: Request) -> str:
        client_key = identity(request)
        status = gate.status(client_key, request.cookies.get(COOKIE_NAME))
        if status.blocked:
            raise HTTPException(status_code=423, detail="ip_blocked")
        if not status.authorized:
            raise HTTPException(status_code=401, detail="authentication_required")
        return client_key

    def require_same_origin(request: Request) -> None:
        fetch_site = request.headers.get("Sec-Fetch-Site", "").casefold()
        if fetch_site and fetch_site not in {"same-origin", "none"}:
            raise HTTPException(status_code=403, detail="invalid_origin")
        origin = request.headers.get("Origin")
        if not origin:
            return
        allowed_origins = {
            str(request.base_url).rstrip("/"),
            f"https://{active_settings.public_host}",
        }
        if origin.rstrip("/").casefold() not in {
            candidate.casefold() for candidate in allowed_origins
        }:
            raise HTTPException(status_code=403, detail="invalid_origin")

    @app.exception_handler(HTTPException)
    async def http_error_handler(_: Request, exc: HTTPException):
        code = str(exc.detail) if isinstance(exc.detail, str) else "request_failed"
        return _json_error(code, exc.status_code)

    @app.get("/healthz")
    async def health() -> dict[str, object]:
        return {
            "ok": not active_settings.configuration_errors,
            "configured": not active_settings.configuration_errors,
        }

    @app.get("/api/auth/status")
    async def auth_status(request: Request):
        if active_settings.configuration_errors:
            return _json_error("service_not_configured", 503)
        client_key = identity(request)
        status = gate.status(client_key, request.cookies.get(COOKIE_NAME))
        return {
            "ok": True,
            "authorized": status.authorized,
            "blocked": status.blocked,
            "remainingAttempts": status.remaining_attempts,
        }

    @app.post("/api/auth/answer")
    async def answer_gate(payload: GateAnswer, request: Request):
        require_same_origin(request)
        if active_settings.configuration_errors:
            return _json_error("service_not_configured", 503)
        client_key = identity(request)
        status, token = gate.answer(client_key, payload.answer)
        if status.blocked:
            return _json_error("ip_blocked", 423, remainingAttempts=0)
        if not status.authorized or token is None:
            return _json_error(
                "invalid_answer", 401, remainingAttempts=status.remaining_attempts
            )
        response = JSONResponse({"ok": True, "authorized": True})
        response.set_cookie(
            COOKIE_NAME,
            token,
            secure=active_settings.secure_cookie,
            httponly=True,
            samesite="strict",
            path="/",
        )
        return response

    @app.post("/api/auth/logout")
    async def logout(request: Request):
        require_same_origin(request)
        gate.logout(request.cookies.get(COOKIE_NAME))
        response = JSONResponse({"ok": True})
        response.delete_cookie(COOKIE_NAME, path="/")
        return response

    @app.get("/api/plan")
    async def plan(request: Request):
        require_access(request)
        payload = synchronizer.public_plan()
        if payload is None:
            return _json_error("plan_unavailable", 503)
        return payload

    @app.post("/api/feedback")
    async def feedback(payload: FeedbackSubmission, request: Request):
        require_same_origin(request)
        require_access(request)
        if request.headers.get("X-VPlan-Request") != "feedback":
            return _json_error("invalid_request", 400)
        message = " ".join(payload.message.strip().split())
        if not payload.privacy_confirmed:
            return _json_error("privacy_confirmation_required", 400)
        if HTML_RE.search(message):
            return _json_error("html_not_allowed", 400)
        if CONTACT_RE.search(message) or any(
            sum(character.isdigit() for character in candidate) >= 6
            for candidate in PHONE_RE.findall(message)
        ):
            return _json_error("contact_data_not_allowed", 400)
        if not database.consume_feedback_rate_limit():
            return _json_error("rate_limited", 429)
        database.save_feedback(message)
        return {"ok": True}

    dist_dir = active_settings.base_dir / "dist"
    public_dir = active_settings.base_dir / "public"
    if (dist_dir / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist_dir / "assets"), name="assets")

    @app.get("/vplan")
    async def legacy_vplan_redirect():
        return RedirectResponse("/", status_code=308)

    @app.get("/sw.js")
    async def service_worker():
        response = FileResponse(public_dir / "sw.js", media_type="application/javascript")
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Service-Worker-Allowed"] = "/"
        return response

    @app.get("/manifest.webmanifest")
    async def manifest():
        response = FileResponse(
            public_dir / "manifest.webmanifest", media_type="application/manifest+json"
        )
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/i18n/{filename}")
    async def i18n_file(filename: str):
        if not re.fullmatch(r"[a-z]{2}\.json|languages\.json", filename):
            raise HTTPException(status_code=404, detail="not_found")
        response = FileResponse(
            public_dir / "i18n" / filename, media_type="application/json"
        )
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/icons/{filename}")
    async def icon(filename: str):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+\.(?:svg|png)", filename):
            raise HTTPException(status_code=404, detail="not_found")
        return FileResponse(public_dir / "icons" / filename)

    @app.get("/{path:path}")
    async def frontend(path: str):
        index_path = dist_dir / "index.html"
        if not index_path.is_file():
            return _json_error("frontend_not_built", 503)
        return FileResponse(index_path, media_type="text/html")

    return app


app = create_app()
