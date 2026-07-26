"use client";

import {
  CartesianGrid,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import type { Cycle } from "../lib/types";

/**
 * The cycle clock: growth level (x) against 3-month momentum (y), with the
 * last 60 months as a trail.
 *
 * Colour choice matters here. Colouring points by PHASE would need five
 * categorical hues in a scatter -- an all-pairs form, where the palette caps
 * safe categorical use at three slots. So phase is encoded by the quadrant
 * BACKGROUND (position, always readable) and the trail is coloured by
 * RECENCY on a single-hue sequential ramp, which is what the eye actually
 * needs: "where are we now versus where were we".
 */
export function CycleClock({ cycle }: { cycle: Cycle }) {
  const pts = cycle.history.map((p, i) => ({
    ...p,
    // Recency 0..1 across the trail.
    recency: cycle.history.length > 1 ? i / (cycle.history.length - 1) : 1,
    isLatest: i === cycle.history.length - 1,
  }));

  const xs = pts.map((p) => p.level);
  const ys = pts.map((p) => p.momentum);
  const pad = 0.35;

  // Snap the domain outward to a clean 0.5 step. Deriving bounds straight from
  // the data leaks binary floating-point noise into the tick labels -- Recharts
  // renders the raw domain numbers, producing axis ticks like
  // "-0.7499999999999998". Rounding the domain fixes the cause; the
  // tickFormatter below is the belt-and-braces for interpolated ticks.
  const floorTo = (v: number, step = 0.5) => Math.floor(v / step) * step;
  const ceilTo = (v: number, step = 0.5) => Math.ceil(v / step) * step;

  const xMin = floorTo(Math.min(-1.2, ...xs) - pad);
  const xMax = ceilTo(Math.max(1.2, ...xs) + pad);
  const yMin = floorTo(Math.min(-0.6, ...ys) - pad);
  const yMax = ceilTo(Math.max(0.6, ...ys) + pad);

  const axisTick = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}`;

  const RAMP = [
    "var(--seq-250)",
    "var(--seq-350)",
    "var(--seq-450)",
    "var(--seq-550)",
    "var(--seq-700)",
  ];
  const rampColor = (r: number) =>
    RAMP[Math.min(RAMP.length - 1, Math.floor(r * RAMP.length))];

  const CONTRACTION_LEVEL = -0.7;

  const quadrants = [
    { x1: 0.15, x2: xMax, y1: 0, y2: yMax, label: "Expansion" },
    { x1: 0.15, x2: xMax, y1: yMin, y2: 0, label: "Peak" },
    { x1: xMin, x2: CONTRACTION_LEVEL, y1: yMin, y2: 0, label: "Contraction" },
    { x1: xMin, x2: CONTRACTION_LEVEL, y1: 0, y2: yMax, label: "Trough / Recovery" },
  ];

  return (
    <div className="card">
      <p className="h-eyebrow">Cycle clock — last 60 months</p>
      <div style={{ width: "100%", height: 340 }}>
        <ResponsiveContainer>
          <ScatterChart margin={{ top: 12, right: 20, bottom: 34, left: 8 }}>
            {quadrants.map((q) => (
              <ReferenceArea
                key={q.label}
                x1={q.x1}
                x2={q.x2}
                y1={q.y1}
                y2={q.y2}
                fill="var(--text-primary)"
                fillOpacity={0.035}
                stroke="none"
                label={{
                  value: q.label,
                  position: "insideTopLeft",
                  fill: "var(--text-muted)",
                  fontSize: 10,
                }}
              />
            ))}

            <CartesianGrid stroke="var(--grid)" strokeDasharray="2 4" />
            <ReferenceLine y={0} stroke="var(--axis)" />
            <ReferenceLine x={0} stroke="var(--axis)" />
            <ReferenceLine
              x={CONTRACTION_LEVEL}
              stroke="var(--status-critical)"
              strokeDasharray="4 3"
              label={{
                value: "recession threshold",
                position: "insideBottomLeft",
                fill: "var(--status-critical)",
                fontSize: 10,
              }}
            />

            <XAxis
              type="number"
              dataKey="level"
              domain={[xMin, xMax]}
              tickCount={7}
              tickFormatter={axisTick}
              tick={{ fill: "var(--text-muted)", fontSize: 11 }}
              stroke="var(--axis)"
              label={{
                value: "Growth level (σ from trend)",
                position: "insideBottom",
                offset: -18,
                fill: "var(--text-secondary)",
                fontSize: 11,
              }}
            />
            <YAxis
              type="number"
              dataKey="momentum"
              domain={[yMin, yMax]}
              tickCount={6}
              tickFormatter={axisTick}
              tick={{ fill: "var(--text-muted)", fontSize: 11 }}
              stroke="var(--axis)"
              label={{
                value: "3m momentum (σ)",
                angle: -90,
                position: "insideLeft",
                fill: "var(--text-secondary)",
                fontSize: 11,
              }}
            />
            <ZAxis range={[36, 36]} />

            <Tooltip
              cursor={{ stroke: "var(--axis)", strokeDasharray: "3 3" }}
              contentStyle={{
                background: "var(--surface-1)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                fontSize: 12,
              }}
              formatter={(v: number, name: string) => [v.toFixed(3), name]}
              labelFormatter={() => ""}
              content={({ payload }) => {
                if (!payload?.length) return null;
                const p = payload[0].payload;
                return (
                  <div
                    style={{
                      background: "var(--surface-1)",
                      border: "1px solid var(--border)",
                      borderRadius: 8,
                      padding: "8px 10px",
                      fontSize: 12,
                    }}
                  >
                    <div style={{ fontWeight: 650 }}>{p.date}</div>
                    <div className="muted">Phase: {p.phase}</div>
                    <div className="tabular muted">
                      level {p.level.toFixed(2)}σ · momentum{" "}
                      {p.momentum.toFixed(2)}σ
                    </div>
                  </div>
                );
              }}
            />

            <Scatter
              data={pts}
              isAnimationActive={false}
              shape={(props: any) => {
                const { cx, cy, payload } = props;
                if (payload.isLatest) {
                  return (
                    <g>
                      {/* 2px surface ring keeps the marker legible over the trail. */}
                      <circle cx={cx} cy={cy} r={9} fill="var(--surface-1)" />
                      <circle
                        cx={cx}
                        cy={cy}
                        r={7}
                        fill="var(--status-critical)"
                        stroke="var(--surface-1)"
                        strokeWidth={2}
                      />
                      <text
                        x={cx + 12}
                        y={cy + 4}
                        style={{
                          fontSize: 11,
                          fontWeight: 650,
                          fill: "var(--text-primary)",
                        }}
                      >
                        Now
                      </text>
                    </g>
                  );
                }
                return (
                  <circle
                    cx={cx}
                    cy={cy}
                    r={4}
                    fill={rampColor(payload.recency)}
                    fillOpacity={0.35 + 0.65 * payload.recency}
                  />
                );
              }}
            />
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          fontSize: 11,
          color: "var(--text-muted)",
          marginTop: 4,
        }}
      >
        <span>60 months ago</span>
        <span
          style={{
            flex: "0 1 120px",
            height: 6,
            borderRadius: 3,
            background:
              "linear-gradient(90deg, var(--seq-250), var(--seq-700))",
          }}
        />
        <span>now</span>
      </div>
    </div>
  );
}
