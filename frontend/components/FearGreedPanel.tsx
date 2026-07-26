"use client";

import { Area, AreaChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";

import { FearGreed } from "../lib/markets";
import { Narrative } from "./Narrative";
import { CardHeader, TOOLTIP_STYLE } from "./ui";

/**
 * CNN Fear & Greed index.
 *
 * Same semicircular-gauge grammar as the risk gauge it replaces, so the two
 * read as one system -- but the scale runs the other way: 0 is extreme fear
 * (contrarian positive) and 100 extreme greed. The band label and the number
 * are both text, so nothing depends on reading the arc colour.
 */

const BANDS = [
  { max: 25, label: "Extreme fear", color: "var(--status-critical)" },
  { max: 45, label: "Fear", color: "var(--status-serious)" },
  { max: 55, label: "Neutral", color: "var(--status-warning)" },
  { max: 75, label: "Greed", color: "var(--series-3)" },
  { max: 101, label: "Extreme greed", color: "var(--status-good)" },
];

function band(score: number) {
  return BANDS.find((b) => score < b.max) ?? BANDS[BANDS.length - 1];
}

export function FearGreedPanel({ fg }: { fg?: FearGreed }) {
  const score = fg?.score ?? null;

  if (score === null || score === undefined) {
    return (
      <div className="card">
        <CardHeader eyebrow="Market sentiment" title="CNN Fear & Greed" />
        <p className="muted" style={{ fontSize: 13, margin: 0 }}>
          Sentiment data unavailable right now.
        </p>
      </div>
    );
  }

  const R = 100;
  const CX = 120;
  const CY = 118;
  const clamped = Math.max(0, Math.min(100, score));
  const polar = (p: number) => {
    const a = Math.PI * (1 - p / 100);
    return { x: CX + R * Math.cos(a), y: CY - R * Math.sin(a) };
  };
  const arc = (from: number, to: number) => {
    const a = polar(from);
    const b = polar(to);
    return `M ${a.x} ${a.y} A ${R} ${R} 0 ${to - from > 50 ? 1 : 0} 1 ${b.x} ${b.y}`;
  };
  const needle = polar(clamped);
  const current = band(clamped);

  const refs: { label: string; value: number | null | undefined }[] = [
    { label: "Prev close", value: fg?.previous_close },
    { label: "1 week", value: fg?.previous_1_week },
    { label: "1 month", value: fg?.previous_1_month },
    { label: "1 year", value: fg?.previous_1_year },
  ];

  return (
    <div className="card">
      <CardHeader
        eyebrow="Market sentiment"
        title="CNN Fear & Greed"
        meta={`as of ${fg?.as_of ?? "—"}`}
        caption="Seven positioning and market-internals inputs, scored 0 (extreme fear) to 100 (extreme greed)."
      />

      <div style={{ display: "flex", justifyContent: "center" }}>
        <svg
          viewBox="0 0 240 150"
          style={{ width: "100%", maxWidth: 300 }}
          role="img"
          aria-label={`Fear and Greed index ${score.toFixed(0)} of 100, ${current.label}`}
        >
          {BANDS.map((b, i) => {
            const from = i === 0 ? 0 : BANDS[i - 1].max;
            const to = Math.min(100, b.max);
            return (
              <path
                key={b.label}
                d={arc(from + 0.6, to - 0.6)}
                fill="none"
                stroke={b.color}
                strokeWidth={12}
                opacity={clamped >= from && clamped < b.max ? 1 : 0.22}
              />
            );
          })}
          <line
            x1={CX}
            y1={CY}
            x2={needle.x}
            y2={needle.y}
            stroke="var(--text-primary)"
            strokeWidth={3}
            strokeLinecap="round"
          />
          <circle cx={CX} cy={CY} r={5} fill="var(--text-primary)" />
          <text
            x={CX}
            y={CY - 34}
            textAnchor="middle"
            style={{ fontSize: 38, fontWeight: 650, fill: "var(--text-primary)" }}
          >
            {score.toFixed(0)}
          </text>
          <text
            x={16}
            y={CY + 18}
            style={{ fontSize: 10, fill: "var(--text-muted)" }}
          >
            0 fear
          </text>
          <text
            x={224}
            y={CY + 18}
            textAnchor="end"
            style={{ fontSize: 10, fill: "var(--text-muted)" }}
          >
            greed 100
          </text>
        </svg>
      </div>

      <div style={{ textAlign: "center", marginTop: -6 }}>
        <span
          style={{
            display: "inline-block",
            padding: "3px 12px",
            borderRadius: 999,
            background: current.color,
            color: "#fff",
            fontWeight: 650,
            fontSize: 13,
          }}
        >
          {current.label}
        </span>
      </div>

      <div
        className="tabular"
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: 8,
          marginTop: 12,
          paddingTop: 10,
          borderTop: "1px solid var(--grid)",
          fontSize: 12,
          color: "var(--text-secondary)",
        }}
      >
        {refs.map((r) => (
          <span key={r.label}>
            {r.label}{" "}
            <strong style={{ color: "var(--text-primary)" }}>
              {r.value === null || r.value === undefined
                ? "—"
                : Number(r.value).toFixed(0)}
            </strong>
          </span>
        ))}
      </div>

      {fg?.history && fg.history.length > 5 ? (
        <div style={{ width: "100%", height: 70, marginTop: 10 }}>
          <ResponsiveContainer>
            <AreaChart
              data={fg.history}
              margin={{ top: 4, right: 0, left: 0, bottom: 0 }}
            >
              <YAxis domain={[0, 100]} hide />
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                formatter={(v: number) => [v.toFixed(0), "Index"]}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke="var(--series-1)"
                fill="var(--series-1)"
                fillOpacity={0.15}
                strokeWidth={1.6}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      ) : null}

      {fg?.components && fg.components.length > 0 ? (
        <div style={{ marginTop: 10 }}>
          <p className="h-eyebrow">Inputs</p>
          <div style={{ display: "grid", gap: 5 }}>
            {[...fg.components]
              .sort((a, b) => a.score - b.score)
              .map((c) => (
                <div
                  key={c.key}
                  title={c.detail}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 90px 34px",
                    alignItems: "center",
                    gap: 8,
                    fontSize: 12,
                  }}
                >
                  <span style={{ color: "var(--text-secondary)" }}>{c.name}</span>
                  <div
                    style={{
                      height: 8,
                      background: "var(--grid)",
                      borderRadius: 3,
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${Math.max(0, Math.min(100, c.score))}%`,
                        height: "100%",
                        background: band(c.score).color,
                      }}
                    />
                  </div>
                  <span className="tabular" style={{ textAlign: "right" }}>
                    {c.score.toFixed(0)}
                  </span>
                </div>
              ))}
          </div>
        </div>
      ) : null}

      <Narrative items={fg?.commentary} compact />
    </div>
  );
}
