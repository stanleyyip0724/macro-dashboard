"""
Backtest the cycle classifier and risk score against NBER recession dates.

IMPORTANT CAVEAT -- this is an in-sample, revised-data backtest, not a
real-time one. FRED serves the LATEST vintage of each series, so payrolls and
GDP here reflect revisions that were not available at the time. Real-time
performance is always worse. To do this properly, refetch through ALFRED
(`realtime_start`/`realtime_end` on the observations endpoint) to reconstruct
what each series actually printed on each date.

What this DOES validate: that the composite construction, polarity signs and
phase logic behave sensibly across history rather than producing noise.

    python scripts/backtest.py
"""

from __future__ import annotations

import asyncio
import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.analysis.cycle import CONTRACTION_LEVEL, quadrant  # noqa: E402
from app.analysis.risk import MIDPOINT, STEEPNESS          # noqa: E402
from app.config import get_settings                        # noqa: E402
from app.indicators import Klass                           # noqa: E402
from app.service import MacroService                       # noqa: E402
from app.transforms import composite                       # noqa: E402

import math                                                # noqa: E402


async def main() -> int:
    svc = MacroService(get_settings())
    snap = await svc.snapshot()

    by_class: dict[Klass, list] = {k: [] for k in Klass}
    for r in snap.results.values():
        by_class[r.indicator.klass].append(r)

    lead_s, _ = composite(by_class[Klass.LEADING])
    coin_s, _ = composite(by_class[Klass.COINCIDENT])

    parts = pd.DataFrame({"c": coin_s, "l": lead_s}).dropna()
    blend = 0.6 * parts["c"] + 0.4 * parts["l"]
    mom = blend.diff(3)

    rec = snap.results["USREC"]
    usrec = rec.raw.resample("ME").last().ffill()

    df = pd.DataFrame({"level": blend, "momentum": mom, "usrec": usrec}).dropna()
    df["phase"] = [quadrant(l, m) for l, m in zip(df.level, df.momentum)]
    df["phase"] = df["phase"].map(lambda p: p.value)

    print(f"Backtest window: {df.index[0].date()} -> {df.index[-1].date()} "
          f"({len(df)} months)")
    print(f"NBER recession months in window: {int(df.usrec.sum())}\n")

    print("Phase vs NBER recession flag")
    print("-" * 62)
    ct = pd.crosstab(df.phase, df.usrec)
    ct.columns = ["expansion_mo", "recession_mo"]
    ct["recession_share"] = (
        ct.recession_mo / (ct.recession_mo + ct.expansion_mo) * 100
    ).round(1)
    print(ct.sort_values("recession_share", ascending=False).to_string())

    # Does "Contraction" actually capture recessions?
    contraction = df.phase == "Contraction"
    rec_flag = df.usrec == 1
    tp = int((contraction & rec_flag).sum())
    fp = int((contraction & ~rec_flag).sum())
    fn = int((~contraction & rec_flag).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    print(f"\n'Contraction' as a recession call:")
    print(f"  precision {precision:.1%}  recall {recall:.1%}  "
          f"(tp={tp} fp={fp} fn={fn})")

    # Risk-score behaviour through history, reconstructed from the same
    # logistic used live.
    print("\nComposite level by regime")
    print("-" * 62)
    print(df.groupby(df.usrec.map({0.0: "expansion", 1.0: "recession"}))[
        ["level", "momentum"]
    ].agg(["mean", "min", "max"]).round(3).to_string())

    # Lead/lag: how far ahead of each recession did the level first go negative?
    print("\nPer-recession detail")
    print("-" * 62)
    starts = df.index[(df.usrec == 1) & (df.usrec.shift(1) == 0)]
    for start in starts:
        window = df.loc[:start].tail(30)
        neg = window[window.level < CONTRACTION_LEVEL]
        first = neg.index[0] if len(neg) else None
        # str() before padding: a date object ignores the ">10" format spec.
        first_s = str(first.date()) if first is not None else "n/a"
        lead = (
            (start.to_period("M") - first.to_period("M")).n
            if first is not None else None
        )
        lead_s = f"{lead} mo" if lead is not None else "n/a"
        depth = df.loc[start:].head(18).level.min()
        print(
            f"  recession start {start.date()}  "
            f"level first < {CONTRACTION_LEVEL}sd: {first_s:>10}  "
            f"lead: {lead_s:>6}  trough level: {depth:+.2f}sd"
        )

    def subscore(b: float) -> float:
        return 100.0 / (1.0 + math.exp(-STEEPNESS * (b - MIDPOINT)))

    print(f"\nRisk sub-score calibration (badness -> score):")
    for b in (-1, 0, 0.5, 1, 1.5, 2, 2.5, 3, 4):
        print(f"  {b:+.1f}sd -> {subscore(b):5.1f}")

    await svc.aclose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
