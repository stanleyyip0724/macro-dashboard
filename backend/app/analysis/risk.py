"""
Composite systemic-risk index (0-100).

Design decisions worth understanding before you tune the weights:

1. RISK IS NOT THE INVERSE OF GROWTH. A slow-growing economy with clean
   balance sheets and tight spreads is low-risk. A fast-growing economy with
   an inverted curve, blowing-out credit spreads and tightening bank standards
   is high-risk. So the risk score is built from its own weighted subset of
   indicators (`risk_weight > 0`), not from the cycle composites.

2. NON-LINEAR MAPPING. Risk does not scale linearly with a z-score -- the
   move from +2sd to +3sd matters far more than 0sd to +1sd. Each input is
   pushed through a logistic so the score saturates at the extremes:

       badness  b = -polarity * z        (positive = bad)
       sub      = 100 / (1 + exp(-STEEPNESS * (b - MIDPOINT)))

   With MIDPOINT=1.0 and STEEPNESS=1.3: b=0 -> 21, b=1 -> 50, b=2 -> 79,
   b=3 -> 93. A perfectly average economy scores about 21, not 50, which is
   the behaviour you want from a *risk* gauge.

3. PILLARS. A single number hides where the risk lives. Every input is mapped
   to a pillar (Growth, Labour, Inflation & Policy, Credit & Financial,
   Housing) so the UI can show that a 55 driven entirely by Credit is a very
   different situation from a 55 spread evenly.

4. TRIGGER BONUS. Rule-based signals (Sahm, curve inversion, CFNAI) do not
   average well -- their information is in the crossing, not the magnitude.
   They are applied as a bounded additive premium on top of the weighted base.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from ..indicators import Indicator
from ..transforms import SeriesResult

MIDPOINT = 1.0
STEEPNESS = 1.3
MAX_TRIGGER_BONUS = 18.0


class RiskBand(str, Enum):
    LOW = "Low"
    MODERATE = "Moderate"
    ELEVATED = "Elevated"
    HIGH = "High"
    SEVERE = "Severe"


BANDS: list[tuple[float, RiskBand, str]] = [
    (20, RiskBand.LOW, "Conditions are benign across growth, credit and labour."),
    (40, RiskBand.MODERATE, "Normal cyclical risk. Some indicators soft, none critical."),
    (60, RiskBand.ELEVATED, "Multiple stress indicators are meaningfully above normal."),
    (80, RiskBand.HIGH, "Broad-based deterioration consistent with a pre-recessionary regime."),
    (101, RiskBand.SEVERE, "Acute systemic stress across activity, credit and labour."),
]


class Pillar(str, Enum):
    GROWTH = "Growth"
    LABOUR = "Labour"
    INFLATION = "Inflation & Policy"
    CREDIT = "Credit & Financial"
    HOUSING = "Housing"


# Tag -> pillar, first match wins. Ordering matters: 'stress' and 'credit'
# outrank 'labour' for a series tagged with both.
TAG_PILLARS: list[tuple[str, Pillar]] = [
    ("stress", Pillar.CREDIT),
    ("credit", Pillar.CREDIT),
    ("yield-curve", Pillar.CREDIT),
    ("leverage", Pillar.CREDIT),
    ("household", Pillar.CREDIT),
    ("inflation", Pillar.INFLATION),
    ("policy", Pillar.INFLATION),
    ("monetary", Pillar.INFLATION),
    ("fed-target", Pillar.INFLATION),
    ("housing", Pillar.HOUSING),
    ("labour", Pillar.LABOUR),
    ("recession", Pillar.GROWTH),
]


def pillar_for(ind: Indicator) -> Pillar:
    for tag, pillar in TAG_PILLARS:
        if tag in ind.tags:
            return pillar
    return Pillar.GROWTH


@dataclass
class RiskContribution:
    series_id: str
    name: str
    short: str
    pillar: str
    weight: float
    zscore: float
    badness: float
    subscore: float
    contribution: float     # weighted share of the base score
    latest_value: float | None
    latest_date: str | None
    unit: str


@dataclass
class RiskTrigger:
    name: str
    fired: bool
    value: float | None
    threshold: str
    points: float
    detail: str


@dataclass
class RiskAssessment:
    score: float
    band: str
    band_description: str
    base_score: float
    trigger_bonus: float
    coverage: float
    pillars: dict[str, float]
    pillar_weights: dict[str, float]
    contributions: list[RiskContribution]
    triggers: list[RiskTrigger]
    top_drivers: list[str] = field(default_factory=list)


def _subscore(badness: float) -> float:
    return 100.0 / (1.0 + math.exp(-STEEPNESS * (badness - MIDPOINT)))


def _band(score: float) -> tuple[RiskBand, str]:
    for ceiling, band, desc in BANDS:
        if score < ceiling:
            return band, desc
    return RiskBand.SEVERE, BANDS[-1][2]


def _triggers(results: dict[str, SeriesResult]) -> list[RiskTrigger]:
    def raw(sid: str) -> float | None:
        r = results.get(sid)
        return r.latest_raw if r else None

    sahm = raw("SAHMREALTIME")
    t10y3m = raw("T10Y3M")
    t10y2y = raw("T10Y2Y")
    cfnai = raw("CFNAIMA3")
    hy = raw("BAMLH0A0HYM2")
    sloos = raw("DRTSCILM")
    recprob = raw("RECPROUSM156N")

    return [
        RiskTrigger(
            "Sahm Rule triggered", bool(sahm is not None and sahm >= 0.50),
            sahm, ">= 0.50pp", 6.0,
            "Real-time unemployment gap at a level that has always accompanied recession.",
        ),
        RiskTrigger(
            "10Y-3M curve inverted", bool(t10y3m is not None and t10y3m < 0),
            t10y3m, "< 0pp", 4.0,
            "The NY Fed's preferred recession predictor. Leads by 6-18 months.",
        ),
        RiskTrigger(
            "10Y-2Y curve inverted", bool(t10y2y is not None and t10y2y < 0),
            t10y2y, "< 0pp", 2.0,
            "Confirms the inversion is across the curve, not a single tenor.",
        ),
        RiskTrigger(
            "CFNAI below recession threshold", bool(cfnai is not None and cfnai < -0.70),
            cfnai, "< -0.70", 5.0,
            "Broad activity index at the Chicago Fed's published recession-onset level.",
        ),
        RiskTrigger(
            "High-yield spreads stressed", bool(hy is not None and hy > 6.0),
            hy, "> 6.0pp", 4.0,
            "Credit markets are pricing a materially higher default cycle.",
        ),
        RiskTrigger(
            "Banks tightening sharply", bool(sloos is not None and sloos > 20.0),
            sloos, "> 20 net %", 3.0,
            "SLOOS net tightening at levels that have preceded every recession since 1990.",
        ),
        RiskTrigger(
            "Model recession probability elevated",
            bool(recprob is not None and recprob > 20.0),
            recprob, "> 20%", 4.0,
            "Chauvet-Piger smoothed probability well above its expansion baseline.",
        ),
    ]


def score(results: dict[str, SeriesResult]) -> RiskAssessment:
    contributions: list[RiskContribution] = []
    total_weight = 0.0
    available_weight = 0.0

    for r in results.values():
        ind = r.indicator
        if ind.risk_weight <= 0:
            continue
        total_weight += ind.risk_weight
        z = r.latest_z
        if z is None:
            continue
        available_weight += ind.risk_weight

        badness = -ind.polarity * z
        sub = _subscore(badness)
        contributions.append(
            RiskContribution(
                series_id=ind.series_id,
                name=ind.name,
                short=ind.short,
                pillar=pillar_for(ind).value,
                weight=ind.risk_weight,
                zscore=round(z, 3),
                badness=round(badness, 3),
                subscore=round(sub, 2),
                contribution=0.0,   # filled below once we know the denominator
                latest_value=(
                    None if r.latest_value is None else round(r.latest_value, 3)
                ),
                latest_date=r.latest_date,
                unit=ind.unit,
            )
        )

    if not contributions or available_weight == 0:
        return RiskAssessment(
            score=0.0, band=RiskBand.LOW.value,
            band_description="Insufficient data to score risk.",
            base_score=0.0, trigger_bonus=0.0, coverage=0.0,
            pillars={}, pillar_weights={}, contributions=[], triggers=[],
        )

    base = sum(c.subscore * c.weight for c in contributions) / available_weight
    for c in contributions:
        c.contribution = round(c.subscore * c.weight / available_weight, 3)

    # Pillar scores: weighted average within each pillar.
    pillars: dict[str, float] = {}
    pillar_weights: dict[str, float] = {}
    for p in Pillar:
        members = [c for c in contributions if c.pillar == p.value]
        if not members:
            continue
        w = sum(c.weight for c in members)
        pillars[p.value] = round(sum(c.subscore * c.weight for c in members) / w, 1)
        pillar_weights[p.value] = round(w, 2)

    triggers = _triggers(results)
    bonus = min(MAX_TRIGGER_BONUS, sum(t.points for t in triggers if t.fired))

    final = max(0.0, min(100.0, base + bonus))
    band, band_desc = _band(final)

    ranked = sorted(contributions, key=lambda c: c.contribution, reverse=True)
    top = [
        f"{c.short}: {c.subscore:.0f}/100 ({c.zscore:+.1f}sd)"
        for c in ranked[:5]
    ]

    return RiskAssessment(
        score=round(final, 1),
        band=band.value,
        band_description=band_desc,
        base_score=round(base, 1),
        trigger_bonus=round(bonus, 1),
        coverage=round(available_weight / total_weight, 3),
        pillars=pillars,
        pillar_weights=pillar_weights,
        contributions=ranked,
        triggers=triggers,
        top_drivers=top,
    )
