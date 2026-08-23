from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import tempfile
import threading
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from curl_cffi import requests
from curl_cffi.requests.exceptions import RequestException
from dotenv import set_key
from pydantic import TypeAdapter, ValidationError

from .config import Settings
from .database import Database
from .schemas import UpstreamSubstitution


BERLIN = ZoneInfo("Europe/Berlin")
UPSTREAM_LIST = TypeAdapter(list[UpstreamSubstitution])
EXPLICIT_TEACHER_RE = re.compile(r"\bLiGyDe\.[^\s,;.<>()]+", re.IGNORECASE)
PERSON_NAME_PART_PATTERN = (
    r"[A-ZÄÖÜÀ-ÖØ-ÞĀ-Ž]"
    r"[A-Za-zÄÖÜäöüßÀ-ÖØ-öø-ÿĀ-ž'’-]{1,60}"
)
TEACHER_TITLE_PREFIX_RE = re.compile(
    r"^(?:Frau|Herr)\s+(?:(?:Dr|Prof)\.\s+)?", re.IGNORECASE
)
TEACHER_TITLE_RE = re.compile(
    rf"\b(?:Frau|Herr)\s+(?:(?:Dr|Prof)\.\s+)?{PERSON_NAME_PART_PATTERN}"
    rf"(?:\s+{PERSON_NAME_PART_PATTERN}){{0,2}}(?![\w-])"
)
TASK_TEACHER_RE = re.compile(
    r"(\bAufgaben\s+von\s+)(?!Lehrkraft\b)([A-ZÄÖÜ][A-Za-zÄÖÜäöüß.-]{1,30})\b"
)
TEACHER_PAIR_BEFORE_ROOM_RE = re.compile(
    r"\b([A-ZÄÖÜ][a-zäöüß]{2})\s+(?:und|&|/)\s+"
    r"([A-ZÄÖÜ][a-zäöüß]{2})(?=\s+in\s+(?:[A-ZÄÖÜ]\d{2,4}|TH\d+|Aula)\b)"
)
COURSE_CODE_RE = re.compile(r"^(?:0?[5-9]|1[0-2])[A-Za-z0-9ÄÖÜäöüß_.-]{1,62}$")
JWT_RE = re.compile(
    r"^[A-Za-z0-9_-]+={0,2}\.[A-Za-z0-9_-]+={0,2}\.[A-Za-z0-9_-]+={0,2}$"
)
AUTHENTICATION_ERRORS = {"upstream_http_401", "upstream_http_403"}


class UpstreamError(RuntimeError):
    pass


def school_year(today: date) -> str:
    first = today.year if today.month >= 8 else today.year - 1
    return f"{first}-{first + 1}"


def query_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    current = (now or datetime.now(BERLIN)).astimezone(BERLIN).date()
    following = current + timedelta(days=1)
    while following.weekday() >= 5:
        following += timedelta(days=1)
    return (
        datetime.combine(current, datetime_time.min),
        datetime.combine(following, datetime_time(23, 59, 59)),
    )


def _clean_text(value: str | None, maximum: int = 2_000) -> str:
    text = re.sub(r"<[^>]*>", "", str(value or ""))
    return " ".join(text.replace("\x00", "").split())[:maximum]


def teacher_name_variants(value: str | None) -> set[str]:
    name = _clean_text(value, 200)
    if not 2 <= len(name) <= 200:
        return set()
    variants = {name}
    explicit_code = EXPLICIT_TEACHER_RE.fullmatch(name)
    if explicit_code:
        short_code = name.split(".", 1)[1]
        if 2 <= len(short_code) <= 30:
            variants.add(short_code)
    without_title = TEACHER_TITLE_PREFIX_RE.sub("", name, count=1).strip()
    if without_title != name and 2 <= len(without_title) <= 200:
        variants.add(without_title)
    return variants


def _teacher_names(entries: list[UpstreamSubstitution]) -> set[str]:
    names: set[str] = set()
    for entry in entries:
        for teacher in (*entry.oldTeachers, *entry.newTeachers):
            names.update(teacher_name_variants(teacher.name))
        for value in (entry.oldSubject, entry.newSubject, entry.comment):
            text = _clean_text(value)
            for match in EXPLICIT_TEACHER_RE.finditer(text):
                names.update(teacher_name_variants(match.group(0)))
            for match in TASK_TEACHER_RE.finditer(text):
                names.update(teacher_name_variants(match.group(2)))
            for match in TEACHER_PAIR_BEFORE_ROOM_RE.finditer(text):
                for code in match.groups():
                    names.update(teacher_name_variants(code))
    return names


