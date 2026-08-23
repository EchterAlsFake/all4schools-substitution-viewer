from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values, load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().casefold() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return min(maximum, max(minimum, value))


def normalize_gate_answer(value: str) -> str:
    return "".join(str(value).strip().upper().split())


def _local_path(base_dir: Path, raw_value: str | os.PathLike[str]) -> Path:
    path = Path(raw_value)
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


@dataclass(frozen=True, slots=True)
class Settings:
    base_dir: Path
    api_url: str
    api_refresh_url: str
    api_auth_url: str
    api_token: str = field(repr=False)
    api_username: str = field(repr=False)
    api_password: str = field(repr=False)
    school_id: int | None
    gate_answers: tuple[str, ...]
    public_host: str
    trust_cloudflare_ip: bool
    secure_cookie: bool
    upgrade_insecure_requests: bool
    sync_enabled: bool
    sync_interval_seconds: int
    request_timeout_seconds: int
    max_response_bytes: int
    database_path: Path
    cache_path: Path
    configuration_errors: tuple[str, ...]

    @classmethod
    def load(cls, base_dir: Path = BASE_DIR) -> "Settings":
        dotenv_path = base_dir / ".env"
        load_dotenv(dotenv_path, override=False)
        file_values = dotenv_values(dotenv_path)
        errors: list[str] = []
        api_token = os.environ.get("VPLAN_API_TOKEN", "").strip()
        if not api_token:
            errors.append("missing_api_token")

        api_url = os.environ.get("VPLAN_API_URL", "").strip()
        parsed_api_url = urlsplit(api_url)
        if not api_url:
            errors.append("missing_api_url")
        elif parsed_api_url.scheme != "https" or not parsed_api_url.hostname:
            errors.append("invalid_api_url")

        api_refresh_url = os.environ.get("VPLAN_API_REFRESH_URL", "").strip()
        parsed_refresh_url = urlsplit(api_refresh_url)
        if not api_refresh_url:
            errors.append("missing_api_refresh_url")
        elif parsed_refresh_url.scheme != "https" or not parsed_refresh_url.hostname:
            errors.append("invalid_api_refresh_url")

        api_auth_url = os.environ.get("VPLAN_API_AUTH_URL", "").strip()
        parsed_auth_url = urlsplit(api_auth_url)
        if not api_auth_url:
            errors.append("missing_api_auth_url")
        elif parsed_auth_url.scheme != "https" or not parsed_auth_url.hostname:
            errors.append("invalid_api_auth_url")

        raw_school_id = os.environ.get("VPLAN_SCHOOL_ID", "").strip()
        try:
            school_id = int(raw_school_id)
            if school_id <= 0:
                raise ValueError
        except ValueError:
            school_id = None
            errors.append("invalid_school_id")

        answers = tuple(
            dict.fromkeys(
                normalized
                for raw in os.environ.get("VPLAN_GATE_ANSWERS", "").split(",")
                if (normalized := normalize_gate_answer(raw))
            )
        )
        if not answers:
            errors.append("missing_gate_answers")

        data_dir = _local_path(
            base_dir, os.environ.get("VPLAN_DATA_DIR", base_dir / "data")
        )
        return cls(
            base_dir=base_dir,
            api_url=api_url,
            api_refresh_url=api_refresh_url,
            api_auth_url=api_auth_url,
            api_token=api_token,
            api_username=str(
                file_values.get("USERNAME") or os.environ.get("USERNAME", "")
            ).strip(),
            api_password=str(
                file_values.get("PASSWORD")
                if file_values.get("PASSWORD") is not None
                else os.environ.get("PASSWORD", "")
            ),
            school_id=school_id,
            gate_answers=answers,
            public_host=os.environ.get(
                "VPLAN_PUBLIC_HOST", "vplan.echteralsfake.me"
            ).strip().casefold().rstrip("."),
            trust_cloudflare_ip=_env_bool("VPLAN_TRUST_CLOUDFLARE_IP", True),
            secure_cookie=_env_bool("VPLAN_SECURE_COOKIE", True),
            upgrade_insecure_requests=_env_bool(
                "VPLAN_UPGRADE_INSECURE_REQUESTS", True
            ),
            sync_enabled=_env_bool("VPLAN_SYNC_ENABLED", True),
            sync_interval_seconds=_env_int(
                "VPLAN_SYNC_INTERVAL_SECONDS", 300, 300, 86_400
            ),
            request_timeout_seconds=_env_int(
                "VPLAN_REQUEST_TIMEOUT_SECONDS", 20, 5, 120
            ),
            max_response_bytes=_env_int(
                "VPLAN_MAX_RESPONSE_BYTES", 5 * 1024 * 1024, 64 * 1024, 20 * 1024 * 1024
            ),
            database_path=_local_path(
                base_dir,
                os.environ.get("VPLAN_DATABASE_PATH", data_dir / "vplan.db"),
            ),
            cache_path=_local_path(
                base_dir,
                os.environ.get("VPLAN_CACHE_PATH", data_dir / "plan-cache.json"),
            ),
            configuration_errors=tuple(errors),
        )
