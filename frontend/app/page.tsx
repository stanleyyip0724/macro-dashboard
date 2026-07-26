"use client";

import { useState } from "react";

import { useSummary, triggerRefresh } from "../lib/api";
import { useMarkets } from "../lib/markets";
import { MetricCard } from "../components/MetricCard";
import { RiskGauge } from "../components/RiskGauge";
import { RiskBreakdown } from "../components/RiskBreakdown";
import { AlertPanel } from "../components/AlertPanel";
import { FearGreedPanel } from "../components/FearGreedPanel";
import { MarketTable } from "../components/MarketTable";
import { Narrative } from "../components/Narrative";
import { NewsPanel } from "../components/NewsPanel";
import { PerformanceTreemap } from "../components/PerformanceTreemap";
import { YieldCurveChart } from "../components/YieldCurveChart";
import { VolatilityCard } from "../components/VolatilityCard";
import { YtdPathChart } from "../components/YtdPathChart";

type Tab = "markets" | "macro";

export default function Dashboard() {
  const { data, error, isLoading, mutate } = useSummary();
  // Markets load independently of the macro summary: they come from public
  // endpoints with no SLA, so a failure there degrades one tab, not the page.
  const { data: mkt, error: mktError, mutate: mutateMarkets } = useMarkets();
  const [tab, setTab] = useState<Tab>("markets");
  const [refreshing, setRefreshing] = useState(false);

  async function onRefresh() {
    setRefreshing(true);
    try {
      await triggerRefresh(false);
      await Promise.all([mutate(), mutateMarkets()]);
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

  const { risk, alerts, headline } = data;

  // Sectors only: the map answers "what is leading inside the US market", and
  // every other asset class already has a table with the horizons on it.
  const treemapGroups = [
    { name: "US equity sectors", rows: mkt?.sections.sectors ?? [] },
  ].filter((g) => g.rows.length > 0);

  const vix = mkt?.sections.volatility?.[0];

  return (
    <main className="wrap">
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-end",
          flexWrap: "wrap",
          gap: 12,
          marginBottom: 14,
        }}
      >
        <div>
          <h1 style={{ fontSize: 22, margin: 0, fontWeight: 650 }}>
            Markets &amp; US Macro Health
          </h1>
          <p className="muted" style={{ margin: "4px 0 0", fontSize: 12 }}>
            Macro through {data.data_as_of ?? "—"}
            {mkt?.data_as_of ? ` · prices through ${mkt.data_as_of}` : ""} ·
            computed {data.generated_at.replace("T", " ")}
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

      <nav
        style={{
          display: "flex",
          gap: 4,
          borderBottom: "1px solid var(--border)",
          marginBottom: 16,
        }}
      >
        {(
          [
            ["markets", "Markets"],
            ["macro", "US macro"],
          ] as [Tab, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            aria-pressed={tab === key}
            style={{
              font: "inherit",
              fontSize: 13,
              fontWeight: tab === key ? 650 : 500,
              padding: "8px 14px",
              cursor: "pointer",
              border: "none",
              background: "transparent",
              color: tab === key ? "var(--text-primary)" : "var(--text-muted)",
              borderBottom: `2px solid ${
                tab === key ? "var(--text-primary)" : "transparent"
              }`,
              marginBottom: -1,
            }}
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === "markets" ? (
        <>
          {mktError && !mkt ? (
            <div className="card" style={{ marginBottom: 16 }}>
              <p className="h-eyebrow">Markets</p>
              <p className="muted" style={{ margin: 0, fontSize: 13 }}>
                Market data is unavailable right now ({String(mktError)}). The US
                macro tab is unaffected.
              </p>
            </div>
          ) : null}

          {!mkt ? (
            <p className="muted">Loading market data…</p>
          ) : (
            <>
              {/* The read on the whole tape, before any individual number. */}
              <section className="card" style={{ marginBottom: 16 }}>
                <p className="h-eyebrow">Where markets stand</p>
                <Narrative items={mkt.summary} title="" />
                <p
                  style={{
                    fontSize: 11,
                    color: "var(--text-muted)",
                    margin: "10px 0 0",
                  }}
                >
                  {mkt.coverage_note}
                  {Object.keys(mkt.errors ?? {}).length > 0
                    ? ` Degraded sections: ${Object.keys(mkt.errors).join(", ")}.`
                    : ""}
                </p>
              </section>

              <section style={{ marginBottom: 16 }}>
                <PerformanceTreemap
                  groups={treemapGroups}
                  title="US equity sector map"
                  height={420}
                />
              </section>

              <section style={{ marginBottom: 16 }}>
                <MarketTable
                  eyebrow="Equities"
                  title="Major index performance"
                  rows={mkt.sections.indices}
                  commentary={mkt.commentary.equities}
                  showRegion
                />
              </section>

              <section style={{ marginBottom: 16 }}>
                <MarketTable
                  eyebrow="Equities"
                  title="US sector performance"
                  rows={mkt.sections.sectors}
                  commentary={mkt.commentary.sectors}
                />
              </section>

              <section style={{ marginBottom: 16 }}>
                <YtdPathChart rows={mkt.sections.indices ?? []} />
              </section>

              <section
                className="grid"
                style={{
                  gridTemplateColumns:
                    "repeat(auto-fit, minmax(min(460px, 100%), 1fr))",
                  marginBottom: 16,
                  alignItems: "start",
                }}
              >
                <MarketTable
                  eyebrow="Commodities"
                  title="Key commodity prices"
                  rows={mkt.sections.commodities}
                  commentary={mkt.commentary.commodities}
                />
                <MarketTable
                  eyebrow="Crypto & FX"
                  title="Bitcoin and the dollar"
                  rows={[
                    ...(mkt.sections.crypto ?? []),
                    ...(mkt.sections.fx ?? []),
                  ]}
                  commentary={mkt.commentary.fx_crypto}
                />
              </section>

              <section
                className="grid"
                style={{
                  gridTemplateColumns:
                    "repeat(auto-fit, minmax(min(420px, 100%), 1fr))",
                  marginBottom: 16,
                  alignItems: "start",
                }}
              >
                {/* Risk gauges first (VIX, then sentiment), curve last: the
                    two gauges are the fastest-moving reads on the page. */}
                <VolatilityCard row={vix} />
                <FearGreedPanel fg={mkt.fear_greed} />
              </section>

              <section style={{ marginBottom: 16 }}>
                <YieldCurveChart curve={mkt.curve} />
              </section>

              <section style={{ marginBottom: 16 }}>
                <NewsPanel items={mkt.news} />
              </section>
            </>
          )}
        </>
      ) : (
        <>
          {/* Headline metric cards */}
          <section
            className="grid"
            style={{
              // min(Npx, 100%) is load-bearing: a bare minmax(Npx, 1fr) forces a
              // column wider than a narrow viewport, which scrolls the whole page
              // sideways. The min() lets the track collapse below its ideal width.
              gridTemplateColumns:
                "repeat(auto-fill, minmax(min(190px, 100%), 1fr))",
              marginBottom: 16,
            }}
          >
            {headline.map((c) => (
              <MetricCard key={c.series_id} card={c} />
            ))}
          </section>

          {/* Sentiment lives on the Markets tab only -- it is a market read,
              not a macro one, and showing the same gauge twice made the two
              tabs look like they were reporting different things. */}
          <section style={{ marginBottom: 16 }}>
            <AlertPanel alerts={alerts} />
          </section>

          <section
            className="grid"
            style={{
              gridTemplateColumns:
                "repeat(auto-fit, minmax(min(320px, 100%), 1fr))",
              marginBottom: 16,
              alignItems: "start",
            }}
          >
            <RiskGauge risk={risk} />
            <RiskBreakdown risk={risk} />
          </section>

          <p className="muted" style={{ fontSize: 11, margin: "0 0 8px" }}>
            {data.coverage_note}
          </p>
        </>
      )}

      <footer
        className="muted"
        style={{ fontSize: 11, lineHeight: 1.6, marginTop: 8 }}
      >
        <p style={{ margin: 0 }}>
          Macro source: Federal Reserve Bank of St. Louis (FRED). Prices: Yahoo
          Finance. Sentiment: CNN Fear &amp; Greed. Headlines: Google News. This
          dashboard is a quantitative summary of public data, not investment
          advice. The cycle phase and risk score are model outputs calibrated on
          revised — not real-time — history; see <code>scripts/backtest.py</code>{" "}
          for measured precision and recall. Written commentary is generated by
          deterministic rules over the same snapshot the charts are drawn from,
          and describes historical transmission channels rather than forecasts.
        </p>
      </footer>
    </main>
  );
}
