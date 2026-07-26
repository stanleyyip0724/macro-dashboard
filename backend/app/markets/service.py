"""
Markets service: fetches, caches and assembles everything the markets page needs.

Isolation is the design rule here. Market data comes from public endpoints with
no SLA, so every section is fetched independently and a failure yields an empty
section plus a recorded error — never a 500. The macro side of the dashboard
(cycle, risk, alerts) does not touch this module and cannot be broken by it.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import time
from dataclasses import dataclass, field

from ..config import Settings
from . import narrative, providers
from .catalog import (
    ALL, BY_SYMBOL, COMMODITIES, CRYPTO, FX, Group, INDICES, SECTORS, VOL,
)

log = logging.getLogger(__name__)

# Prices move all day; sentiment and the curve are daily prints. Separate TTLs
# keep us cheap on the slow sources without making prices stale.
TTL_QUOTES = 15 * 60
TTL_CURVE = 6 * 3600
TTL_FEAR_GREED = 3600
TTL_NEWS = 30 * 60


@dataclass
class _Slot:
    """One cached section with its own TTL and its own last-error record."""

    ttl: float
    value: object = None
    fetched_at: float = 0.0
    error: str | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def fresh(self) -> bool:
        return self.value is not None and (time.time() - self.fetched_at) < self.ttl


def _thin(points: list[dict], target: int) -> list[dict]:
    """Even-stride downsample that always keeps the first and last point."""
    if len(points) <= target or target < 2:
        return points
    step = len(points) / target
    kept = [points[int(i * step)] for i in range(target)]
    if kept[-1] is not points[-1]:
        kept[-1] = points[-1]
    return kept


class MarketsService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._quotes = _Slot(TTL_QUOTES)
        self._curve = _Slot(TTL_CURVE)
        self._fg = _Slot(TTL_FEAR_GREED)
        self._news = _Slot(TTL_NEWS)

    async def _load(self, slot: _Slot, coro_factory, label: str, force: bool):
        """
        Fetch into a slot, serialised per slot, with stale-on-error semantics:
        if the upstream call fails we keep serving the last good payload.
        """
        if slot.fresh() and not force:
            return slot.value
        async with slot.lock:
            if slot.fresh() and not force:
                return slot.value
            try:
                value = await coro_factory()
                slot.value = value
                slot.fetched_at = time.time()
                slot.error = None
            except Exception as exc:  # noqa: BLE001
                slot.error = f"{type(exc).__name__}: {exc}"
                log.warning("Markets section '%s' failed: %s", label, slot.error)
                # Keep the stale value if we have one; the UI labels it by as_of.
            return slot.value

    async def quotes(self, force: bool = False) -> dict[str, providers.Quote]:
        v = await self._load(self._quotes, lambda: providers.fetch_quotes(ALL),
                             "quotes", force)
        return v or {}

    async def curve(self, force: bool = False) -> dict:
        v = await self._load(
            self._curve, lambda: providers.fetch_curve(self.settings.fred_api_key),
            "curve", force,
        )
        return v or {}

    async def fear_greed(self, force: bool = False) -> dict:
        v = await self._load(self._fg, providers.fetch_fear_greed, "fear_greed", force)
        return v or {}

    async def news(self, force: bool = False) -> list[dict]:
        v = await self._load(self._news, providers.fetch_news, "news", force)
        return v or []

    # -- assembly ---------------------------------------------------------

    def _rows(self, quotes: dict[str, providers.Quote], group_members) -> list[dict]:
        rows = []
        for inst in group_members:
            q = quotes.get(inst.symbol)
            if q is None:
                continue
            rows.append({
                "symbol": inst.symbol,
                "name": inst.name,
                "short": inst.short,
                "group": inst.group.value,
                "region": inst.region,
                "unit": inst.unit,
                "size": inst.size,
                "notes": inst.notes,
                "price": q.price,
                "currency": q.currency,
                "as_of": q.as_of,
                "changes": {k: (None if v is None else round(v, 3))
                            for k, v in q.changes.items()},
                "high_52w": q.high_52w,
                "low_52w": q.low_52w,
                "range_position": (None if q.range_position is None
                                   else round(q.range_position, 4)),
                # Downsampled: the YTD line is ~200px tall on screen, so daily
                # resolution past ~130 points is bytes the reader cannot see.
                "ytd_path": _thin(q.ytd_path, 130),
                # Price history is only carried for series plotted as levels
                # (VIX), not for the ones plotted as returns -- the YTD path
                # already covers those, and shipping both doubles the payload.
                "history": (
                    _thin(q.history[-260:], 180)
                    if inst.group is Group.VOL else []
                ),
                "commentary": narrative.instrument_note(q),
            })
        # Best YTD first: the table is read as a ranking, not as a list.
        rows.sort(key=lambda r: (r["changes"].get("ytd") is None,
                                 -(r["changes"].get("ytd") or 0)))
        return rows

    async def overview(self, force: bool = False) -> dict:
        quotes, curve, fg, news = await asyncio.gather(
            self.quotes(force), self.curve(force),
            self.fear_greed(force), self.news(force),
        )

        sections = {
            "indices": self._rows(quotes, INDICES),
            "sectors": self._rows(quotes, SECTORS),
            "volatility": self._rows(quotes, VOL),
            "commodities": self._rows(quotes, COMMODITIES),
            "crypto": self._rows(quotes, CRYPTO),
            "fx": self._rows(quotes, FX),
        }

        annotated = narrative.annotate_news(news)
        curve["commentary"] = narrative.curve_commentary(curve) if curve else []
        if fg:
            fg["commentary"] = narrative.fear_greed_commentary(fg, quotes)

        as_of_dates = [q.as_of for q in quotes.values() if q.as_of]

        return {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "data_as_of": max(as_of_dates) if as_of_dates else None,
            "summary": narrative.top_summary(quotes, curve, fg),
            "sections": sections,
            "commentary": {
                "equities": narrative.equity_commentary(quotes),
                "sectors": narrative.sector_commentary(quotes),
                "commodities": narrative.commodity_commentary(quotes),
                "fx_crypto": narrative.fx_crypto_commentary(quotes),
            },
            "curve": curve,
            "fear_greed": fg,
            "news": annotated,
            "errors": {
                k: v for k, v in {
                    "quotes": self._quotes.error,
                    "curve": self._curve.error,
                    "fear_greed": self._fg.error,
                    "news": self._news.error,
                }.items() if v
            },
            "coverage_note": (
                f"{len(quotes)} of {len(ALL)} instruments priced."
                + ("" if len(quotes) == len(ALL) else " Missing: "
                   + ", ".join(BY_SYMBOL[s].short for s in
                               (i.symbol for i in ALL) if s not in quotes))
            ),
        }
