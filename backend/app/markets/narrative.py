"""
The interpretation layer.

Every number on the markets page is paired with a sentence that says which way
it is moving, how that compares with the rest of the tape, and what it implies.
The rules here are deterministic and cross-referential by design: a gold move is
read against the dollar and real yields, an index move against its own YTD path
and its peers, the curve against where it sat a month ago.

Nothing in this module fetches. It takes the assembled market state and returns
text, so the wording can be reviewed and tested without a network call.
"""

from __future__ import annotations

from .catalog import BY_SYMBOL, CYCLICAL_SECTORS, DEFENSIVE_SECTORS
from .providers import Quote


def _fmt_pct(v: float | None, digits: int = 1) -> str:
    if v is None:
        return "n/a"
    return f"{v:+.{digits}f}%"


def _dir(v: float | None, up: str = "higher", down: str = "lower",
         flat: str = "broadly flat") -> str:
    if v is None:
        return flat
    if v > 0.15:
        return up
    if v < -0.15:
        return down
    return flat


def _get(quotes: dict[str, Quote], symbol: str, horizon: str = "ytd") -> float | None:
    q = quotes.get(symbol)
    return q.changes.get(horizon) if q else None


def _trend_phrase(q: Quote) -> str:
    """Short-vs-long horizon comparison: is the recent move with or against trend?"""
    ytd, m1, w1 = q.changes.get("ytd"), q.changes.get("1m"), q.changes.get("1w")
    if ytd is None or m1 is None:
        return ""
    if ytd > 0 and m1 > 0:
        return "the last month has extended an already-positive year"
    if ytd > 0 and m1 < 0:
        return "the last month has given back part of the year's gain"
    if ytd < 0 and m1 > 0:
        return "the last month has clawed back some of the year's decline"
    if ytd < 0 and m1 < 0:
        return "the decline is accelerating rather than stabilising"
    return "the recent move is small relative to the year to date"


def instrument_note(q: Quote) -> str:
    """One sentence per instrument: level, direction, position in range, trend."""
    inst = BY_SYMBOL.get(q.symbol)
    if inst is None:
        return ""
    ytd = q.changes.get("ytd")
    pos = q.range_position

    where = ""
    if pos is not None:
        if pos > 0.95:
            where = " and is sitting on its 52-week high"
        elif pos > 0.8:
            where = " and trades in the top fifth of its 52-week range"
        elif pos < 0.05:
            where = " and is at a 52-week low"
        elif pos < 0.2:
            where = " and trades in the bottom fifth of its 52-week range"

    trend = _trend_phrase(q)
    tail = f"; {trend}" if trend else ""
    return (
        f"{inst.short} is {_fmt_pct(ytd)} year to date, {_fmt_pct(q.changes.get('1m'))} "
        f"over a month and {_fmt_pct(q.changes.get('1d'), 2)} on the day{where}{tail}."
    )


# -- panel-level commentary -------------------------------------------------


