"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { MarketRow, moveColor, pct } from "../lib/markets";
import { AXIS_TICK, CardHeader, Caption, TOOLTIP_STYLE } from "./ui";

/**
 * VIX, given its own card rather than a row in the index table.
 *
 * It is not an index you can be long in the same sense as the others -- it is
 * the price of insurance on them, and it inverts: a rising VIX is bad news
 * while every other row on that table is good news when it rises. Pulling it
 * out avoids a column of green that means the opposite of the green above it.
 *
 * The history line carries a reference line at 20, the level above which the
 * market is pricing genuinely unsettled conditions. A level alone does not say
 * whether 18 is calm or the tail of a spike; the line does.
 */

const THRESHOLD = 20;

const REGIMES = [
  { max: 15, label: "Complacent", color: "var(--status-good)",
    read: "Hedges are cheap. Positioning risk builds quietly in exactly this regime, because nothing forces anyone to cut exposure." },
  { max: THRESHOLD, label: "Normal", color: "var(--status-warning)",
    read: "Implied volatility is below 20, so options are pricing an ordinary market — day-to-day moves of well under 1% on the S&P 500." },
  { max: 30, label: "Unsettled", color: "var(--status-serious)",
    read: "Above 20 the market is paying up for protection and expecting daily swings above 1%. Elevated vol raises the cost of leverage and shrinks the position sizes risk models allow." },
  { max: 999, label: "Stress", color: "var(--status-critical)",
    read: "Stress territory. At this level systematic and vol-target strategies cut equity exposure mechanically, which is what turns a drawdown into a cascade." },
];

export function VolatilityCard({ row }: { row?: MarketRow }) {
  if (!row || row.price === null) return null;

  const level = row.price;
  const regime = REGIMES.find((r) => level < r.max) ?? REGIMES[REGIMES.length - 1];
  const history = row.history ?? [];
  const daysAbove = history.filter((p) => p.value > THRESHOLD).length;
  const share = history.length ? (daysAbove / history.length) * 100 : null;

  return (
    <div className="card">
      <CardHeader
        eyebrow="Volatility"
        title="VIX — the equity fear gauge"
        meta={row.as_of ? `as of ${row.as_of}` : undefined}
      />

      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 10,
          flexWrap: "wrap",
        }}
      >
        <span
          className="tabular"
          style={{ fontSize: 32, fontWeight: 650, lineHeight: 1.1 }}
        >
          {level.toFixed(2)}
        </span>
        <span
          style={{
            padding: "2px 10px",
            borderRadius: 999,
            background: regime.color,
            color: "#fff",
            fontSize: 12,
            fontWeight: 650,
          }}
        >
          {regime.label}
        </span>
        <span
          className="tabular"
          style={{ fontSize: 12.5, color: "var(--text-muted)" }}
        >
          {level >= THRESHOLD
            ? `${(level - THRESHOLD).toFixed(1)} above the 20 line`
            : `${(THRESHOLD - level).toFixed(1)} below the 20 line`}
        </span>
      </div>

      <div
        className="tabular"
        style={{
          display: "flex",
          gap: 16,
          flexWrap: "wrap",
          margin: "10px 0 0",
          fontSize: 12.5,
        }}
      >
        {(["1d", "1w", "1m", "ytd"] as const).map((h) => (
          <span key={h}>
            <span style={{ color: "var(--text-muted)" }}>
              {h.toUpperCase()}{" "}
            </span>
            {/* Polarity -1: a rising fear gauge is not good news. */}
            <strong style={{ color: moveColor(row.changes[h], -1) }}>
              {pct(row.changes[h], 1)}
            </strong>
          </span>
        ))}
      </div>

      {history.length > 5 ? (
        <div style={{ width: "100%", height: 150, marginTop: 12 }}>
          <ResponsiveContainer>
            <AreaChart
              data={history}
              margin={{ top: 6, right: 6, left: 0, bottom: 0 }}
            >
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
                width={34}
                domain={[
                  (min: number) => Math.floor(Math.min(min, 12)),
                  "auto",
                ]}
              />
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                formatter={(v: number) => [v.toFixed(2), "VIX"]}
              />
              {/* The regime line, labelled -- 20 is the number the commentary
                  refers to, so it has to be visible on the chart itself. */}
              <ReferenceLine
                y={THRESHOLD}
                stroke="var(--status-critical)"
                strokeDasharray="4 3"
                label={{
                  value: "20 · unsettled above",
                  position: "insideTopLeft",
                  fill: "var(--status-critical)",
                  fontSize: 10,
                }}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke="var(--series-1)"
                fill="var(--series-1)"
                fillOpacity={0.14}
                strokeWidth={1.6}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      ) : null}

      <p
        style={{
          margin: "10px 0 0",
          fontSize: 12.5,
          lineHeight: 1.55,
          color: "var(--text-secondary)",
        }}
      >
        {regime.read}
      </p>

      <Caption>
        {row.low_52w !== null && row.high_52w !== null
          ? `52-week range ${row.low_52w.toFixed(1)}–${row.high_52w.toFixed(1)}`
          : ""}
        {row.range_position !== null
          ? ` · currently at the ${(row.range_position * 100).toFixed(0)}th percentile of it`
          : ""}
        {share !== null
          ? ` · closed above 20 on ${share.toFixed(0)}% of the last ${history.length} sessions`
          : ""}
      </Caption>
    </div>
  );
}
