"use client";

import type { Cycle } from "../lib/types";

const PHASE_COLOR: Record<string, string> = {
  Expansion: "var(--status-good)",
  Recovery: "var(--status-good)",
  Peak: "var(--status-warning)",
  Trough: "var(--status-serious)",
  Contraction: "var(--status-critical)",
};

const COMPOSITE_LABEL: Record<string, string> = {
  leading: "Leading",
  coincident: "Coincident",
  lagging: "Lagging (inflation/policy)",
  financial: "Financial conditions",
  growth_blend: "Growth blend",
};

export function CyclePanel({ cycle }: { cycle: Cycle }) {
  const color = PHASE_COLOR[cycle.phase] ?? "var(--series-1)";

  return (
    <div className="card">
      <p className="h-eyebrow">Business cycle phase</p>

      <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
        <span style={{ fontSize: 30, fontWeight: 650, color }}>{cycle.phase}</span>
        <span className="tabular" style={{ fontSize: 13, color: "var(--text-muted)" }}>
          {(cycle.confidence * 100).toFixed(0)}% confidence
        </span>
      </div>

      {/* Confidence is stated numerically AND as a bar -- a low-confidence call
          shown only as a big word reads as certainty it does not have. */}
      <div
        style={{
          height: 4,
          background: "var(--grid)",
          borderRadius: 2,
          margin: "8px 0 10px",
        }}
      >
        <div
          style={{
            width: `${Math.max(2, cycle.confidence * 100)}%`,
            height: "100%",
            background: color,
            borderRadius: 2,
          }}
        />
      </div>

      <p className="muted" style={{ fontSize: 13, margin: "0 0 12px" }}>
        {cycle.description}
      </p>

      <div className="scroll-x">
        <table>
          <thead>
            <tr>
              <th>Composite</th>
              <th style={{ textAlign: "right" }}>Level</th>
              <th style={{ textAlign: "right" }}>Coverage</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(cycle.composites).map(([k, v]) => (
              <tr key={k}>
                <td>{COMPOSITE_LABEL[k] ?? k}</td>
                <td
                  className="tabular"
                  style={{
                    textAlign: "right",
                    color:
                      v === null
                        ? "var(--text-muted)"
                        : v >= 0
                          ? "var(--success-text)"
                          : "var(--status-critical)",
                  }}
                >
                  {v === null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}σ`}
                </td>
                <td
                  className="tabular"
                  style={{ textAlign: "right", color: "var(--text-muted)" }}
                >
                  {cycle.coverage[k]
                    ? `${(cycle.coverage[k].coverage * 100).toFixed(0)}%`
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="h-eyebrow" style={{ marginTop: 16 }}>
        Rule-based signals
      </p>
      <div style={{ display: "grid", gap: 6 }}>
        {cycle.hard_signals.map((h) => (
          <div
            key={h.name}
            title={h.detail}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 8,
              fontSize: 12,
              padding: "6px 10px",
              borderRadius: 6,
              background: "var(--page)",
            }}
          >
            <span>
              <span
                aria-hidden="true"
                style={{
                  color: h.fired ? "var(--status-critical)" : "var(--status-good)",
                  marginRight: 7,
                  fontWeight: 700,
                }}
              >
                {h.fired ? "▲" : "✓"}
              </span>
              {h.name}
            </span>
            <span className="tabular" style={{ color: "var(--text-secondary)" }}>
              {h.value === null ? "—" : h.value.toFixed(2)}{" "}
              <span style={{ color: "var(--text-muted)" }}>
                / {h.threshold}
              </span>
            </span>
          </div>
        ))}
      </div>

      <p className="h-eyebrow" style={{ marginTop: 16 }}>
        Why this call
      </p>
      <ul
        className="muted"
        style={{ fontSize: 12, margin: 0, paddingLeft: 18, lineHeight: 1.6 }}
      >
        {cycle.rationale.map((r, i) => (
          <li key={i}>{r}</li>
        ))}
      </ul>
    </div>
  );
}
