from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..deps import get_service
from ..indicators import ALL_INDICATORS, Klass
from ..schemas import IndicatorCard, SeriesDetail
from ..service import MacroService
from ..transforms import to_records
from .summary import card

router = APIRouter(prefix="/series", tags=["series"])


@router.get("", response_model=list[IndicatorCard])
async def list_series(
    svc: MacroService = Depends(get_service),
    klass: str | None = Query(None, pattern="^(leading|coincident|lagging|financial)$"),
    tag: str | None = Query(None, description="Filter by registry tag, e.g. 'inflation'"),
) -> list[IndicatorCard]:
    snap = await svc.snapshot()
    out = []
    for ind in ALL_INDICATORS:
        if klass and ind.klass != Klass(klass):
            continue
        if tag and tag not in ind.tags:
            continue
        r = snap.results.get(ind.series_id)
        if r is not None:
            out.append(card(r))
    return out


@router.get("/{series_id}", response_model=SeriesDetail)
async def get_series(
    series_id: str,
    svc: MacroService = Depends(get_service),
    limit: int = Query(600, ge=12, le=20000, description="Observations to return"),
) -> SeriesDetail:
    series_id = series_id.upper()
    if svc.indicator(series_id) is None:
        raise HTTPException(
            404,
            f"{series_id} is not in the indicator registry. "
            f"Add it to app/indicators.py to expose it.",
        )

    snap = await svc.snapshot()
    r = snap.results.get(series_id)
    if r is None:
        raise HTTPException(
            503,
            f"{series_id} is registered but not cached yet. "
            f"POST /api/refresh to populate it.",
        )

    base = card(r)
    return SeriesDetail(
        **base.model_dump(),
        raw_history=to_records(r.raw, limit=limit),
        transformed_history=to_records(r.transformed, limit=limit),
        zscore_history=to_records(r.zscore, limit=limit),
    )
