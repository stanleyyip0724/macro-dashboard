"""
Registry of tradable instruments shown on the markets side of the dashboard.

Kept deliberately separate from `app.indicators`: those series feed the cycle
classifier and the systemic-risk score, and adding market prices to that
registry would silently change both models. Nothing here touches them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Group(str, Enum):
    INDEX = "index"
    SECTOR = "sector"
    COMMODITY = "commodity"
    CRYPTO = "crypto"
    FX = "fx"
    VOL = "volatility"


@dataclass(frozen=True)
class Instrument:
    symbol: str          # Yahoo Finance symbol
    name: str
    short: str
    group: Group
    region: str = ""
    unit: str = ""
    # Weight used to size the tree-map tile. Relative, not a real market cap --
    # it only controls how much visual area the tile gets.
    size: float = 1.0
    # +1 when a rising price is "risk-on", -1 when it signals stress.
    risk_polarity: int = 1
    notes: str = ""


INDICES: list[Instrument] = [
    Instrument("^GSPC", "S&P 500", "S&P 500", Group.INDEX, "United States",
               size=10, notes="Broad US large cap; the global risk benchmark."),
    Instrument("^NDX", "Nasdaq 100", "Nasdaq 100", Group.INDEX, "United States",
               size=8, notes="US mega-cap technology; the long-duration equity trade."),
    Instrument("^DJI", "Dow Jones Industrial Average", "Dow Jones", Group.INDEX,
               "United States", size=6,
               notes="Price-weighted US industrials and old-economy cyclicals."),
    Instrument("^RUT", "Russell 2000", "Russell 2000", Group.INDEX, "United States",
               size=3,
               notes="US small caps -- domestic demand and floating-rate debt sensitivity."),
    Instrument("^STOXX50E", "Euro Stoxx 50", "Euro Stoxx 50", Group.INDEX, "Europe",
               size=4, notes="Euro-area large cap."),
    Instrument("^FTSE", "FTSE 100", "FTSE 100", Group.INDEX, "United Kingdom",
               size=3, notes="UK large cap; commodity and financials heavy."),
    Instrument("^N225", "Nikkei 225", "Nikkei 225", Group.INDEX, "Japan",
               size=5, notes="Japan large cap; highly sensitive to USD/JPY."),
    Instrument("^HSI", "Hang Seng", "Hang Seng", Group.INDEX, "Hong Kong",
               size=4, notes="Hong Kong listings; China growth and policy proxy."),
    Instrument("000001.SS", "Shanghai Composite", "Shanghai Comp", Group.INDEX,
               "China", size=4, notes="Onshore China A-shares."),
    Instrument("^KS11", "KOSPI", "KOSPI", Group.INDEX, "South Korea", size=3,
               notes="Korea; memory/semis exports lead the global goods cycle."),
    Instrument("^TWII", "Taiwan Weighted", "Taiwan TAIEX", Group.INDEX, "Taiwan",
               size=3, notes="Taiwan; the foundry end of the AI supply chain."),
    Instrument("^BSESN", "BSE Sensex", "Sensex", Group.INDEX, "India", size=3,
               notes="India large cap; domestic-demand driven."),
]

# US equity sectors, via the SPDR Select Sector funds -- the standard liquid
# proxy for GICS sector performance. `size` is roughly each sector's weight in
# the S&P 500, so the tree map's areas match where the index's risk actually
# sits rather than treating all eleven as equals.
#
# `cyclical` drives the rotation read in narrative.py: defensives leading is a
# different market from cyclicals leading, even at the same index level.
SECTORS: list[Instrument] = [
    Instrument("XLK", "Technology (XLK)", "Technology", Group.SECTOR, "United States",
               size=32, notes="Semis, software, hardware. Longest duration in the index."),
    Instrument("XLF", "Financials (XLF)", "Financials", Group.SECTOR, "United States",
               size=14, notes="Banks, insurers, exchanges. Levered to the curve's slope."),
    Instrument("XLV", "Health care (XLV)", "Health care", Group.SECTOR, "United States",
               size=10, notes="Defensive; policy and pricing risk rather than cycle risk."),
    Instrument("XLY", "Consumer discretionary (XLY)", "Cons. discretionary", Group.SECTOR,
               "United States", size=10,
               notes="The purest read on household spending capacity."),
    Instrument("XLC", "Communication services (XLC)", "Communications", Group.SECTOR,
               "United States", size=10, notes="Mega-cap platforms and advertising spend."),
    Instrument("XLI", "Industrials (XLI)", "Industrials", Group.SECTOR, "United States",
               size=8, notes="Capex, freight and defence — the goods-cycle sector."),
    Instrument("XLP", "Consumer staples (XLP)", "Cons. staples", Group.SECTOR,
               "United States", size=5,
               notes="Defensive; leads when investors doubt the growth outlook."),
    Instrument("XLE", "Energy (XLE)", "Energy", Group.SECTOR, "United States", size=3,
               notes="Tracks crude with a lag; the natural hedge against oil-led inflation."),
    Instrument("XLU", "Utilities (XLU)", "Utilities", Group.SECTOR, "United States",
               size=3, notes="Bond proxy — and now an AI-power-demand story as well."),
    Instrument("XLRE", "Real estate (XLRE)", "Real estate", Group.SECTOR, "United States",
               size=2, notes="The most rate-sensitive sector in the index."),
    Instrument("XLB", "Materials (XLB)", "Materials", Group.SECTOR, "United States",
               size=2, notes="Chemicals, metals, packaging — early-cycle input demand."),
]

# Sectors that lead when growth expectations are rising, used for the rotation read.
CYCLICAL_SECTORS = {"XLK", "XLF", "XLY", "XLI", "XLB", "XLE"}
DEFENSIVE_SECTORS = {"XLP", "XLV", "XLU", "XLRE"}

VOL: list[Instrument] = [
    Instrument("^VIX", "CBOE Volatility Index", "VIX", Group.VOL, "United States",
               unit="vol pts", size=2, risk_polarity=-1,
               notes="30-day implied vol on the S&P 500; the equity fear gauge."),
]

COMMODITIES: list[Instrument] = [
    Instrument("GC=F", "Gold futures", "Gold", Group.COMMODITY, unit="$/oz", size=6,
               notes="Real-rate and debasement hedge; also a geopolitical bid."),
    Instrument("SI=F", "Silver futures", "Silver", Group.COMMODITY, unit="$/oz", size=3,
               notes="Half precious metal, half industrial -- solar and electronics demand."),
    Instrument("CL=F", "WTI crude futures", "WTI Crude", Group.COMMODITY, unit="$/bbl",
               size=6, notes="US crude benchmark; the fastest channel into headline CPI."),
    Instrument("BZ=F", "Brent crude futures", "Brent Crude", Group.COMMODITY,
               unit="$/bbl", size=4, notes="Global crude benchmark."),
    Instrument("HG=F", "Copper futures", "Copper", Group.COMMODITY, unit="$/lb", size=4,
               notes="'Dr Copper' -- global industrial and construction activity."),
    Instrument("NG=F", "Natural gas futures", "Nat Gas", Group.COMMODITY, unit="$/MMBtu",
               size=3, notes="US gas; power prices and industrial input costs."),
]

CRYPTO: list[Instrument] = [
    Instrument("BTC-USD", "Bitcoin", "Bitcoin", Group.CRYPTO, unit="$", size=6,
               notes="Highest-beta expression of global liquidity and risk appetite."),
    Instrument("ETH-USD", "Ethereum", "Ethereum", Group.CRYPTO, unit="$", size=3,
               notes="Second-largest crypto asset; tracks BTC with more beta."),
]

FX: list[Instrument] = [
    Instrument("DX-Y.NYB", "US Dollar Index", "Dollar Index", Group.FX,
               unit="index", size=6, risk_polarity=-1,
               notes="Trade-weighted USD. A stronger dollar tightens global financial conditions."),
    Instrument("EURUSD=X", "Euro / US Dollar", "EUR/USD", Group.FX, unit="rate", size=4),
    Instrument("USDJPY=X", "US Dollar / Japanese Yen", "USD/JPY", Group.FX,
               unit="rate", size=4,
               notes="The carry-trade barometer; sharp yen strength unwinds global risk."),
    Instrument("GBPUSD=X", "Pound / US Dollar", "GBP/USD", Group.FX, unit="rate", size=2),
    Instrument("USDCNY=X", "US Dollar / Chinese Yuan", "USD/CNY", Group.FX,
               unit="rate", size=3,
               notes="PBoC-managed; a weaker yuan exports disinflation and pressures Asian FX."),
    Instrument("USDKRW=X", "US Dollar / Korean Won", "USD/KRW", Group.FX,
               unit="rate", size=2,
               notes="High-beta Asian FX; weakens when the global tech cycle rolls over."),
]

ALL: list[Instrument] = INDICES + SECTORS + VOL + COMMODITIES + CRYPTO + FX
BY_SYMBOL: dict[str, Instrument] = {i.symbol: i for i in ALL}

# The US Treasury curve, pulled from FRED (not Yahoo) because FRED publishes the
# full constant-maturity set as one consistent daily vintage.
CURVE_TENORS: list[tuple[str, str, float]] = [
    ("DGS1MO", "1M", 1 / 12),
    ("DGS3MO", "3M", 0.25),
    ("DGS6MO", "6M", 0.5),
    ("DGS1", "1Y", 1),
    ("DGS2", "2Y", 2),
    ("DGS3", "3Y", 3),
    ("DGS5", "5Y", 5),
    ("DGS7", "7Y", 7),
    ("DGS10", "10Y", 10),
    ("DGS20", "20Y", 20),
    ("DGS30", "30Y", 30),
]
