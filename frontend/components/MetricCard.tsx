"use client";

import { Area, AreaChart, ResponsiveContainer, YAxis } from "recharts";
import type { IndicatorCard } from "../lib/types";
import { changeSentiment, formatDelta, formatValue } from "../lib/api";

/**
 * One headline metric: value, 3-month delta, z-score context, and a sparkline.
 *
 * The delta is coloured by SENTIMENT, not by sign -- falling unemployment and
 * rising GDP both render green. The arrow still shows the raw direction, so the
 * two channels together say "down, and that's good" rather than relying on
 * colour alone.
 */
export function MetricCard({
  card,
  onSelect,
}: {
  card: IndicatorCard;
  onSelect?: (seriesId: string) => void;
}) {
  const sentiment = changeSentiment(card.change_3m, card.polarity);
  const deltaColor =
    sentiment === "good"
      ? "var(--success-text)"
      : sentiment === "bad"
        ? "var(--status-critical)"
        : "var(--text-muted)";

  // Sparkline hue tracks the signal, so a wall of cards reads at a glance.
  const sig = card.signal ?? 0;
  const strokeColor =
    sig > 0.5
      ? "var(--status-good)"
      : sig < -0.5
        ? "var(--status-critical)"
        : "var(--series-1)";

  const zLabel =
    card.latest_z === null
      ? "—"
      : `${card.latest_z >= 0 ? "+" : ""}${card.latest_z.toFixed(2)}σ`;

  return (
    <button
      type="button"
      onClick={() => onSelect?.(card.series_id)}
      title={card.notes || card.name}
      style={{
        display: "block",
        width: "100%",
        textAlign: "left",
        font: "inherit",
        color: "inherit",
        cursor: onSelect ? "pointer" : "default",
        background: "var(--surface-1)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        padding: 14,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          gap: 8,
        }}
      >
        <span
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: "var(--text-secondary)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {card.short}
        </span>
        <span
          className="tabular"
          style={{ fontSize: 11, color: "var(--text-muted)" }}
        >
          {zLabel}
        </span>
      </div>

      <div
        className="tabular"
        style={{ fontSize: 26, fontWeight: 600, marginTop: 4, lineHeight: 1.15 }}
      >
        {formatValue(card.latest_value, card.unit)}
      </div>

      <div
        className="tabular"
        style={{ fontSize: 12, color: deltaColor, marginTop: 2 }}
      >
        {formatDelta(card.change_3m, card.unit)}
        <span style={{ color: "var(--text-muted)" }}> vs 3m ago</span>
      </div>

      <div style={{ height: 34, marginTop: 8 }} aria-hidden="true">
        {card.sparkline.length > 1 && (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={card.sparkline}
              margin={{ top: 2, right: 0, bottom: 0, left: 0 }}
            >
              <defs>
                <linearGradient
                  id={`fill-${card.series_id}`}
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop offset="0%" stopColor={strokeColor} stopOpacity={0.28} />
                  <stop offset="100%" stopColor={strokeColor} stopOpacity={0} />
                </linearGradient>
              </defs>
              {/* Domain from the data, not zero-based: a sparkline shows shape. */}
              <YAxis hide domain={["dataMin", "dataMax"]} />
              <Area
                type="monotone"
                dataKey="value"
                stroke={strokeColor}
                strokeWidth={2}
                fill={`url(#fill-${card.series_id})`}
                isAnimationActive={false}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>
        {card.series_id} · {card.as_of ?? "—"}
      </div>
    </button>
  );
}
