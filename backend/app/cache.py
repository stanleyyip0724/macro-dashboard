"""
SQLite-backed observation cache.

Why SQLite rather than Redis: the entire dataset is ~50 series x a few thousand
rows. It fits in a file, survives restarts with zero infrastructure, and gives
us a durable audit trail of what we fetched and when. Swap in Redis/Postgres
only when you need multiple backend replicas to share a cache.

The two-tier freshness strategy is the important part:

  Tier 1 (TTL)      -- inside the TTL, serve from SQLite, zero upstream calls.
  Tier 2 (metadata) -- past the TTL, spend ONE cheap /fred/series call to read
                       `last_updated`. If it matches what we already stored,
                       stamp the row as re-checked and skip the (much larger)
                       observations download entirely.

Tier 2 is what actually keeps us off the rate limit: most series are checked
many times a day but genuinely change only once a month.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS series_meta (
    series_id       TEXT PRIMARY KEY,
    title           TEXT,
    units           TEXT,
    frequency       TEXT,
    seasonal_adj    TEXT,
    last_updated    TEXT,   -- FRED's own last_updated stamp
    observation_end TEXT,
    fetched_at      REAL,   -- when we last downloaded observations
    checked_at      REAL,   -- when we last verified freshness (cheap call)
    payload         TEXT    -- full FRED metadata blob, for debugging
);

CREATE TABLE IF NOT EXISTS observations (
    series_id TEXT NOT NULL,
    obs_date  TEXT NOT NULL,
    value     REAL,          -- NULL for FRED's "." missing marker
    PRIMARY KEY (series_id, obs_date)
);

CREATE INDEX IF NOT EXISTS idx_obs_series_date
    ON observations (series_id, obs_date);

CREATE TABLE IF NOT EXISTS fetch_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id  TEXT,
    kind       TEXT,     -- 'meta' | 'observations'
    at         REAL,
    rows       INTEGER,
    note       TEXT
);
"""


@dataclass
class CachedSeries:
    series_id: str
    title: str
    units: str
    last_updated: str
    observation_end: str
    fetched_at: float
    checked_at: float
    observations: list[tuple[str, float | None]]


class Cache:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        with self.connect() as c:
            c.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            # WAL lets the scheduler write while requests read.
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn
        return conn

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = self._conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    # -- reads ------------------------------------------------------------

    def get_meta(self, series_id: str) -> sqlite3.Row | None:
        with self.connect() as c:
            return c.execute(
                "SELECT * FROM series_meta WHERE series_id = ?", (series_id,)
            ).fetchone()

    def get_series(self, series_id: str) -> CachedSeries | None:
        meta = self.get_meta(series_id)
        if meta is None:
            return None
        with self.connect() as c:
            rows = c.execute(
                "SELECT obs_date, value FROM observations "
                "WHERE series_id = ? ORDER BY obs_date",
                (series_id,),
            ).fetchall()
        return CachedSeries(
            series_id=series_id,
            title=meta["title"] or "",
            units=meta["units"] or "",
            last_updated=meta["last_updated"] or "",
            observation_end=meta["observation_end"] or "",
            fetched_at=meta["fetched_at"] or 0.0,
            checked_at=meta["checked_at"] or 0.0,
            observations=[(r["obs_date"], r["value"]) for r in rows],
        )

    def is_fresh(self, series_id: str, ttl_seconds: int) -> bool:
        meta = self.get_meta(series_id)
        if meta is None or not meta["fetched_at"]:
            return False
        reference = max(meta["checked_at"] or 0.0, meta["fetched_at"] or 0.0)
        return (time.time() - reference) < ttl_seconds

    def stored_last_updated(self, series_id: str) -> str | None:
        meta = self.get_meta(series_id)
        return meta["last_updated"] if meta else None

    # -- writes -----------------------------------------------------------

    def put_meta(self, series_id: str, meta: dict) -> None:
        now = time.time()
        with self.connect() as c:
            c.execute(
                """
                INSERT INTO series_meta
                    (series_id, title, units, frequency, seasonal_adj,
                     last_updated, observation_end, fetched_at, checked_at, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(
                            (SELECT fetched_at FROM series_meta WHERE series_id = ?), 0), ?, ?)
                ON CONFLICT(series_id) DO UPDATE SET
                    title           = excluded.title,
                    units           = excluded.units,
                    frequency       = excluded.frequency,
                    seasonal_adj    = excluded.seasonal_adj,
                    last_updated    = excluded.last_updated,
                    observation_end = excluded.observation_end,
                    checked_at      = excluded.checked_at,
                    payload         = excluded.payload
                """,
                (
                    series_id,
                    meta.get("title"),
                    meta.get("units"),
                    meta.get("frequency_short"),
                    meta.get("seasonal_adjustment_short"),
                    meta.get("last_updated"),
                    meta.get("observation_end"),
                    series_id,
                    now,
                    json.dumps(meta),
                ),
            )
            c.execute(
                "INSERT INTO fetch_log (series_id, kind, at, rows, note) "
                "VALUES (?, 'meta', ?, 0, ?)",
                (series_id, now, meta.get("last_updated")),
            )

    def put_observations(
        self, series_id: str, observations: list[tuple[str, float | None]]
    ) -> None:
        now = time.time()
        with self.connect() as c:
            # Full replace: FRED revises history freely (GDP, payrolls), so an
            # append-only merge would leave us serving superseded numbers.
            c.execute("DELETE FROM observations WHERE series_id = ?", (series_id,))
            c.executemany(
                "INSERT INTO observations (series_id, obs_date, value) VALUES (?, ?, ?)",
                [(series_id, d, v) for d, v in observations],
            )
            c.execute(
                "UPDATE series_meta SET fetched_at = ?, checked_at = ? WHERE series_id = ?",
                (now, now, series_id),
            )
            c.execute(
                "INSERT INTO fetch_log (series_id, kind, at, rows, note) "
                "VALUES (?, 'observations', ?, ?, NULL)",
                (series_id, now, len(observations)),
            )

    def touch_checked(self, series_id: str) -> None:
        """Mark as verified-unchanged without re-downloading observations."""
        with self.connect() as c:
            c.execute(
                "UPDATE series_meta SET checked_at = ? WHERE series_id = ?",
                (time.time(), series_id),
            )

    def stats(self) -> dict:
        with self.connect() as c:
            series = c.execute("SELECT COUNT(*) n FROM series_meta").fetchone()["n"]
            obs = c.execute("SELECT COUNT(*) n FROM observations").fetchone()["n"]
            since = time.time() - 3600
            calls = c.execute(
                "SELECT kind, COUNT(*) n FROM fetch_log WHERE at > ? GROUP BY kind",
                (since,),
            ).fetchall()
        return {
            "series_cached": series,
            "observations_cached": obs,
            "upstream_calls_last_hour": {r["kind"]: r["n"] for r in calls},
        }
