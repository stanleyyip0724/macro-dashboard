"use client";

import { useState } from "react";

import { Horizon, HORIZONS, MarketRow, pct } from "../lib/markets";
import { CardHeader, Caption, HorizonPills } from "./ui";

/**
 * Grouped (two-level) squarified tree map.
 *
 * Level one lays out asset-class blocks -- US equity sectors, global indices,
 * commodities, crypto & FX -- sized by the total weight of their members.
 * Level two lays out the members inside each block. Grouping is what makes the
 * map readable: comparing a semiconductor sector against the yen in one flat
 * grid invites a comparison that means nothing, whereas "tech is carrying the
 * US while commodities are red" is the actual question the map answers.
 *
 * Area is weight, colour and the printed figure are the selected-horizon
 * return. The number is always printed, so the ramp is a redundant encoding.
 */

type Rect = { x: number; y: number; w: number; h: number };
type Node<T> = T & Rect;

export type TreemapGroup = { name: string; rows: MarketRow[] };

/** Bruls/Huizing/van Wijk squarified layout, trimmed to what we need here. */
function squarify<T>(
  items: { value: number; item: T }[],
  box: Rect,
): Node<T>[] {
  const out: Node<T>[] = [];
  const rest = [...items].sort((a, b) => b.value - a.value);
  let { x: cx, y: cy, w: cw, h: ch } = box;

  const worst = (row: { value: number }[], side: number, scale: number) => {
    const sum = row.reduce((s, r) => s + r.value, 0) * scale;
    const max = Math.max(...row.map((r) => r.value)) * scale;
    const min = Math.min(...row.map((r) => r.value)) * scale;
    const s2 = sum * sum;
    return Math.max((side * side * max) / s2, s2 / (side * side * min));
  };

  while (rest.length > 0) {
    const total = rest.reduce((s, r) => s + r.value, 0);
    if (total <= 0 || cw <= 0 || ch <= 0) break;
    const scale = (cw * ch) / total;
    const side = Math.min(cw, ch);

    const row: { value: number; item: T }[] = [];
    while (rest.length > 0) {
      const candidate = [...row, rest[0]];
      if (row.length > 0 && worst(candidate, side, scale) > worst(row, side, scale)) {
        break;
      }
      row.push(rest.shift()!);
    }

    const thickness = (row.reduce((s, r) => s + r.value, 0) * scale) / side;
    let offset = 0;
    for (const entry of row) {
      const length = (entry.value * scale) / thickness;
      out.push(
        cw >= ch
          ? { ...(entry.item as T), x: cx, y: cy + offset, w: thickness, h: length }
          : { ...(entry.item as T), x: cx + offset, y: cy, w: length, h: thickness },
      );
      offset += length;
    }

    if (cw >= ch) {
      cx += thickness;
      cw -= thickness;
    } else {
      cy += thickness;
      ch -= thickness;
    }
  }
  return out;
}

/** Diverging ramp. Saturation encodes magnitude, hue encodes sign. */
function tileColor(v: number | null | undefined, cap: number): string {
  if (v === null || v === undefined) return "var(--grid)";
  const t = Math.min(1, Math.abs(v) / cap);
  const alpha = 0.16 + t * 0.72;
  return v >= 0 ? `rgba(12, 163, 12, ${alpha})` : `rgba(208, 59, 59, ${alpha})`;
}

const HEADER = 22; // group title strip, in viewBox units

