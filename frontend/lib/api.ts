import useSWR from "swr";
import type { Summary, SeriesDetail, IndicatorCard } from "./types";

// The API base is a PUBLIC env var, and that is the point: the browser never
// sees the FRED key. All FRED access happens server-side in the FastAPI
// backend. Never put the FRED key in a NEXT_PUBLIC_* variable -- anything with
// that prefix is inlined into the JavaScript bundle and shipped to every user.
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function fetcher<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(
      `${res.status} ${res.statusText}${body ? `: ${body.slice(0, 200)}` : ""}`,
      res.status,
    );
  }
  return res.json() as Promise<T>;
}

// The backend recomputes its snapshot at most every 5 minutes, so polling
// faster than that only burns bandwidth for identical bytes.
const REFRESH_MS = 5 * 60 * 1000;

export function useSummary() {
  return useSWR<Summary>("/api/summary", fetcher, {
    refreshInterval: REFRESH_MS,
    revalidateOnFocus: false,
    keepPreviousData: true,
  });
}

export function useSeries(seriesId: string | null) {
  return useSWR<SeriesDetail>(
    seriesId ? `/api/series/${seriesId}` : null,
    fetcher,
    { revalidateOnFocus: false, keepPreviousData: true },
  );
}

export function useSeriesList(klass?: string) {
  const qs = klass ? `?klass=${klass}` : "";
  return useSWR<IndicatorCard[]>(`/api/series${qs}`, fetcher, {
    refreshInterval: REFRESH_MS,
    revalidateOnFocus: false,
  });
}

export async function triggerRefresh(force = false): Promise<void> {
  const res = await fetch(`${API_BASE}/api/refresh?force=${force}`, {
    method: "POST",
  });
  if (!res.ok) throw new ApiError(`refresh failed: ${res.status}`, res.status);
}

// -- formatting helpers -------------------------------------------------

export function formatValue(v: number | null, unit: string): string {
  if (v === null || Number.isNaN(v)) return "—";
  switch (unit) {
    case "%":
      return `${v.toFixed(2)}%`;
    case "pp":
      return `${v >= 0 ? "+" : ""}${v.toFixed(2)}pp`;
    case "k jobs":
      return `${v >= 0 ? "+" : ""}${Math.round(v).toLocaleString()}k`;
    case "std dev":
    case "sd":
      return `${v >= 0 ? "+" : ""}${v.toFixed(2)}σ`;
    case "index":
    case "0/1":
      return v.toFixed(1);
    case "hrs":
      return `${v >= 0 ? "+" : ""}${v.toFixed(2)}h`;
    case "net %":
      return `${v.toFixed(1)}%`;
    default:
      return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
}

export function formatDelta(v: number | null, unit: string): string {
  if (v === null || Number.isNaN(v)) return "—";
  const s = formatValue(Math.abs(v), unit).replace(/^[+-]/, "");
  return `${v >= 0 ? "▲" : "▼"} ${s}`;
}

/**
 * Direction a change should be COLOURED, accounting for polarity.
 * Falling unemployment and rising GDP are both "good" and must both render
 * green -- colouring by the raw sign of the change would get half the
 * dashboard exactly backwards.
 */
export function changeSentiment(
  change: number | null,
  polarity: number,
): "good" | "bad" | "neutral" {
  if (change === null || Math.abs(change) < 1e-9) return "neutral";
  return change * polarity > 0 ? "good" : "bad";
}
