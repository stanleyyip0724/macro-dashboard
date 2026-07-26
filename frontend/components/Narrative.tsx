"use client";

/**
 * The written read on a panel's data.
 *
 * Every markets panel pairs its numbers with these sentences, because a level
 * on its own ("gold $4,071") carries no information the reader can act on --
 * direction, pace, and what it implies when combined with the rest of the tape
 * do. The text is generated server-side so it always describes the same
 * snapshot the charts were drawn from.
 */
export function Narrative({
  items,
  title = "What the data is saying",
  compact = false,
}: {
  items?: string[];
  title?: string;
  compact?: boolean;
}) {
  if (!items || items.length === 0) return null;
  return (
    <div style={{ marginTop: compact ? 8 : 12 }}>
      {title ? <p className="h-eyebrow">{title}</p> : null}
      <ul
        style={{
          margin: 0,
          paddingLeft: 16,
          display: "grid",
          gap: compact ? 5 : 7,
          fontSize: compact ? 12 : 13,
          color: "var(--text-secondary)",
          lineHeight: 1.55,
        }}
      >
        {items.map((t, i) => (
          <li key={i}>{t}</li>
        ))}
      </ul>
    </div>
  );
}
