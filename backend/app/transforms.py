"""
Turn raw FRED levels into comparable signals.

Three problems have to be solved before indicators can be added together:

  1. UNITS      -- payrolls are in thousands of jobs, CPI is an index level,
                   T10Y2Y is percentage points. Solved by `apply_transform`
                   (each series declares the transform that makes it a rate of
                   change or an already-comparable level) plus a z-score.

  2. DIRECTION  -- rising unemployment and rising GDP are both "up", but they
                   mean opposite things. Solved by `polarity`: every signal is
                   multiplied by +/-1 so that positive ALWAYS means "good for
                   the economy".

  3. FREQUENCY  -- daily, weekly, monthly and quarterly series cannot be summed
                   directly. Solved by computing each transform at its native
                   frequency (so a YoY is a true YoY) and only THEN resampling
                   the resulting z-score to month-end.

The z-score window is rolling, not full-history. A full-history z-score would
compare today against the 1970s and mark a normal 2020s reading as extreme;
a ~10-year rolling window asks the question that actually matters: "is this
unusual versus the recent regime?"
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .indicators import Freq, Indicator, Transform

# Observations per year, used to express "12 months ago" in native periods.
PERIODS_PER_YEAR: dict[Freq, int] = {
    Freq.DAILY: 252,
    Freq.WEEKLY: 52,
    Freq.MONTHLY: 12,
    Freq.QUARTERLY: 4,
}


def periods_for_months(freq: Freq, months: int) -> int:
    return max(1, round(PERIODS_PER_YEAR[freq] * months / 12))


@dataclass
class SeriesResult:
    """Everything the API and the analytics layer need about one indicator."""

    indicator: Indicator
    raw: pd.Series             # native frequency, cleaned
    transformed: pd.Series     # native frequency, after apply_transform
    zscore: pd.Series          # native frequency, rolling z of `transformed`
    signal: pd.Series          # monthly, polarity-adjusted z (+ = good)

    @property
    def latest_raw(self) -> float | None:
        return _last(self.raw)

    @property
    def latest_value(self) -> float | None:
        return _last(self.transformed)

    @property
    def latest_z(self) -> float | None:
        return _last(self.zscore)

    @property
    def latest_signal(self) -> float | None:
        return _last(self.signal)

    @property
    def latest_date(self) -> str | None:
        s = self.transformed.dropna()
        return s.index[-1].date().isoformat() if len(s) else None

    def change(self, months: int) -> float | None:
        """Change in the transformed value over N months (for card sparkline deltas)."""
        s = self.transformed.dropna()
        n = periods_for_months(self.indicator.freq, months)
        if len(s) <= n:
            return None
        return float(s.iloc[-1] - s.iloc[-1 - n])


def _last(s: pd.Series) -> float | None:
    s = s.dropna()
    if not len(s):
        return None
    v = float(s.iloc[-1])
    return None if not np.isfinite(v) else v


def to_series(observations: list[tuple[str, float | None]]) -> pd.Series:
    if not observations:
        return pd.Series(dtype="float64", index=pd.DatetimeIndex([]))
    idx = pd.to_datetime([d for d, _ in observations])
    vals = [np.nan if v is None else v for _, v in observations]
    s = pd.Series(vals, index=idx, dtype="float64").sort_index()
    return s[~s.index.duplicated(keep="last")]


def apply_transform(s: pd.Series, ind: Indicator) -> pd.Series:
    t, freq = ind.transform, ind.freq
    yr = PERIODS_PER_YEAR[freq]

    # fill_method=None is deliberate. pandas' default ('pad') forward-fills
    # NaNs BEFORE differencing, which would compute a year-on-year change
    # against a stale carried-forward level and report it as a real move.
    # A gap should produce NaN and be handled by the coverage logic instead.
    if t is Transform.LEVEL:
        out = s
    elif t is Transform.YOY_PCT:
        out = s.pct_change(yr, fill_method=None) * 100.0
    elif t is Transform.MOM_PCT:
        out = s.pct_change(1, fill_method=None) * 100.0
    elif t is Transform.MOM_DIFF:
        out = s.diff(1)
    elif t is Transform.CHG_3M:
        out = s.diff(periods_for_months(freq, 3))
    elif t is Transform.CHG_12M:
        out = s.diff(periods_for_months(freq, 12))
    elif t is Transform.ANNUALISED_3M:
        n = periods_for_months(freq, 3)
        ratio = s / s.shift(n)  # noqa: E501 -- explicit shift, no implicit fill
        # Guard against non-positive levels before fractional exponentiation.
        ratio = ratio.where(ratio > 0)
        out = (ratio ** (12.0 / 3.0) - 1.0) * 100.0
    else:
        raise ValueError(f"unhandled transform {t}")

    return out.replace([np.inf, -np.inf], np.nan)


def rolling_z(s: pd.Series, window: int) -> pd.Series:
    """
    Rolling z-score with a warm-up floor.

    min_periods is set to a quarter of the window so a series with limited
    history still produces a usable (if noisier) signal instead of all-NaN.
    Zero-variance stretches would divide by zero, so those are masked out.
    """
    clean = s.dropna()
    if len(clean) < 8:
        return pd.Series(np.nan, index=s.index)
    min_p = max(8, window // 4)
    mean = clean.rolling(window, min_periods=min_p).mean()
    std = clean.rolling(window, min_periods=min_p).std(ddof=0)
    z = (clean - mean) / std.where(std > 1e-9)
    # Winsorise: a single data glitch should not dominate a composite.
    return z.clip(-4.0, 4.0).reindex(s.index)


# How many months a signal stays valid after its last print, by frequency.
# This is publication lag, not extrapolation: Q1 GDP released in April is still
# the best available estimate of GDP in June, and core PCE for May is still the
# current inflation read in July. Without this the composites silently empty out
# in the most recent months -- daily series keep reporting, monthly and
# quarterly ones do not, and the "current" reading ends up computed from the
# yield curve and credit spreads alone.
STALE_TOLERANCE_MONTHS: dict[Freq, int] = {
    Freq.DAILY: 2,
    Freq.WEEKLY: 2,
    Freq.MONTHLY: 4,
    Freq.QUARTERLY: 8,
}


def current_month_end() -> pd.Timestamp:
    return pd.Timestamp.today().normalize().to_period("M").to_timestamp("M")


def to_monthly(s: pd.Series, ind: Indicator, horizon: pd.Timestamp | None = None) -> pd.Series:
    """
    Resample to month-end, extend to a common horizon, then carry the last
    known value forward within a bounded window.

    The reindex is load-bearing and easy to miss: `resample` can only produce
    bins up to a series' own final observation, so a monthly series whose last
    print is May yields an index ending in May and `ffill` has no slots to fill
    into. Every series must first be projected onto the SAME month-end index --
    only then does forward-filling actually bridge publication lag.

    The bound is what keeps this honest: an unbounded ffill would let a
    discontinued series (see USSLIND) contribute to composites forever.
    """
    if not len(s):
        return s
    monthly = s.resample("ME").last()
    horizon = horizon or current_month_end()
    if monthly.index[-1] < horizon:
        extension = pd.date_range(monthly.index[-1], horizon, freq="ME")
        monthly = monthly.reindex(monthly.index.union(extension))
    return monthly.ffill(limit=STALE_TOLERANCE_MONTHS[ind.freq])


def build(ind: Indicator, observations: list[tuple[str, float | None]]) -> SeriesResult:
    raw = to_series(observations)
    transformed = apply_transform(raw, ind)
    z = rolling_z(transformed, ind.z_window)
    signal = to_monthly(z, ind) * ind.polarity
    return SeriesResult(
        indicator=ind,
        raw=raw,
        transformed=transformed,
        zscore=z,
        signal=signal,
    )


def composite(
    results: list[SeriesResult], min_coverage: float = 0.5
) -> tuple[pd.Series, dict]:
    """
    Weighted average of monthly polarity-adjusted signals.

    Weights are renormalised over whichever members are actually present in
    each month, so the composite does not lurch when a slow-reporting series
    (quarterly GDP, SLOOS) has not printed yet. Months where less than
    `min_coverage` of total weight is available are dropped rather than
    reported as a misleadingly precise number.
    """
    # weight == 0 members (USREC, the raw recession-probability series) are
    # registered for the risk engine and alerts, not for the cycle composites.
    usable = [
        r for r in results
        if r.indicator.weight > 0 and r.signal.dropna().size > 0
    ]
    if not usable:
        return pd.Series(dtype="float64"), {"members": 0, "coverage": 0.0}

    frame = pd.DataFrame({r.indicator.series_id: r.signal for r in usable})
    weights = pd.Series(
        {r.indicator.series_id: r.indicator.weight for r in usable}, dtype="float64"
    )

    present = frame.notna()
    available_weight = present.mul(weights, axis=1).sum(axis=1)
    total_weight = float(weights.sum())
    weighted_sum = frame.mul(weights, axis=1).sum(axis=1, skipna=True)

    coverage = available_weight / total_weight
    comp = (weighted_sum / available_weight.where(available_weight > 0))
    comp = comp.where(coverage >= min_coverage).dropna()

    # Report coverage as of the last month the composite actually RETAINED,
    # not the last month in the index. Those differ whenever the newest month
    # fell below min_coverage, and reporting the latter describes a month whose
    # value was discarded.
    latest_cov = float(coverage.loc[comp.index[-1]]) if len(comp) else 0.0
    missing_now = (
        [c for c in frame.columns if pd.isna(frame.loc[comp.index[-1], c])]
        if len(comp) else list(frame.columns)
    )
    return comp, {
        "members": len(usable),
        "coverage": round(latest_cov, 3),
        "as_of": comp.index[-1].date().isoformat() if len(comp) else None,
        "missing_at_latest": missing_now,
        "weights": {k: round(float(v), 3) for k, v in weights.items()},
    }


def slope(s: pd.Series, months: int) -> float | None:
    """Change in a monthly composite over N months -- the momentum term."""
    s = s.dropna()
    if len(s) <= months:
        return None
    return float(s.iloc[-1] - s.iloc[-1 - months])


def to_records(s: pd.Series, limit: int | None = None) -> list[dict]:
    """Serialise a series for the frontend charts."""
    s = s.dropna()
    if limit:
        s = s.iloc[-limit:]
    return [
        {"date": idx.date().isoformat(), "value": round(float(v), 4)}
        for idx, v in s.items()
        if np.isfinite(v)
    ]
