"use client";

import { useMemo, useState } from "react";

import { NewsItem } from "../lib/markets";
import { CardHeader, Caption } from "./ui";

/**
 * Latest market headlines, each tagged with its transmission channel and the
 * mechanism by which it reaches prices.
 *
 * The headline alone is not the product -- the second line is. A story about
 * export controls matters because it re-routes a supply chain and lifts input
 * costs, and that sentence is what the reader is here for.
 */

const CHANNEL_COLOR: Record<string, string> = {
  Rates: "var(--series-1)",
  Inflation: "var(--status-serious)",
  "Trade & supply chain": "var(--series-2)",
  Semiconductors: "var(--series-3)",
  Energy: "var(--series-4)",
  Labour: "var(--seq-450)",
  Credit: "var(--status-critical)",
  Earnings: "var(--seq-550)",
  China: "var(--status-warning)",
  Geopolitics: "var(--status-critical)",
  "AI capex": "var(--series-3)",
  Market: "var(--text-muted)",
};

function timeAgo(published: string): string {
  const t = Date.parse(published);
  if (Number.isNaN(t)) return "";
  const mins = Math.round((Date.now() - t) / 60000);
  if (mins < 60) return `${Math.max(1, mins)}m ago`;
  if (mins < 60 * 24) return `${Math.round(mins / 60)}h ago`;
  return `${Math.round(mins / 1440)}d ago`;
}

export function NewsPanel({ items }: { items?: NewsItem[] }) {
  const [channel, setChannel] = useState<string | null>(null);
  const [limit, setLimit] = useState(10);

  const channels = useMemo(() => {
    const counts = new Map<string, number>();
    for (const i of items ?? []) {
      counts.set(i.channel, (counts.get(i.channel) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [items]);

  if (!items || items.length === 0) {
    return (
      <div className="card">
        <CardHeader eyebrow="News" title="Latest market news" />
        <p className="muted" style={{ fontSize: 13, margin: 0 }}>
          Headline feed unavailable right now.
        </p>
      </div>
    );
  }

  const filtered = channel
    ? items.filter((i) => i.channel === channel)
    : items;

  return (
    <div className="card">
      <CardHeader
        eyebrow="News"
        title="Latest market news & what it transmits to"
        caption="Each headline is tagged with the channel it reaches markets through, and the mechanism underneath. Filter by channel to see the cluster."
      />

      <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginBottom: 12 }}>
        <button
          onClick={() => setChannel(null)}
          aria-pressed={channel === null}
          style={chipStyle(channel === null, "var(--text-primary)")}
        >
          All {items.length}
        </button>
        {channels.map(([c, n]) => (
          <button
            key={c}
            onClick={() => setChannel(channel === c ? null : c)}
            aria-pressed={channel === c}
            style={chipStyle(channel === c, CHANNEL_COLOR[c] ?? "var(--text-muted)")}
          >
            {c} {n}
          </button>
        ))}
      </div>

      <ol style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 12 }}>
        {filtered.slice(0, limit).map((it, i) => (
          <li
            key={`${it.link}-${i}`}
            style={{
              borderLeft: `3px solid ${CHANNEL_COLOR[it.channel] ?? "var(--grid)"}`,
              paddingLeft: 10,
            }}
          >
            <div
              style={{
                display: "flex",
                gap: 8,
                alignItems: "baseline",
                flexWrap: "wrap",
                fontSize: 11,
                color: "var(--text-muted)",
              }}
            >
              <span
                style={{
                  fontWeight: 650,
                  color: CHANNEL_COLOR[it.channel] ?? "var(--text-secondary)",
                }}
              >
                {it.channel}
              </span>
              {it.source ? <span>· {it.source}</span> : null}
              {it.published ? <span>· {timeAgo(it.published)}</span> : null}
            </div>
            <a
              href={it.link}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: "block",
                fontSize: 13.5,
                fontWeight: 600,
                color: "var(--text-primary)",
                textDecoration: "none",
                lineHeight: 1.4,
                marginTop: 2,
              }}
            >
              {it.title}
            </a>
            <p
              style={{
                margin: "3px 0 0",
                fontSize: 12,
                lineHeight: 1.5,
                color: "var(--text-secondary)",
              }}
            >
              <strong style={{ color: "var(--text-primary)" }}>Implication: </strong>
              {it.implication}
            </p>
          </li>
        ))}
      </ol>

      {filtered.length > limit ? (
        <button
          onClick={() => setLimit((l) => l + 10)}
          style={{
            font: "inherit",
            fontSize: 12,
            marginTop: 12,
            padding: "5px 12px",
            borderRadius: 8,
            cursor: "pointer",
            border: "1px solid var(--border)",
            background: "transparent",
            color: "var(--text-secondary)",
          }}
        >
          Show {Math.min(10, filtered.length - limit)} more
        </button>
      ) : null}

      <Caption>
        Headlines via Google News. Implications are rule-based readings of the
        usual transmission channel, not forecasts.
      </Caption>
    </div>
  );
}

function chipStyle(active: boolean, color: string): React.CSSProperties {
  return {
    font: "inherit",
    fontSize: 11,
    padding: "2px 9px",
    borderRadius: 999,
    cursor: "pointer",
    border: `1px solid ${active ? color : "var(--border)"}`,
    background: active ? color : "transparent",
    color: active ? "var(--surface-1)" : "var(--text-secondary)",
  };
}
