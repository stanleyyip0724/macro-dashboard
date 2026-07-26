# US Macroeconomic Health Dashboard

Aggregates 48 FRED series into a business-cycle phase classification, a
composite systemic-risk index, and a threshold alert engine.

Every series ID in this repo has been verified live against the FRED API, and
the cycle classifier's thresholds are calibrated against NBER recession dates
rather than chosen by intuition.

---

## 1. Quick start

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate    # Windows
# python3 -m venv .venv && source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
cp .env.example .env        # then paste your FRED key into .env
python scripts/validate_series.py    # confirms all 48 series resolve
uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev                 # http://localhost:3000
```

API docs are at <http://localhost:8000/docs>.

### Verification scripts

| Script | What it proves |
|---|---|
| `scripts/validate_series.py` | All series IDs resolve, are not discontinued, and match their declared frequency. Exits non-zero on failure — wire it into CI. |
| `scripts/smoke_test.py` | Full pipeline end to end: fetch → transform → classify → score → alert. |
| `scripts/backtest.py` | Cycle classifier measured against NBER recession dates. |
| `scripts/test_api.py` | Every HTTP route returns 200 and the expected payload shape. |

---

## 2. Indicator selection & FRED mapping

The registry lives in one file, [`backend/app/indicators.py`](backend/app/indicators.py).
Nothing downstream hardcodes a series ID — fetching, caching, transforms,
composites, alerts, and the UI cards are all driven from it.

### Leading — turn before the cycle

| Series ID | Indicator | Freq | Why it's here |
|---|---|---|---|
| `T10Y3M` | 10Y−3M Treasury spread | D | NY Fed's preferred recession predictor; leads 6–18 months |
| `T10Y2Y` | 10Y−2Y Treasury spread | D | Inverted before every recession since 1970 |
| `ICSA` | Initial jobless claims | W | Highest-frequency read on labour demand |
| `PERMIT` | Building permits | M | Most rate-sensitive real-economy series |
| `HOUST` | Housing starts | M | Confirms the permits signal |
| `NEWORDER` | Core capital goods orders | M | Business investment intentions |
| `AWHMAN` | Avg weekly hours, manufacturing | M | Firms cut hours before heads |
| `UMCSENT` | U. Michigan consumer sentiment | M | Consumer expectations |
| `BBKMLEIX` | Brave-Butters-Kelley Leading Index | M | Chicago Fed dynamic-factor leading index |
| `SP500` | S&P 500 | D | Market's forward discount (10y history only) |
| `M2REAL` | Real M2 money stock | M | Real liquidity impulse |

> **Note:** `USSLIND` (Philadelphia Fed Leading Index) appears in most FRED
> tutorials but **FRED discontinued it in February 2020**. It still resolves
> through the API, which is exactly what makes it dangerous — it returns 200 OK
> with six-year-old data. `BBKMLEIX` replaces it. `validate_series.py` now has a
> frequency-aware staleness check specifically to catch this class of failure.

### Coincident — define where we are now

| Series ID | Indicator | Freq | Why it's here |
|---|---|---|---|
| `PAYEMS` | Nonfarm payrolls | M | The most important monthly release |
| `INDPRO` | Industrial production | M | NBER coincident series |
| `W875RX1` | Real income ex-transfers | M | NBER series; strips stimulus distortion |
| `CMRMTSPL` | Real manufacturing & trade sales | M | NBER series |
| `PCEC96` | Real consumer spending | M | ~68% of GDP |
| `RSAFS` | Retail sales | M | Nominal — deflate before interpreting |
| `GDPC1` | Real GDP | Q | Context, not timing (heavily revised) |
| `TCU` | Capacity utilization | M | Late-cycle capacity pressure |
| `USPHCI` | Coincident activity index | M | Philadelphia Fed composite |
| `CFNAIMA3` | CFNAI, 3-month average | M | 85 indicators in one number |
| `CFNAIDIFF` | CFNAI diffusion index | M | How **broad** weakness is, not just how deep |
| `BBKMCOIX` | BBK Coincident Index | M | Dynamic-factor cross-check |

### Lagging — confirm the cycle, define the policy regime

| Series ID | Indicator | Freq | Why it's here |
|---|---|---|---|
| `UNRATE` | Unemployment rate | M | Lags badly at turns — use Sahm for timing |
| `U6RATE` | U-6 underemployment | M | Broadest labour slack |
| `CPIAUCSL` | Headline CPI | M | Political/expectations anchor |
| `CPILFESL` | Core CPI | M | Trend inflation |
| `PCEPILFE` | Core PCE | M | **The Fed's actual target variable** |
| `CORESTICKM159SFRBATL` | Sticky-price core CPI | M | Embedded inflation expectations |
| `FEDFUNDS` | Fed funds rate | M | Policy stance |
| `CIVPART` | Participation rate | M | Labour supply |
| `ULCNFB` | Unit labour costs | Q | Wage-price pressure net of productivity |
| `TOTCI` | C&I loans | W | Bank credit to business |
| `CSUSHPINSA` | Case-Shiller home prices | M | Household wealth effect |

### Financial & systemic stress — excluded from the cycle clock, heaviest risk weights

`NFCI`, `ANFCI`, `STLFSI4`, `BAMLH0A0HYM2` (HY OAS), `BAMLC0A0CM` (IG OAS),
`DRSFRMACBS`, `DRCCLACBS`, `TDSP`, `DRTSCILM` (SLOOS bank tightening),
`T10YIE`, `WALCL`.

These are market prices, not activity, so they do not vote on the growth phase —
but they carry the largest weights in the risk score.

### Rule-based recession signals

`SAHMREALTIME`, `RECPROUSM156N` (Chauvet-Piger), `USREC` (NBER ground truth,
used only for backtesting — it is published with a long lag and is never a live
signal).

---

## 3. Economic analysis framework

### 3.1 Making indicators comparable

Three problems must be solved before indicators can be added together
([`transforms.py`](backend/app/transforms.py)):

1. **Units.** Payrolls are thousands of jobs, CPI is an index, `T10Y2Y` is
   percentage points. Each series declares a transform (`YOY_PCT`, `MOM_DIFF`,
   `LEVEL`, …) and then gets a **rolling 10-year z-score**. The window is
   rolling, not full-history, deliberately: a full-history z-score compares
   today against the 1970s and marks a normal 2020s reading as extreme.
2. **Direction.** Every indicator declares a `polarity`. Signals are multiplied
   by ±1 so **positive always means "good for the economy"** — rising
   unemployment and rising GDP must not both read as "up".
3. **Frequency.** Transforms are computed at native frequency (so a YoY is a
   true YoY), then the z-score is resampled to month-end and forward-filled
   within a bounded window.

> That last bound is the subtlest part of the codebase. Publication lag means
> that in July, GDP is from Q1 and core PCE is from May. Without a bounded
> forward-fill the recent months of every composite are computed from whichever
> series happen to report fastest — the yield curve and credit spreads — which
> silently biases the "current" reading. Building this correctly moved the
> coincident composite from −0.008 to −0.114 and lifted composite coverage from
> 57% to 100%.
>
> The fill is **bounded** (2 months for daily/weekly, 4 monthly, 8 quarterly) so
> a discontinued series ages out instead of contributing forever.

### 3.2 The cycle clock

Two axes ([`analysis/cycle.py`](backend/app/analysis/cycle.py)):

- **level** = `0.6 × coincident + 0.4 × leading` composite, in z-space.
  Coincident is weighted higher because leading indicators are noisy and
  produce false positives when trusted on level.
- **momentum** = the 3-month change in that blend.

```
                    momentum ≥ 0        momentum < 0
  level > +0.15  |   EXPANSION      |   PEAK          |
  −0.70…+0.15    |   RECOVERY       |   PEAK          |   ← slowdown band
  level < −0.70  |   TROUGH/RECOVERY|   CONTRACTION   |   ← recession zone