def equity_commentary(quotes: dict[str, Quote]) -> list[str]:
    us = {s: _get(quotes, s) for s in ("^GSPC", "^NDX", "^DJI", "^RUT")}
    asia = {s: _get(quotes, s) for s in ("^HSI", "^N225", "^KS11", "000001.SS", "^TWII")}
    eu = {s: _get(quotes, s) for s in ("^STOXX50E", "^FTSE")}
    live = {s: v for s, v in {**us, **asia, **eu}.items() if v is not None}
    if not live:
        return []

    out: list[str] = []
    spx = us.get("^GSPC")
    ndx = us.get("^NDX")
    rut = us.get("^RUT")
    dji = us.get("^DJI")

    if spx is not None:
        winners = sorted(live.items(), key=lambda kv: kv[1], reverse=True)
        best, worst = winners[0], winners[-1]
        out.append(
            f"The S&P 500 is {_fmt_pct(spx)} year to date. The widest gap in the "
            f"tracked set is {BY_SYMBOL[best[0]].short} at {_fmt_pct(best[1])} versus "
            f"{BY_SYMBOL[worst[0]].short} at {_fmt_pct(worst[1])} — a "
            f"{abs(best[1] - worst[1]):.0f}pp dispersion, which is what says whether "
            f"this is a global re-rating or a handful of local stories."
        )

    if spx is not None and ndx is not None:
        gap = ndx - spx
        if gap > 3:
            out.append(
                f"Nasdaq 100 leadership is intact: {_fmt_pct(ndx)} versus "
                f"{_fmt_pct(spx)} for the broad index. Narrow, long-duration "
                f"leadership like this makes the market more sensitive to the long "
                f"end of the curve than the index level alone suggests."
            )
        elif gap < -3:
            out.append(
                f"Growth leadership has stalled — Nasdaq 100 {_fmt_pct(ndx)} is "
                f"trailing the S&P 500's {_fmt_pct(spx)}. Rotation out of "
                f"long-duration equity usually shows up first in relative "
                f"performance, before the index level breaks."
            )

    if spx is not None and rut is not None:
        breadth_gap = rut - spx
        if breadth_gap < -5:
            out.append(
                f"Breadth is poor: Russell 2000 {_fmt_pct(rut)} lags the S&P 500 by "
                f"{abs(breadth_gap):.0f}pp. Small caps carry floating-rate debt and "
                f"domestic revenue, so this combination reads as tight financing "
                f"conditions rather than broad economic strength."
            )
        elif breadth_gap > 3:
            out.append(
                f"Breadth is improving — Russell 2000 {_fmt_pct(rut)} is ahead of the "
                f"S&P 500. Small-cap leadership normally requires both easier "
                f"financing expectations and a firmer domestic demand outlook."
            )

    asia_live = {s: v for s, v in asia.items() if v is not None}
    if asia_live and spx is not None:
        avg_asia = sum(asia_live.values()) / len(asia_live)
        if avg_asia - spx > 4:
            out.append(
                f"Asian equity is outperforming: average {_fmt_pct(avg_asia)} across "
                f"{len(asia_live)} tracked markets against {_fmt_pct(spx)} for the "
                f"S&P 500. Korea and Taiwan lead the global goods and semiconductor "
                f"cycle, so strength there tends to precede upgrades in US hardware "
                f"and industrial earnings."
            )
        elif spx - avg_asia > 4:
            out.append(
                f"Asian equity is lagging: average {_fmt_pct(avg_asia)} against the "
                f"S&P 500's {_fmt_pct(spx)}. Weak Korea/Taiwan tape combined with a "
                f"firm dollar is the classic signature of a slowing export and "
                f"semiconductor cycle."
            )

    eu_live = {s: v for s, v in eu.items() if v is not None}
    if eu_live and dji is not None:
        avg_eu = sum(eu_live.values()) / len(eu_live)
        out.append(
            f"Europe is {_fmt_pct(avg_eu)} year to date against the Dow's "
            f"{_fmt_pct(dji)}; the two are both cyclical, value-tilted baskets, so a "
            f"persistent gap between them is usually a currency and energy-cost "
            f"story rather than a growth story."
        )

    vix = quotes.get("^VIX")
    if vix and vix.price is not None:
        level = vix.price
        if level < 15:
            read = ("options markets are pricing calm; hedges are cheap and "
                    "positioning risk builds quietly in exactly this regime")
        elif level < 22:
            read = "implied volatility is around its long-run norm"
        elif level < 30:
            read = ("implied volatility is elevated — the market is paying up for "
                    "downside protection")
        else:
            read = ("implied volatility is in stress territory; moves of this size "
                    "force systematic strategies to cut equity exposure mechanically")
        out.append(f"VIX at {level:.1f} ({_fmt_pct(vix.changes.get('1w'))} on the week): {read}.")

    return out


