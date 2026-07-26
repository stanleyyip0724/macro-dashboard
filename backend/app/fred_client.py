"""
Async FRED client: rate limiting, retries, and the cache-aware refresh path.

The API key is read from Settings (env/.env) and injected as a query parameter
at request time. It is never logged: `_safe_url` strips it before anything
touches the logger, because FRED requires the key in the URL and URLs are the
single most common accidental credential leak in HTTP clients.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Any

import httpx

from .cache import Cache
from .config import Settings
from .indicators import Indicator

log = logging.getLogger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred"


class FredError(RuntimeError):
    pass


class RateLimiter:
    """Sliding-window limiter. FRED allows 120 req/min; we default to 60."""

    def __init__(self, max_per_minute: int) -> None:
        self.max_per_minute = max_per_minute
        self._hits: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                while self._hits and now - self._hits[0] > 60.0:
                    self._hits.popleft()
                if len(self._hits) < self.max_per_minute:
                    self._hits.append(now)
                    return
                sleep_for = 60.0 - (now - self._hits[0]) + 0.01
                log.warning("Rate limit reached; sleeping %.2fs", sleep_for)
                await asyncio.sleep(sleep_for)


def _safe_url(url: str) -> str:
    """Redact the api_key before a URL is ever logged."""
    import re

    return re.sub(r"api_key=[^&]+", "api_key=***", url)


class FredClient:
    def __init__(self, settings: Settings, cache: Cache) -> None:
        self._settings = settings
        self._cache = cache
        self._limiter = RateLimiter(settings.max_requests_per_minute)
        self._sem = asyncio.Semaphore(settings.max_concurrent_requests)
        self._client = httpx.AsyncClient(
            timeout=settings.request_timeout_seconds,
            headers={"User-Agent": "macro-dashboard/1.0"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict[str, Any]) -> dict:
        params = {
            **params,
            "api_key": self._settings.fred_api_key,
            "file_type": "json",
        }
        url = f"{FRED_BASE}/{path}"
        backoff = 1.0

        for attempt in range(5):
            await self._limiter.acquire()
            async with self._sem:
                try:
                    r = await self._client.get(url, params=params)
                except httpx.RequestError as exc:
                    log.warning("Network error on %s: %s", _safe_url(url), exc)
                    if attempt == 4:
                        raise FredError(f"network error for {path}: {exc}") from exc
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue

            if r.status_code == 200:
                return r.json()

            # 429 = rate limited, 5xx = transient upstream. Both are retryable.
            if r.status_code == 429 or r.status_code >= 500:
                wait = float(r.headers.get("Retry-After", backoff))
                log.warning(
                    "FRED %s on %s; retrying in %.1fs",
                    r.status_code, _safe_url(str(r.url)), wait,
                )
                await asyncio.sleep(wait)
                backoff *= 2
                continue

            # 400 usually means a bad series_id -- retrying will not help.
            raise FredError(
                f"FRED {r.status_code} for {path} "
                f"({params.get('series_id')}): {r.text[:300]}"
            )

        raise FredError(f"exhausted retries for {path} ({params.get('series_id')})")

    # -- raw endpoints ----------------------------------------------------

    async def series_meta(self, series_id: str) -> dict:
        data = await self._get("series", {"series_id": series_id})
        seriess = data.get("seriess") or []
        if not seriess:
            raise FredError(f"no metadata returned for {series_id}")
        return seriess[0]

    async def observations(self, series_id: str) -> list[tuple[str, float | None]]:
        data = await self._get(
            "series/observations",
            {
                "series_id": series_id,
                "observation_start": self._settings.observation_start,
                "sort_order": "asc",
            },
        )
        out: list[tuple[str, float | None]] = []
        for o in data.get("observations", []):
            raw = o.get("value")
            # FRED encodes missing values as the string "."
            value = None if raw in (".", "", None) else float(raw)
            out.append((o["date"], value))
        return out

    # -- cache-aware refresh ---------------------------------------------

    async def ensure_series(self, ind: Indicator, force: bool = False) -> None:
        """
        Bring one series up to date, doing the least work that is correct.

        Returns without any upstream call if the TTL has not expired.
        Otherwise makes one metadata call, and only downloads observations
        when FRED's `last_updated` differs from what we already hold.
        """
        ttl = self._settings.ttl_seconds.get(ind.freq.value, 24 * 3600)

        if not force and self._cache.is_fresh(ind.series_id, ttl):
            return

        meta = await self.series_meta(ind.series_id)
        previous = self._cache.stored_last_updated(ind.series_id)
        self._cache.put_meta(ind.series_id, meta)

        unchanged = (
            not force
            and previous is not None
            and previous == meta.get("last_updated")
            and self._cache.get_meta(ind.series_id)["fetched_at"]
        )
        if unchanged:
            self._cache.touch_checked(ind.series_id)
            log.debug("%s unchanged upstream; skipped observation fetch", ind.series_id)
            return

        obs = await self.observations(ind.series_id)
        self._cache.put_observations(ind.series_id, obs)
        log.info("%s refreshed: %d observations", ind.series_id, len(obs))

    async def ensure_many(
        self, indicators: list[Indicator], force: bool = False
    ) -> dict[str, str]:
        """
        Refresh many series concurrently. One bad series must not take down the
        whole dashboard, so failures are collected and returned rather than
        raised -- the composites simply drop that member and report reduced
        coverage.
        """
        results = await asyncio.gather(
            *(self.ensure_series(i, force) for i in indicators),
            return_exceptions=True,
        )
        errors: dict[str, str] = {}
        for ind, res in zip(indicators, results):
            if isinstance(res, BaseException):
                log.error("Refresh failed for %s: %s", ind.series_id, res)
                errors[ind.series_id] = str(res)
        return errors
