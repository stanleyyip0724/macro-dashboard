"use client";

import type { CSSProperties, ReactNode } from "react";

import { HORIZONS, Horizon } from "../lib/markets";

/**
 * Shared chrome for every markets panel.
 *
 * These exist so the page reads as one instrument rather than eight: the same
 * eyebrow-over-title header, the same pill row, the same caption size and the
 * same chart frame everywhere. Panels that each invent their own spacing look
 * amateurish long before any individual one looks wrong.
 */

export const CHART_MARGIN = { top: 6, right: 16, left: 0, bottom: 0 };

export const AXIS_TICK = { fontSize: 11, fill: "var(--text-muted)" } as const;

export const TOOLTIP_STYLE: CSSProperties = {
  background: "var(--surface-1)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  fontSize: 12,
};

/** Eyebrow, title, and an optional right-hand slot (as-of stamp or controls). */
export function CardHeader({
  eyebrow,
  title,
  meta,
  right,
  caption,
}: {
  eyebrow: string;
  title: string;
  meta?: string;
  right?: ReactNode;
  caption?: string;
}) {
  return (
    <div style={{ marginBottom: caption ? 10 : 12 }}>
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <div style={{ minWidth: 0 }}>
          <p className="h-eyebrow">{eyebrow}</p>
          <h2 className="h-section" style={{ marginBottom: 0 }}>
            {title}
          </h2>
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            flexWrap: "wrap",
          }}
        >
          {right}
          {meta ? (
            <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
              {meta}
            </span>
          ) : null}
        </div>
      </div>
      {caption ? (
        <p className="muted" style={{ fontSize: 12, margin: "6px 0 0" }}>
          {caption}
        </p>
      ) : null}
    </div>
  );
}

/** The 1D…12M selector, identical wherever a horizon can be chosen. */
export function HorizonPills({
  value,
  onChange,
}: {
  value: Horizon;
  onChange: (h: Horizon) => void;
}) {
  return (
    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
      {HORIZONS.map((h) => {
        const on = value === h.key;
        return (
          <button
            key={h.key}
            onClick={() => onChange(h.key)}
            aria-pressed={on}
            style={{
              font: "inherit",
              fontSize: 11,
              lineHeight: 1.6,
              padding: "2px 9px",
              borderRadius: 999,
              cursor: "pointer",
              border: "1px solid var(--border)",
              background: on ? "var(--text-primary)" : "transparent",
              color: on ? "var(--surface-1)" : "var(--text-secondary)",
              fontWeight: on ? 650 : 400,
            }}
          >
            {h.label}
          </button>
        );
      })}
    </div>
  );
}

/** Footnote under a chart or table. One size, one colour, everywhere. */
export function Caption({ children }: { children: ReactNode }) {
  return (
    <p style={{ fontSize: 11, color: "var(--text-muted)", margin: "8px 0 0" }}>
      {children}
    </p>
  );
}

/** A labelled hero figure, used for curve spreads and the VIX level. */
export function Stat({
  label,
  value,
  sub,
  tone = "neutral",
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "neutral" | "bad";
}) {
  return (
    <div>
      <p className="h-eyebrow" style={{ margin: 0 }}>
        {label}
      </p>
      <p
        className="tabular"
        style={{
          margin: 0,
          fontSize: 20,
          fontWeight: 650,
          lineHeight: 1.25,
          color:
            tone === "bad" ? "var(--status-critical)" : "var(--text-primary)",
        }}
      >
        {value}
      </p>
      {sub ? (
        <p style={{ margin: 0, fontSize: 11, color: "var(--text-muted)" }}>
          {sub}
        </p>
      ) : null}
    </div>
  );
}
