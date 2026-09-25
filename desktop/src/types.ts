export type Filing = {
  form: string; filing_date: string; report_date: string; accession_number: string;
  primary_document: string; cik: string; source_url: string;
};
export type MetricValue = { year: number; value: number | null; display: string };
export type MetricRow = {
  id: string; label: string; values: MetricValue[]; latest_change: string;
  ratio: boolean; featured: boolean; formula: string | null;
  components: Record<string, string>[];
  provenance: { concept: string; filing_date: string; accession: string } | null;
};
export type MetricSection = { title: string; rows: MetricRow[] };
export type QuarterlyGroup = {
  title: string; basis: string;
  rows: { id: string; label: string; value: number | null; display: string;
    period_start: string | null; period_end: string; concept: string }[];
};
export type QuarterlyData = { filing: Filing; groups: QuarterlyGroup[] };
export type CompositionMetric = {
  id: string; label: string; value: number; display: string;
  concept: string | null; period_start: string; period_end: string;
  origin: "reported" | "calculated";
};
export type RevenueSplit = {
  title: string; total: number; total_display: string; period_start: string; period_end: string;
  items: { label: string; value: number; display: string; share: number;
    member: string; axis: string; concept: string }[];
};
export type CompositionData = {
  filing: Filing; basis: string; period_start: string | null; period_end: string;
  metrics: Record<string, CompositionMetric>; bridge: CompositionMetric[];
  expense_details: CompositionMetric[]; revenue_splits: RevenueSplit[];
  reconciliations: { gross_profit: boolean | null; operating_income: boolean | null; net_income: boolean | null };
  split_status: string;
};
export type Anomaly = {
  metric: string; label: string; period: number; prior: number | null; current: number | null;
  absolute_change: number | null; percentage_change: number | null; score: number | null;
  severity: string; method: string; explanation: string;
  impact_direction: string; raw_direction: string; impact_signed: number | null;
};
export type CompanyData = {
  company: { ticker: string; name: string; cik: string };
  latest_year: number | null;
  filings: { annual: Filing | null; quarterly: Filing | null; recent: Filing[] };
  hero: { id: string; label: string; value: string; change: string | null }[];
  ratios: { id: string; label: string; value: string }[];
  statements: Record<string, MetricSection[]>;
  quarterly: QuarterlyData | null;
  flags: { total: number; significant: number; notable: number };
  anomalies: Anomaly[];
  source: { label: string; url: string; latest_filing_date: string | null; cache_updated_at: string | null; loaded_at: string };
};
export type Provider = { id: string; label: string; models: string[]; free_models: string[]; status: string };
export type Answer = {
  answer: string; status: string; filing: Filing;
  sources: { section: string; text: string; url: string; form?: string; score?: number; chunk_id: string }[];
};
export type Brief = { text: string; filing: Filing; filings: Filing[]; sources: Answer["sources"] };
export type FilingIndex = { filing: Filing; chunk_count: number; sections: { title: string; text: string }[] };
export type InsiderData = {
  filings_reviewed: number; failures: string[];
  summary: { purchases: number; sales: number; net: number; insiders: number };
  transactions: Record<string, string | number | boolean | null>[];
};
export type AppSettings = { sec_user_agent: string; ollama_cloud_key_saved: boolean; openai_key_saved: boolean; anthropic_key_saved: boolean; cache_dir: string };