def sector_commentary(quotes: dict[str, Quote], horizon: str = "ytd") -> list[str]:
    """
    What US sector leadership says about the growth and rates outlook.

    Sector dispersion carries information the index level cannot: the same +8%
    year looks entirely different if utilities and staples produced it than if
    industrials and financials did.
    """
    perf = {
        s: q.changes.get(horizon)
        for s, q in quotes.items()
        if BY_SYMBOL.get(s) and BY_SYMBOL[s].group.value == "sector"
        and q.changes.get(horizon) is not None
    }
    if len(perf) < 4:
        return []

    out: list[str] = []
    ranked = sorted(perf.items(), key=lambda kv: kv[1], reverse=True)
    best, worst = ranked[0], ranked[-1]
    out.append(
        f"Sector leadership: {BY_SYMBOL[best[0]].short} {_fmt_pct(best[1])} at the "
        f"top, {BY_SYMBOL[worst[0]].short} {_fmt_pct(worst[1])} at the bottom — a "
        f"{best[1] - worst[1]:.0f}pp spread across the eleven S&P sectors."
    )

    cyc = [v for s, v in perf.items() if s in CYCLICAL_SECTORS]
    dfn = [v for s, v in perf.items() if s in DEFENSIVE_SECTORS]
    if cyc and dfn:
        c, d = sum(cyc) / len(cyc), sum(dfn) / len(dfn)
        gap = c - d
        if gap > 4:
            out.append(
                f"Cyclicals are beating defensives by {gap:.0f}pp ({_fmt_pct(c)} vs "
                f"{_fmt_pct(d)}). That is the market voting for growth holding up; it "
                f"normally coincides with rising earnings revisions and a steeper "
                f"curve, and it tends to break before the macro data does."
            )
        elif gap < -4:
            out.append(
                f"Defensives are beating cyclicals by {abs(gap):.0f}pp ({_fmt_pct(d)} "
                f"vs {_fmt_pct(c)}). Staples, health care and utilities leading is the "
                f"classic late-cycle rotation — investors staying invested while "
                f"downgrading their growth expectations."
            )
        else:
            out.append(
                f"Cyclicals ({_fmt_pct(c)}) and defensives ({_fmt_pct(d)}) are running "
                f"together, so sector positioning is not yet expressing a directional "
                f"view on growth."
            )

    tech, util = perf.get("XLK"), perf.get("XLU")
    if tech is not None and util is not None and tech > 5 and util > 5:
        out.append(
            f"Technology {_fmt_pct(tech)} and utilities {_fmt_pct(util)} rising "
            f"together is the AI-capex signature rather than a normal cycle: the same "
            f"data-centre build-out drives semiconductor orders and the power demand "
            f"utilities are being re-rated on."
        )

    energy, wti = perf.get("XLE"), _get(quotes, "CL=F", horizon)
    if energy is not None and wti is not None and abs(energy - wti) > 20:
        out.append(
            f"Energy equities are {_fmt_pct(energy)} against crude's {_fmt_pct(wti)}. "
            f"Equities discount a long-run oil price, so a gap this wide means the "
            f"market is treating the move in crude as temporary."
        )

    fins, rates = perf.get("XLF"), perf.get("XLRE")
    if fins is not None and rates is not None and fins - rates > 10:
        out.append(
            f"Financials {_fmt_pct(fins)} versus real estate {_fmt_pct(rates)} is a "
            f"higher-for-longer trade: banks earn on a wider spread while the most "
            f"rate-sensitive sector in the index carries the refinancing cost."
        )
    return out


