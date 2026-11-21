"""Single source of configuration, read from environment variables.

Every variable is listed in `.env.example`. Nothing else should read `os.environ`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_USER_AGENT = "sakuna/0.1 (open-data research project; non-commercial)"
MAX_PARALLEL_CAP = 6  # NPC Advisory 2026-01 Sec 4: be polite to DROMIC
ENV_VARS = (
    "LOG_LEVEL",
    "RAW_ROOT",
    "LAKE_ROOT",
    "DROMIC_BASE_URL",
    "HTTP_USER_AGENT",
    "MAX_PARALLEL_REQUESTS",
    "REQUEST_TIMEOUT_SECONDS",
    "REQUEST_RETRIES",
)


def _env(name: str, default: str) -> str:
    """Return an env var, treating an empty value as unset."""
    return os.environ.get(name, "").strip() or default


def _int_env(name: str, default: int, low: int, high: int | None = None) -> int:
    """Return an env var as an int within [low, high], with an error naming the variable."""
    raw = _env(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{name} must be a whole number, got {raw!r}") from None
    if value < low or (high is not None and value > high):
        bound = f"between {low} and {high}" if high is not None else f"at least {low}"
        raise ValueError(f"{name} must be {bound}, got {value}")
    return value


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of all configuration for one run."""

    log_level: str
    raw_root: Path
    lake_root: Path
    dromic_base_url: str
    http_user_agent: str
    max_parallel_requests: int
    request_timeout_seconds: int
    request_retries: int


def load_settings() -> Settings:
    """Build Settings from the environment, validating every value."""
    return Settings(
        log_level=_env("LOG_LEVEL", "INFO").upper(),
        raw_root=Path(_env("RAW_ROOT", "./raw")),
        lake_root=Path(_env("LAKE_ROOT", "./lake")),
        dromic_base_url=_env("DROMIC_BASE_URL", "https://dromic.dswd.gov.ph").rstrip("/"),
        http_user_agent=_env("HTTP_USER_AGENT", DEFAULT_USER_AGENT),
        max_parallel_requests=_int_env("MAX_PARALLEL_REQUESTS", 6, 1, MAX_PARALLEL_CAP),
        request_timeout_seconds=_int_env("REQUEST_TIMEOUT_SECONDS", 60, 1),
        request_retries=_int_env("REQUEST_RETRIES", 3, 0),
    )
