// Types and hooks for the markets side of the dashboard.
//
// Every field is optional or defaulted on purpose: the backend assembles this
// payload from four independent public sources and any one of them can come
// back empty. The UI must render a partial page, never an error page.

import useSWR from "swr";

import { API_BASE } from "./api";

export type Point = { date: string; value: number };

export type Horizon = "1d" | "1w" | "1m" | "3m" | "6m" | "ytd" | "12m";

export const HORIZONS: { key: Horizon; label: string }[] = [
  { key: "1d", label: "1D" },
  { key: "1w", label: "1W" },
  { key: "1m", label: "1M" },
  { key: "3m", label: "3M" },
  { key: "6m", label: "6M" },
  { key: "ytd", label: "YTD" },
  { key: "12m", label: "12M" },
];

export interface MarketRow {
  symbol: string;
  name: string;
  short: string;
  group: "index" | "sector" | "commodity" | "crypto" | "fx" | "volatility";
  region: string;
  unit: string;
  size: number;
  notes: string;
  price: number | null;
  currency: string;
  as_of: string | null;
  changes: Partial<Record<Horizon, number | null>>;
  high_52w: number | null;
  low_52w: number | null;
  /** 0 = at the 52-week low, 1 = at the 52-week high. */
  range_position: number | null;
  /** Cumulative % return from 1 January, downsampled for plotting. */
  ytd_path: Point[];
  /** Price levels, carried only for series plotted as levels (VIX). */
  history: Point[];
  commentary: string;
}

export interface CurvePoint {
  series_id: string;
  label: string;
  years: number;
  current: number | null;
  week_ago: number | null;
  month_ago: number | null;
  year_ago: number | null;
}

export interface Curve {
  as_of?: string;
  points?: CurvePoint[];
  ten_year_history?: Point[];
  commentary?: string[];
}

export interface FearGreedComponent {
  key: string;
  name: string;
  detail: string;
  score: number;
  rating: string;
}

export interface FearGreed {
  score?: number | null;
  rating?: string;
  as_of?: string | null;
  previous_close?: number | null;
  previous_1_week?: number | null;
  previous_1_month?: number | null;
  previous_1_year?: number | null;
  components?: FearGreedComponent[];
  history?: Point[];
  commentary?: string[];
}

export interface NewsItem {
  topic: string;
  title: string;
  link: string;
  published: string;
  source: string;
  summary: string;
  channel: string;
  implication: string;
}

export interface MarketsOverview {
  generated_at: string;
  data_as_of: string | null;
  summary: string[];
  sections: {
    indices?: MarketRow[];
    sectors?: MarketRow[];
    volatility?: MarketRow[];
    commodities?: MarketRow[];
    crypto?: MarketRow[];
    fx?: MarketRow[];
  };
  commentary: {
    equities?: string[];
    sectors?: string[];
    commodities?: string[];
    fx_crypto?: string[];
  };
  curve: Curve;
  fear_greed: FearGreed;
  news: NewsItem[];
  errors: Record<string, string>;
  coverage_note: string;
}

async function fetcher<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

// Prices are cached backend-side for 15 minutes; polling faster only re-sends
// identical bytes.
export function useMarkets() {
  return useSWR<MarketsOverview>("/api/markets", fetcher, {
    refreshInterval: 5 * 60 * 1000,
    revalidateOnFocus: false,
    keepPreviousData: true,
    shouldRetryOnError: false,
  });
}

// -- formatting -------------------------------------------------------------

export function pct(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

export function price(v: number | null | undefined, unit = ""): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const digits = Math.abs(v) >= 1000 ? 0 : Math.abs(v) >= 10 ? 2 : 4;
  // Pinned to en-US: the browser default renders "6.691" for 6,691 in several
  // European locales, which reads as a price of six on a financial table.
  const n = v.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
  return unit.startsWith("$") ? `$${n}` : n;
}

/**
 * Colour for a percentage move. Deliberately NOT a red/green literal: the two
 * status tokens are already defined for light and dark, and VIX-style series
 * invert (a rising fear gauge is not "good").
 */
export function moveColor(v: number | null | undefined, polarity = 1): string {
  if (v === null || v === undefined || Math.abs(v) < 0.005) {
    return "var(--text-secondary)";
  }
  return v * polarity > 0 ? "var(--success-text)" : "var(--status-critical)";
}