def commodity_commentary(quotes: dict[str, Quote]) -> list[str]:
    out: list[str] = []
    gold, silver = quotes.get("GC=F"), quotes.get("SI=F")
    wti, copper = quotes.get("CL=F"), quotes.get("HG=F")
    dxy = quotes.get("DX-Y.NYB")

    if gold and gold.price is not None:
        g = gold.changes.get("ytd")
        d = dxy.changes.get("ytd") if dxy else None
        base = (f"Gold at ${gold.price:,.0f}/oz is {_fmt_pct(g)} year to date and "
                f"{_dir(gold.changes.get('1m'))} over the past month")
        if d is not None and g is not None and g > 0 and d > 0:
            base += (". Gold rising alongside a stronger dollar is unusual and is the "
                     "signature of reserve-diversification and geopolitical demand "
                     "rather than a pure real-rate trade")
        elif d is not None and g is not None and g > 0 and d < 0:
            base += (". With the dollar weaker on the year, this is the textbook "
                     "combination — falling real rates and a softer dollar both lift "
                     "gold, so the move is corroborated rather than idiosyncratic")
        elif d is not None and g is not None and g < 0 and d > 0:
            base += (". Gold falling while the dollar firms is the standard "
                     "relationship working: a higher dollar and higher real yields "
                     "both raise the opportunity cost of holding a non-yielding asset")
        elif g is not None and g < 0:
            base += (". Weak gold with no offsetting dollar move usually means real "
                     "yields are doing the work — worth checking the 10-year before "
                     "reading it as fading haven demand")
        out.append(base + ".")

    if gold and silver and gold.price and silver.price:
        ratio = gold.price / silver.price
        if ratio > 85:
            read = ("an unusually wide ratio, which historically reflects defensive "
                    "demand for gold outpacing industrial demand for silver — a "
                    "risk-off tell inside the metals complex")
        elif ratio < 65:
            read = ("a narrow ratio, consistent with industrial and solar demand "
                    "pulling silver up faster than gold — the pro-cyclical read")
        else:
            read = "close to its long-run average, so the metals complex is sending no strong cyclical signal"
        out.append(f"The gold/silver ratio is {ratio:.0f}: {read}.")

    if wti and wti.price is not None:
        w = wti.changes.get("ytd")
        note = (f"WTI at ${wti.price:,.1f}/bbl is {_fmt_pct(w)} year to date, "
                f"{_fmt_pct(wti.changes.get('1m'))} over a month")
        if w is not None and w > 15:
            note += (". A move of this size feeds headline CPI within roughly one to "
                     "two months and squeezes transport, chemicals and airline "
                     "margins first; it also cuts the odds of near-term rate cuts")
        elif w is not None and w < -15:
            note += (". Crude this weak pulls headline inflation down and hands "
                     "consumers a real-income boost, but it is also a demand signal — "
                     "worth checking against copper before reading it as good news")
        out.append(note + ".")

    if copper and wti and copper.changes.get("ytd") is not None and wti.changes.get("ytd") is not None:
        c, w = copper.changes["ytd"], wti.changes["ytd"]
        if c > 5 and w < -5:
            out.append(
                f"Copper {_fmt_pct(c)} while crude is {_fmt_pct(w)}: the split says "
                f"the bid is electrification and grid/data-centre capex, not a broad "
                f"industrial upturn — energy demand would be rising too if it were."
            )
        elif c < -5 and w < -5:
            out.append(
                f"Copper {_fmt_pct(c)} and crude {_fmt_pct(w)} falling together is a "
                f"genuine global demand warning; both are physical-demand series with "
                f"no earnings-multiple component to explain the move away."
            )
        elif c > 5 and w > 5:
            out.append(
                f"Copper {_fmt_pct(c)} and crude {_fmt_pct(w)} rising together points "
                f"to a real activity upswing — and to goods-price inflation returning "
                f"through input costs over the next two quarters."
            )
    return out


