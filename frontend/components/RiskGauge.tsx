"use client";

import type { Risk } from "../lib/types";

const BANDS = [
  { max: 20, label: "Low", color: "var(--status-good)" },
  { max: 40, label: "Moderate", color: "var(--status-warning)" },
  { max: 60, label: "Elevated", color: "var(--status-serious)" },
  { max: 80, label: "High", color: "var(--status-critical)" },
  { max: 100, label: "Severe", color: "var(--status-critical)" },
];

function bandColor(score: number): string {
  return (BANDS.find((b) => score < b.max) ?? BANDS[BANDS.length - 1]).color;
}

/**
 * Semicircular risk gauge.
 *
 * Drawn as an SVG arc rather than a chart-library radial: it is a single
 * value, so this is a hero figure with a scale, not a plot. The numeric score
 * and the band name are both rendered as text, so the reading never depends on
 * the arc's colour -- which matters because two of the five bands share the
 * critical red.
 */
export function RiskGauge({ risk }: { risk: Risk }) {
  const R = 100;
  const CX = 120;
  const CY = 118;
  const clamped = Math.max(0, Math.min(100, risk.score));

  // Semicircle: 180deg (left) -> 0deg (right).
  const polar = (pct: number) => {
    const angle = Math.PI * (1 - pct / 100);
    return { x: CX + R * Math.cos(angle), y: CY - R * Math.sin(angle) };
  };

  const arc = (from: number, to: number) => {
    const a = polar(from);
    const b = polar(to);
    const large = to - from > 50 ? 1 : 0;
    return `M ${a.x} ${a.y} A ${R} ${R} 0 ${large} 1 ${b.x} ${b.y}`;
  };

  const needle = polar(clamped);
  const color = bandColor(clamped);

  return (
    <div className="card">
      <p className="h-eyebrow">Composite economic risk</p>

      <div style={{ display: "flex", justifyContent: "center" }}>
        <svg
          viewBox="0 0 240 150"
          style={{ width: "100%", maxWidth: 300 }}
          role="img"
          aria-label={`Economic risk score ${risk.score} out of 100, band ${risk.band}`}
        >
          {/* Band track. A 2px surface gap separates adjacent segments. */}
          {BANDS.map((b, i) => {
            const from = i === 0 ? 0 : BANDS[i - 1].max;
            return (
              <path
                key={b.label}
                d={arc(from + 0.6, b.max - 0.6)}
                fill="none"
                stroke={b.color}
                strokeWidth={12}
                strokeLinecap="butt"
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
            {risk.score.toFixed(0)}
          </text>
          <text
            x={CX}
            y={CY - 16}
            textAnchor="middle"
            style={{ fontSize: 12, fill: "var(--text-muted)" }}
          >
            / 100
          </text>

          <text x={16} y={CY + 18} style={{ fontSize: 10, fill: "var(--text-muted)" }}>
            0
          </text>
          <text
            x={224}
            y={CY + 18}
            textAnchor="end"
            style={{ fontSize: 10, fill: "var(--text-muted)" }}
          >
            100
          </text>
        </svg>
      </div>

      <div style={{ textAlign: "center", marginTop: -6 }}>
        <span
          style={{
            display: "inline-block",
            padding: "3px 12px",
            borderRadius: 999,
            background: color,
            color: "#fff",
            fontWeight: 650,
            fontSize: 13,
          }}
        >
          {risk.band}
        </span>
        <p className="muted" style={{ fontSize: 12, margin: "8px 0 0" }}>
          {risk.band_description}
        </p>
      </div>

      <div
        className="tabular"
        style={{
          marginTop: 12,
          paddingTop: 10,
          borderTop: `1px solid var(--grid)`,
          fontSize: 12,
          color: "var(--text-secondary)",
          display: "flex",
          justifyContent: "space-between",
        }}
      >
        <span>Base {risk.base_score.toFixed(1)}</span>
        <span>
          Triggers +{risk.trigger_bonus.toFixed(1)}
        </span>
        <span>Coverage {(risk.coverage * 100).toFixed(0)}%</span>
      </div>
    </div>
  );
}