def redact_teacher_text(value: str | None, teacher_names: set[str]) -> str:
    redacted = _clean_text(value)
    redacted = EXPLICIT_TEACHER_RE.sub("Lehrkraft", redacted)
    for name in sorted(teacher_names, key=len, reverse=True):
        redacted = re.sub(
            rf"(?<![\w.]){re.escape(name)}(?![\w-])",
            "Lehrkraft",
            redacted,
            flags=re.IGNORECASE,
        )
    redacted = TEACHER_TITLE_RE.sub("Lehrkraft", redacted)
    redacted = TASK_TEACHER_RE.sub(r"\1Lehrkraft", redacted)
    return redacted


def _reference_names(references: list[Any]) -> list[str]:
    return [
        name
        for reference in references
        if (name := _clean_text(getattr(reference, "name", None), 100))
    ]


def normalize_entries(
    entries: list[UpstreamSubstitution], teacher_names: set[str]
) -> tuple[list[dict[str, Any]], set[str]]:
    public_entries: list[dict[str, Any]] = []
    courses: set[str] = set()
    identity_occurrences: dict[str, int] = {}
    kind_names = {1: "change", 2: "cancelled", 3: "self_study"}
    for entry in entries:
        classes = list(
            dict.fromkeys(
                [
                    *_reference_names(entry.oldClasses),
                    *_reference_names(entry.newClasses),
                ]
            )
        )
        courses.update(code for code in classes if COURSE_CODE_RE.fullmatch(code))
        old_subject = redact_teacher_text(entry.oldSubject, teacher_names)
        new_subject = redact_teacher_text(entry.newSubject, teacher_names)
        public_identity = json.dumps(
            {
                "type": entry.type,
                "start": entry.start.isoformat(),
                "end": entry.end.isoformat(),
                "classes": classes,
                "oldSubject": old_subject,
                "newSubject": new_subject,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        occurrence = identity_occurrences.get(public_identity, 0)
        identity_occurrences[public_identity] = occurrence + 1
        public_entries.append(
            {
                "id": hashlib.sha256(
                    f"{public_identity}:{occurrence}".encode("utf-8")
                ).hexdigest()[:20],
                "kind": kind_names.get(entry.type, "unknown"),
                "start": entry.start.isoformat(),
                "end": entry.end.isoformat(),
                "oldSubject": old_subject,
                "newSubject": new_subject,
                "oldRooms": _reference_names(entry.oldRooms),
                "newRooms": _reference_names(entry.newRooms),
                "classes": classes,
                "comment": redact_teacher_text(entry.comment, teacher_names),
            }
        )
    public_entries.sort(key=lambda item: (item["start"], item["classes"], item["id"]))
    return public_entries, courses


def group_days(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        day = str(entry["start"])[:10]
        grouped.setdefault(day, []).append(entry)
    return [{"date": day, "entries": grouped[day]} for day in sorted(grouped)]


def canonical_hash(days: list[dict[str, Any]]) -> str:
    payload = json.dumps(days, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def sanitize_cached_plan(path: Path, teacher_names: set[str]) -> bool:
    try:
        cache = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(cache, dict) or not isinstance(cache.get("days"), list):
        return False

    changed = False
    for day in cache["days"]:
        if not isinstance(day, dict) or not isinstance(day.get("entries"), list):
            return False
        for entry in day["entries"]:
            if not isinstance(entry, dict):
                return False
            for field in ("oldSubject", "newSubject", "comment"):
                value = entry.get(field)
                if not isinstance(value, str):
                    continue
                redacted = redact_teacher_text(value, teacher_names)
                if redacted != value:
                    entry[field] = redacted
                    changed = True
    if changed:
        cache["version"] = canonical_hash(cache["days"])
        _atomic_write(path, cache)
    return changed


def _decode_jwt_segment(segment: str) -> dict[str, Any]:
    padding = "=" * (-len(segment) % 4)
    decoded = base64.urlsafe_b64decode(segment + padding)
    payload = json.loads(decoded.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError
    return payload


def _extract_jwt(
    response: Any,
    *,
    required: bool = True,
    error_code: str = "invalid_refreshed_token",
) -> str | None:
    candidate: Any = None
    headers = getattr(response, "headers", {})
    for header_name in (
        "Authorization",
        "X-Authorization",
        "X-Access-Token",
        "Access-Token",
        "JWT",
    ):
        header_value = headers.get(header_name) if hasattr(headers, "get") else None
        if isinstance(header_value, str) and header_value.strip():
            candidate = header_value
            break

    try:
        payload = response.json()
    except (TypeError, ValueError):
        payload = getattr(response, "text", "")

    if candidate is None and isinstance(payload, str) and payload.strip():
        candidate = payload
    elif candidate is None and isinstance(payload, dict):
        normalized = {str(key).casefold(): value for key, value in payload.items()}
        candidate = next(
            (
                normalized[key]
                for key in (
                    "token",
                    "jwt",
                    "jwttoken",
                    "accesstoken",
                    "access_token",
                    "bearertoken",
                    "data",
                    "result",
                    "value",
                )
                if isinstance(normalized.get(key), str)
            ),
            None,
        )
        if candidate is None and isinstance(normalized.get("data"), dict):
            nested = {
                str(key).casefold(): value
                for key, value in normalized["data"].items()
            }
            candidate = next(
                (
                    nested[key]
                    for key in ("token", "jwt", "accesstoken", "access_token")
                    if isinstance(nested.get(key), str)
                ),
                None,
            )

    if candidate is None and not required:
        return None
    if not isinstance(candidate, str):
        raise UpstreamError(error_code)
    token = candidate.strip()
    if token.casefold().startswith("bearer "):
        token = token[7:].strip()
    if len(token) > 16_384 or not JWT_RE.fullmatch(token):
        raise UpstreamError(error_code)
    try:
        _decode_jwt_segment(token.split(".", 2)[0])
        _decode_jwt_segment(token.split(".", 2)[1])
    except ValueError:
        raise UpstreamError(error_code) from None
    return token


class PlanSynchronizer:
    def __init__(self, settings: Settings, database: Database) -> None:
        self.settings = settings
        self.database = database
        self._session = requests.Session(impersonate="chrome")
        self._api_token = settings.api_token
        self._send_bearer = bool(settings.api_token)
        self._lock = threading.Lock()
        self._last_fetch_failed = True
        self._last_attempt_at: str | None = None
        self._last_successful_fetch_at: str | None = None

    def _request(self, payload: dict[str, Any], http_version: str):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._send_bearer and self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"
        try:
            response = self._session.post(
                self.settings.api_url,
                headers=headers,
                json=payload,
                impersonate="chrome",
                http_version=http_version,
                timeout=self.settings.request_timeout_seconds,
            )
        except RequestException as exc:
            raise UpstreamError(f"transport_error_{http_version}") from exc
        if response.status_code >= 400:
            raise UpstreamError(f"upstream_http_{response.status_code}")
        try:
            announced_size = int(response.headers.get("Content-Length", "0"))
        except (TypeError, ValueError):
            announced_size = 0
        if announced_size > self.settings.max_response_bytes:
            raise UpstreamError("upstream_response_too_large")
        if len(response.content) > self.settings.max_response_bytes:
            raise UpstreamError("upstream_response_too_large")
        return response

    def _refresh_request(self, token: str, http_version: str):
        request_options = {
            "headers": {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            "impersonate": "chrome",
            "http_version": http_version,
            "timeout": self.settings.request_timeout_seconds,
        }
        try:
            response = self._session.post(
                self.settings.api_refresh_url, **request_options
            )
            if response.status_code == 405:
                response = self._session.get(
                    self.settings.api_refresh_url, **request_options
                )
        except RequestException as exc:
            raise UpstreamError(f"transport_error_{http_version}") from exc
        if response.status_code >= 400:
            raise UpstreamError(f"upstream_http_{response.status_code}")
        if len(response.content) > min(self.settings.max_response_bytes, 64 * 1024):
            raise UpstreamError("upstream_response_too_large")
        return response

    @staticmethod
    def _with_protocol_fallback(callback: Callable[[str], Any]) -> tuple[Any, str]:
        try:
            return callback("v3"), "h3"
        except UpstreamError as first_error:
            if not str(first_error).startswith("transport_error_"):
                raise
        return callback("v2"), "h2_fallback"

    def _persist_api_token(self, token: str, error_code: str) -> None:
        try:
            result = set_key(
                self.settings.base_dir / ".env",
                "VPLAN_API_TOKEN",
                token,
                quote_mode="always",
            )
        except (OSError, ValueError) as exc:
            raise UpstreamError(error_code) from exc
        if result[0] is not True:
            raise UpstreamError(error_code)
        self._api_token = token
        self._send_bearer = True

    def _refresh_api_token(self) -> None:
        try:
            response, _ = self._with_protocol_fallback(
                lambda version: self._refresh_request(self._api_token, version)
            )
            refreshed_token = _extract_jwt(response)
        except UpstreamError as exc:
            raise UpstreamError(f"token_refresh_{exc}") from exc

        assert refreshed_token is not None
        self._persist_api_token(
            refreshed_token, "token_refresh_persist_error"
        )

    def _session_login_request(self, http_version: str) -> tuple[Any, Any]:
        candidate_session = requests.Session(impersonate="chrome")
        try:
            response = candidate_session.post(
                self.settings.api_auth_url,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "Username": self.settings.api_username,
                    "Password": self.settings.api_password,
                    "Pin": None,
                },
                impersonate="chrome",
                http_version=http_version,
                timeout=self.settings.request_timeout_seconds,
            )
        except RequestException as exc:
            candidate_session.close()
            raise UpstreamError(f"transport_error_{http_version}") from exc
        if response.status_code >= 400:
            candidate_session.close()
            raise UpstreamError(f"upstream_http_{response.status_code}")
        if len(response.content) > min(self.settings.max_response_bytes, 64 * 1024):
            candidate_session.close()
            raise UpstreamError("upstream_response_too_large")
        return response, candidate_session

    def _authenticate_new_session(self) -> None:
        username = self.settings.api_username
        password = self.settings.api_password
        if (
            not username
            or not password
            or len(username) > 320
            or len(password) > 1_024
        ):
            raise UpstreamError("session_auth_credentials_unavailable")

        try:
            (response, candidate_session), _ = self._with_protocol_fallback(
                self._session_login_request
            )
        except UpstreamError as exc:
            raise UpstreamError(f"session_auth_{exc}") from exc

        try:
            has_session_cookie = bool(candidate_session.cookies)
            try:
                authenticated_token = _extract_jwt(
                    response,
                    required=False,
                    error_code="invalid_session_token",
                )
            except UpstreamError:
                if not has_session_cookie:
                    raise
                authenticated_token = None
            if authenticated_token is None and not has_session_cookie:
                raise UpstreamError("session_auth_material_missing")
            if authenticated_token is not None:
                self._persist_api_token(
                    authenticated_token, "session_auth_persist_error"
                )
            else:
                self._send_bearer = False
        except UpstreamError:
            candidate_session.close()
            raise

        previous_session = self._session
        self._session = candidate_session
        previous_session.close()

    def close(self) -> None:
        self._session.close()

    def fetch(self) -> dict[str, Any]:
        if self.settings.configuration_errors or self.settings.school_id is None:
            return {"status": "configuration_error"}
        if not self._lock.acquire(blocking=False):
            return {"status": "busy"}
        try:
            start, end = query_window()
            payload = {
                "schoolIds": [self.settings.school_id],
                "from": start.isoformat(timespec="seconds"),
                "to": end.isoformat(timespec="seconds"),
            }
            self._last_attempt_at = datetime.now(timezone.utc).isoformat()
            token_refresh_attempted = False
            token_refreshed = False
            session_auth_attempted = False
            session_reauthenticated = False
            try:
                response, protocol = self._with_protocol_fallback(
                    lambda version: self._request(payload, version)
                )
            except UpstreamError as request_error:
                if str(request_error) not in AUTHENTICATION_ERRORS:
                    self._last_fetch_failed = True
                    return {"status": "error", "code": str(request_error)}
                token_refresh_attempted = True
                refresh_error: str | None = None
                try:
                    self._refresh_api_token()
                    token_refreshed = True
                except UpstreamError as token_error:
                    refresh_error = str(token_error)

                if refresh_error is None:
                    try:
                        response, protocol = self._with_protocol_fallback(
                            lambda version: self._request(payload, version)
                        )
                    except UpstreamError as refresh_retry_error:
                        if str(refresh_retry_error) in AUTHENTICATION_ERRORS:
                            refresh_error = (
                                f"after_token_refresh_{refresh_retry_error}"
                            )
                        else:
                            self._last_fetch_failed = True
                            return {
                                "status": "error",
                                "code": f"after_token_refresh_{refresh_retry_error}",
                                "tokenRefreshAttempted": True,
                            }

                if refresh_error is not None:
                    session_auth_attempted = True
                    try:
                        self._authenticate_new_session()
                        session_reauthenticated = True
                        response, protocol = self._with_protocol_fallback(
                            lambda version: self._request(payload, version)
                        )
                    except UpstreamError as session_error:
                        self._last_fetch_failed = True
                        code = str(session_error)
                        if session_reauthenticated:
                            code = f"after_session_auth_{code}"
                        return {
                            "status": "error",
                            "code": code,
                            "refreshCode": refresh_error,
                            "tokenRefreshAttempted": True,
                            "sessionAuthAttempted": True,
                        }

                if not token_refreshed and not session_reauthenticated:
                    self._last_fetch_failed = True
                    return {
                        "status": "error",
                        "code": "authentication_recovery_failed",
                        "tokenRefreshAttempted": True,
                    }

            try:
                raw_payload = response.json()
                if not isinstance(raw_payload, list) or len(raw_payload) > 10_000:
                    raise ValueError
                upstream_entries = UPSTREAM_LIST.validate_python(raw_payload)
            except (ValueError, ValidationError) as exc:
                self._last_fetch_failed = True
                result: dict[str, Any] = {
                    "status": "error",
                    "code": "invalid_upstream_schema",
                }
                if token_refresh_attempted:
                    result["tokenRefreshAttempted"] = True
                if session_auth_attempted:
                    result["sessionAuthAttempted"] = True
                return result

            now_berlin = datetime.now(BERLIN)
            current_school_year = school_year(now_berlin.date())
            current_names = _teacher_names(upstream_entries)
            known_names = set(self.database.learned_teacher_names(current_school_year))
            all_names = known_names | current_names
            normalized, courses = normalize_entries(upstream_entries, all_names)
            self.database.learn(current_school_year, courses, current_names)
            learned_courses = self.database.learned_courses(current_school_year)
            days = group_days(normalized)
            version = canonical_hash(days)
            fetched_at = datetime.now(timezone.utc).isoformat()
            current_cache = self._read_cache()
            cache = {
                "version": version,
                "lastSuccessfulFetchAt": fetched_at,
                "sourceFrom": start.isoformat(timespec="seconds"),
                "sourceTo": end.isoformat(timespec="seconds"),
                "schoolYear": current_school_year,
                "learnedCourseCodes": learned_courses,
                "days": days,
            }
            if not current_cache or current_cache.get("version") != version or current_cache.get(
                "learnedCourseCodes"
            ) != learned_courses:
                _atomic_write(self.settings.cache_path, cache)
                status = "updated"
            else:
                status = "unchanged"
            self._last_successful_fetch_at = fetched_at
            self._last_fetch_failed = False
            result = {"status": status, "protocol": protocol, "entries": len(normalized)}
            if token_refreshed:
                result["tokenRefreshed"] = True
            if session_reauthenticated:
                result["sessionReauthenticated"] = True
            return result
        finally:
            self._lock.release()

    def _read_cache(self) -> dict[str, Any] | None:
        try:
            payload = json.loads(self.settings.cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) and isinstance(payload.get("days"), list) else None

    def public_plan(self) -> dict[str, Any] | None:
        cache = self._read_cache()
        if cache is None:
            return None
        current_year = school_year(datetime.now(BERLIN).date())
        cache["learnedCourseCodes"] = self.database.learned_courses(current_year)
        cache["stale"] = self._last_fetch_failed
        cache["lastAttemptAt"] = self._last_attempt_at
        if self._last_successful_fetch_at:
            cache["lastSuccessfulFetchAt"] = self._last_successful_fetch_at
        return cache