def fx_crypto_commentary(quotes: dict[str, Quote]) -> list[str]:
    out: list[str] = []
    dxy, jpy, cny, krw = (quotes.get(s) for s in ("DX-Y.NYB", "USDJPY=X", "USDCNY=X", "USDKRW=X"))
    btc = quotes.get("BTC-USD")

    if dxy and dxy.price is not None:
        d = dxy.changes.get("ytd")
        note = (f"The dollar index at {dxy.price:,.1f} is {_fmt_pct(d)} year to date "
                f"and {_dir(dxy.changes.get('1m'))} over the month")
        if d is not None and d > 3:
            note += (". A stronger dollar tightens conditions everywhere outside the "
                     "US: it raises the cost of the roughly $13tn of dollar debt owed "
                     "offshore, compresses emerging-market equity returns in USD "
                     "terms, and mechanically trims the reported earnings of US "
                     "multinationals")
        elif d is not None and d < -3:
            note += (". A weaker dollar loosens global conditions, flatters US "
                     "multinational earnings on translation, and is normally a "
                     "tailwind for emerging-market equity and for commodities priced "
                     "in dollars")
        out.append(note + ".")

    if jpy and jpy.price is not None:
        j = jpy.changes.get("3m")
        if j is not None and j < -4:
            out.append(
                f"USD/JPY at {jpy.price:,.1f} is {_fmt_pct(j)} over three months — yen "
                f"strength of this speed is the mechanism that unwinds carry trades, "
                f"and it has historically hit high-beta equity and crypto before it "
                f"shows up anywhere else."
            )
        elif j is not None and j > 4:
            out.append(
                f"USD/JPY at {jpy.price:,.1f} is {_fmt_pct(j)} over three months. A "
                f"weaker yen supports Japanese exporter earnings and keeps the carry "
                f"trade funded, but it raises the odds of MoF intervention and of a "
                f"disorderly reversal."
            )

    if cny and cny.price is not None and cny.changes.get("ytd") is not None:
        c = cny.changes["ytd"]
        if abs(c) > 1.5:
            if c > 0:
                read = ("A weaker yuan exports disinflation through cheaper Chinese "
                        "goods, pressures Korean and Taiwanese exporters competing on "
                        "price, and raises the political temperature around tariffs")
            else:
                read = ("A stronger yuan lifts Chinese import purchasing power — "
                        "supportive for industrial commodities and for European "
                        "exporters into China — and relieves competitive pressure on "
                        "the rest of Asian manufacturing")
            out.append(
                f"USD/CNY at {cny.price:.2f} ({_fmt_pct(c)} YTD) means a "
                f"{'weaker' if c > 0 else 'stronger'} yuan. {read}."
            )

    if krw and krw.changes.get("ytd") is not None and abs(krw.changes["ytd"]) > 3:
        out.append(
            f"USD/KRW is {_fmt_pct(krw.changes['ytd'])} YTD; the won is a high-beta "
            f"read on the semiconductor cycle and tends to move before Korean export "
            f"data confirms the turn."
        )

    if btc and btc.price is not None:
        b = btc.changes.get("ytd")
        spx = _get(quotes, "^GSPC")
        note = (f"Bitcoin at ${btc.price:,.0f} is {_fmt_pct(b)} year to date, "
                f"{_fmt_pct(btc.changes.get('1m'))} over a month")
        if b is not None and spx is not None:
            if b > spx + 10:
                note += (". Crypto outrunning equity is the cleanest available read on "
                         "excess liquidity and speculative appetite — it is the "
                         "highest-beta leg of the same risk trade, and it usually "
                         "turns down first")
            elif b < spx - 10:
                note += (". Crypto lagging equity while indices hold up suggests the "
                         "marginal speculative dollar has already been withdrawn, "
                         "which typically precedes weaker breadth in equities")
        out.append(note + ".")
    return out


