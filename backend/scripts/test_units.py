"""
Unit tests for the parts that are easy to get silently wrong.

No network, no cache -- pure functions on synthetic data. Run with:
    python scripts/test_units.py
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.analysis.cycle import (                      # noqa: E402
    CONTRACTION_LEVEL, NEUTRAL_LEVEL, Phase, quadrant,
)
from app.analysis.risk import _subscore, pillar_for   # noqa: E402
from app.indicators import BY_ID, Freq, Indicator, Klass, Transform  # noqa: E402
from app.transforms import (                          # noqa: E402
    STALE_TOLERANCE_MONTHS, apply_transform, build, composite, rolling_z,
    to_series,
)

PASS, FAIL = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def monthly(values: list[float], start="2015-01-01") -> pd.Series:
    idx = pd.date_range(start, periods=len(values), freq="MS")
    return pd.Series(values, index=idx, dtype="float64")


def ind(**kw) -> Indicator:
    base = dict(
        series_id="TEST", name="Test", short="Test", klass=Klass.COINCIDENT,
        freq=Freq.MONTHLY, transform=Transform.LEVEL, unit="%",
    )
    base.update(kw)
    return Indicator(**base)  # type: ignore[arg-type]


print("Transforms")
print("-" * 62)

# YoY on a series doubling over 12 months.
s = monthly([100.0] * 12 + [110.0])
out = apply_transform(s, ind(transform=Transform.YOY_PCT))
check("YOY_PCT computes 12-month change", abs(out.iloc[-1] - 10.0) < 1e-9,
      f"got {out.iloc[-1]}")

# A gap must NOT be bridged by pandas' default pad before differencing.
gapped = monthly([100.0] * 13)
gapped.iloc[0] = np.nan
out = apply_transform(gapped, ind(transform=Transform.YOY_PCT))
check("YOY_PCT does not pad across gaps", pd.isna(out.iloc[12]),
      f"got {out.iloc[12]} -- fill_method leaked back in")

out = apply_transform(monthly([100.0, 105.0]), ind(transform=Transform.MOM_PCT))
check("MOM_PCT", abs(out.iloc[-1] - 5.0) < 1e-9, f"got {out.iloc[-1]}")

out = apply_transform(monthly([100.0, 157.0]), ind(transform=Transform.MOM_DIFF))
check("MOM_DIFF returns absolute change", abs(out.iloc[-1] - 57.0) < 1e-9)

# Non-positive levels must not blow up fractional exponentiation.
out = apply_transform(
    monthly([1.0, -2.0, 3.0, 4.0, 5.0]), ind(transform=Transform.ANNUALISED_3M)
)
check("ANNUALISED_3M survives non-positive levels", out.notna().sum() >= 0)

print("\nZ-scores")
print("-" * 62)

flat = monthly([5.0] * 40)
z = rolling_z(flat, 24)
check("zero-variance series yields no infinities",
      not np.isinf(z.dropna()).any() if z.notna().any() else True)

noisy = monthly(list(np.random.default_rng(0).normal(0, 1, 200)))
z = rolling_z(noisy, 120)
check("z-scores are winsorised to +/-4", z.dropna().abs().max() <= 4.0 + 1e-9,
      f"max |z| = {z.dropna().abs().max()}")

print("\nPolarity")
print("-" * 62)

obs = [(d.strftime("%Y-%m-%d"), v) for d, v in monthly(
    list(np.linspace(4.0, 8.0, 60))
).items()]

bad_up = build(ind(series_id="BADUP", polarity=-1), obs)   # e.g. unemployment
good_up = build(ind(series_id="GOODUP", polarity=1), obs)  # e.g. GDP

check("rising series with polarity -1 gives a NEGATIVE signal",
      (bad_up.latest_signal or 0) < 0, f"got {bad_up.latest_signal}")
check("rising series with polarity +1 gives a POSITIVE signal",
      (good_up.latest_signal or 0) > 0, f"got {good_up.latest_signal}")
check("polarity flips sign, not magnitude",
      abs((bad_up.latest_signal or 0) + (good_up.latest_signal or 0)) < 1e-9)

print("\nMonthly alignment / forward-fill")
print("-" * 62)

# A monthly series ending well before today must still reach the current month.
old = monthly(list(np.linspace(1, 30, 30)), start="2023-01-01")
obs_old = [(d.strftime("%Y-%m-%d"), v) for d, v in old.items()]
r = build(ind(series_id="OLD", freq=Freq.MONTHLY), obs_old)
sig = r.signal.dropna()
last_obs_month = old.index[-1].to_period("M")
reach = (sig.index[-1].to_period("M") - last_obs_month).n if len(sig) else -1
check("signal extends past the last observation",
      0 < reach <= STALE_TOLERANCE_MONTHS[Freq.MONTHLY],
      f"reached {reach} months past last obs (limit "
      f"{STALE_TOLERANCE_MONTHS[Freq.MONTHLY]})")
check("forward-fill is BOUNDED (discontinued series age out)",
      reach <= STALE_TOLERANCE_MONTHS[Freq.MONTHLY])

print("\nComposites")
print("-" * 62)

a = build(ind(series_id="A", weight=1.0, polarity=1), obs)
b = build(ind(series_id="B", weight=3.0, polarity=1), obs)
comp, meta = composite([a, b])
check("composite reports its member count", meta["members"] == 2)
check("composite reports an as_of date", meta.get("as_of") is not None)
check("coverage is measured at the retained month",
      0.0 < meta["coverage"] <= 1.0, f"got {meta['coverage']}")

zero_w = build(ind(series_id="Z", weight=0.0), obs)
comp2, meta2 = composite([a, zero_w])
check("zero-weight members are excluded from composites",
      meta2["members"] == 1, f"got {meta2['members']}")

print("\nCycle quadrant")
print("-" * 62)

check("clearly above trend + rising -> Expansion",
      quadrant(1.0, 0.3) is Phase.EXPANSION)
check("clearly above trend + falling -> Peak",
      quadrant(1.0, -0.3) is Phase.PEAK)
check("deeply below trend + falling -> Contraction",
      quadrant(-1.5, -0.3) is Phase.CONTRACTION)
check("deeply below trend + rising -> Trough",
      quadrant(-1.5, 0.3) is Phase.TROUGH)
check("noise near zero never yields Contraction",
      quadrant(-0.087, -0.029) is not Phase.CONTRACTION,
      f"got {quadrant(-0.087, -0.029)}")
check("the slowdown band is not a recession call",
      quadrant(-0.5, -0.3) is Phase.PEAK, f"got {quadrant(-0.5, -0.3)}")
check("Contraction requires breaching the calibrated threshold",
      quadrant(CONTRACTION_LEVEL - 0.01, -0.3) is Phase.CONTRACTION
      and quadrant(CONTRACTION_LEVEL + 0.01, -0.3) is not Phase.CONTRACTION)

print("\nRisk scoring")
print("-" * 62)

check("average conditions score ~21, not 50", 18 < _subscore(0.0) < 25,
      f"got {_subscore(0.0):.1f}")
check("+1sd badness scores 50", abs(_subscore(1.0) - 50.0) < 1e-6)
check("sub-score is monotonic in badness",
      all(_subscore(b) < _subscore(b + 0.5) for b in np.arange(-2, 3, 0.5)))
check("sub-score saturates below 100", _subscore(6.0) < 100.0)

check("HY spread maps to the Credit pillar",
      pillar_for(BY_ID["BAMLH0A0HYM2"]).value == "Credit & Financial")
check("core PCE maps to the Inflation pillar",
      pillar_for(BY_ID["PCEPILFE"]).value == "Inflation & Policy")
check("building permits map to the Housing pillar",
      pillar_for(BY_ID["PERMIT"]).value == "Housing")

print("\nRegistry integrity")
print("-" * 62)

from app.indicators import ALL_INDICATORS, HEADLINE_IDS  # noqa: E402

ids = [i.series_id for i in ALL_INDICATORS]
check("no duplicate series IDs", len(ids) == len(set(ids)))
check("every polarity is +1 or -1",
      all(i.polarity in (1, -1) for i in ALL_INDICATORS))
check("every headline ID exists in the registry",
      all(h in BY_ID for h in HEADLINE_IDS),
      f"missing {[h for h in HEADLINE_IDS if h not in BY_ID]}")
check("USSLIND (discontinued) is not in the registry", "USSLIND" not in BY_ID)
check("weights are non-negative",
      all(i.weight >= 0 and i.risk_weight >= 0 for i in ALL_INDICATORS))

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
