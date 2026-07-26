"""
Business-cycle phase classification.

The model is a two-axis "cycle clock". Every phase is a combination of where
growth IS and which way it is MOVING:

                       momentum > 0        momentum < 0
    level > 0     |    EXPANSION      |    PEAK           |
    level < 0     |    RECOVERY       |    CONTRACTION    |
                                            (aka TROUGH when momentum turns)

  level    = a blend of the coincident composite (where we are now) and the
             leading composite (where we are heading), in z-space.
             Weighted 60/40 toward coincident: leading indicators are noisy
             and produce false positives if trusted too heavily on level.

  momentum = the 3-month change in that blend. This is what separates a Peak
             from an Expansion -- both have a healthy LEVEL, but a Peak is
             rolling over.

Two refinements on top of the raw quadrant:

  * BREADTH. A composite can be dragged negative by one collapsing sector.
    `CFNAIDIFF` and the share of members with a negative signal tell us
    whether weakness is broad. Narrow weakness lowers confidence.

  * HARD RULES. The Sahm gap and the CFNAI 3-month average have documented,
    non-negotiable recession thresholds. When they fire they override the
    quadrant, because "the composite says Expansion" is not a position worth
    defending against a triggered Sahm rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import pandas as pd

from ..indicators import Klass
from ..transforms import SeriesResult, composite, slope


# Phase boundaries. These are calibrated against NBER recession dates by
# scripts/backtest.py -- do not adjust them by intuition, re-run the sweep.
#
# NEUTRAL_LEVEL: dead zone around zero. Without it the classifier treats 0.000
#   as a hard boundary, so a growth level of -0.09sd -- statistically
#   indistinguishable from trend -- flips the call to a full recession warning.
#
# CONTRACTION_LEVEL: how far below trend the economy must be before the model
#   will say "Contraction". Calibrated at -0.70sd, where a threshold sweep over
#   1993-2026 maximises usable signal: precision 70.6% at unchanged 85.7%
#   recall, versus 23.8% precision at -0.15sd. Every NBER recession month in
#   the window had a composite level at or below -0.70sd (the recession-month
#   maximum was exactly -0.70), while only ~5% of expansion months did.
#   That this lands on the Chicago Fed's own published CFNAI recession
#   threshold of -0.70 is independent corroboration, not a coincidence we
#   engineered -- the sweep was run blind to it.
#
#   The band between CONTRACTION_LEVEL and NEUTRAL_LEVEL is a SLOWDOWN, not a
#   recession, and is classified as Peak (deteriorating) or Recovery
#   (improving). Conflating that band with Contraction was the single largest
#   source of false alarms in the backtest.
NEUTRAL_LEVEL = 0.15
NEUTRAL_MOMENTUM = 0.05
CONTRACTION_LEVEL = -0.70
TROUGH_LEVEL = -1.00


class Phase(str, Enum):
    EXPANSION = "Expansion"
    PEAK = "Peak"
    CONTRACTION = "Contraction"
    TROUGH = "Trough"
    RECOVERY = "Recovery"


PHASE_DESCRIPTIONS: dict[Phase, str] = {
    Phase.EXPANSION: (
        "Activity is above trend and still improving. Slack is being absorbed, "
        "employment is growing, and credit is available."
    ),
    Phase.PEAK: (
        "Activity is still above trend but momentum has turned negative. "
        "This is the late-cycle window: strong current data, deteriorating "
        "forward-looking data."
    ),
    Phase.CONTRACTION: (
        "Activity is below trend and still falling. Growth, labour and credit "
        "indicators are deteriorating together."
    ),
    Phase.TROUGH: (
        "Activity is deeply below trend but the rate of decline has stopped "
        "worsening. Historically the highest-uncertainty phase to call in "
        "real time."
    ),
    Phase.RECOVERY: (
        "Activity is still below trend but improving. Leading indicators have "
        "turned up ahead of the coincident data."
    ),
}


@dataclass
class PhaseSignal:
    name: str
    fired: bool
    value: float | None
    threshold: float
    detail: str


@dataclass
class CycleAssessment:
    phase: Phase
    description: str
    confidence: float                 # 0-1
    growth_level: float | None
    growth_momentum: float | None
    inflation_pressure: float | None
    breadth: float | None             # share of members with a positive signal
    composites: dict[str, float | None]
    coverage: dict[str, dict]
    history: list[dict] = field(default_factory=list)
    hard_signals: list[PhaseSignal] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)


def _latest(s: pd.Series) -> float | None:
    s = s.dropna()
    return float(s.iloc[-1]) if len(s) else None


def _at(s: pd.Series, when) -> float | None:
    """
    Value of a composite as of a given month, falling back to the most recent
    prior month. Composites can end on different dates (the lagging block is
    gated by quarterly releases), and comparing a June coincident reading
    against an April lagging reading would be a silent apples-to-oranges bug.
    """
    s = s.dropna()
    if not len(s):
        return None
    if when is None:
        return float(s.iloc[-1])
    usable = s.loc[:when]
    return float(usable.iloc[-1]) if len(usable) else None


def quadrant(level: float, momentum: float) -> Phase:
    """
    Map a (level, momentum) pair to a cycle phase, respecting the dead zones.

    Shared by the live classification and the historical trail so the two can
    never disagree about what a given point on the clock means.
    """
    improving = momentum >= NEUTRAL_MOMENTUM

    if level < CONTRACTION_LEVEL:
        # Deeply below trend -- the genuine recession zone.
        if improving:
            return Phase.TROUGH if level < TROUGH_LEVEL else Phase.RECOVERY
        return Phase.CONTRACTION

    if level > NEUTRAL_LEVEL:
        # Clearly above trend.
        return Phase.EXPANSION if momentum >= -NEUTRAL_MOMENTUM else Phase.PEAK

    # The slowdown band: below trend but not at recessionary depth, or inside
    # the neutral dead zone. Direction decides, and the worst call available
    # here is Peak -- reaching this band is not evidence of a recession.
    if improving:
        return Phase.RECOVERY if level < -NEUTRAL_LEVEL else Phase.EXPANSION
    return Phase.PEAK


def _breadth(results: list[SeriesResult]) -> float | None:
    vals = [r.latest_signal for r in results if r.latest_signal is not None]
    if not vals:
        return None
    return sum(1 for v in vals if v > 0) / len(vals)


def classify(results: dict[str, SeriesResult]) -> CycleAssessment:
    by_class: dict[Klass, list[SeriesResult]] = {k: [] for k in Klass}
    for r in results.values():
        by_class[r.indicator.klass].append(r)

    lead_s, lead_meta = composite(by_class[Klass.LEADING])
    coin_s, coin_meta = composite(by_class[Klass.COINCIDENT])
    lag_s, lag_meta = composite(by_class[Klass.LAGGING])
    fin_s, fin_meta = composite(by_class[Klass.FINANCIAL])

    # The growth blend, weighted 60/40 toward coincident.
    #
    # Built on the months where BOTH composites exist. An `add(fill_value=0)`
    # here would be a real error, not a convenience: a month where the leading
    # composite is absent would be scored as leading == 0.0 ("exactly trend")
    # rather than "unknown", pulling the blend toward zero precisely when data
    # is thinnest.
    parts = pd.DataFrame({"coincident": coin_s, "lead": lead_s}).dropna()
    if len(parts):
        blend_s = 0.6 * parts["coincident"] + 0.4 * parts["lead"]
    elif coin_s.dropna().size:
        blend_s = coin_s.dropna()
    elif lead_s.dropna().size:
        blend_s = lead_s.dropna()
    else:
        blend_s = pd.Series(dtype="float64")

    level = _latest(blend_s)
    momentum = slope(blend_s, 3)

    # Read every composite as of the blend's own date so the reported numbers
    # describe one moment in time rather than four different ones.
    as_of = blend_s.index[-1] if len(blend_s) else None
    lead, coin, lag, fin = (
        _at(s, as_of) for s in (lead_s, coin_s, lag_s, fin_s)
    )

    # Lagging composite is polarity-adjusted so positive = benign. Flip it to
    # express "price and policy pressure", which is what the clock reads.
    inflation_pressure = None if lag is None else -lag

    breadth = _breadth(by_class[Klass.LEADING] + by_class[Klass.COINCIDENT])

    # -- hard rules ------------------------------------------------------
    sahm = results.get("SAHMREALTIME")
    cfnai = results.get("CFNAIMA3")
    diff = results.get("CFNAIDIFF")

    hard: list[PhaseSignal] = []
    sahm_v = sahm.latest_raw if sahm else None
    hard.append(PhaseSignal(
        "Sahm Rule", bool(sahm_v is not None and sahm_v >= 0.50), sahm_v, 0.50,
        "3m avg unemployment minus its trailing 12m low >= 0.50pp. "
        "Has coincided with the start of every US recession since 1960.",
    ))
    cfnai_v = cfnai.latest_raw if cfnai else None
    hard.append(PhaseSignal(
        "CFNAI 3M Average", bool(cfnai_v is not None and cfnai_v < -0.70), cfnai_v, -0.70,
        "Chicago Fed's published recession-onset threshold for the 85-indicator "
        "activity index.",
    ))
    diff_v = diff.latest_raw if diff else None
    hard.append(PhaseSignal(
        "CFNAI Diffusion", bool(diff_v is not None and diff_v < -0.35), diff_v, -0.35,
        "Weakness is broad-based across components, not concentrated in one sector.",
    ))

    fired = [h for h in hard if h.fired]

    # -- quadrant --------------------------------------------------------
    rationale: list[str] = []

    if level is None or momentum is None:
        phase = Phase.EXPANSION
        confidence = 0.0
        rationale.append("Insufficient data to classify; defaulting to Expansion.")
    else:
        phase = quadrant(level, momentum)
        in_band = abs(level) <= NEUTRAL_LEVEL

        position = (
            "essentially at trend" if in_band
            else "above trend" if level > 0
            else "below trend"
        )
        rationale.append(
            f"Growth level {level:+.2f}sd ({position}) with 3-month momentum "
            f"{momentum:+.2f}sd "
            f"({'improving' if momentum >= 0 else 'deteriorating'})."
        )
        if in_band:
            rationale.append(
                f"Level is inside the +/-{NEUTRAL_LEVEL:.2f}sd neutral band, so the "
                f"call rests on momentum rather than on the level. Treat the "
                f"phase as provisional."
            )

        # Hard rules override an over-optimistic quadrant call.
        if len(fired) >= 2 and phase in (Phase.EXPANSION, Phase.PEAK):
            phase = Phase.CONTRACTION
            rationale.append(
                "Overridden to Contraction: "
                + ", ".join(h.name for h in fired)
                + " triggered simultaneously, which outranks the composite quadrant."
            )
        elif len(fired) == 1 and phase is Phase.EXPANSION:
            phase = Phase.PEAK
            rationale.append(
                f"Downgraded from Expansion to Peak: {fired[0].name} has triggered."
            )

    # -- confidence ------------------------------------------------------
    # Confident when the reading is far from the axes, breadth agrees with the
    # sign of the level, and coverage is high.
    if level is None or momentum is None:
        confidence = 0.0
    else:
        distance = min(1.0, (abs(level) / 1.5) * 0.5 + (abs(momentum) / 0.6) * 0.5)
        cov = (coin_meta["coverage"] + lead_meta["coverage"]) / 2
        if breadth is None:
            agreement = 0.5
        else:
            # breadth 0.5 = maximum ambiguity; 0 or 1 = full agreement
            agreement = abs(breadth - 0.5) * 2
            if (breadth > 0.5) != (level >= 0):
                agreement *= 0.4  # breadth contradicts the level
        confidence = round(
            max(0.05, min(0.98, 0.45 * distance + 0.30 * agreement + 0.25 * cov)), 3
        )

    if breadth is not None:
        rationale.append(
            f"{breadth:.0%} of leading and coincident members are sending a "
            f"positive signal."
        )
    if inflation_pressure is not None:
        stance = (
            "elevated" if inflation_pressure > 0.5
            else "contained" if inflation_pressure < -0.5
            else "near neutral"
        )
        rationale.append(
            f"Lagging (inflation/policy) pressure {inflation_pressure:+.2f}sd -- {stance}."
        )
    if fin is not None:
        rationale.append(
            f"Financial conditions composite {fin:+.2f}sd "
            f"({'supportive' if fin > 0 else 'restrictive'})."
        )

    history = _history(blend_s, months=60)

    return CycleAssessment(
        phase=phase,
        description=PHASE_DESCRIPTIONS[phase],
        confidence=confidence,
        growth_level=level,
        growth_momentum=momentum,
        inflation_pressure=inflation_pressure,
        breadth=breadth,
        composites={
            "leading": lead, "coincident": coin,
            "lagging": lag, "financial": fin,
            "growth_blend": level,
        },
        coverage={
            "leading": lead_meta, "coincident": coin_meta,
            "lagging": lag_meta, "financial": fin_meta,
        },
        history=history,
        hard_signals=hard,
        rationale=rationale,
    )


def _history(blend: pd.Series, months: int) -> list[dict]:
    """Phase path over time -- drives the cycle-clock trail in the UI."""
    blend = blend.dropna()
    if not len(blend):
        return []
    mom = blend.diff(3)
    out = []
    for date, lvl in blend.iloc[-months:].items():
        m = mom.get(date)
        if m is None or pd.isna(m):
            continue
        p = quadrant(float(lvl), float(m))
        out.append({
            "date": date.date().isoformat(),
            "level": round(float(lvl), 4),
            "momentum": round(float(m), 4),
            "phase": p.value,
        })
    return out