def curve_commentary(curve: dict) -> list[str]:
    pts = {p["label"]: p for p in curve.get("points", [])}
    out: list[str] = []
    if not pts:
        return out

    def spread(a: str, b: str, key: str = "current") -> float | None:
        pa, pb = pts.get(a), pts.get(b)
        if not pa or not pb or pa.get(key) is None or pb.get(key) is None:
            return None
        return pa[key] - pb[key]

    s10_2 = spread("10Y", "2Y")
    s10_3m = spread("10Y", "3M")
    s10_2_prev = spread("10Y", "2Y", "month_ago")

    if s10_2 is not None:
        shape = ("inverted" if s10_2 < 0 else "flat" if s10_2 < 0.25 else "positively sloped")
        move = ""
        if s10_2_prev is not None:
            delta = (s10_2 - s10_2_prev) * 100
            if delta > 5:
                move = (f", and it has steepened {delta:.0f}bp in a month")
            elif delta < -5:
                move = (f", and it has flattened {abs(delta):.0f}bp in a month")
        out.append(
            f"The 10Y–2Y spread is {s10_2 * 100:+.0f}bp, so the curve is {shape}{move}."
        )
        if s10_2 < 0:
            out.append(
                "An inverted curve has preceded every US recession since 1970, but the "
                "signal fires 6–18 months early and the recession has historically "
                "started only after the curve re-steepens back through zero — so the "
                "direction of travel matters more than the level."
            )
        elif s10_2_prev is not None and s10_2 > 0 and s10_2_prev < 0:
            out.append(
                "The curve has just dis-inverted. Bull steepening (front end falling "
                "faster) is the market pricing cuts into a slowdown; bear steepening "
                "(long end rising) is a term-premium and fiscal-supply story. Check "
                "which end moved before reading it as an all-clear."
            )

    ten = pts.get("10Y")
    if ten and ten.get("current") is not None:
        parts = [f"The 10-year yield is {ten['current']:.2f}%"]
        for key, label in (("month_ago", "a month ago"), ("year_ago", "a year ago")):
            if ten.get(key) is not None:
                bp = (ten["current"] - ten[key]) * 100
                parts.append(f"{bp:+.0f}bp versus {label}")
        out.append(
            ", ".join(parts) +
            ". The 10-year is the discount rate for every long-duration asset, so "
            "moves here transmit directly into equity multiples, mortgage rates and "
            "the affordability of corporate refinancing."
        )

    if s10_3m is not None and s10_2 is not None and s10_3m < 0 <= s10_2:
        out.append(
            f"Note the disagreement between the two standard measures: 10Y–3M is "
            f"{s10_3m * 100:+.0f}bp while 10Y–2Y is {s10_2 * 100:+.0f}bp. The 3-month "
            f"leg is anchored to the current policy rate, so this combination says the "
            f"market expects cuts that have not yet been delivered."
        )

    front = pts.get("3M") or pts.get("1M")
    if front and front.get("current") is not None and front.get("year_ago") is not None:
        bp = (front["current"] - front["year_ago"]) * 100
        if abs(bp) > 25:
            out.append(
                f"The front end ({front['label']}) is {bp:+.0f}bp over twelve months, "
                f"which is where actual policy shows up. Cash yielding "
                f"{front['current']:.2f}% is the hurdle rate every other asset has to "
                f"clear."
            )
    return out


def fear_greed_commentary(fg: dict, quotes: dict[str, Quote]) -> list[str]:
    score = fg.get("score")
    if score is None:
        return []
    out: list[str] = []
    rating = (fg.get("rating") or "").replace("_", " ")

    prev_m = fg.get("previous_1_month")
    prev_y = fg.get("previous_1_year")
    move = ""
    if prev_m is not None:
        delta = score - prev_m
        move = (f", {abs(delta):.0f} points {'above' if delta > 0 else 'below'} where "
                f"it sat a month ago")
    out.append(f"CNN's Fear & Greed index reads {score:.0f} ({rating}){move}.")

    if score <= 25:
        out.append(
            "Extreme fear is a contrarian positive on a multi-week horizon: it means "
            "hedging is already in place and weak hands have largely sold, so the "
            "marginal seller is scarce. It is not a timing signal — sentiment can stay "
            "depressed for months while prices grind lower."
        )
    elif score <= 45:
        out.append(
            "Fear-side readings mean positioning is defensive; upside surprises get "
            "amplified because there is dry powder to redeploy."
        )
    elif score < 55:
        out.append("A neutral reading gives no positioning edge in either direction.")
    elif score < 75:
        out.append(
            "Greed-side readings mean the market is already long the good news; "
            "returns from here depend on earnings delivery rather than on multiple "
            "expansion."
        )
    else:
        out.append(
            "Extreme greed marks crowded positioning and thin hedges. It does not "
            "predict a top, but it does mean any negative catalyst lands on a market "
            "with no cushion, which is why drawdowns from these levels are faster."
        )

    spx = quotes.get("^GSPC")
    if spx and spx.changes.get("1m") is not None and prev_m is not None:
        px, sent = spx.changes["1m"], score - prev_m
        if px > 1 and sent < -5:
            out.append(
                f"Watch the divergence: the S&P 500 is {_fmt_pct(px)} over the month "
                f"while sentiment has fallen {abs(sent):.0f} points. Prices holding up "
                f"on deteriorating internals — breadth, put/call, junk demand — is a "
                f"classic late-rally pattern."
            )
        elif px < -1 and sent > 5:
            out.append(
                f"Sentiment is improving ({sent:+.0f} points) even though the S&P 500 "
                f"is {_fmt_pct(px)} on the month, which usually means the internals "
                f"(breadth and credit) are repairing before the index does."
            )

    weakest = sorted(
        (c for c in fg.get("components", []) if c.get("score") is not None),
        key=lambda c: c["score"],
    )
    if weakest:
        lo, hi = weakest[0], weakest[-1]
        out.append(
            f"The index is being dragged by {lo['name'].lower()} ({lo['score']:.0f}) "
            f"and supported by {hi['name'].lower()} ({hi['score']:.0f}) — "
            f"{lo['detail'].lower()} versus {hi['detail'].lower()}."
        )
    return out


