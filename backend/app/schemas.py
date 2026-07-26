"""Pydantic response models -- the contract the frontend codes against."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Point(BaseModel):
    date: str
    value: float


class IndicatorCard(BaseModel):
    series_id: str
    name: str
    short: str
    klass: str
    unit: str
    transform: str
    frequency: str
    polarity: int
    latest_raw: float | None
    latest_value: float | None = Field(
        None, description="Transformed value -- the number shown on the card"
    )
    latest_z: float | None
    signal: float | None = Field(
        None, description="Polarity-adjusted z-score; positive is always good"
    )
    change_3m: float | None
    change_12m: float | None
    as_of: str | None
    notes: str
    tags: list[str]
    sparkline: list[Point] = []


class SeriesDetail(IndicatorCard):
    raw_history: list[Point]
    transformed_history: list[Point]
    zscore_history: list[Point]


class PhaseSignalOut(BaseModel):
    name: str
    fired: bool
    value: float | None
    threshold: float
    detail: str


class CyclePoint(BaseModel):
    date: str
    level: float
    momentum: float
    phase: str


class CycleOut(BaseModel):
    phase: str
    description: str
    confidence: float
    growth_level: float | None
    growth_momentum: float | None
    inflation_pressure: float | None
    breadth: float | None
    composites: dict[str, float | None]
    coverage: dict[str, dict]
    hard_signals: list[PhaseSignalOut]
    rationale: list[str]
    history: list[CyclePoint]


class RiskContributionOut(BaseModel):
    series_id: str
    name: str
    short: str
    pillar: str
    weight: float
    zscore: float
    badness: float
    subscore: float
    contribution: float
    latest_value: float | None
    latest_date: str | None
    unit: str


class RiskTriggerOut(BaseModel):
    name: str
    fired: bool
    value: float | None
    threshold: str
    points: float
    detail: str


class RiskOut(BaseModel):
    score: float
    band: str
    band_description: str
    base_score: float
    trigger_bonus: float
    coverage: float
    pillars: dict[str, float]
    pillar_weights: dict[str, float]
    contributions: list[RiskContributionOut]
    triggers: list[RiskTriggerOut]
    top_drivers: list[str]


class AlertOut(BaseModel):
    id: str
    severity: str
    kind: str
    series_id: str
    title: str
    message: str
    value: float | None
    threshold: float | None
    unit: str
    as_of: str | None


class CompositeSeries(BaseModel):
    name: str
    points: list[Point]


class SummaryOut(BaseModel):
    generated_at: str
    data_as_of: str | None
    cycle: CycleOut
    risk: RiskOut
    alerts: list[AlertOut]
    headline: list[IndicatorCard]
    composites: list[CompositeSeries]
    missing_series: list[str]
    coverage_note: str


class HealthOut(BaseModel):
    status: str
    series_registered: int
    series_cached: int
    missing_series: list[str]
    last_refresh: str | None
    refresh_errors: dict[str, str]
    cache: dict
