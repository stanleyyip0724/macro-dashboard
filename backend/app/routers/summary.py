from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query

from ..analysis.risk import RiskAssessment
from ..deps import get_service
from ..indicators import HEADLINE_IDS, BY_ID, Klass
from ..schemas import (
    AlertOut, CompositeSeries, CycleOut, HealthOut, IndicatorCard,
    RiskOut, SummaryOut,
)
from ..service import MacroService, Snapshot
from ..transforms import SeriesResult, composite, to_records

router = APIRouter(tags=["summary"])


def _r(v: float | None, places: int = 4) -> float | None:
    return None if v is None else round(v, places)


def card(r: SeriesResult, sparkline_points: int = 36) -> IndicatorCard:
    ind = r.indicator
    return IndicatorCard(
        series_id=ind.series_id,
        name=ind.name,
        short=ind.short,
        klass=ind.klass.value,
        unit=ind.unit,
        transform=ind.transform.value,
        frequency=ind.freq.value,
        polarity=ind.polarity,
        latest_raw=_r(r.latest_raw),
        latest_value=_r(r.latest_value),
        latest_z=_r(r.latest_z),
        signal=_r(r.latest_signal),
        change_3m=_r(r.change(3)),
        change_12m=_r(r.change(12)),
        as_of=r.latest_date,
        notes=ind.notes,
        tags=list(ind.tags),
        sparkline=to_records(r.transformed, limit=sparkline_points),
    )


def cycle_out(snap: Snapshot) -> CycleOut:
    c = snap.cycle
    return CycleOut(
        phase=c.phase.value,
        description=c.description,
        confidence=c.confidence,
        growth_level=c.growth_level,
        growth_momentum=c.growth_momentum,
        inflation_pressure=c.inflation_pressure,
        breadth=c.breadth,
        composites=c.composites,
        coverage=c.coverage,
        hard_signals=[vars(h) for h in c.hard_signals],
        rationale=c.rationale,
        history=c.history,
    )


def risk_out(r: RiskAssessment) -> RiskOut:
    return RiskOut(
        score=r.score, band=r.band, band_description=r.band_description,
        base_score=r.base_score, trigger_bonus=r.trigger_bonus,
        coverage=r.coverage, pillars=r.pillars, pillar_weights=r.pillar_weights,
        contributions=[vars(c) for c in r.contributions],
        triggers=[vars(t) for t in r.triggers],
        top_drivers=r.top_drivers,
    )


@router.get("/summary", response_model=SummaryOut)
async def get_summary(
    svc: MacroService = Depends(get_service),
    history_months: int = Query(120, ge=12, le=420),
) -> SummaryOut:
    """
    The single call that renders the whole dashboard.

    Deliberately one endpoint rather than six: every widget derives from the
    same snapshot, and splitting it would let the cards disagree with the gauge
    if a refresh landed between requests.
    """
    snap = await svc.snapshot()

    headline = [
        card(snap.results[sid]) for sid in HEADLINE_IDS if sid in snap.results
    ]

    by_class: dict[Klass, list[SeriesResult]] = {k: [] for k in Klass}
    for r in snap.results.values():
        by_class[r.indicator.klass].append(r)

    composites: list[CompositeSeries] = []
    for klass in (Klass.LEADING, Klass.COINCIDENT, Klass.LAGGING, Klass.FINANCIAL):
        s, _meta = composite(by_class[klass])
        composites.append(
            CompositeSeries(
                name=klass.value,
                points=to_records(s, limit=history_months),
            )
        )

    dates = [r.latest_date for r in snap.results.values() if r.latest_date]
    data_as_of = max(dates) if dates else None

    missing_names = [BY_ID[m].short for m in snap.missing if m in BY_ID]
    note = (
        f"{len(snap.results)} of {len(snap.results) + len(snap.missing)} series "
        f"available."
    )
    if missing_names:
        note += " Unavailable: " + ", ".join(missing_names) + "."

    return SummaryOut(
        generated_at=dt.datetime.fromtimestamp(snap.built_at).isoformat(timespec="seconds"),
        data_as_of=data_as_of,
        cycle=cycle_out(snap),
        risk=risk_out(snap.risk),
        alerts=[AlertOut(**vars(a)) for a in snap.alerts],
        headline=headline,
        composites=composites,
        missing_series=snap.missing,
        coverage_note=note,
    )


@router.get("/cycle", response_model=CycleOut)
async def get_cycle(svc: MacroService = Depends(get_service)) -> CycleOut:
    return cycle_out(await svc.snapshot())


@router.get("/risk", response_model=RiskOut)
async def get_risk(svc: MacroService = Depends(get_service)) -> RiskOut:
    return risk_out((await svc.snapshot()).risk)


@router.get("/alerts", response_model=list[AlertOut])
async def get_alerts(
    svc: MacroService = Depends(get_service),
    severity: str | None = Query(None, pattern="^(critical|warning|info)$"),
) -> list[AlertOut]:
    snap = await svc.snapshot()
    items = snap.alerts
    if severity:
        items = [a for a in items if a.severity == severity]
    return [AlertOut(**vars(a)) for a in items]


@router.get("/health", response_model=HealthOut)
async def health(svc: MacroService = Depends(get_service)) -> HealthOut:
    snap = await svc.snapshot()
    return HealthOut(
        status="degraded" if snap.missing else "ok",
        series_registered=len(snap.results) + len(snap.missing),
        series_cached=len(snap.results),
        missing_series=snap.missing,
        last_refresh=(
            dt.datetime.fromtimestamp(svc.last_refresh).isoformat(timespec="seconds")
            if svc.last_refresh else None
        ),
        refresh_errors=svc.last_refresh_errors,
        cache=svc.cache.stats(),
    )


@router.post("/refresh")
async def refresh(
    svc: MacroService = Depends(get_service),
    force: bool = Query(False, description="Bypass TTL and last_updated checks"),
) -> dict:
    """
    Manual refresh. `force=true` ignores both cache tiers -- use it sparingly,
    it costs one metadata call plus one observations call per series.
    """
    errors = await svc.refresh(force=force)
    return {"refreshed": True, "forced": force, "errors": errors}
