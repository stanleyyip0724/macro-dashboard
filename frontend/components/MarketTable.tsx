"use client";

import { useState } from "react";

import {
  HORIZONS,
  Horizon,
  MarketRow,
  moveColor,
  pct,
  price,
} from "../lib/markets";
import { Narrative } from "./Narrative";
import { CardHeader, Caption, HorizonPills } from "./ui";

/**
 * Performance table for one asset group.
 *
 * The YTD column carries a bar as well as a number: across a dozen markets the
 * ranking is the point, and a shared-scale bar makes "Korea is running away
 * from everyone" readable at a glance in a way a column of figures is not. The
 * bar is a redundant encoding -- the number is always there -- so nothing is
 * lost if it is missed.
 */
export function MarketTable({
  title,
  eyebrow,
  rows,
  commentary,
  defaultSort = "ytd",
  showRegion = false,
}: {
  title: string;
  eyebrow?: string;
  rows?: MarketRow[];
  commentary?: string[];
  defaultSort?: Horizon;
  showRegion?: boolean;
}) {
  const [sort, setSort] = useState<Horizon>(defaultSort);
  const [open, setOpen] = useState<string | null>(null);

  if (!rows || rows.length === 0) {
    return (
      <div className="card">
        <CardHeader eyebrow={eyebrow ?? "Markets"} title={title} />
        <p className="muted" style={{ fontSize: 13, margin: 0 }}>
          Price data unavailable right now. The rest of the dashboard is
          unaffected.
        </p>
      </div>
    );
  }

  const sorted = [...rows].sort((a, b) => {
    const av = a.changes[sort];
    const bv = b.changes[sort];
    if (av === null || av === undefined) return 1;
    if (bv === null || bv === undefined) return -1;
    return bv - av;
  });

  // One shared scale for the bars, so column widths are comparable row to row.
  const maxAbs = Math.max(
    1,
    ...rows.map((r) => Math.abs(r.changes[sort] ?? 0)),
  );

  return (
    <div className="card">
      <CardHeader
        eyebrow={eyebrow ?? "Markets"}
        title={title}
        right={<HorizonPills value={sort} onChange={setSort} />}
        caption={`Ranked by ${HORIZONS.find((h) => h.key === sort)?.label} return, best first.`}
      />

      <div className="scroll-x">
        <table className="tabular">
          <thead>
            <tr>
              <th>Instrument</th>
              {showRegion ? <th>Region</th> : null}
              <th style={{ textAlign: "right" }}>Last</th>
              {HORIZONS.map((h) => (
                <th
                  key={h.key}
                  onClick={() => setSort(h.key)}
                  aria-sort={h.key === sort ? "descending" : "none"}
                  title={`Sort by ${h.label} return, best first`}
                  style={{
                    textAlign: "right",
                    cursor: "pointer",
                    color:
                      h.key === sort ? "var(--text-primary)" : "var(--text-muted)",
                  }}
                >
                  {h.label}
                  {/* The arrow marks which column the ranking is by, and its
                      direction. Without it the row order looks arbitrary. */}
                  {h.key === sort ? (
                    <span aria-hidden="true" style={{ marginLeft: 3 }}>
                      ▼
                    </span>
                  ) : null}
                </th>
              ))}
              <th style={{ width: 130 }}>
                {sort.toUpperCase()} vs peers ▼
              </th>
              <th style={{ width: 92 }}>52w range</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => {
              const v = r.changes[sort] ?? null;
              const polarity = r.group === "volatility" ? -1 : 1;
              const width = v === null ? 0 : (Math.abs(v) / maxAbs) * 50;
              return (
                <tr
                  key={r.symbol}
                  onClick={() => setOpen(open === r.symbol ? null : r.symbol)}
                  style={{ cursor: "pointer" }}
                  title={r.notes || r.name}
                >
                  <td style={{ fontWeight: 600 }}>{r.short}</td>
                  {showRegion ? (
                    <td className="muted" style={{ fontSize: 12 }}>
                      {r.region}
                    </td>
                  ) : null}
                  <td style={{ textAlign: "right" }}>
                    {price(r.price, r.unit)}
                  </td>
                  {HORIZONS.map((h) => (
                    <td
                      key={h.key}
                      style={{
                        textAlign: "right",
                        color: moveColor(r.changes[h.key], polarity),
                        fontWeight: h.key === sort ? 650 : 400,
                      }}
                    >
                      {pct(r.changes[h.key], h.key === "1d" ? 2 : 1)}
                    </td>
                  ))}
                  <td>
                    {/* Diverging bar from a centre line: sign is position, size is magnitude. */}
                    <div
                      style={{
                        position: "relative",
                        height: 10,
                        background: "var(--grid)",
                        borderRadius: 3,
                      }}
                    >
                      <div
                        style={{
                          position: "absolute",
                          left: v !== null && v < 0 ? `${50 - width}%` : "50%",
                          width: `${width}%`,
                          top: 0,
                          bottom: 0,
                          background: moveColor(v, polarity),
                          borderRadius: 3,
                        }}
                      />
                      <div
                        style={{
                          position: "absolute",
                          left: "50%",
                          top: -2,
                          bottom: -2,
                          width: 1,
                          background: "var(--axis)",
                        }}
                      />
                    </div>
                  </td>
                  <td>
                    <RangeDots position={r.range_position} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {open
        ? (() => {
            const r = rows.find((x) => x.symbol === open);
            if (!r) return null;
            return (
              <div
                style={{
                  marginTop: 10,
                  padding: "10px 12px",
                  borderRadius: 8,
                  background: "var(--page)",
                  border: "1px solid var(--border)",
                }}
              >
                <p style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>
                  {r.name}
                </p>
                <p
                  className="muted"
                  style={{ margin: "4px 0 0", fontSize: 12.5, lineHeight: 1.55 }}
                >
                  {r.commentary}
                </p>
                {r.notes ? (
                  <p
                    style={{
                      margin: "6px 0 0",
                      fontSize: 12,
                      color: "var(--text-muted)",
                    }}
                  >
                    {r.notes}
                  </p>
                ) : null}
              </div>
            );
          })()
        : <Caption>Select a row for the read on that instrument.</Caption>}

      <Narrative items={commentary} />
    </div>
  );
}

/** Where the last price sits inside the 52-week range. */
function RangeDots({ position }: { position: number | null }) {
  if (position === null) return <span className="muted">—</span>;
  return (
    <div
      style={{ position: "relative", height: 10 }}
      title={`${(position * 100).toFixed(0)}% of the 52-week range`}
    >
      <div
        style={{
          position: "absolute",
          top: 4,
          left: 0,
          right: 0,
          height: 2,
          background: "var(--grid)",
        }}
      />
      <div
        style={{
          position: "absolute",
          top: 1,
          left: `calc(${Math.max(0, Math.min(100, position * 100))}% - 4px)`,
          width: 8,
          height: 8,
          borderRadius: 999,
          background: "var(--series-1)",
        }}
      />
    </div>
  );
}
