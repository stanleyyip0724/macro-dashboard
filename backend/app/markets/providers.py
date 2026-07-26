"""
Upstream fetchers for market data.

Four independent sources, each isolated behind its own function so that one of
them going down degrades a single panel instead of the whole page:

  * Yahoo Finance chart API -- prices for indices, commodities, crypto and FX.
  * FRED                    -- the US Treasury constant-maturity curve.
  * CNN                     -- the Fear & Greed index.
  * Google News RSS         -- market headlines.

None of them needs a key except FRED, which the app already holds.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import httpx

from .catalog import CURVE_TENORS, Instrument

log = logging.getLogger(__name__)

# Yahoo and CNN both reject the default httpx UA. This is a plain browser UA --
# we are reading the same public JSON their own web pages read.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

YAHOO_HOSTS = (
    "https://query1.finance.yahoo.com",
    "https://query2.finance.yahoo.com",
)
CNN_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
FRED_OBS_URL = "https://api.stlouisfed.org/fred/series/observations"


@dataclass
class Quote:
    """One instrument's price history reduced to the numbers the UI needs."""

    symbol: str
    price: float | None = None
    previous_close: float | None = None
    currency: str = ""
    as_of: str | None = None
    changes: dict[str, float | None] = field(default_factory=dict)  # pct, by horizon
    high_52w: float | None = None
    low_52w: float | None = None
    range_position: float | None = None   # 0 = at 52w low, 1 = at 52w high
    history: list[dict] = field(default_factory=list)   # [{date, value}] daily
    ytd_path: list[dict] = field(default_factory=list)  # [{date, value}] % from Jan 1


def _pct(new: float | None, old: float | None) -> float | None:
    if new is None or old is None or old == 0:
        return None
    return (new / old - 1.0) * 100.0


def _parse_chart(symbol: str, payload: dict) -> Quote | None:
    try:
        result = payload["chart"]["result"][0]
        meta = result["meta"]
        stamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError):
        return None

    # Yahoo emits nulls on non-trading stamps; drop them rather than
    # forward-filling, which would invent prices on holidays.
    series: list[tuple[dt.date, float]] = [
        (dt.datetime.utcfromtimestamp(t).date(), float(c))
        for t, c in zip(stamps, closes)
        if c is not None
    ]
    if not series:
        return None
    series.sort(key=lambda p: p[0])

    dates = [d for d, _ in series]
    values = [v for _, v in series]
    price = meta.get("regularMarketPrice") or values[-1]
    last_date = dates[-1]

    def at_or_before(target: dt.date) -> float | None:
        prior = [v for d, v in series if d <= target]
        return prior[-1] if prior else None

    def n_back(n: int) -> float | None:
        return values[-1 - n] if len(values) > n else None

    jan1 = dt.date(last_date.year, 1, 1)
    ytd_base = at_or_before(jan1 - dt.timedelta(days=1)) or values[0]

    changes = {
        # NOT meta.chartPreviousClose: on a multi-year range that field is the
        # close before the START of the range, so using it turns "1D" into a
        # two-year return. The prior daily close is the only correct anchor.
        "1d": _pct(price, n_back(1)),
        "1w": _pct(price, at_or_before(last_date - dt.timedelta(days=7))),
        "1m": _pct(price, at_or_before(last_date - dt.timedelta(days=30))),
        "3m": _pct(price, at_or_before(last_date - dt.timedelta(days=91))),
        "6m": _pct(price, at_or_before(last_date - dt.timedelta(days=182))),
        "ytd": _pct(price, ytd_base),
        "12m": _pct(price, at_or_before(last_date - dt.timedelta(days=365))),
    }

    window = [v for d, v in series if d >= last_date - dt.timedelta(days=365)]
    hi, lo = (max(window), min(window)) if window else (None, None)
    pos = None
    if hi is not None and lo is not None and hi > lo and price is not None:
        pos = max(0.0, min(1.0, (price - lo) / (hi - lo)))

    # Keep the plotted history light: ~1y of daily closes is enough for a
    # sparkline and for the YTD-path chart, and keeps the payload small.
    recent = [(d, v) for d, v in series if d >= last_date - dt.timedelta(days=400)]
    ytd_pts = [
        {"date": d.isoformat(), "value": round((v / ytd_base - 1) * 100, 3)}
        for d, v in series
        if d >= jan1 and ytd_base
    ]

    return Quote(
        symbol=symbol,
        price=price,
        previous_close=n_back(1),
        currency=meta.get("currency", ""),
        as_of=last_date.isoformat(),
        changes=changes,
        high_52w=hi,
        low_52w=lo,
        range_position=pos,
        history=[{"date": d.isoformat(), "value": round(v, 4)} for d, v in recent],
        ytd_path=ytd_pts,
    )


