from __future__ import annotations

import hashlib
import hmac
import ipaddress
import secrets
import threading
from dataclasses import dataclass

from fastapi import Request

from .config import Settings, normalize_gate_answer


COOKIE_NAME = "vplan_access"


class ClientIdentityError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class GateStatus:
    authorized: bool
    blocked: bool
    remaining_attempts: int


class AccessGate:
    def __init__(self, answers: tuple[str, ...]) -> None:
        self._answers = answers
        self._hmac_key = secrets.token_bytes(32)
        self._attempts: dict[str, int] = {}
        self._blocked: set[str] = set()
        self._sessions: dict[str, str] = {}
        self._lock = threading.Lock()

    def client_key(self, request: Request, settings: Settings) -> str:
        peer = request.client.host if request.client else ""
        raw_identity = peer
        if settings.trust_cloudflare_ip:
            try:
                peer_ip = ipaddress.ip_address(peer)
            except ValueError as exc:
                raise ClientIdentityError("untrusted proxy peer") from exc
            if not peer_ip.is_loopback:
                raise ClientIdentityError("proxy peer is not loopback")
            raw_identity = request.headers.get("CF-Connecting-IP", "").strip()
            if not raw_identity or "," in raw_identity:
                raise ClientIdentityError("missing trusted client address")

        try:
            packed_identity = ipaddress.ip_address(raw_identity).packed
        except ValueError:
            if settings.trust_cloudflare_ip or not raw_identity:
                raise ClientIdentityError("invalid client address") from None
            packed_identity = raw_identity.encode("utf-8", errors="strict")
        return hmac.new(self._hmac_key, packed_identity, hashlib.sha256).hexdigest()

    def status(self, client_key: str, token: str | None) -> GateStatus:
        with self._lock:
            blocked = client_key in self._blocked
            authorized = bool(
                not blocked
                and token
                and hmac.compare_digest(
                    self._sessions.get(token, ""), client_key
                )
            )
            failures = self._attempts.get(client_key, 0)
            return GateStatus(authorized, blocked, max(0, 3 - failures))

    def answer(self, client_key: str, answer: str) -> tuple[GateStatus, str | None]:
        normalized = normalize_gate_answer(answer)
        with self._lock:
            if client_key in self._blocked:
                return GateStatus(False, True, 0), None
            valid = any(
                hmac.compare_digest(normalized, expected)
                for expected in self._answers
            )
            if valid:
                self._attempts.pop(client_key, None)
                token = secrets.token_urlsafe(32)
                self._sessions[token] = client_key
                return GateStatus(True, False, 3), token

            failures = self._attempts.get(client_key, 0) + 1
            self._attempts[client_key] = failures
            if failures >= 3:
                self._blocked.add(client_key)
                self._sessions = {
                    token: value
                    for token, value in self._sessions.items()
                    if value != client_key
                }
                return GateStatus(False, True, 0), None
            return GateStatus(False, False, 3 - failures), None

    def logout(self, token: str | None) -> None:
        if not token:
            return
        with self._lock:
            self._sessions.pop(token, None)

