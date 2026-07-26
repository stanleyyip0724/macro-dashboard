"""
Validate every series ID in the registry against the live FRED API.

Run this after editing indicators.py, and in CI. A typo in a series ID is
otherwise a silent runtime hole -- the composite just quietly loses a member.

    python scripts/validate_series.py
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.indicators import ALL_INDICATORS  # noqa: E402

BASE = "https://api.stlouisfed.org/fred/series"

# Max tolerable age of the newest observation, by declared frequency. Anything
# beyond this means the series was discontinued or renamed upstream -- which is
# exactly how USSLIND silently rotted out of this registry.
STALE_DAYS = {"d": 10, "w": 21, "m": 120, "q": 260}


def load_key() -> str:
    key = os.environ.get("FRED_API_KEY")
    if key:
        return key
    env = Path(__file__).resolve().parents[1] / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("FRED_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("FRED_API_KEY not set (env var or backend/.env)")


def fetch(series_id: str, key: str) -> dict:
    qs = urllib.parse.urlencode(
        {"series_id": series_id, "api_key": key, "file_type": "json"}
    )
    with urllib.request.urlopen(f"{BASE}?{qs}", timeout=30) as r:
        return json.loads(r.read().decode())


def main() -> int:
    key = load_key()
    today = datetime.date.today()
    ok, bad, stale, mismatched = [], [], [], []

    for ind in ALL_INDICATORS:
        try:
            s = fetch(ind.series_id, key)["seriess"][0]
        except Exception as exc:  # noqa: BLE001
            bad.append((ind.series_id, exc))
            print(f"  FAIL  {ind.series_id:<22} {exc}")
            continue

        ok.append(ind.series_id)
        declared = ind.freq.value.lower()
        actual = s["frequency_short"].lower()
        if not actual.startswith(declared):
            mismatched.append((ind.series_id, declared, actual))

        age = (today - datetime.date.fromisoformat(s["observation_end"])).days
        budget = STALE_DAYS.get(declared, 120)
        marker = ""
        if age > budget:
            stale.append((ind.series_id, s["observation_end"], age, budget))
            marker = f"  <-- STALE (>{budget}d)"

        print(
            f"  OK    {ind.series_id:<22} {actual:<3} "
            f"end={s['observation_end']} age={age:>4}d  "
            f"{s['title'][:52]}{marker}"
        )
        time.sleep(0.05)  # stay far below FRED's 120 req/min ceiling

    print(
        f"\n{len(ok)} resolved / {len(bad)} broken / {len(stale)} stale "
        f"/ {len(mismatched)} freq-mismatched  (of {len(ALL_INDICATORS)})"
    )

    for sid, exc in bad:
        print(f"  BROKEN {sid}: {exc}")
    for sid, end, age, budget in stale:
        print(f"  STALE  {sid}: last obs {end} ({age}d old, budget {budget}d)")
    for sid, d, a in mismatched:
        print(f"  FREQ   {sid}: declared={d} fred={a}")

    return 1 if (bad or stale or mismatched) else 0


if __name__ == "__main__":
    raise SystemExit(main())