async def fetch_quote(client: httpx.AsyncClient, inst: Instrument) -> Quote | None:
    """One instrument. Falls back to the second Yahoo host before giving up."""
    params = {"range": "2y", "interval": "1d", "includePrePost": "false"}
    for host in YAHOO_HOSTS:
        try:
            r = await client.get(
                f"{host}/v8/finance/chart/{inst.symbol}",
                params=params,
                headers=BROWSER_HEADERS,
                timeout=20.0,
            )
            if r.status_code != 200:
                continue
            q = _parse_chart(inst.symbol, r.json())
            if q is not None:
                return q
        except Exception as exc:  # noqa: BLE001
            log.warning("Yahoo fetch failed for %s via %s: %s", inst.symbol, host, exc)
    return None


async def fetch_quotes(instruments: list[Instrument]) -> dict[str, Quote]:
    """All instruments concurrently, bounded so we do not look like a scraper."""
    sem = asyncio.Semaphore(6)
    out: dict[str, Quote] = {}

    async with httpx.AsyncClient(follow_redirects=True) as client:
        async def one(inst: Instrument) -> None:
            async with sem:
                q = await fetch_quote(client, inst)
            if q is not None:
                out[inst.symbol] = q

        await asyncio.gather(*(one(i) for i in instruments))

    missing = [i.symbol for i in instruments if i.symbol not in out]
    if missing:
        log.warning("No quote for %d symbols: %s", len(missing), ", ".join(missing))
    return out


# -- US Treasury curve ------------------------------------------------------


async def fetch_curve(fred_api_key: str) -> dict:
    """
    Current curve plus 1-week, 1-month and 1-year-ago vintages.

    Each tenor is fetched over a 400-day window in a single call, so the
    historical comparison costs no extra requests.
    """
    start = (dt.date.today() - dt.timedelta(days=430)).isoformat()
    sem = asyncio.Semaphore(6)
    series: dict[str, list[tuple[dt.date, float]]] = {}

    async with httpx.AsyncClient() as client:
        async def one(sid: str) -> None:
            params = {
                "series_id": sid,
                "api_key": fred_api_key,
                "file_type": "json",
                "observation_start": start,
            }
            async with sem:
                try:
                    r = await client.get(FRED_OBS_URL, params=params, timeout=25.0)
                    r.raise_for_status()
                    obs = r.json().get("observations", [])
                except Exception as exc:  # noqa: BLE001
                    log.warning("FRED curve fetch failed for %s: %s", sid, exc)
                    return
            pts = [
                (dt.date.fromisoformat(o["date"]), float(o["value"]))
                for o in obs
                if o.get("value") not in (".", "", None)
            ]
            if pts:
                series[sid] = sorted(pts)

        await asyncio.gather(*(one(sid) for sid, _, _ in CURVE_TENORS))

    if not series:
        return {}

    latest_date = max(pts[-1][0] for pts in series.values())

    def vintage(target: dt.date) -> dict[str, float]:
        row: dict[str, float] = {}
        for sid, pts in series.items():
            prior = [v for d, v in pts if d <= target]
            if prior:
                row[sid] = prior[-1]
        return row

    now = vintage(latest_date)
    wk = vintage(latest_date - dt.timedelta(days=7))
    mo = vintage(latest_date - dt.timedelta(days=30))
    yr = vintage(latest_date - dt.timedelta(days=365))

    points = []
    for sid, label, years in CURVE_TENORS:
        if sid not in now:
            continue
        points.append({
            "series_id": sid,
            "label": label,
            "years": years,
            "current": round(now[sid], 3),
            "week_ago": round(wk[sid], 3) if sid in wk else None,
            "month_ago": round(mo[sid], 3) if sid in mo else None,
            "year_ago": round(yr[sid], 3) if sid in yr else None,
        })

    # 10Y history, for the "where are long rates heading" strip.
    tens = series.get("DGS10", [])
    history = [
        {"date": d.isoformat(), "value": v}
        for d, v in tens
        if d >= latest_date - dt.timedelta(days=365)
    ]

    return {"as_of": latest_date.isoformat(), "points": points, "ten_year_history": history}


