"""Private, restart-safe upstream credentials; never part of the public cache."""

import base64
import json
import os
from pathlib import Path
import re
import tempfile

MAX_TOKEN_LENGTH = 16_384
JWT_RE = re.compile(
    r"^[A-Za-z0-9_-]+={0,2}\.[A-Za-z0-9_-]+={0,2}\.[A-Za-z0-9_-]+={0,2}$"
)


def valid_token(token: str) -> bool:
    """Check syntax only; the upstream remains responsible for authentication."""
    if len(token) > MAX_TOKEN_LENGTH or not JWT_RE.fullmatch(token):
        return False
    try:
        for segment in token.split(".")[:2]:
            decoded = base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
            if not isinstance(json.loads(decoded), dict):
                return False
    except (ValueError, UnicodeError):
        return False
    return True


def read_token(path: Path) -> str | None:
    try:
        with path.open("r", encoding="utf-8") as stream:
            token = stream.read(MAX_TOKEN_LENGTH + 2).strip()
    except (FileNotFoundError, UnicodeError):
        return None
    return token if valid_token(token) else None


def write_token(path: Path, token: str) -> None:
    if not valid_token(token):
        raise ValueError("invalid_api_token")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".api-token-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(token + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