```

**The thresholds are calibrated, not guessed.** `scripts/backtest.py` sweeps
them against NBER recession months over 1993–2026:

| Contraction threshold | Precision | Recall |
|---|---|---|
| −0.15 (naive "below zero") | 23.8% | 85.7% |
| **−0.70 (adopted)** | **70.6%** | **85.7%** |
| −0.80 (best F1) | 82.1% | 82.1% |

Every NBER recession month in the window had a composite level ≤ −0.70 (the
recession-month maximum was exactly −0.70), while only ~5% of expansion months
did. −0.70 was chosen over the marginally better F1 at −0.80 because for a risk
dashboard a missed recession costs more than a false alarm.

That the sweep landed on the Chicago Fed's own published CFNAI recession
threshold of −0.70 is independent corroboration — the sweep was run blind to it.

**Measured performance of the final classifier (394 months, 28 recession months):**

| Phase | Expansion months | Recession months | % recessionary |
|---|---|---|---|
| Contraction | 10 | 24 | 70.6% |
| Trough | 5 | 4 | 44.4% |
| **Expansion** | 141 | **0** | **0%** |
| **Peak** | 171 | **0** | **0%** |
| **Recovery** | 39 | **0** | **0%** |

The critical property: **no recession month is ever labelled Expansion, Peak, or
Recovery.** Contraction and Trough together capture all 28.

Two refinements sit on top of the quadrant:

- **Neutral bands.** Without a dead zone around zero, a level of −0.087σ —
  statistically indistinguishable from trend — flips the call to the most
  alarming label in the model. Inside the band the worst available call is Peak.
- **Hard-rule overrides.** The Sahm gap (≥0.50) and CFNAI-3M (<−0.70) have
  published, non-negotiable thresholds. Two firing at once overrides the
  quadrant outright — "the composite says Expansion" is not a position worth
  defending against a triggered Sahm rule.

### 3.3 The risk score

`0–100`, in [`analysis/risk.py`](backend/app/analysis/risk.py).

**Risk is not the inverse of growth.** Slow growth with clean balance sheets is
low-risk; fast growth with an inverted curve and blowing-out spreads is not. So
the score is built from its own weighted subset of indicators, not from the
cycle composites.

Each input is mapped through a logistic rather than linearly, because the move
from +2σ to +3σ matters far more than 0σ to +1σ:

```
badness  b = −polarity × z          (positive = bad)
subscore   = 100 / (1 + exp(−1.3 × (b − 1.0)))
```

| badness | 0σ | +1σ | +2σ | +3σ |
|---|---|---|---|---|
| sub-score | 21 | 50 | 79 | 93 |

A perfectly average economy scores ~21, not 50 — which is the behaviour you want
from a *risk* gauge.

**Pillars.** Every input maps to Growth, Labour, Inflation & Policy, Credit &
Financial, or Housing. A 55 driven entirely by Credit calls for a completely
different response than a 55 spread evenly, and a single number hides that.

**Trigger bonus.** Rule-based signals (Sahm, curve inversion, CFNAI, HY spreads,
SLOOS, recession probability) don't average well — their information is in the
crossing, not the magnitude. They apply as a bounded additive premium (max +18).

**Bands:** 0–20 Low · 20–40 Moderate · 40–60 Elevated · 60–80 High · 80–100 Severe.

### 3.4 Alerts

Three independent sources, so no single model quirk can manufacture *or*
suppress a warning:

1. **Threshold** — published, externally-defined lines (Sahm 0.50, CFNAI −0.70,
   curve at zero), not tuned numbers.
2. **Statistical** — any indicator >2σ into adverse territory.
3. **Velocity** — a z-score moving >1.5σ in three months. Catches turning points
   while the *level* still looks fine.

Deduplicated to the most severe alert per series so one indicator firing on all
three rules doesn't flood the panel.

---

## 4. Architecture & caching

```
Browser ──▶ Next.js 14 (React, Recharts, SWR)
                │  NEXT_PUBLIC_API_BASE — no secrets in the bundle
                ▼
           FastAPI  ──▶ MacroService ──▶ Snapshot cache (RAM, 5 min TTL)
                                 │
                                 ▼
                        SQLite observation cache
                                 │  two-tier freshness
                                 ▼
                          FRED API (rate-limited, retrying)
