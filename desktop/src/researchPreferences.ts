import type { CompanyData, Filing } from "./types";

export type ResearchApproach = "explore" | "evaluate" | "follow";
export type SavedCompany = { ticker: string; name: string };
export type ResearchChange = { label: string; detail: string; url: string | null };

export const approaches: { id: ResearchApproach; label: string; description: string }[] = [
  { id: "explore", label: "Explore", description: "Get to know a company and its filings." },
  { id: "evaluate", label: "Evaluate", description: "Examine financial trends, risks, and open questions." },
  { id: "follow", label: "Follow", description: "Keep up with companies you care about." },
];

export const suggestedQuestions: Record<ResearchApproach, string[]> = {
  explore: [
    "How does this company make money?",
    "What does the filing say about its main business segments?",
    "What major risks does the company describe?",
  ],
  evaluate: [
    "How have revenue, margins, and cash generation changed?",
    "What does the filing say about debt and liquidity risks?",
    "Which reported facts complicate a positive reading of recent results?",
  ],
  follow: [
    "What financial trends should I track in future filings?",
    "What does management say drove recent cash flow?",
    "Which disclosed risks should I monitor over time?",
  ],
};

type FilingMarker = Pick<Filing, "accession_number" | "filing_date">;
export type ResearchSnapshot = {
  checkedAt: string;
  latestYear: number | null;
  annual: FilingMarker | null;
  quarterly: FilingMarker | null;
  headline: Record<string, { label: string; value: string }>;
};

const APPROACH_KEY = "fl:research-approach";
const COMPANIES_KEY = "fl:saved-companies";
const snapshotKey = (ticker: string) => `fl:research-snapshot:${ticker}`;

export function readApproach(): ResearchApproach {
  try {
    const value = localStorage.getItem(APPROACH_KEY);
    return approaches.some(item => item.id === value) ? value as ResearchApproach : "explore";
  } catch { return "explore"; }
}

export function saveApproach(value: ResearchApproach) {
  try { localStorage.setItem(APPROACH_KEY, value); } catch { /* research still works without saved preferences */ }
}

export function readSavedCompanies(): SavedCompany[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(COMPANIES_KEY) || "[]");
    if (!Array.isArray(value)) return [];
    return value.filter((item): item is SavedCompany =>
      typeof item?.ticker === "string" && /^[A-Z0-9-]{1,10}$/.test(item.ticker) &&
      typeof item?.name === "string"
    );
  } catch { return []; }
}

export function saveCompanies(value: SavedCompany[]) {
  try { localStorage.setItem(COMPANIES_KEY, JSON.stringify(value)); } catch { /* keep the in-session list */ }
}

export function makeSnapshot(data: CompanyData): ResearchSnapshot {
  return {
    checkedAt: new Date().toISOString(),
    latestYear: data.latest_year,
    annual: data.filings.annual && { accession_number: data.filings.annual.accession_number, filing_date: data.filings.annual.filing_date },
    quarterly: data.filings.quarterly && { accession_number: data.filings.quarterly.accession_number, filing_date: data.filings.quarterly.filing_date },
    headline: Object.fromEntries(data.hero.map(item => [item.id, { label: item.label, value: item.value }])),
  };
}

export function readSnapshot(ticker: string): ResearchSnapshot | null {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(snapshotKey(ticker)) || "null");
    if (!value || typeof value !== "object") return null;
    const snapshot = value as ResearchSnapshot;
    return typeof snapshot.checkedAt === "string" && snapshot.headline && typeof snapshot.headline === "object" ? snapshot : null;
  } catch { return null; }
}

export function saveSnapshot(ticker: string, snapshot: ResearchSnapshot) {
  try { localStorage.setItem(snapshotKey(ticker), JSON.stringify(snapshot)); } catch { /* do not block SEC research */ }
}

export function compareSnapshots(before: ResearchSnapshot | null, after: ResearchSnapshot, data: CompanyData): ResearchChange[] {
  if (!before) return [];
  const changes: ResearchChange[] = [];
  if (after.annual && after.annual.accession_number !== before.annual?.accession_number) {
    changes.push({ label: "New annual filing", detail: `${data.filings.annual?.form || "Annual report"} filed ${after.annual.filing_date}`, url: data.filings.annual?.source_url || null });
  }
  if (after.quarterly && after.quarterly.accession_number !== before.quarterly?.accession_number) {
    changes.push({ label: "New quarterly filing", detail: `${data.filings.quarterly?.form || "Quarterly report"} filed ${after.quarterly.filing_date}`, url: data.filings.quarterly?.source_url || null });
  }
  for (const [id, current] of Object.entries(after.headline)) {
    const previous = before.headline[id];
    if (!previous || previous.value === current.value) continue;
    const periods = before.latestYear === after.latestYear
      ? `FY${after.latestYear ?? "—"} display: ${previous.value} → ${current.value}`
      : `FY${before.latestYear ?? "—"} ${previous.value} → FY${after.latestYear ?? "—"} ${current.value}`;
    changes.push({ label: current.label, detail: periods, url: data.source.url });
  }
  return changes;
}