# -- CNN Fear & Greed -------------------------------------------------------


async def fetch_fear_greed() -> dict:
    headers = {**BROWSER_HEADERS, "Referer": "https://edition.cnn.com/",
               "Origin": "https://edition.cnn.com"}
    async with httpx.AsyncClient(follow_redirects=True) as client:
        r = await client.get(CNN_URL, headers=headers, timeout=20.0)
        r.raise_for_status()
        payload = r.json()

    fg = payload.get("fear_and_greed", {})
    hist_block = payload.get("fear_and_greed_historical", {}) or {}
    raw_hist = hist_block.get("data", []) or []
    # CNN ships ~2 years of daily points; the last ~180 is plenty for a chart.
    history = [
        {
            "date": dt.datetime.utcfromtimestamp(p["x"] / 1000).date().isoformat(),
            "value": round(float(p["y"]), 2),
        }
        for p in raw_hist[-180:]
        if p.get("x") and p.get("y") is not None
    ]

    components = []
    labels = {
        "market_momentum_sp500": ("Market momentum", "S&P 500 vs its 125-day average"),
        "stock_price_strength": ("Price strength", "52-week highs vs lows on the NYSE"),
        "stock_price_breadth": ("Price breadth", "Volume in advancing vs declining stocks"),
        "put_call_options": ("Put/call ratio", "Options positioning over five days"),
        "market_volatility_vix": ("Volatility", "VIX vs its 50-day average"),
        "safe_haven_demand": ("Safe-haven demand", "Stock returns vs Treasury returns"),
        "junk_bond_demand": ("Junk bond demand", "High-yield vs investment-grade spread"),
    }
    for key, (name, detail) in labels.items():
        block = payload.get(key)
        if not isinstance(block, dict) or block.get("score") is None:
            continue
        components.append({
            "key": key,
            "name": name,
            "detail": detail,
            "score": round(float(block["score"]), 1),
            "rating": block.get("rating", ""),
        })

    return {
        "score": round(float(fg.get("score", 0)), 1) if fg.get("score") is not None else None,
        "rating": fg.get("rating", ""),
        "as_of": (fg.get("timestamp") or "")[:10] or None,
        "previous_close": fg.get("previous_close"),
        "previous_1_week": fg.get("previous_1_week"),
        "previous_1_month": fg.get("previous_1_month"),
        "previous_1_year": fg.get("previous_1_year"),
        "components": components,
        "history": history,
    }


# -- News -------------------------------------------------------------------

NEWS_QUERIES: list[tuple[str, str]] = [
    ("markets", "stock market OR equities when:3d"),
    ("central-banks", "Federal Reserve OR ECB OR Bank of Japan interest rates when:3d"),
    ("inflation", "inflation OR CPI OR PPI data when:5d"),
    ("supply-chain", "supply chain OR semiconductor OR tariff OR export controls when:5d"),
    ("energy", "oil prices OR OPEC OR energy markets when:3d"),
    ("geopolitics", "geopolitical risk OR sanctions OR trade war when:3d"),
]

_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", text)).strip()


async def fetch_news(limit_per_query: int = 6) -> list[dict]:
    """Headlines from Google News RSS. Returns [] rather than raising."""
    items: list[dict] = []
    seen: set[str] = set()

    async with httpx.AsyncClient(follow_redirects=True) as client:
        async def one(topic: str, query: str) -> list[dict]:
            url = "https://news.google.com/rss/search"
            params = {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}
            try:
                r = await client.get(url, params=params, headers=BROWSER_HEADERS,
                                     timeout=20.0)
                r.raise_for_status()
                root = ET.fromstring(r.text)
            except Exception as exc:  # noqa: BLE001
                log.warning("News fetch failed for %s: %s", topic, exc)
                return []

            out = []
            for node in root.findall(".//item")[:limit_per_query]:
                title = _clean(node.findtext("title"))
                if not title:
                    continue
                source_node = node.find("source")
                out.append({
                    "topic": topic,
                    "title": title,
                    "link": node.findtext("link") or "",
                    "published": node.findtext("pubDate") or "",
                    "source": _clean(source_node.text) if source_node is not None else "",
                    "summary": _clean(node.findtext("description"))[:400],
                })
            return out

        for batch in await asyncio.gather(*(one(t, q) for t, q in NEWS_QUERIES)):
            for it in batch:
                key = it["title"].lower()[:90]
                if key in seen:
                    continue
                seen.add(key)
                items.append(it)

    return items
