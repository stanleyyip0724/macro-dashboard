"""In-process API test -- exercises the real routes without a live server."""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings        # noqa: E402
from app.main import app                   # noqa: E402
from app.service import MacroService       # noqa: E402


def main() -> int:
    # Attach a service without triggering lifespan's network refresh; the
    # SQLite cache is already populated by smoke_test.
    app.state.service = MacroService(get_settings())

    client = TestClient(app)
    failures = 0

    def check(name: str, path: str, method: str = "GET"):
        nonlocal failures
        r = client.request(method, path)
        ok = r.status_code == 200
        failures += 0 if ok else 1
        print(f"  {'PASS' if ok else 'FAIL'}  {method} {path} -> {r.status_code}")
        return r.json() if ok else None

    print("Endpoint checks")
    print("-" * 60)
    summary = check("summary", "/api/summary")
    check("cycle", "/api/cycle")
    check("risk", "/api/risk")
    check("alerts", "/api/alerts")
    check("series list", "/api/series")
    check("series filtered", "/api/series?klass=leading")
    check("series detail", "/api/series/UNRATE")
    check("health", "/api/health")

    r = client.get("/api/series/NOTAREALSERIES")
    ok = r.status_code == 404
    failures += 0 if ok else 1
    print(f"  {'PASS' if ok else 'FAIL'}  unknown series -> {r.status_code} (want 404)")

    if summary:
        print("\nSummary payload shape")
        print("-" * 60)
        print(f"  data_as_of      {summary['data_as_of']}")
        print(f"  phase           {summary['cycle']['phase']} "
              f"(confidence {summary['cycle']['confidence']})")
        print(f"  risk            {summary['risk']['score']} [{summary['risk']['band']}]")
        print(f"  alerts          {len(summary['alerts'])}")
        print(f"  headline cards  {len(summary['headline'])}")
        print(f"  composites      {[c['name'] for c in summary['composites']]}")
        print(f"  composite pts   "
              f"{[len(c['points']) for c in summary['composites']]}")
        print(f"  missing         {summary['missing_series']}")
        print(f"  payload bytes   {len(json.dumps(summary)):,}")

        card = summary["headline"][0]
        print(f"\n  sample card: {card['short']} = {card['latest_value']} "
              f"{card['unit']} (z {card['latest_z']}), "
              f"{len(card['sparkline'])} sparkline points")

    print(f"\n{'ALL PASS' if failures == 0 else f'{failures} FAILURES'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
