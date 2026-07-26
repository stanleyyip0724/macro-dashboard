"""
Application service: the single place that turns cached observations into
analysed results, and holds the computed snapshot in memory.

There are two caches, and they exist for different reasons:

  * Cache (SQLite)  -- avoids hitting the FRED API. Persistent.
  * _Snapshot (RAM) -- avoids recomputing ~50 pandas pipelines on every
                       request. Rebuilt whenever the underlying data changes
                       or the snapshot TTL expires.

Without the second one, a dashboard with ten widgets would run the full
transform stack ten times per page load for identical output.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from .analysis import alerts as alerts_mod
from .analysis import cycle as cycle_mod
from .analysis import risk as risk_mod
from .cache import Cache
from .config import Settings
from .fred_client import FredClient
from .indicators import ALL_INDICATORS, BY_ID, Indicator
from .transforms import SeriesResult, build

log = logging.getLogger(__name__)

SNAPSHOT_TTL_SECONDS = 300


@dataclass
class Snapshot:
    built_at: float
    results: dict[str, SeriesResult]
    cycle: cycle_mod.CycleAssessment
    risk: risk_mod.RiskAssessment
    alerts: list[alerts_mod.Alert]
    missing: list[str]


class MacroService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.cache = Cache(settings.cache_db_path)
        self.client = FredClient(settings, self.cache)
        self._snapshot: Snapshot | None = None
        self._lock = asyncio.Lock()
        self.last_refresh: float | None = None
        self.last_refresh_errors: dict[str, str] = {}

    async def aclose(self) -> None:
        await self.client.aclose()

    # -- data refresh -----------------------------------------------------

    async def refresh(self, force: bool = False) -> dict[str, str]:
        errors = await self.client.ensure_many(ALL_INDICATORS, force=force)
        self.last_refresh = time.time()
        self.last_refresh_errors = errors
        self.invalidate()
        return errors

    def invalidate(self) -> None:
        self._snapshot = None

    # -- computation ------------------------------------------------------

    def _build_results(self) -> tuple[dict[str, SeriesResult], list[str]]:
        results: dict[str, SeriesResult] = {}
        missing: list[str] = []
        for ind in ALL_INDICATORS:
            cached = self.cache.get_series(ind.series_id)
            if cached is None or not cached.observations:
                missing.append(ind.series_id)
                continue
            try:
                results[ind.series_id] = build(ind, cached.observations)
            except Exception as exc:  # noqa: BLE001
                # One malformed series must never blank the dashboard.
                log.exception("Transform failed for %s: %s", ind.series_id, exc)
                missing.append(ind.series_id)
        return results, missing

    async def snapshot(self) -> Snapshot:
        snap = self._snapshot
        if snap is not None and (time.time() - snap.built_at) < SNAPSHOT_TTL_SECONDS:
            return snap

        async with self._lock:
            # Re-check: another coroutine may have rebuilt while we waited.
            snap = self._snapshot
            if snap is not None and (time.time() - snap.built_at) < SNAPSHOT_TTL_SECONDS:
                return snap

            # pandas work is CPU-bound and releases no GIL benefit here, so run
            # it in a worker thread to keep the event loop responsive.
            snap = await asyncio.to_thread(self._compute)
            self._snapshot = snap
            return snap

    def _compute(self) -> Snapshot:
        started = time.perf_counter()
        results, missing = self._build_results()
        snap = Snapshot(
            built_at=time.time(),
            results=results,
            cycle=cycle_mod.classify(results),
            risk=risk_mod.score(results),
            alerts=alerts_mod.evaluate(results),
            missing=missing,
        )
        log.info(
            "Snapshot rebuilt: %d series, %d missing, %.0fms",
            len(results), len(missing), (time.perf_counter() - started) * 1000,
        )
        return snap

    # -- lookups ----------------------------------------------------------

    def indicator(self, series_id: str) -> Indicator | None:
        return BY_ID.get(series_id)