export function PerformanceTreemap({
  groups,
  title = "Market map",
  height = 520,
}: {
  groups: TreemapGroup[];
  title?: string;
  height?: number;
}) {
  const [horizon, setHorizon] = useState<Horizon>("ytd");

  const live = groups
    .map((g) => ({ ...g, rows: g.rows.filter((r) => r.size > 0) }))
    .filter((g) => g.rows.length > 0);

  if (live.length === 0) {
    return (
      <div className="card">
        <CardHeader eyebrow="Equities" title={title} />
        <p className="muted" style={{ fontSize: 13, margin: 0 }}>
          Price data unavailable.
        </p>
      </div>
    );
  }

  const W = 1000;
  const H = height;

  const blocks = squarify(
    live.map((g) => ({
      value: g.rows.reduce((s, r) => s + r.size, 0),
      item: g,
    })),
    { x: 0, y: 0, w: W, h: H },
  );

  // Cap the ramp at the 90th percentile of absolute moves so one runaway
  // market does not flatten every other tile to the same pale shade.
  const all = live.flatMap((g) => g.rows);
  const moves = all
    .map((r) => Math.abs(r.changes[horizon] ?? 0))
    .sort((a, b) => a - b);
  const cap = Math.max(2, moves[Math.floor(moves.length * 0.9)] ?? 10);

  return (
    <div className="card">
      <CardHeader
        eyebrow="Equities"
        title={title}
        right={<HorizonPills value={horizon} onChange={setHorizon} />}
        caption={`${
          live.length > 1 ? "Grouped by asset class. Tile" : "Tile"
        } area is index weight; colour and the printed figure are the ${
          HORIZONS.find((h) => h.key === horizon)?.label
        } return.`}
      />

      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: "100%", height: "auto", display: "block" }}
        role="img"
        aria-label={`Grouped tree map of ${all.length} instruments by ${horizon} return`}
      >
        {blocks.map((b) => {
          // With a single class there is nothing to distinguish, so the header
          // strip is dead space -- give it back to the tiles.
          const header = live.length === 1 ? 4 : HEADER;
          const inner = {
            x: b.x + 3,
            y: b.y + header,
            w: Math.max(0, b.w - 6),
            h: Math.max(0, b.h - header - 4),
          };
          const tiles = squarify(
            b.rows.map((r) => ({ value: r.size, item: r })),
            inner,
          );
          // Class-level aggregate: weighted by the same sizes the areas use.
          const totalSize = b.rows.reduce((s, r) => s + r.size, 0);
          const agg =
            totalSize > 0
              ? b.rows.reduce(
                  (s, r) => s + (r.changes[horizon] ?? 0) * r.size,
                  0,
                ) / totalSize
              : null;

          return (
            <g key={b.name}>
              <rect
                x={b.x + 1}
                y={b.y + 1}
                width={Math.max(0, b.w - 2)}
                height={Math.max(0, b.h - 2)}
                rx={8}
                fill="var(--page)"
                stroke="var(--border)"
              />
              {live.length > 1 ? (
                <text
                  x={b.x + 10}
                  y={b.y + 16}
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    letterSpacing: "0.04em",
                    fill: "var(--text-secondary)",
                    textTransform: "uppercase",
                  }}
                >
                  {b.name}
                </text>
              ) : null}
              {agg !== null && b.w > 200 && live.length > 1 ? (
                <text
                  x={b.x + b.w - 10}
                  y={b.y + 16}
                  textAnchor="end"
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    fill: "var(--text-secondary)",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {pct(agg, 1)}
                </text>
              ) : null}

              {tiles.map((n) => {
                const v = n.changes[horizon] ?? null;
                // Three tiers rather than "label or no label": a tile too small
                // for 13px type is usually still big enough for 9px, and an
                // unlabelled tile is unreadable however precise its figure is.
                const tier: "lg" | "sm" | "xs" =
                  n.w >= 84 && n.h >= 40 ? "lg" : n.h >= 24 ? "sm" : "xs";
                const nameSize = tier === "lg" ? 13 : 9.5;
                // SVG text neither wraps nor clips, so a long name on a narrow
                // tile spills over its neighbour. ~0.55em per character.
                const budget = Math.floor((n.w - 12) / (nameSize * 0.55));
                const label =
                  n.short.length > budget
                    ? `${n.short.slice(0, Math.max(2, budget - 1))}…`
                    : n.short;
                return (
                  <g key={n.symbol}>
                    <title>{`${n.name}: ${pct(v)} (${horizon.toUpperCase()})`}</title>
                    <rect
                      x={n.x + 1.5}
                      y={n.y + 1.5}
                      width={Math.max(0, n.w - 3)}
                      height={Math.max(0, n.h - 3)}
                      rx={5}
                      fill={tileColor(v, cap)}
                      stroke="var(--border)"
                    />
                    {tier === "lg" ? (
                      <>
                        <text
                          x={n.x + 9}
                          y={n.y + 22}
                          style={{
                            fontSize: 13,
                            fontWeight: 650,
                            fill: "var(--text-primary)",
                          }}
                        >
                          {label}
                        </text>
                        <text
                          x={n.x + 9}
                          y={n.y + 41}
                          style={{
                            fontSize: 15,
                            fontWeight: 650,
                            fill: "var(--text-primary)",
                            fontVariantNumeric: "tabular-nums",
                          }}
                        >
                          {pct(v, 1)}
                        </text>
                      </>
                    ) : tier === "sm" ? (
                      <>
                        <text
                          x={n.x + n.w / 2}
                          y={n.y + n.h / 2 - 3}
                          textAnchor="middle"
                          style={{
                            fontSize: 9.5,
                            fontWeight: 600,
                            fill: "var(--text-secondary)",
                          }}
                        >
                          {label}
                        </text>
                        <text
                          x={n.x + n.w / 2}
                          y={n.y + n.h / 2 + 10}
                          textAnchor="middle"
                          style={{
                            fontSize: 11,
                            fontWeight: 650,
                            fill: "var(--text-primary)",
                            fontVariantNumeric: "tabular-nums",
                          }}
                        >
                          {pct(v, 1)}
                        </text>
                      </>
                    ) : (
                      <text
                        x={n.x + n.w / 2}
                        y={n.y + n.h / 2 + 3}
                        textAnchor="middle"
                        style={{
                          fontSize: 9.5,
                          fontWeight: 600,
                          fill: "var(--text-primary)",
                          fontVariantNumeric: "tabular-nums",
                        }}
                      >
                        {`${label} ${pct(v, 0)}`}
                      </text>
                    )}
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>

      <Caption>
        {live.length > 1
          ? "The figure beside each class name is its weighted aggregate return. "
          : ""}
        Hover any tile for its full name and exact return.
      </Caption>
    </div>
  );
}
