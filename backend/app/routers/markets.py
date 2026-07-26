"""
Market routes.

Untyped dict responses on purpose: this payload is a composition of four
independent upstream shapes that can each degrade to empty, and pinning it to a
response_model would turn a partial outage into a 500. The frontend types in
`frontend/lib/markets.ts` are the contract, and every field is optional there.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from ..markets import MarketsService

router = APIRouter(tags=["markets"])


def get_markets(request: Request) -> MarketsService:
    return request.app.state.markets


@router.get("/markets")
async def markets_overview(
    svc: MarketsService = Depends(get_markets),
    force: bool = Query(False, description="Bypass the section TTLs"),
) -> dict:
    """Everything the markets page renders, in one call."""
    return await svc.overview(force=force)


@router.get("/markets/quotes")
async def markets_quotes(svc: MarketsService = Depends(get_markets)) -> dict:
    quotes = await svc.quotes()
    return {s: vars(q) for s, q in quotes.items()}


@router.get("/markets/curve")
async def markets_curve(svc: MarketsService = Depends(get_markets)) -> dict:
    from ..markets import narrative  # local import keeps the module graph flat

    curve = await svc.curve()
    if curve:
        curve = {**curve, "commentary": narrative.curve_commentary(curve)}
    return curve


@router.get("/markets/fear-greed")
async def markets_fear_greed(svc: MarketsService = Depends(get_markets)) -> dict:
    from ..markets import narrative

    fg = await svc.fear_greed()
    if fg:
        fg = {**fg, "commentary": narrative.fear_greed_commentary(fg, await svc.quotes())}
    return fg


@router.get("/markets/news")
async def markets_news(
    svc: MarketsService = Depends(get_markets),
    topic: str | None = Query(None),
    limit: int = Query(30, ge=1, le=100),
) -> list[dict]:
    from ..markets import narrative

    items = narrative.annotate_news(await svc.news())
    if topic:
        items = [i for i in items if i.get("topic") == topic]
    return items[:limit]
