"use client";

import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { MarketRow, pct } from "../lib/markets";
import { AXIS_TICK, CardHeader, CHART_MARGIN, TOOLTIP_STYLE } from "./ui";

const PALETTE = [
  "var(--series-1)",
  "var(--series-2)",
  "var(--series-3)",
  "var(--series-4)",
  "var(--seq-550)",
  "var(--status-serious)",
];

/**
 * Cumulative return from 1 January, rebased to zero.
 *
 * The point is comparison, not levels: indices with different price scales are
 * only comparable once rebased, and the spread between the lines at the right
 * edge is the dispersion figure the commentary refers to. Six series is the
 * cap -- past that the lines are indistinguishable regardless of palette.
 */
export function YtdPathChart({
  rows,
  title = "Year-to-date performance",
  maxSeries = 6,
}: {
  rows: MarketRow[];
  title?: string;
  maxSeries?: number;
}) {
  const candidates = rows.filter((r) => r.ytd_path && r.ytd_path.length > 3);
  const [selected, setSelected] = useState<string[]>(() =>
    candidates.slice(0, maxSeries).map((r) => r.symbol),
  );

  const active = candidates.filter((r) => selected.includes(r.symbol));

  const data = useMemo(() => {
    const byDate = new Map<string, Record<string, number | string>>();
    for (const r of active) {
      for (const p of r.ytd_path) {
        const row = byDate.get(p.date) ?? { date: p.date };
        row[r.symbol] = p.value;
        byDate.set(p.date, row);
      }
    }
    return [...byDate.values()].sort((a, b) =>
      String(a.date) < String(b.date) ? -1 : 1,
    );
  }, [active]);

  if (candidates.length === 0) return null;

  function toggle(symbol: string) {
    setSelected((prev) =>
      prev.includes(symbol)
        ? prev.filter((s) => s !== symbol)
        : [...prev, symbol].slice(-maxSeries),
    );
  }

  return (
    <div className="card">
      <CardHeader
        eyebrow="Relative performance"
        title={title}
        caption={`Each line is cumulative % return since 1 January, so markets with different price levels are directly comparable. Select up to ${maxSeries}.`}
      />

      <div
        style={{
          display: "flex",
          gap: 6,
          flexWrap: "wrap",
          marginBottom: 10,
        }}
      >
        {candidates.map((r) => {
          const idx = active.findIndex((a) => a.symbol === r.symbol);
          const on = idx >= 0;
          return (
            <button
              key={r.symbol}
              onClick={() => toggle(r.symbol)}
              aria-pressed={on}
              style={{
                font: "inherit",
                fontSize: 11,
                padding: "2px 9px",
                borderRadius: 999,
                cursor: "pointer",
                border: `1px solid ${on ? PALETTE[idx % PALETTE.length] : "var(--border)"}`,
                background: "transparent",
                color: on ? "var(--text-primary)" : "var(--text-muted)",
                fontWeight: on ? 600 : 400,
              }}
            >
              {on ? "● " : ""}
              {r.short} {pct(r.changes.ytd, 1)}
            </button>
          );
        })}
      </div>

      <div style={{ width: "100%", height: 300 }}>
        <ResponsiveContainer>
          <LineChart data={data} margin={CHART_MARGIN}>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis
              dataKey="date"
              tick={AXIS_TICK}
              stroke="var(--axis)"
              minTickGap={52}
            />
            <YAxis
              tick={AXIS_TICK}
              stroke="var(--axis)"
              tickFormatter={(v: number) => `${v.toFixed(0)}%`}
              width={48}
            />
            <ReferenceLine y={0} stroke="var(--axis)" strokeWidth={1.5} />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              formatter={(value: number, key: string) => [
                pct(value, 1),
                active.find((a) => a.symbol === key)?.short ?? key,
              ]}
            />
            {active.map((r, i) => (
              <Line
                key={r.symbol}
                type="monotone"
                dataKey={r.symbol}
                stroke={PALETTE[i % PALETTE.length]}
                strokeWidth={1.8}
                dot={false}
                connectNulls
                name={r.short}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
