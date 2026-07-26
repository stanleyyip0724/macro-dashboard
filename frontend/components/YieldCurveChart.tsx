"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Curve } from "../lib/markets";
import { Narrative } from "./Narrative";
import { AXIS_TICK, CardHeader, CHART_MARGIN, Stat, TOOLTIP_STYLE } from "./ui";

/**
 * US Treasury constant-maturity curve, current against three earlier vintages.
 *
 * Plotted against tenor, not time: the shape IS the signal, and the month-ago
 * and year-ago lines are what turn a static shape into a direction. The x-axis
 * is a category scale so the short end is not crushed into the first 5% of the
 * width, which is exactly where inversions live.
 */
export function YieldCurveChart({ curve }: { curve?: Curve }) {
  const points = curve?.points ?? [];

  if (points.length === 0) {
    return (
      <div className="card">
        <CardHeader eyebrow="Rates" title="US Treasury yield curve" />
        <p className="muted" style={{ fontSize: 13, margin: 0 }}>
          Curve data unavailable right now.
        </p>
      </div>
    );
  }

  const data = points.map((p) => ({
    label: p.label,
    current: p.current,
    month_ago: p.month_ago,
    year_ago: p.year_ago,
  }));

  const spread = (a: string, b: string, key: "current" | "month_ago") => {
    const pa = points.find((p) => p.label === a);
    const pb = points.find((p) => p.label === b);
    if (!pa || !pb || pa[key] === null || pb[key] === null) return null;
    return (pa[key] as number) - (pb[key] as number);
  };

  const s = spread("10Y", "2Y", "current");
  const sPrev = spread("10Y", "2Y", "month_ago");
  const s3m = spread("10Y", "3M", "current");

  return (
    <div className="card">
      <CardHeader
        eyebrow="Rates"
        title="US Treasury yield curve"
        meta={`as of ${curve?.as_of ?? "—"}`}
        caption="Plotted against tenor: the shape is the signal, and the earlier vintages turn a static shape into a direction."
      />

      <div style={{ display: "flex", gap: 18, flexWrap: "wrap", margin: "0 0 10px" }}>
        <Stat
          label="10Y–2Y"
          value={s === null ? "—" : `${(s * 100).toFixed(0)}bp`}
          sub={
            s === null || sPrev === null
              ? ""
              : `${((s - sPrev) * 100 >= 0 ? "+" : "")}${((s - sPrev) * 100).toFixed(0)}bp vs 1m`
          }
          tone={s !== null && s < 0 ? "bad" : "neutral"}
        />
        <Stat
          label="10Y–3M"
          value={s3m === null ? "—" : `${(s3m * 100).toFixed(0)}bp`}
          sub={s3m !== null && s3m < 0 ? "inverted" : "positive"}
          tone={s3m !== null && s3m < 0 ? "bad" : "neutral"}
        />
        <Stat
          label="10Y level"
          value={
            points.find((p) => p.label === "10Y")?.current?.toFixed(2) ?? "—"
          }
          sub="%"
        />
      </div>

      <div style={{ width: "100%", height: 280 }}>
        <ResponsiveContainer>
          <LineChart data={data} margin={CHART_MARGIN}>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis
              dataKey="label"
              tick={AXIS_TICK}
              stroke="var(--axis)"
            />
            <YAxis
              tick={AXIS_TICK}
              stroke="var(--axis)"
              domain={["auto", "auto"]}
              tickFormatter={(v: number) => `${v.toFixed(1)}%`}
              width={48}
            />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              formatter={(v: number, key: string) => [
                `${v.toFixed(2)}%`,
                key === "current"
                  ? "Today"
                  : key === "month_ago"
                    ? "1 month ago"
                    : "1 year ago",
              ]}
            />
            <Line
              type="monotone"
              dataKey="year_ago"
              stroke="var(--seq-250)"
              strokeWidth={1.4}
              strokeDasharray="2 3"
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="month_ago"
              stroke="var(--seq-350)"
              strokeWidth={1.6}
              strokeDasharray="5 3"
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="current"
              stroke="var(--seq-700)"
              strokeWidth={2.6}
              dot={{ r: 2.5 }}
              connectNulls
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Direct labels: the three vintages differ by weight and dash as well as
          hue, so the chart is readable without relying on colour alone. */}
      <div
        style={{
          display: "flex",
          gap: 14,
          flexWrap: "wrap",
          fontSize: 11,
          color: "var(--text-secondary)",
          marginTop: 6,
        }}
      >
        <LegendItem color="var(--seq-700)" dash={false} label="Today" />
        <LegendItem color="var(--seq-350)" dash label="1 month ago" />
        <LegendItem color="var(--seq-250)" dash label="1 year ago" />
      </div>

      <Narrative items={curve?.commentary} />
    </div>
  );
}

function LegendItem({
  color,
  dash,
  label,
}: {
  color: string;
  dash: boolean;
  label: string;
}) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <svg width={22} height={8} aria-hidden="true">
        <line
          x1={0}
          y1={4}
          x2={22}
          y2={4}
          stroke={color}
          strokeWidth={dash ? 1.6 : 2.6}
          strokeDasharray={dash ? "5 3" : undefined}
        />
      </svg>
      {label}
    </span>
  );
}