# -- news implications ------------------------------------------------------

# Keyword -> (what it touches, how it usually transmits). Matched against the
# headline text; a headline can hit several rules and we keep the strongest few.
IMPLICATION_RULES: list[tuple[tuple[str, ...], str, str]] = [
    (("rate cut", "cuts rates", "lower rates", "dovish", "easing"),
     "Rates",
     "Lower policy rates compress the front end first, steepen the curve, and lift "
     "long-duration equity and gold; banks' net interest margins compress."),
    (("rate hike", "hikes rates", "hawkish", "tightening"),
     "Rates",
     "Tighter policy lifts the front end, strengthens the dollar, and pressures "
     "high-multiple equity, small caps and emerging markets first."),
    (("inflation", "cpi", "ppi", "price index"),
     "Inflation",
     "Inflation prints set the path of policy: an upside surprise pushes real yields "
     "up and equity multiples down, a downside surprise does the reverse."),
    (("tariff", "export control", "sanction", "trade war", "quota"),
     "Trade & supply chain",
     "Trade restrictions raise input costs and re-route supply chains: importers and "
     "manufacturers with thin margins absorb the hit first, and the affected "
     "components tend to see inventory build ahead of implementation dates."),
    (("semiconductor", "chip", "foundry", "tsmc", "nvidia", "asml"),
     "Semiconductors",
     "Semis sit at the head of the hardware supply chain — orders there lead capex, "
     "Korean and Taiwanese exports, and industrial earnings by one to two quarters."),
    (("oil", "opec", "crude", "refinery", "pipeline"),
     "Energy",
     "Crude feeds headline CPI within one to two months and directly compresses "
     "transport, chemical and airline margins while lifting energy-sector earnings."),
    (("layoff", "job cuts", "unemployment", "payroll", "jobless"),
     "Labour",
     "Labour data drives both the consumption outlook and the policy path; rising "
     "claims soften wage pressure but tighten credit conditions for consumer lenders."),
    (("bank", "credit", "default", "bankruptcy", "spread"),
     "Credit",
     "Credit stress transmits faster than equity stress: widening spreads raise "
     "refinancing costs for leveraged borrowers and typically precede equity drawdowns."),
    (("earnings", "guidance", "profit warning", "revenue"),
     "Earnings",
     "Guidance changes reset the denominator of every valuation multiple, and tend to "
     "cluster through a supply chain rather than stopping at one company."),
    (("china", "beijing", "pboc", "yuan"),
     "China",
     "Chinese demand and policy set the marginal bid for industrial commodities and "
     "the earnings of European luxury, autos and machinery exporters."),
    (("war", "strike", "conflict", "missile", "attack", "blockade"),
     "Geopolitics",
     "Geopolitical escalation bids gold, oil and the dollar together, widens shipping "
     "and insurance costs, and lengthens delivery times through affected corridors."),
    (("ai", "data center", "data centre", "cloud capex"),
     "AI capex",
     "AI capex is currently the single largest swing factor in US equity earnings "
     "growth, and it pulls through power demand, copper, cooling and construction."),
]