```

**Why Python:** the analytics are the hard part, and pandas makes rolling
z-scores, resampling, and mixed-frequency alignment tractable. Node would mean
hand-rolling all of it.

### The caching strategy

FRED allows 120 requests/minute. The dashboard makes far fewer, via **two
independent cache tiers**:

| Tier | Mechanism | Effect |
|---|---|---|
| 1 | TTL by frequency (6h daily · 12h weekly · 24h monthly/quarterly) | Inside the TTL, zero upstream calls |
| 2 | `last_updated` check | Past the TTL, spend **one** cheap `/fred/series` metadata call. If `last_updated` is unchanged, skip the observations download entirely |

Tier 2 is what actually keeps us off the rate limit: most series are checked
many times a day but genuinely change once a month.

A third, separate cache holds the **computed snapshot** in RAM. Without it, a
page with ten widgets would run ~50 pandas pipelines ten times per load for
byte-identical output.

The background scheduler sweeps on a cadence matched to each frequency —
checking quarterly GDP every 15 minutes spends calls to learn nothing.

**Cold start:** 48 series ≈ 65s and ~96 upstream calls. Warm snapshot rebuild:
~500ms. Steady state: a handful of metadata calls per hour.

### Key handling

- The key is read from `.env` via pydantic-settings, never hardcoded.
- It is typed so `repr()` won't leak it into logs or validation errors.
- `_safe_url()` strips `api_key=` from any URL before it reaches the logger —
  FRED requires the key as a query parameter, and URLs are the single most
  common accidental credential leak in HTTP clients.
- `.gitignore` excludes `.env`; only `.env.example` is committed.
- **The browser never sees it.** All FRED access is server-side. Never put the
  key in a `NEXT_PUBLIC_*` variable — that prefix inlines it into the JS bundle.

### API surface

| Endpoint | Returns |
|---|---|
| `GET /api/summary` | Everything the dashboard needs, in one call |
| `GET /api/cycle` | Phase, composites, rationale, 60-month history |
| `GET /api/risk` | Score, band, pillars, per-indicator contributions |
| `GET /api/alerts` | Active alerts (`?severity=critical`) |
| `GET /api/series` | All indicator cards (`?klass=leading`, `?tag=inflation`) |
| `GET /api/series/{id}` | Full history: raw, transformed, z-score |
| `GET /api/health` | Coverage, missing series, cache stats |
| `POST /api/refresh` | Manual refresh (`?force=true` bypasses both tiers) |

`/api/summary` is deliberately one endpoint rather than six: every widget
derives from the same snapshot, and splitting it would let the cards disagree
with the gauge if a refresh landed between requests.

---

## 5. Known limitations

- **The backtest is in-sample and uses revised data.** FRED serves the latest
  vintage, so payrolls and GDP here reflect revisions unavailable at the time.
  Real-time performance is always worse. For an honest evaluation, refetch
  through **ALFRED** (`realtime_start`/`realtime_end` on the observations
  endpoint) to reconstruct what each series actually printed on each date.
- **Three recessions is a small sample.** 1993–2026 contains 2001, 2008, and
  2020 — and 2020 was an exogenous shock, not a credit cycle. Treat the
  precision/recall figures as indicative, not precise.
- **Weights are judgement, not optimisation.** They're deliberately not fitted;
  with three recessions, fitting weights would overfit badly. They encode
  economic reasoning and are all in one file to make disagreement easy.
- **`RSAFS` is nominal.** In a high-inflation regime it overstates real demand.
- **The frontend has not been built or run here** — Node isn't installed in the
  environment where this was authored. The backend is fully verified; the
  frontend is type-consistent with the API contract but expects a normal
  `npm install && npm run dev` shakedown.

## 6. Troubleshooting

**Page stuck on "Loading macro data…" forever.** Open DevTools → Network. If
`/_next/static/chunks/*.js` are returning **404**, the JS never loaded, so React
never hydrated and you are looking at frozen server-rendered HTML.

The usual cause is running `npm run build` while `npm run dev` is running —
both write to `.next/`, and the production build overwrites the dev server's
chunks. Fix:

```bash
# stop the dev server first, then:
rm -rf .next        # Windows PowerShell: Remove-Item -Recurse -Force .next
npm run dev
```

Then **hard-refresh** the browser (Ctrl+Shift+R) — a normal reload will serve
the cached broken page. Never run `build` and `dev` against the same directory
at the same time.

**Page shows "Cannot reach the API".** The backend isn't running, or
`NEXT_PUBLIC_API_BASE` doesn't match its port. Check `curl
http://localhost:8000/api/health`.

**`node` not recognised after installing via nvm-windows.** nvm installs the
runtime but the shim directory (`C:\nvm4w\nodejs`) may not land on `PATH`:

```powershell
[Environment]::SetEnvironmentVariable('Path', [Environment]::GetEnvironmentVariable('Path','User') + ';C:\nvm4w\nodejs', 'User')
```

Open a new terminal afterwards.

## 7. Extending it

Adding an indicator is a one-file change:

```python
Indicator(
    "ICSA", "Initial Jobless Claims", "Initial Claims",
    Klass.LEADING, Freq.WEEKLY, Transform.YOY_PCT, "%",
    polarity=-1,        # rising claims are BAD
    weight=1.2,         # weight inside the leading composite
    risk_weight=1.2,    # weight in the risk score (0 = excluded)
    tags=("labour",),   # drives pillar assignment
)
```

Then run `python scripts/validate_series.py` to confirm it resolves and is live,
and `python scripts/backtest.py` to check you haven't degraded the classifier.
