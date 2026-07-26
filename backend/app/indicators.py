"""
FRED series registry.

Every indicator the application knows about is declared here exactly once.
The registry drives fetching, caching, transformation, composite construction,
and the frontend metric cards -- nothing downstream hardcodes a series ID.

Key fields
----------
klass      : LEADING | COINCIDENT | LAGGING  (business-cycle timing)
transform  : how the raw level is turned into a comparable signal
polarity   : +1 if "up is economically good", -1 if "up is bad"
             (unemployment, initial claims, credit spreads are -1)
weight     : contribution inside its own composite (weights are normalised
             per composite at runtime, so they need not sum to 1 here)
risk_weight: contribution to the systemic-risk score (0 = not a risk input)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Klass(str, Enum):
    LEADING = "leading"
    COINCIDENT = "coincident"
    LAGGING = "lagging"
    # Not part of the cycle clock -- pure stress / policy context.
    FINANCIAL = "financial"


class Transform(str, Enum):
    LEVEL = "level"              # use the raw value (rates, spreads, indexes)
    YOY_PCT = "yoy_pct"          # % change vs. same period one year ago
    MOM_PCT = "mom_pct"          # % change vs. prior period
    MOM_DIFF = "mom_diff"        # absolute change vs. prior period
    CHG_3M = "chg_3m"            # absolute change vs. 3 periods ago
    CHG_12M = "chg_12m"          # absolute change vs. 12 periods ago
    ANNUALISED_3M = "ann_3m"     # 3-period % change, annualised (inflation runrate)


class Freq(str, Enum):
    DAILY = "d"
    WEEKLY = "w"
    MONTHLY = "m"
    QUARTERLY = "q"


@dataclass(frozen=True)
class Indicator:
    series_id: str
    name: str
    short: str                       # label for compact metric cards
    klass: Klass
    freq: Freq
    transform: Transform
    unit: str
    polarity: int = 1
    weight: float = 1.0
    risk_weight: float = 0.0
    # Rolling window (in observations) used for the z-score. Longer windows for
    # slow series; ~10y of history is the target for all of them.
    z_window: int = 120
    # Optional hard reference level used by the alert engine.
    alert_below: float | None = None
    alert_above: float | None = None
    notes: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def key(self) -> str:
        return self.series_id


# ---------------------------------------------------------------------------
# LEADING -- turn ahead of the cycle. These drive the "where are we going"
# half of the cycle clock and carry most of the early-warning risk weight.
# ---------------------------------------------------------------------------
LEADING: list[Indicator] = [
    Indicator(
        "T10Y2Y", "10Y minus 2Y Treasury Spread", "10Y-2Y Curve",
        Klass.LEADING, Freq.DAILY, Transform.LEVEL, "pp",
        polarity=1, weight=1.4, risk_weight=1.5, z_window=2600,
        alert_below=0.0,
        notes="Inversion has preceded every US recession since 1970 by 6-24 months.",
        tags=("yield-curve", "headline"),
    ),
    Indicator(
        "T10Y3M", "10Y minus 3M Treasury Spread", "10Y-3M Curve",
        Klass.LEADING, Freq.DAILY, Transform.LEVEL, "pp",
        polarity=1, weight=1.4, risk_weight=2.0, z_window=2600,
        alert_below=0.0,
        notes="NY Fed's preferred recession-probability input; cleaner signal than 10Y-2Y.",
        tags=("yield-curve", "headline"),
    ),
    Indicator(
        "ICSA", "Initial Jobless Claims (SA)", "Initial Claims",
        Klass.LEADING, Freq.WEEKLY, Transform.YOY_PCT, "%",
        polarity=-1, weight=1.2, risk_weight=1.2, z_window=260,
        notes="Highest-frequency read on labour demand. Rising = deteriorating.",
        tags=("labour", "headline"),
    ),
    Indicator(
        "PERMIT", "New Private Housing Units Authorized by Permit", "Building Permits",
        Klass.LEADING, Freq.MONTHLY, Transform.YOY_PCT, "%",
        polarity=1, weight=1.0, risk_weight=0.6,
        notes="Most rate-sensitive real-economy series; leads construction employment.",
        tags=("housing",),
    ),
    Indicator(
        "HOUST", "Housing Starts", "Housing Starts",
        Klass.LEADING, Freq.MONTHLY, Transform.YOY_PCT, "%",
        polarity=1, weight=0.7,
        tags=("housing",),
    ),
    Indicator(
        "NEWORDER", "Core Capital Goods New Orders (ex-aircraft)", "Core Capex Orders",
        Klass.LEADING, Freq.MONTHLY, Transform.YOY_PCT, "%",
        polarity=1, weight=1.0, risk_weight=0.5,
        notes="Business investment intentions; leads equipment spending in GDP.",
        tags=("business-investment",),
    ),
    Indicator(
        "AWHMAN", "Average Weekly Hours, Manufacturing", "Mfg Weekly Hours",
        Klass.LEADING, Freq.MONTHLY, Transform.CHG_12M, "hrs",
        polarity=1, weight=0.8,
        notes="Firms cut hours before they cut heads -- a classic Conference Board LEI input.",
        tags=("labour", "manufacturing"),
    ),
    Indicator(
        "UMCSENT", "U. Michigan Consumer Sentiment", "Consumer Sentiment",
        Klass.LEADING, Freq.MONTHLY, Transform.LEVEL, "index",
        polarity=1, weight=0.7,
        tags=("consumer",),
    ),
    Indicator(
        "BBKMLEIX", "Brave-Butters-Kelley Leading Index", "BBK Leading Index",
        Klass.LEADING, Freq.MONTHLY, Transform.LEVEL, "std dev",
        polarity=1, weight=1.2, risk_weight=0.8,
        alert_below=0.0,
        notes=(
            "Chicago Fed dynamic-factor leading index, in standard deviations from "
            "trend growth. Replaces the Philadelphia Fed USSLIND, which FRED "
            "discontinued in February 2020 -- do not reintroduce it."
        ),
        tags=("composite", "headline"),
    ),
    Indicator(
        "SP500", "S&P 500 Index", "S&P 500",
        Klass.LEADING, Freq.DAILY, Transform.YOY_PCT, "%",
        polarity=1, weight=0.6, z_window=1300,
        notes="FRED only serves the trailing 10 years for this series.",
        tags=("markets",),
    ),
    Indicator(
        "M2REAL", "Real M2 Money Stock", "Real M2",
        Klass.LEADING, Freq.MONTHLY, Transform.YOY_PCT, "%",
        polarity=1, weight=0.6, risk_weight=0.4,
        notes="Real liquidity growth; sharply negative readings precede credit contraction.",
        tags=("monetary",),
    ),
]

# ---------------------------------------------------------------------------
# COINCIDENT -- these define "where are we now". NBER's dating committee
# effectively watches this exact list.
# ---------------------------------------------------------------------------
COINCIDENT: list[Indicator] = [
    Indicator(
        "PAYEMS", "All Employees, Total Nonfarm", "Nonfarm Payrolls",
        Klass.COINCIDENT, Freq.MONTHLY, Transform.MOM_DIFF, "k jobs",
        polarity=1, weight=1.6, risk_weight=1.0,
        alert_below=0.0,
        notes="The single most important monthly release. MoM diff = jobs added (thousands).",
        tags=("labour", "headline", "nber"),
    ),
    Indicator(
        "INDPRO", "Industrial Production Index", "Industrial Production",
        Klass.COINCIDENT, Freq.MONTHLY, Transform.YOY_PCT, "%",
        polarity=1, weight=1.2, risk_weight=0.6,
        tags=("manufacturing", "headline", "nber"),
    ),
    Indicator(
        "W875RX1", "Real Personal Income excl. Transfer Receipts", "Real Income ex-Transfers",
        Klass.COINCIDENT, Freq.MONTHLY, Transform.YOY_PCT, "%",
        polarity=1, weight=1.2,
        notes="NBER coincident series -- strips out stimulus/benefit distortions.",
        tags=("consumer", "nber"),
    ),
    Indicator(
        "CMRMTSPL", "Real Manufacturing & Trade Industries Sales", "Real Mfg & Trade Sales",
        Klass.COINCIDENT, Freq.MONTHLY, Transform.YOY_PCT, "%",
        polarity=1, weight=1.0,
        tags=("nber",),
    ),
    Indicator(
        "PCEC96", "Real Personal Consumption Expenditures", "Real Consumer Spending",
        Klass.COINCIDENT, Freq.MONTHLY, Transform.YOY_PCT, "%",
        polarity=1, weight=1.2,
        notes="~68% of GDP. The consumer is the cycle.",
        tags=("consumer", "headline"),
    ),
    Indicator(
        "RSAFS", "Advance Retail Sales: Retail & Food Services", "Retail Sales",
        Klass.COINCIDENT, Freq.MONTHLY, Transform.YOY_PCT, "%",
        polarity=1, weight=0.8,
        notes="Nominal -- deflate against CPI before drawing conclusions in high-inflation regimes.",
        tags=("consumer",),
    ),
    Indicator(
        "GDPC1", "Real Gross Domestic Product", "Real GDP",
        Klass.COINCIDENT, Freq.QUARTERLY, Transform.YOY_PCT, "%",
        polarity=1, weight=1.5, risk_weight=0.8, z_window=80,
        notes="Quarterly and heavily revised -- context, not a timing signal.",
        tags=("headline", "gdp"),
    ),
    Indicator(
        "TCU", "Capacity Utilization: Total Industry", "Capacity Utilization",
        Klass.COINCIDENT, Freq.MONTHLY, Transform.LEVEL, "%",
        polarity=1, weight=0.8,
        notes="Above ~80% signals late-cycle capacity pressure and capex demand.",
        tags=("manufacturing", "slack"),
    ),
    Indicator(
        "USPHCI", "Coincident Economic Activity Index for the US", "Coincident Activity Index",
        Klass.COINCIDENT, Freq.MONTHLY, Transform.YOY_PCT, "%",
        polarity=1, weight=1.0,
        tags=("composite",),
    ),
    Indicator(
        "CFNAIMA3", "Chicago Fed National Activity Index (3-Month MA)", "CFNAI 3M Avg",
        Klass.COINCIDENT, Freq.MONTHLY, Transform.LEVEL, "std dev",
        polarity=1, weight=1.5, risk_weight=1.2,
        alert_below=-0.70,
        notes=(
            "Weighted average of 85 activity indicators; 0 = trend growth. The "
            "Chicago Fed's own rule: crossing below -0.70 signals recession onset, "
            "rising above +0.20 signals the expansion has resumed."
        ),
        tags=("composite", "headline"),
    ),
    Indicator(
        "CFNAIDIFF", "CFNAI Diffusion Index", "CFNAI Diffusion",
        Klass.COINCIDENT, Freq.MONTHLY, Transform.LEVEL, "index",
        polarity=1, weight=1.0, risk_weight=0.8,
        alert_below=-0.35,
        notes=(
            "Share of the 85 CFNAI components making a positive contribution. "
            "Measures how BROAD weakness is, not just how deep -- the key "
            "distinction between a sector slowdown and a genuine recession."
        ),
        tags=("composite", "breadth"),
    ),
    Indicator(
        "BBKMCOIX", "Brave-Butters-Kelley Coincident Index", "BBK Coincident Index",
        Klass.COINCIDENT, Freq.MONTHLY, Transform.LEVEL, "std dev",
        polarity=1, weight=1.0,
        tags=("composite",),
    ),
]

# ---------------------------------------------------------------------------
# LAGGING -- confirm the cycle after the fact and describe the policy regime.
# Lagging indicators are where inflation and the Fed live.
# ---------------------------------------------------------------------------
LAGGING: list[Indicator] = [
    Indicator(
        "UNRATE", "Unemployment Rate", "Unemployment Rate",
        Klass.LAGGING, Freq.MONTHLY, Transform.LEVEL, "%",
        polarity=-1, weight=1.5, risk_weight=0.8,
        alert_above=5.0,
        notes="Lags the cycle badly at turning points -- use the Sahm gap for timing.",
        tags=("labour", "headline"),
    ),
    Indicator(
        "U6RATE", "U-6 Total Unemployed + Marginally Attached + Part-Time", "U-6 Underemployment",
        Klass.LAGGING, Freq.MONTHLY, Transform.LEVEL, "%",
        polarity=-1, weight=0.7,
        notes="Broadest labour-slack measure; widens vs. U-3 early in downturns.",
        tags=("labour",),
    ),
    Indicator(
        "CPIAUCSL", "Consumer Price Index, All Urban Consumers", "Headline CPI",
        Klass.LAGGING, Freq.MONTHLY, Transform.YOY_PCT, "%",
        polarity=-1, weight=1.2, risk_weight=0.6,
        alert_above=3.0,
        tags=("inflation", "headline"),
    ),
    Indicator(
        "CPILFESL", "CPI Less Food & Energy", "Core CPI",
        Klass.LAGGING, Freq.MONTHLY, Transform.YOY_PCT, "%",
        polarity=-1, weight=1.2, risk_weight=0.6,
        alert_above=3.0,
        tags=("inflation", "headline"),
    ),
    Indicator(
        "PCEPILFE", "Core PCE Price Index", "Core PCE",
        Klass.LAGGING, Freq.MONTHLY, Transform.YOY_PCT, "%",
        polarity=-1, weight=1.4, risk_weight=0.8,
        alert_above=2.5,
        notes="The Fed's actual 2% target variable. This is the one that moves policy.",
        tags=("inflation", "headline", "fed-target"),
    ),
    Indicator(
        "CORESTICKM159SFRBATL", "Atlanta Fed Sticky-Price CPI (Core)", "Sticky Core CPI",
        Klass.LAGGING, Freq.MONTHLY, Transform.LEVEL, "%",
        polarity=-1, weight=0.8, risk_weight=0.4,
        notes="Prices that reset infrequently -- proxy for embedded inflation expectations.",
        tags=("inflation",),
    ),
    Indicator(
        "FEDFUNDS", "Effective Federal Funds Rate (monthly avg)", "Fed Funds Rate",
        Klass.LAGGING, Freq.MONTHLY, Transform.LEVEL, "%",
        polarity=-1, weight=1.0, risk_weight=0.5,
        notes="Policy stance. Judge restrictiveness as FEDFUNDS minus core PCE YoY.",
        tags=("policy", "headline"),
    ),
    Indicator(
        "CIVPART", "Labor Force Participation Rate", "Participation Rate",
        Klass.LAGGING, Freq.MONTHLY, Transform.LEVEL, "%",
        polarity=1, weight=0.5,
        tags=("labour",),
    ),
    Indicator(
        "ULCNFB", "Unit Labor Costs, Nonfarm Business", "Unit Labor Costs",
        Klass.LAGGING, Freq.QUARTERLY, Transform.YOY_PCT, "%",
        polarity=-1, weight=0.6, z_window=80,
        notes="Wage-price pressure net of productivity -- a true lagging confirmation.",
        tags=("inflation", "labour"),
    ),
    Indicator(
        "TOTCI", "Commercial & Industrial Loans, All Commercial Banks", "C&I Loans",
        Klass.LAGGING, Freq.WEEKLY, Transform.YOY_PCT, "%",
        polarity=1, weight=0.7, risk_weight=0.5, z_window=260,
        notes="Bank credit to business. Contraction is a classic lagging recession confirmation.",
        tags=("credit",),
    ),
    Indicator(
        "CSUSHPINSA", "S&P CoreLogic Case-Shiller US National Home Price Index", "Home Prices",
        Klass.LAGGING, Freq.MONTHLY, Transform.YOY_PCT, "%",
        polarity=1, weight=0.5,
        tags=("housing", "asset-prices"),
    ),
]

# ---------------------------------------------------------------------------
# FINANCIAL / SYSTEMIC STRESS -- excluded from the cycle clock (they are
# market prices, not activity) but they carry the heaviest risk weights.
# ---------------------------------------------------------------------------
FINANCIAL: list[Indicator] = [
    Indicator(
        "NFCI", "Chicago Fed National Financial Conditions Index", "Financial Conditions",
        Klass.FINANCIAL, Freq.WEEKLY, Transform.LEVEL, "std dev",
        polarity=-1, weight=1.0, risk_weight=1.5, z_window=520,
        alert_above=0.0,
        notes="Zero = average conditions. Positive = tighter than average.",
        tags=("stress", "headline"),
    ),
    Indicator(
        "ANFCI", "Chicago Fed Adjusted National Financial Conditions Index", "Adjusted Fin. Conditions",
        Klass.FINANCIAL, Freq.WEEKLY, Transform.LEVEL, "std dev",
        polarity=-1, weight=0.8, risk_weight=1.0, z_window=520,
        alert_above=0.0,
        notes=(
            "NFCI with the business-cycle component regressed out. Answers "
            "'are conditions tight RELATIVE to where the economy is?' -- which is "
            "the question that matters when judging policy-driven stress."
        ),
        tags=("stress",),
    ),
    Indicator(
        "STLFSI4", "St. Louis Fed Financial Stress Index", "Financial Stress",
        Klass.FINANCIAL, Freq.WEEKLY, Transform.LEVEL, "std dev",
        polarity=-1, weight=0.8, risk_weight=1.0, z_window=520,
        alert_above=1.0,
        tags=("stress",),
    ),
    Indicator(
        "BAMLH0A0HYM2", "ICE BofA US High Yield Option-Adjusted Spread", "HY Credit Spread",
        Klass.FINANCIAL, Freq.DAILY, Transform.LEVEL, "pp",
        polarity=-1, weight=1.2, risk_weight=1.8, z_window=2600,
        alert_above=6.0,
        notes="The market's real-time default-risk premium. Blows out before defaults arrive.",
        tags=("credit", "stress", "headline"),
    ),
    Indicator(
        "BAMLC0A0CM", "ICE BofA US Corporate Index OAS (IG)", "IG Credit Spread",
        Klass.FINANCIAL, Freq.DAILY, Transform.LEVEL, "pp",
        polarity=-1, weight=0.8, risk_weight=0.8, z_window=2600,
        tags=("credit", "stress"),
    ),
    Indicator(
        "DRSFRMACBS", "Delinquency Rate: Single-Family Residential Mortgages", "Mortgage Delinquency",
        Klass.FINANCIAL, Freq.QUARTERLY, Transform.LEVEL, "%",
        polarity=-1, weight=0.6, risk_weight=0.6, z_window=80,
        tags=("credit", "household"),
    ),
    Indicator(
        "DRCCLACBS", "Delinquency Rate: Credit Card Loans, All Banks", "Credit Card Delinquency",
        Klass.FINANCIAL, Freq.QUARTERLY, Transform.LEVEL, "%",
        polarity=-1, weight=0.7, risk_weight=0.9, z_window=80,
        notes="Leads consumer retrenchment; the household-balance-sheet canary.",
        tags=("credit", "household"),
    ),
    Indicator(
        "TDSP", "Household Debt Service Ratio", "Debt Service Ratio",
        Klass.FINANCIAL, Freq.QUARTERLY, Transform.LEVEL, "%",
        polarity=-1, weight=0.5, risk_weight=0.4, z_window=80,
        tags=("household", "leverage"),
    ),
    Indicator(
        "DRTSCILM", "Net % of Banks Tightening C&I Standards (Large/Medium Firms)", "Bank Lending Standards",
        Klass.FINANCIAL, Freq.QUARTERLY, Transform.LEVEL, "net %",
        polarity=-1, weight=1.0, risk_weight=1.2, z_window=80,
        alert_above=20.0,
        notes="SLOOS. Above ~20% net tightening has preceded every recession since 1990.",
        tags=("credit", "stress", "headline"),
    ),
    Indicator(
        "T10YIE", "10-Year Breakeven Inflation Rate", "10Y Breakeven",
        Klass.FINANCIAL, Freq.DAILY, Transform.LEVEL, "%",
        polarity=1, weight=0.5, risk_weight=0.3, z_window=2600,
        notes="Market-implied inflation expectations. De-anchoring in either direction is a risk.",
        tags=("inflation", "markets"),
    ),
    Indicator(
        "WALCL", "Total Assets, Federal Reserve Balance Sheet", "Fed Balance Sheet",
        Klass.FINANCIAL, Freq.WEEKLY, Transform.YOY_PCT, "%",
        polarity=1, weight=0.4, z_window=260,
        notes="QT/QE liquidity impulse.",
        tags=("monetary", "policy"),
    ),
]

# ---------------------------------------------------------------------------
# DIRECT RECESSION / RULE-BASED SIGNALS
# Not composited -- consumed verbatim by the risk engine and the alert engine.
# ---------------------------------------------------------------------------
RECESSION_SIGNALS: list[Indicator] = [
    Indicator(
        "SAHMREALTIME", "Sahm Rule Recession Indicator (Real-Time)", "Sahm Rule Gap",
        Klass.FINANCIAL, Freq.MONTHLY, Transform.LEVEL, "pp",
        polarity=-1, weight=0.0, risk_weight=2.0,
        alert_above=0.50,
        notes="3m avg U-3 minus its trailing 12m low. >= 0.50 has meant recession, every time.",
        tags=("recession", "labour", "headline"),
    ),
    Indicator(
        "RECPROUSM156N", "Smoothed US Recession Probabilities", "Recession Probability",
        Klass.FINANCIAL, Freq.MONTHLY, Transform.LEVEL, "%",
        polarity=-1, weight=0.0, risk_weight=1.5,
        alert_above=20.0,
        notes="Chauvet-Piger dynamic-factor Markov-switching model.",
        tags=("recession", "headline"),
    ),
    Indicator(
        "USREC", "NBER Recession Indicator (0/1)", "NBER Recession",
        Klass.FINANCIAL, Freq.MONTHLY, Transform.LEVEL, "0/1",
        polarity=-1, weight=0.0, risk_weight=0.0,
        notes="Ground truth for backtesting. Published with a long lag -- never a live signal.",
        tags=("recession", "backtest"),
    ),
]


ALL_INDICATORS: list[Indicator] = (
    LEADING + COINCIDENT + LAGGING + FINANCIAL + RECESSION_SIGNALS
)

BY_ID: dict[str, Indicator] = {i.series_id: i for i in ALL_INDICATORS}

# Composites used by the cycle clock. FINANCIAL is deliberately excluded --
# it feeds risk, not the growth/inflation phase decision.
COMPOSITE_MEMBERS: dict[Klass, list[Indicator]] = {
    Klass.LEADING: LEADING,
    Klass.COINCIDENT: COINCIDENT,
    Klass.LAGGING: LAGGING,
    Klass.FINANCIAL: FINANCIAL,
}

# Series shown on the dashboard's headline card row, in display order.
#
# Six, deliberately: growth, labour, two inflation gauges, and policy. The
# spreads and model-derived series that used to sit on a second row (T10Y2Y,
# T10Y3M, CFNAIMA3, SAHMREALTIME, BAMLH0A0HYM2, NFCI) are all still fetched,
# scored and alerted on -- they are risk-model inputs and appear in the risk
# breakdown. They are simply not headline cards; the curve now has its own
# chart on the Markets tab, which reads better than two cards ever did.
HEADLINE_IDS: tuple[str, ...] = (
    "GDPC1", "UNRATE", "PAYEMS", "CPILFESL", "PCEPILFE", "FEDFUNDS",
)


def by_class(klass: Klass) -> list[Indicator]:
    return [i for i in ALL_INDICATORS if i.klass == klass]


def risk_inputs() -> list[Indicator]:
    return [i for i in ALL_INDICATORS if i.risk_weight > 0]