def news_implication(title: str, summary: str = "") -> tuple[str, str] | None:
    """Match a headline to its transmission channel. Returns (channel, implication)."""
    text = f"{title} {summary}".lower()
    for keys, channel, implication in IMPLICATION_RULES:
        if any(k in text for k in keys):
            return channel, implication
    return None


def annotate_news(items: list[dict]) -> list[dict]:
    out = []
    for it in items:
        hit = news_implication(it.get("title", ""), it.get("summary", ""))
        enriched = dict(it)
        enriched["channel"] = hit[0] if hit else "Market"
        enriched["implication"] = hit[1] if hit else (
            "General market news — no direct, mechanical transmission channel "
            "identified; treat as context rather than as a driver."
        )
        out.append(enriched)
    return out


# -- the top-of-page synthesis ---------------------------------------------


def top_summary(quotes: dict[str, Quote], curve: dict, fg: dict) -> list[str]:
    """Three or four sentences tying the whole tape together."""
    out: list[str] = []
    spx = _get(quotes, "^GSPC")
    dxy = _get(quotes, "DX-Y.NYB")
    gold = _get(quotes, "GC=F")
    btc = _get(quotes, "BTC-USD")
    vix = quotes.get("^VIX")

    pts = {p["label"]: p for p in curve.get("points", [])}
    ten = pts.get("10Y", {}).get("current")
    ten_prev = pts.get("10Y", {}).get("month_ago")

    risk_on = sum(1 for v in (spx, btc) if v is not None and v > 0)
    defensive = (gold is not None and gold > 5) or (vix and vix.price and vix.price > 22)

    if spx is not None:
        lead = f"Equities are {_dir(spx, 'up', 'down')} on the year (S&P 500 {_fmt_pct(spx)})"
        if ten is not None and ten_prev is not None:
            bp = (ten - ten_prev) * 100
            lead += (f" with the 10-year at {ten:.2f}% ({bp:+.0f}bp in a month)")
        out.append(lead + ".")

    if risk_on == 2 and not defensive:
        out.append(
            "Risk assets and the safe-haven complex are pointing the same way: this is "
            "a liquidity-led tape, and it is most vulnerable to a rise in real yields "
            "rather than to a growth disappointment."
        )
    elif defensive and spx is not None and spx > 0:
        out.append(
            "Equities and defensives are both bid — gold and volatility rising "
            "alongside stocks means investors are buying the upside and the insurance "
            "at once, which is characteristic of a market that does not trust its own "
            "rally."
        )
    elif spx is not None and spx < 0:
        out.append(
            "The equity tape is negative on the year; the question is whether credit "
            "and the front end are confirming, which is what separates a de-rating "
            "from a genuine downturn."
        )

    if dxy is not None and gold is not None:
        if dxy > 2 and gold > 5:
            out.append(
                "The dollar and gold are rising together — an unusual pair that "
                "normally reflects reserve diversification and geopolitical hedging "
                "rather than a rates story, and it tightens conditions for every "
                "dollar borrower outside the US."
            )
        elif dxy < -2:
            out.append(
                "A softer dollar is doing quiet work across the tape: it lifts "
                "commodity prices in USD terms, flatters US multinational earnings on "
                "translation, and eases funding stress in emerging markets."
            )

    score = fg.get("score")
    if score is not None and spx is not None:
        out.append(
            f"Sentiment (Fear & Greed {score:.0f}) sits {'below' if score < 50 else 'above'} "
            f"neutral against a {_fmt_pct(spx)} year for the S&P 500, so positioning "
            f"is {'a cushion' if score < 45 else 'a risk' if score > 70 else 'roughly balanced'} "
            f"rather than a tailwind."
        )
    return out
