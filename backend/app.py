from __future__ import annotations

import asyncio
import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime, time as datetime_time, timedelta, timezone
from typing import Callable, TypeVar

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, RedirectResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from .auth import COOKIE_NAME, AccessGate, ClientIdentityError
from .config import Settings
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
SchemaType = TypeVar("SchemaType")


def _json_error(code: str, status_code: int, **extra: object) -> JSONResponse:
    return JSONResponse({"ok": False, "code": code, **extra}, status_code=status_code)


async def _validated_json(
    request: Request, parser: Callable[[object], SchemaType]
) -> SchemaType:
    try:
        return parser(await request.json())
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="invalid_request") from exc


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


def create_app(settings: Settings | None = None) -> Starlette:
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
    async def lifespan(_: Starlette):
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

    async def http_error_handler(_: Request, exc: HTTPException):
        code = str(exc.detail) if isinstance(exc.detail, str) else "request_failed"
        return _json_error(code, exc.status_code)

    async def health(_: Request) -> JSONResponse:
        return JSONResponse(
            {
                "ok": not active_settings.configuration_errors,
                "configured": not active_settings.configuration_errors,
            }
        )

    async def auth_status(request: Request):
        if active_settings.configuration_errors:
            return _json_error("service_not_configured", 503)
        client_key = identity(request)
        status = gate.status(client_key, request.cookies.get(COOKIE_NAME))
        return JSONResponse(
            {
                "ok": True,
                "authorized": status.authorized,
                "blocked": status.blocked,
                "remainingAttempts": status.remaining_attempts,
            }
        )

    async def answer_gate(request: Request):
        require_same_origin(request)
        payload = await _validated_json(request, GateAnswer.from_payload)
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

    async def logout(request: Request):
        require_same_origin(request)
        gate.logout(request.cookies.get(COOKIE_NAME))
        response = JSONResponse({"ok": True})
        response.delete_cookie(COOKIE_NAME, path="/")
        return response

    async def plan(request: Request):
        require_access(request)
        payload = synchronizer.public_plan()
        if payload is None:
            return _json_error("plan_unavailable", 503)
        return JSONResponse(payload)

    async def feedback(request: Request):
        require_same_origin(request)
        require_access(request)
        payload = await _validated_json(request, FeedbackSubmission.from_payload)
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
        return JSONResponse({"ok": True})

    dist_dir = active_settings.base_dir / "dist"
    public_dir = active_settings.base_dir / "public"

    async def legacy_vplan_redirect(_: Request):
        return RedirectResponse("/", status_code=308)

    async def service_worker(_: Request):
        response = FileResponse(public_dir / "sw.js", media_type="application/javascript")
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Service-Worker-Allowed"] = "/"
        return response

    async def manifest(_: Request):
        response = FileResponse(
            public_dir / "manifest.webmanifest", media_type="application/manifest+json"
        )
        response.headers["Cache-Control"] = "no-cache"
        return response

    async def i18n_file(request: Request):
        filename = request.path_params["filename"]
        if not re.fullmatch(r"[a-z]{2}\.json|languages\.json", filename):
            raise HTTPException(status_code=404, detail="not_found")
        response = FileResponse(
            public_dir / "i18n" / filename, media_type="application/json"
        )
        response.headers["Cache-Control"] = "no-cache"
        return response

    async def icon(request: Request):
        filename = request.path_params["filename"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+\.(?:svg|png)", filename):
            raise HTTPException(status_code=404, detail="not_found")
        return FileResponse(public_dir / "icons" / filename)

    async def frontend(_: Request):
        index_path = dist_dir / "index.html"
        if not index_path.is_file():
            return _json_error("frontend_not_built", 503)
        return FileResponse(index_path, media_type="text/html")

    routes = [
        Route("/healthz", health, methods=["GET"]),
        Route("/api/auth/status", auth_status, methods=["GET"]),
        Route("/api/auth/answer", answer_gate, methods=["POST"]),
        Route("/api/auth/logout", logout, methods=["POST"]),
        Route("/api/plan", plan, methods=["GET"]),
        Route("/api/feedback", feedback, methods=["POST"]),
        Route("/vplan", legacy_vplan_redirect, methods=["GET"]),
        Route("/sw.js", service_worker, methods=["GET"]),
        Route("/manifest.webmanifest", manifest, methods=["GET"]),
        Route("/i18n/{filename}", i18n_file, methods=["GET"]),
        Route("/icons/{filename}", icon, methods=["GET"]),
        Route("/{path:path}", frontend, methods=["GET"]),
    ]
    if (dist_dir / "assets").is_dir():
        routes.insert(
            0,
            Mount(
                "/assets",
                app=StaticFiles(directory=dist_dir / "assets"),
                name="assets",
            ),
        )

    app = Starlette(
        routes=routes,
        middleware=[
            Middleware(BaseHTTPMiddleware, dispatch=security_headers),
            Middleware(
                TrustedHostMiddleware,
                allowed_hosts=[
                    active_settings.public_host,
                    "localhost",
                    "127.0.0.1",
                    "[::1]",
                    "testserver",
                ],
            ),
        ],
        exception_handlers={HTTPException: http_error_handler},
        lifespan=lifespan,
    )
    app.state.settings = active_settings
    app.state.database = database
    app.state.gate = gate
    app.state.synchronizer = synchronizer
    app.state.stop_event = stop_event
    return app


app = create_app()
