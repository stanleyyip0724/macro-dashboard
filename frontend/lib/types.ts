// Mirrors backend/app/schemas.py. Keep the two in sync -- or generate this
// file from the OpenAPI schema FastAPI already publishes at /openapi.json:
//   npx openapi-typescript http://localhost:8000/openapi.json -o lib/types.ts

export type Point = { date: string; value: number };

export type Klass = "leading" | "coincident" | "lagging" | "financial";

export interface IndicatorCard {
  series_id: string;
  name: string;
  short: string;
  klass: Klass;
  unit: string;
  transform: string;
  frequency: string;
  /** +1 if a rising value is good for the economy, -1 if it is bad. */
  polarity: number;
  latest_raw: number | null;
  latest_value: number | null;
  latest_z: number | null;
  /** Polarity-adjusted z-score: positive is ALWAYS good, whatever the series. */
  signal: number | null;
  change_3m: number | null;
  change_12m: number | null;
  as_of: string | null;
  notes: string;
  tags: string[];
  sparkline: Point[];
}

export interface SeriesDetail extends IndicatorCard {
  raw_history: Point[];
  transformed_history: Point[];
  zscore_history: Point[];
}

export type Phase =
  | "Expansion"
  | "Peak"
  | "Contraction"
  | "Trough"
  | "Recovery";

export interface PhaseSignal {
  name: string;
  fired: boolean;
  value: number | null;
  threshold: number;
  detail: string;
}

export interface CyclePoint {
  date: string;
  level: number;
  momentum: number;
  phase: Phase;
}

export interface Cycle {
  phase: Phase;
  description: string;
  confidence: number;
  growth_level: number | null;
  growth_momentum: number | null;
  inflation_pressure: number | null;
  breadth: number | null;
  composites: Record<string, number | null>;
  coverage: Record<string, { coverage: number; members: number; as_of?: string }>;
  hard_signals: PhaseSignal[];
  rationale: string[];
  history: CyclePoint[];
}

export interface RiskContribution {
  series_id: string;
  name: string;
  short: string;
  pillar: string;
  weight: number;
  zscore: number;
  badness: number;
  subscore: number;
  contribution: number;
  latest_value: number | null;
  latest_date: string | null;
  unit: string;
}

export interface RiskTrigger {
  name: string;
  fired: boolean;
  value: number | null;
  threshold: string;
  points: number;
  detail: string;
}

export type RiskBand = "Low" | "Moderate" | "Elevated" | "High" | "Severe";

export interface Risk {
  score: number;
  band: RiskBand;
  band_description: string;
  base_score: number;
  trigger_bonus: number;
  coverage: number;
  pillars: Record<string, number>;
  pillar_weights: Record<string, number>;
  contributions: RiskContribution[];
  triggers: RiskTrigger[];
  top_drivers: string[];
}

export type Severity = "critical" | "warning" | "info";

export interface Alert {
  id: string;
  severity: Severity;
  kind: "threshold" | "statistical" | "velocity";
  series_id: string;
  title: string;
  message: string;
  value: number | null;
  threshold: number | null;
  unit: string;
  as_of: string | null;
}

export interface CompositeSeries {
  name: string;
  points: Point[];
}

export interface Summary {
  generated_at: string;
  data_as_of: string | null;
  cycle: Cycle;
  risk: Risk;
  alerts: Alert[];
  headline: IndicatorCard[];
  composites: CompositeSeries[];
  missing_series: string[];
  coverage_note: string;
}
