"""
Live check of the markets pipeline.

Unlike the FRED tests this one hits four public endpoints with no SLA, so it
reports per-section coverage rather than asserting every section is present.
It fails only on things that are our bug rather than someone else's outage:
a broken parse, a nonsensical figure, or commentary that never fires.

    python scripts/test_markets.py
"""

from __future__ import annotations

import asyncio
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings                 # noqa: E402
from app.markets.catalog import ALL, CURVE_TENORS   # noqa: E402
from app.markets.service import MarketsService      # noqa: E402


def main() -> int:
    svc = MarketsService(get_settings())
    data = asyncio.run(svc.overview())

    failures = 0

    def check(label: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        failures += 0 if ok else 1
        print(f"  {'PASS' if ok else 'FAIL'}  {label}{f' -- {detail}' if detail else ''}")

    print("Coverage")
    print("-" * 68)
    rows = [r for section in data["sections"].values() for r in section]
    print(f"  instruments priced : {len(rows)} / {len(ALL)}")
    print(f"  curve tenors       : {len(data['curve'].get('points', []))} / {len(CURVE_TENORS)}")
    print(f"  fear & greed       : {data['fear_greed'].get('score')}")
    print(f"  headlines          : {len(data['news'])}")
    if data["errors"]:
        print(f"  upstream errors    : {data['errors']}")

    print("\nSanity")
    print("-" * 68)
    check("at least half the instruments priced", len(rows) >= len(ALL) // 2,
          f"{len(rows)} of {len(ALL)}")

    for r in rows:
        if r["price"] is None:
            check(f"{r['short']} has a price", False)
            continue
        if r["price"] <= 0:
            check(f"{r['short']} price is positive", False, str(r["price"]))
        ytd = r["changes"].get("ytd")
        # A YTD move beyond +-300% on an index/FX/commodity means we mis-parsed
        # a split or a currency, not a real move.
        if ytd is not None and abs(ytd) > 300 and r["group"] != "crypto":
            check(f"{r['short']} YTD is plausible", False, f"{ytd:.0f}%")
        pos = r["range_position"]
        if pos is not None and not (0.0 <= pos <= 1.0):
            check(f"{r['short']} range position in [0,1]", False, str(pos))
        if not r["commentary"]:
            check(f"{r['short']} has commentary", False)

    curve_pts = data["curve"].get("points", [])
    if curve_pts:
        yields = [p["current"] for p in curve_pts if p["current"] is not None]
        check("curve yields are in a sane range",
              all(-2 < y < 25 for y in yields), str(yields))
        check("curve is ordered by tenor",
              [p["years"] for p in curve_pts] == sorted(p["years"] for p in curve_pts))
        check("curve commentary generated", len(data["curve"].get("commentary", [])) > 0)

    fg = data["fear_greed"]
    if fg.get("score") is not None:
        check("fear & greed in [0,100]", 0 <= fg["score"] <= 100, str(fg["score"]))
        check("fear & greed commentary generated", len(fg.get("commentary", [])) > 0)

    if data["news"]:
        check("every headline has an implication",
              all(n.get("implication") for n in data["news"]))
        check("every headline has a link", all(n.get("link") for n in data["news"]))

    if rows:
        check("top-level synthesis generated", len(data["summary"]) > 0)
        for key, items in data["commentary"].items():
            check(f"{key} commentary generated", len(items) > 0)

    print("\nSample commentary")
    print("-" * 68)
    for line in data["summary"][:3]:
        print(f"  · {line}")

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
