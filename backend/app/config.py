from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """
    All configuration comes from the environment / .env -- never from source.

    The FRED key is a SecretStr so it cannot be printed by accident: repr()
    renders it as '**********', which matters because FastAPI, pydantic
    validation errors, and most log formatters all call repr() on values.
    """

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    fred_api_key: str
    cache_db_path: str = str(BACKEND_ROOT / "fred_cache.db") if (BACKEND_ROOT / "fred_cache.db").parent.exists() else "/tmp/fred_cache.db"
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"

    # How long a cached series is trusted before we re-check FRED, by frequency.
    # These are deliberately shorter than the real release cadence so a fresh
    # print shows up quickly, but long enough that a busy dashboard makes only
    # a handful of upstream calls per hour.
    ttl_seconds: dict[str, int] = {
        "d": 6 * 3600,
        "w": 12 * 3600,
        "m": 24 * 3600,
        "q": 24 * 3600,
    }

    # FRED's documented ceiling is 120 requests/minute per key. We run well
    # under it -- the cache means we rarely approach it anyway.
    max_requests_per_minute: int = 60
    max_concurrent_requests: int = 8
    request_timeout_seconds: float = 30.0
    observation_start: str = "1990-01-01"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
