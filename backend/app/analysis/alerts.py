"""
Alert engine.

Alerts fire from three independent sources so a single model quirk cannot
either manufacture or suppress a warning:

  1. THRESHOLD  -- the `alert_above` / `alert_below` levels declared on each
                   indicator. These are published, externally-defined lines
                   (Sahm 0.50, CFNAI -0.70, curve at zero), not tuned numbers.
  2. STATISTICAL-- any indicator more than 2sd into "bad" territory, whether or
                   not anyone has written a rule about it.
  3. VELOCITY   -- rapid deterioration. A z-score that moves 1.5sd in three
                   months is informative even while the level is still fine;
                   this is what catches turning points early.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..transforms import SeriesResult


class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


SEVERITY_RANK = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}


@dataclass
class Alert:
    id: str
    severity: str
    kind: str
    series_id: str
    title: str
    message: str
    value: float | None
    threshold: float | None
    unit: str
    as_of: str | None


def _fmt(v: float | None, unit: str) -> str:
    if v is None:
        return "n/a"
    if unit == "%":
        return f"{v:.2f}%"
    if unit == "pp":
        return f"{v:+.2f}pp"
    if unit == "k jobs":
        return f"{v:+,.0f}k"
    return f"{v:,.2f}"


def evaluate(results: dict[str, SeriesResult]) -> list[Alert]:
    alerts: list[Alert] = []

    for r in results.values():
        ind = r.indicator
        raw = r.latest_raw
        transformed = r.latest_value
        z = r.latest_z
        as_of = r.latest_date

        # -- 1. published thresholds --------------------------------------
        # Thresholds are expressed against the value a human would read, which
        # is the transformed value (YoY % for CPI, level for the curve).
        check = transformed if transformed is not None else raw

        if ind.alert_above is not None and check is not None and check > ind.alert_above:
            alerts.append(Alert(
                id=f"{ind.series_id}:above",
                severity=(
                    Severity.CRITICAL.value
                    if "recession" in ind.tags or "stress" in ind.tags
                    else Severity.WARNING.value
                ),
                kind="threshold",
                series_id=ind.series_id,
                title=f"{ind.short} above threshold",
                message=(
                    f"{ind.name} is at {_fmt(check, ind.unit)}, above the "
                    f"{_fmt(ind.alert_above, ind.unit)} threshold. {ind.notes}"
                ).strip(),
                value=round(check, 3), threshold=ind.alert_above,
                unit=ind.unit, as_of=as_of,
            ))

        if ind.alert_below is not None and check is not None and check < ind.alert_below:
            alerts.append(Alert(
                id=f"{ind.series_id}:below",
                severity=(
                    Severity.CRITICAL.value
                    if "yield-curve" in ind.tags or "recession" in ind.tags
                    else Severity.WARNING.value
                ),
                kind="threshold",
                series_id=ind.series_id,
                title=f"{ind.short} below threshold",
                message=(
                    f"{ind.name} is at {_fmt(check, ind.unit)}, below the "
                    f"{_fmt(ind.alert_below, ind.unit)} threshold. {ind.notes}"
                ).strip(),
                value=round(check, 3), threshold=ind.alert_below,
                unit=ind.unit, as_of=as_of,
            ))

        # -- 2. statistical extremes --------------------------------------
        if z is not None:
            badness = -ind.polarity * z
            if badness >= 2.0:
                alerts.append(Alert(
                    id=f"{ind.series_id}:zscore",
                    severity=(
                        Severity.CRITICAL.value if badness >= 2.75
                        else Severity.WARNING.value
                    ),
                    kind="statistical",
                    series_id=ind.series_id,
                    title=f"{ind.short} at a statistical extreme",
                    message=(
                        f"{ind.name} is {badness:.1f} standard deviations into "
                        f"adverse territory versus its own recent history "
                        f"(current {_fmt(transformed, ind.unit)})."
                    ),
                    value=round(z, 3), threshold=2.0, unit="sd", as_of=as_of,
                ))

        # -- 3. velocity ---------------------------------------------------
        zc = _z_change(r, months=3)
        if zc is not None:
            deterioration = -ind.polarity * zc
            if deterioration >= 1.5:
                alerts.append(Alert(
                    id=f"{ind.series_id}:velocity",
                    severity=Severity.WARNING.value,
                    kind="velocity",
                    series_id=ind.series_id,
                    title=f"{ind.short} deteriorating rapidly",
                    message=(
                        f"{ind.name} has moved {deterioration:.1f} standard "
                        f"deviations in the adverse direction over three months. "
                        f"Rate of change, not level, is the signal here."
                    ),
                    value=round(zc, 3), threshold=1.5, unit="sd", as_of=as_of,
                ))

    # Deduplicate: keep only the most severe alert per series, so one series
    # firing on all three rules does not flood the panel.
    best: dict[str, Alert] = {}
    for a in alerts:
        cur = best.get(a.series_id)
        if cur is None or SEVERITY_RANK[Severity(a.severity)] < SEVERITY_RANK[Severity(cur.severity)]:
            best[a.series_id] = a

    return sorted(
        best.values(),
        key=lambda a: (SEVERITY_RANK[Severity(a.severity)], a.series_id),
    )


def _z_change(r: SeriesResult, months: int) -> float | None:
    """Change in the z-score over N months, at the series' native frequency."""
    from ..transforms import periods_for_months

    z = r.zscore.dropna()
    n = periods_for_months(r.indicator.freq, months)
    if len(z) <= n:
        return None
    return float(z.iloc[-1] - z.iloc[-1 - n])
