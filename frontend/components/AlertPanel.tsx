"use client";

import type { Alert, Severity } from "../lib/types";

// Status colour is never the only channel: each severity ships an icon and a
// text label alongside it.
const STYLE: Record<Severity, { color: string; icon: string; label: string }> = {
  critical: { color: "var(--status-critical)", icon: "▲", label: "Critical" },
  warning: { color: "var(--status-warning)", icon: "●", label: "Warning" },
  info: { color: "var(--series-1)", icon: "■", label: "Info" },
};

const KIND_LABEL: Record<string, string> = {
  threshold: "published threshold",
  statistical: "statistical extreme",
  velocity: "rate of change",
};

export function AlertPanel({ alerts }: { alerts: Alert[] }) {
  const critical = alerts.filter((a) => a.severity === "critical").length;

  return (
    <div className="card">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          marginBottom: 10,
        }}
      >
        <p className="h-eyebrow" style={{ margin: 0 }}>
          Risk alerts
        </p>
        <span className="tabular" style={{ fontSize: 12, color: "var(--text-muted)" }}>
          {alerts.length} active{critical > 0 ? ` · ${critical} critical` : ""}
        </span>
      </div>

      {alerts.length === 0 && (
        <p className="muted" style={{ fontSize: 13, margin: 0 }}>
          No indicators are past their thresholds. This is a genuine all-clear,
          not a data failure — check the coverage note if in doubt.
        </p>
      )}

      <div style={{ display: "grid", gap: 8, maxHeight: 420, overflowY: "auto" }}>
        {alerts.map((a) => {
          const s = STYLE[a.severity];
          return (
            <div
              key={a.id}
              style={{
                borderLeft: `3px solid ${s.color}`,
                background: "var(--page)",
                borderRadius: 6,
                padding: "9px 12px",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 10,
                  alignItems: "baseline",
                }}
              >
                <span style={{ fontWeight: 650, fontSize: 13 }}>
                  <span style={{ color: s.color, marginRight: 6 }} aria-hidden="true">
                    {s.icon}
                  </span>
                  {a.title}
                </span>
                <span
                  style={{
                    fontSize: 10,
                    color: s.color,
                    fontWeight: 650,
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    whiteSpace: "nowrap",
                  }}
                >
                  {s.label}
                </span>
              </div>
              <p
                className="muted"
                style={{ fontSize: 12, margin: "4px 0 0", lineHeight: 1.45 }}
              >
                {a.message}
              </p>
              <p
                style={{
                  fontSize: 10,
                  color: "var(--text-muted)",
                  margin: "5px 0 0",
                }}
              >
                {a.series_id} · {KIND_LABEL[a.kind] ?? a.kind} · as of{" "}
                {a.as_of ?? "—"}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
