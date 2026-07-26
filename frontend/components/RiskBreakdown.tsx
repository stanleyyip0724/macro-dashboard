"use client";

import { useState } from "react";
import type { Risk } from "../lib/types";

function scoreColor(v: number): string {
  if (v < 20) return "var(--status-good)";
  if (v < 40) return "var(--status-warning)";
  if (v < 60) return "var(--status-serious)";
  return "var(--status-critical)";
}

/**
 * Where the risk actually lives.
 *
 * A single 0-100 number hides the difference between "55, entirely credit" and
 * "55, evenly spread" -- which call for completely different responses. Pillar
 * bars plus the per-indicator table make the composite auditable, and the table
 * doubles as the accessible view of the bar chart.
 */
export function RiskBreakdown({ risk }: { risk: Risk }) {
  const [showAll, setShowAll] = useState(false);
  const pillars = Object.entries(risk.pillars).sort((a, b) => b[1] - a[1]);
  const rows = showAll ? risk.contributions : risk.contributions.slice(0, 8);

  return (
    <div className="card">
      <p className="h-eyebrow">Risk by pillar</p>

      <div style={{ display: "grid", gap: 9, marginBottom: 18 }}>
        {pillars.map(([name, value]) => (
          <div key={name}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                fontSize: 12,
                marginBottom: 3,
              }}
            >
              <span>{name}</span>
              <span className="tabular" style={{ color: "var(--text-secondary)" }}>
                {value.toFixed(0)}
                <span style={{ color: "var(--text-muted)" }}>
                  {" "}
                  · weight {risk.pillar_weights[name]?.toFixed(1) ?? "—"}
                </span>
              </span>
            </div>
            <div
              style={{ height: 8, background: "var(--grid)", borderRadius: 4 }}
            >
              <div
                style={{
                  width: `${Math.max(1, value)}%`,
                  height: "100%",
                  background: scoreColor(value),
                  borderRadius: 4,
                }}
              />
            </div>
          </div>
        ))}
      </div>

      <p className="h-eyebrow">Triggered rules</p>
      <div style={{ display: "grid", gap: 5, marginBottom: 18 }}>
        {risk.triggers.map((t) => (
          <div
            key={t.name}
            title={t.detail}
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: 8,
              fontSize: 12,
              opacity: t.fired ? 1 : 0.55,
            }}
          >
            <span>
              <span
                aria-hidden="true"
                style={{
                  color: t.fired ? "var(--status-critical)" : "var(--status-good)",
                  marginRight: 7,
                  fontWeight: 700,
                }}
              >
                {t.fired ? "▲" : "✓"}
              </span>
              {t.name}
            </span>
            <span className="tabular" style={{ color: "var(--text-muted)" }}>
              {t.value === null ? "—" : t.value.toFixed(2)} ({t.threshold})
              {t.fired ? ` +${t.points}` : ""}
            </span>
          </div>
        ))}
      </div>

      <p className="h-eyebrow">Indicator contributions</p>
      <div className="scroll-x">
        <table>
          <thead>
            <tr>
              <th>Indicator</th>
              <th>Pillar</th>
              <th style={{ textAlign: "right" }}>Value</th>
              <th style={{ textAlign: "right" }}>z</th>
              <th style={{ textAlign: "right" }}>Sub-score</th>
              <th style={{ textAlign: "right" }}>Weight</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.series_id}>
                <td title={c.name}>{c.short}</td>
                <td style={{ color: "var(--text-muted)" }}>{c.pillar}</td>
                <td className="tabular" style={{ textAlign: "right" }}>
                  {c.latest_value === null ? "—" : c.latest_value.toFixed(2)}
                  <span style={{ color: "var(--text-muted)" }}> {c.unit}</span>
                </td>
                <td
                  className="tabular"
                  style={{
                    textAlign: "right",
                    color:
                      c.badness > 0
                        ? "var(--status-critical)"
                        : "var(--success-text)",
                  }}
                >
                  {c.zscore >= 0 ? "+" : ""}
                  {c.zscore.toFixed(2)}
                </td>
                <td
                  className="tabular"
                  style={{ textAlign: "right", color: scoreColor(c.subscore) }}
                >
                  {c.subscore.toFixed(0)}
                </td>
                <td
                  className="tabular"
                  style={{ textAlign: "right", color: "var(--text-muted)" }}
                >
                  {c.weight.toFixed(1)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {risk.contributions.length > 8 && (
        <button
          onClick={() => setShowAll((v) => !v)}
          style={{
            font: "inherit",
            fontSize: 12,
            marginTop: 10,
            padding: "5px 12px",
            borderRadius: 6,
            cursor: "pointer",
            border: "1px solid var(--border)",
            background: "transparent",
            color: "var(--text-secondary)",
          }}
        >
          {showAll
            ? "Show top 8"
            : `Show all ${risk.contributions.length} inputs`}
        </button>
      )}
    </div>
  );
}
