"""
End-to-end smoke test: fetch everything, run the analytics, print the report.

This exercises the exact code path the API serves, without needing a running
server. Run it after any change to transforms or the analysis modules.

    python scripts/smoke_test.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings          # noqa: E402
from app.indicators import HEADLINE_IDS      # noqa: E402
from app.service import MacroService         # noqa: E402


async def main() -> int:
    logging.basicConfig(level="INFO", format="%(levelname)-7s %(name)s: %(message)s")
    svc = MacroService(get_settings())

    t0 = time.perf_counter()
    errors = await svc.refresh()
    print(f"\nRefresh took {time.perf_counter() - t0:.1f}s, {len(errors)} errors")
    for sid, msg in errors.items():
        print(f"   ! {sid}: {msg}")

    snap = await svc.snapshot()
    print(f"Series analysed: {len(snap.results)}   missing: {snap.missing}")

    c = snap.cycle
    print("\n" + "=" * 78)
    print(f"BUSINESS CYCLE PHASE: {c.phase.value.upper()}  "
          f"(confidence {c.confidence:.0%})")
    print("=" * 78)
    print(f"  growth level      {c.growth_level:+.3f} sd"
          if c.growth_level is not None else "  growth level      n/a")
    print(f"  growth momentum   {c.growth_momentum:+.3f} sd (3m)"
          if c.growth_momentum is not None else "  growth momentum   n/a")
    print(f"  inflation press.  {c.inflation_pressure:+.3f} sd"
          if c.inflation_pressure is not None else "  inflation press.  n/a")
    print(f"  breadth           {c.breadth:.0%}" if c.breadth is not None else "  breadth  n/a")
    print("\n  Composites:")
    for k, v in c.composites.items():
        cov = c.coverage.get(k, {}).get("coverage")
        cov_s = f"  (coverage {cov:.0%})" if cov is not None else ""
        print(f"    {k:<14} {v:+.3f}{cov_s}" if v is not None else f"    {k:<14} n/a")
    print("\n  Hard signals:")
    for h in c.hard_signals:
        v = f"{h.value:+.3f}" if h.value is not None else "n/a"
        print(f"    [{'X' if h.fired else ' '}] {h.name:<22} {v:>8}  (thr {h.threshold})")
    print("\n  Rationale:")
    for line in c.rationale:
        print(f"    - {line}")

    r = snap.risk
    print("\n" + "=" * 78)
    print(f"ECONOMIC RISK LEVEL: {r.score:.1f}/100  [{r.band.upper()}]")
    print("=" * 78)
    print(f"  {r.band_description}")
    print(f"  base {r.base_score:.1f} + trigger bonus {r.trigger_bonus:.1f} "
          f"| input coverage {r.coverage:.0%}")
    print("\n  Pillars:")
    for p, v in sorted(r.pillars.items(), key=lambda kv: -kv[1]):
        bar = "#" * int(v / 3)
        print(f"    {p:<20} {v:5.1f}  {bar}")
    print("\n  Triggers:")
    for t in r.triggers:
        v = f"{t.value:+.2f}" if t.value is not None else "n/a"
        print(f"    [{'X' if t.fired else ' '}] {t.name:<38} {v:>8}  ({t.threshold})")
    print("\n  Top risk drivers:")
    for d in r.top_drivers:
        print(f"    - {d}")

    print("\n" + "=" * 78)
    print(f"ALERTS ({len(snap.alerts)})")
    print("=" * 78)
    for a in snap.alerts:
        print(f"  [{a.severity.upper():<8}] {a.title}  ({a.as_of})")
        print(f"             {a.message[:150]}")

    print("\n" + "=" * 78)
    print("HEADLINE INDICATORS")
    print("=" * 78)
    print(f"  {'series':<14}{'value':>12} {'unit':<8}{'z':>7} {'3m chg':>9}  as-of")
    for sid in HEADLINE_IDS:
        res = snap.results.get(sid)
        if not res:
            continue
        v = res.latest_value
        z = res.latest_z
        ch = res.change(3)
        print(
            f"  {sid:<14}"
            f"{(f'{v:,.2f}' if v is not None else 'n/a'):>12} "
            f"{res.indicator.unit:<8}"
            f"{(f'{z:+.2f}' if z is not None else 'n/a'):>7} "
            f"{(f'{ch:+,.2f}' if ch is not None else 'n/a'):>9}"
            f"  {res.latest_date}"
        )

    print("\nCache stats:", svc.cache.stats())
    await svc.aclose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
