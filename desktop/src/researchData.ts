import { useEffect, useState } from "react";
import { api } from "./api";

export type Observation = {
  value: number; start: string | null; end: string; filed: string; accession: string;
  concept: string; form: string; url: string; last_seen?: string; last_url?: string;
};
export type ResearchValue = { value: number | null; sources: Observation[]; origin?: string };
export type RevisionSeries = {
  id: string; metric: string; label: string; year: number; start: string | null; end: string;
  concept: string; first: number; latest: number; change: number; percent_change: number | null;
  revision_count: number; versions: Observation[];
};
export type RevisionData = {
  years: number[]; series: RevisionSeries[]; revised_periods: number; revised_series: number;
  impacts: { metric: string; label: string; year: number; start: string; end: string;
    first: number; latest: number; unit: "usd" | "percent"; sources: Observation[] }[];
};
export type QuarterPeriod = { start: string; end: string; metrics: Record<string, ResearchValue> };
export type QuarterHistory = { periods: QuarterPeriod[]; ttm: QuarterPeriod | null };
export type PeerData = {
  years: number[]; year: number | null;
  companies: (QuarterPeriod & { company: { ticker: string; name: string } })[];
  errors: { ticker: string; message: string }[];
};

export const currency = (value: number | null | undefined, exact = false) => value == null ? "—" : new Intl.NumberFormat("en-US", {
  style: "currency", currency: "USD", notation: exact ? "standard" : "compact", maximumFractionDigits: exact ? 2 : 2,
}).format(value);
export const percent = (value: number | null | undefined) => value == null ? "—" : `${(value * 100).toFixed(1)}%`;
export const shortDate = (value: string) => new Date(`${value}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
export const periodLabel = (start: string | null, end: string) => start ? `${shortDate(start)} – ${shortDate(end)}` : `As of ${shortDate(end)}`;

export function useResearchData<T>(path: string, version: string) {
  const [state, setState] = useState<{ data: T | null; busy: boolean; error: string }>({ data: null, busy: true, error: "" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setState({ data: null, busy: true, error: "" });
    api<T>(path, { signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) setState({ data, busy: false, error: "" }); })
      .catch(error => { if (!controller.signal.aborted) setState({ data: null, busy: false, error: error instanceof Error ? error.message : "Research data could not be loaded." }); });
    return () => controller.abort();
  }, [path, version, attempt]);
  return { ...state, retry: () => setAttempt(value => value + 1) };
}
