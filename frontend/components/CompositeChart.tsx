"use client";

import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { CompositeSeries } from "../lib/types";

const SERIES = [
  { key: "leading", label: "Leading", color: "var(--series-1)" },
  { key: "coincident", label: "Coincident", color: "var(--series-2)" },
  { key: "lagging", label: "Lagging", color: "var(--series-3)" },
  { key: "financial", label: "Financial", color: "var(--series-4)" },
];

const RANGES = [
  { label: "5Y", months: 60 },
  { label: "10Y", months: 120 },
  { label: "Max", months: Infinity },
];

/**
 * The four composites on one axis.
 *
 * All four are z-scores, which is precisely why they can share an axis -- the
 * normalisation in transforms.py exists to make this chart legal. If you ever
 * add a series in raw units here, split it into its own chart rather than
 * reaching for a second y-axis.
 */
export function CompositeChart({ composites }: { composites: CompositeSeries[] }) {
  const [months, setMonths] = useState(120);

  const data = useMemo(() => {
    const byDate = new Map<string, Record<string, number | string>>();
    for (const c of composites) {
      for (const p of c.points) {
        const row = byDate.get(p.date) ?? { date: p.date };
        row[c.name] = p.value;
        byDate.set(p.date, row);
      }
    }
    const rows = [...byDate.values()].sort((a, b) =>
      String(a.date).localeCompare(String(b.date)),
    );
    return Number.isFinite(months) ? rows.slice(-months) : rows;
  }, [composites, months]);

  return (
    <div className="card">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 8,
          marginBottom: 8,
        }}
      >
        <div>
          <p className="h-eyebrow" style={{ margin: 0 }}>
            Composite indicators
          </p>
          <p className="muted" style={{ fontSize: 12, margin: "2px 0 0" }}>
            Polarity-adjusted z-scores — positive is always economically good
          </p>
        </div>
        {/* Filters live in one row above the chart. */}
        <div style={{ display: "flex", gap: 4 }}>
          {RANGES.map((r) => (
            <button
              key={r.label}
              onClick={() => setMonths(r.months)}
              style={{
                font: "inherit",
                fontSize: 12,
                padding: "4px 10px",
                borderRadius: 6,
                cursor: "pointer",
                border: "1px solid var(--border)",
                background:
                  months === r.months ? "var(--text-primary)" : "transparent",
                color:
                  months === r.months ? "var(--surface-1)" : "var(--text-secondary)",
              }}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      <div style={{ width: "100%", height: 320 }}>
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 6, right: 44, bottom: 4, left: 0 }}>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <ReferenceLine y={0} stroke="var(--axis)" />
            <XAxis
              dataKey="date"
              tick={{ fill: "var(--text-muted)", fontSize: 11 }}
              stroke="var(--axis)"
              minTickGap={44}
              tickFormatter={(d: string) => d.slice(0, 7)}
            />
            <YAxis
              tick={{ fill: "var(--text-muted)", fontSize: 11 }}
              stroke="var(--axis)"
              width={44}
              tickFormatter={(v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}σ`}
            />
            <Tooltip
              contentStyle={{
                background: "var(--surface-1)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                fontSize: 12,
              }}
              labelStyle={{ color: "var(--text-primary)", fontWeight: 650 }}
              formatter={(v: number, n: string) => [
                `${v >= 0 ? "+" : ""}${v.toFixed(2)}σ`,
                n,
              ]}
            />
            <Legend
              verticalAlign="top"
              height={28}
              iconType="plainline"
              wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)" }}
            />
            {SERIES.map((s) => (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={s.color}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                connectNulls
                // Direct end-label: the palette's relief rule requires it for
                // the low-contrast light-mode slots, and it beats a legend
                // round-trip for the reader regardless.
                // Recharts types this render prop as returning a non-null
                // SVG element, so non-final points get an empty <g/> rather
                // than null -- it renders nothing and keeps the type honest.
                label={({ index, x, y }: any) =>
                  index === data.length - 1 ? (
                    <text
                      x={x + 6}
                      y={y + 4}
                      style={{
                        fontSize: 11,
                        fontWeight: 600,
                        fill: "var(--text-secondary)",
                      }}
                    >
                      {s.label.slice(0, 4)}
                    </text>
                  ) : (
                    <g />
                  )
                }
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
