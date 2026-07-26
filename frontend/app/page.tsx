"use client";

import { useState } from "react";
import { useSummary, triggerRefresh } from "../lib/api";
import { MetricCard } from "../components/MetricCard";
import { RiskGauge } from "../components/RiskGauge";
import { RiskBreakdown } from "../components/RiskBreakdown";
import { CyclePanel } from "../components/CyclePanel";
import { CycleClock } from "../components/CycleClock";
import { CompositeChart } from "../components/CompositeChart";
import { AlertPanel } from "../components/AlertPanel";

export default function Dashboard() {
  const { data, error, isLoading, mutate } = useSummary();
  const [refreshing, setRefreshing] = useState(false);

  async function onRefresh() {
    setRefreshing(true);
    try {
      await triggerRefresh(false);
      await mutate();
    } finally {
      setRefreshing(false);
    }
  }

  if (error) {
    return (
      <main className="wrap">
        <div className="card" style={{ borderColor: "var(--status-critical)" }}>
          <h1 style={{ fontSize: 18, margin: "0 0 6px" }}>
            Cannot reach the API
          </h1>
          <p className="muted" style={{ margin: 0, fontSize: 13 }}>
            {String(error)}
          </p>
          <p className="muted" style={{ marginTop: 10, fontSize: 13 }}>
            Start the backend with{" "}
            <code>uvicorn app.main:app --reload</code> and confirm{" "}
            <code>NEXT_PUBLIC_API_BASE</code> points at it.
          </p>
        </div>
      </main>
    );
  }

  if (isLoading || !data) {
    return (
      <main className="wrap">
        <p className="muted">Loading macro data…</p>
      </main>
    );
  }

  const { cycle, risk, alerts, headline, composites } = data;

  return (
    <main className="wrap">
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-end",
          flexWrap: "wrap",
          gap: 12,
          marginBottom: 20,
        }}
      >
        <div>
          <h1 style={{ fontSize: 22, margin: 0, fontWeight: 650 }}>
            US Macroeconomic Health
          </h1>
          <p className="muted" style={{ margin: "4px 0 0", fontSize: 12 }}>
            Data through {data.data_as_of ?? "—"} · computed{" "}
            {data.generated_at.replace("T", " ")} · {data.coverage_note}
          </p>
        </div>
        <button
          onClick={onRefresh}
          disabled={refreshing}
          style={{
            font: "inherit",
            fontSize: 13,
            padding: "7px 14px",
            borderRadius: 8,
            cursor: refreshing ? "wait" : "pointer",
            border: "1px solid var(--border)",
            background: "var(--surface-1)",
            color: "var(--text-primary)",
          }}
        >
          {refreshing ? "Refreshing…" : "Refresh data"}
        </button>
      </header>

      {/* Headline metric cards */}
      <section
        className="grid"
        style={{
          // min(Npx, 100%) is load-bearing: a bare minmax(Npx, 1fr) forces a
          // column wider than a narrow viewport, which scrolls the whole page
          // sideways. The min() lets the track collapse below its ideal width.
          gridTemplateColumns: "repeat(auto-fill, minmax(min(190px, 100%), 1fr))",
          marginBottom: 16,
        }}
      >
        {headline.map((c) => (
          <MetricCard key={c.series_id} card={c} />
        ))}
      </section>

      {/* Verdict row: phase, gauge, alerts */}
      <section
        className="grid"
        style={{
          gridTemplateColumns: "repeat(auto-fit, minmax(min(320px, 100%), 1fr))",
          marginBottom: 16,
          alignItems: "start",
        }}
      >
        <CyclePanel cycle={cycle} />
        <div className="grid">
          <RiskGauge risk={risk} />
        </div>
        <AlertPanel alerts={alerts} />
      </section>

      {/* Charts */}
      <section
        className="grid"
        style={{
          gridTemplateColumns: "repeat(auto-fit, minmax(min(420px, 100%), 1fr))",
          marginBottom: 16,
          alignItems: "start",
        }}
      >
        <CompositeChart composites={composites} />
        <CycleClock cycle={cycle} />
      </section>

      <section style={{ marginBottom: 16 }}>
        <RiskBreakdown risk={risk} />
      </section>

      <footer
        className="muted"
        style={{ fontSize: 11, lineHeight: 1.6, marginTop: 8 }}
      >
        <p style={{ margin: 0 }}>
          Source: Federal Reserve Bank of St. Louis (FRED). This dashboard is a
          quantitative summary of public data, not investment advice. The cycle
          phase and risk score are model outputs calibrated on revised — not
          real-time — history; see <code>scripts/backtest.py</code> for measured
          precision and recall.
        </p>
      </footer>
    </main>
  );
}
