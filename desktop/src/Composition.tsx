import { useEffect, useState } from "react";
import { ArrowRight, BookOpen, ShieldCheck } from "lucide-react";
import { api } from "./api";
import { External, Notice } from "./visuals";
import type { CompanyData, CompositionData, CompositionMetric, RevenueSplit } from "./types";

type FilingForm = "10-K" | "10-Q";
type Depth = "brief" | "deep";
const dateLabel = (value: string | null | undefined) => value
  ? new Date(`${value}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
  : "Unavailable";

function RevenueMix({ group, compact = false }: { group: RevenueSplit; compact?: boolean }) {
  return <div className="composition-mix"><div className="composition-mix-head"><h4>{group.title}</h4><span>Totals {group.total_display}</span></div>
    {(compact ? group.items.slice(0, 5) : group.items).map(item => <div className="mix-row" key={item.member}>
      <div className="mix-label"><strong>{item.label}</strong><span>{item.display} · {(item.share * 100).toFixed(1)}%</span></div>
      <div className="mix-track" aria-hidden="true"><span style={{ width: `${Math.min(100, Math.max(0, item.share * 100))}%` }}/></div>
    </div>)}
    {compact && group.items.length > 5 && <p className="composition-muted">See the remaining categories in Deep dive.</p>}
  </div>;
}

function MetricTable({ rows }: { rows: CompositionMetric[] }) {
  return <div className="table-scroll"><table className="data-table composition-table"><thead><tr><th>Line item</th><th>Amount</th><th>Basis</th><th>US-GAAP concept</th></tr></thead>
    <tbody>{rows.map(row => <tr key={row.id}><td><strong>{row.label}</strong></td><td>{row.display}</td>
      <td>{row.origin === "reported" ? "Reported" : "Calculated"}</td><td>{row.concept || "Derived from reported lines"}</td></tr>)}</tbody>
  </table></div>;
}

function BriefView({ composition }: { composition: CompositionData }) {
  const metrics = composition.metrics;
  const revenue = metrics.revenue;
  const cost = metrics.cost_of_revenue;
  const gross = metrics.gross_profit;
  const operating = metrics.operating_income;
  const net = metrics.net_income;
  const expense = metrics.operating_expenses || metrics.net_operating_costs;
  const mix = composition.revenue_splits.find(group => group.title === "Product and service revenue") || composition.revenue_splits[0];
  const margin = revenue?.value > 0 && net ? Math.abs((net.value / revenue.value) * 100).toFixed(1) : null;

  return <div className="composition-brief">
    {revenue ? <><div className="composition-flow">
      {[revenue, cost, gross, operating, net].filter((item): item is CompositionMetric => Boolean(item)).map((item, index) =>
        <div className="composition-step" key={item.id}><span className="composition-step-index">0{index + 1}</span><span>{item.id === "cost_of_revenue" ? "Direct costs" : item.id === "operating_income" ? "Profit from operations" : item.id === "net_income" ? "Final profit or loss" : item.label}</span><strong>{item.display}</strong></div>)}
    </div>
    <div className="composition-story">
      <h3>Where the money went</h3>
      <p>The company reported <strong>{revenue.display} in sales</strong>{cost ? ` and spent ${cost.display} on the direct cost of providing its products and services` : ""}.
        {gross ? composition.reconciliations.gross_profit ? ` That left ${gross.display} in gross profit.` : ` The filing reports ${gross.display} in gross profit.` : ""} {expense ? composition.reconciliations.operating_income ? `Operating costs beyond those direct costs were ${expense.display}.` : `It also reports ${expense.display} in operating expenses.` : ""}
        {operating ? ` Operating income, the profit from its main business, was ${operating.display}.` : ""}
        {net ? `${composition.reconciliations.net_income ? " After other items and taxes, it reported" : " The filing also reports"} ${net.display} in net ${net.value < 0 ? "loss" : "income"}.` : ""}</p>
      {margin !== null && <p>In everyday terms, about <strong>${margin} of every $100 of revenue</strong> {net!.value < 0 ? "was a net loss" : "remained as net income"}.</p>}
    </div></> : <Notice>No reliably matched revenue figure is available for this filing. The detailed view may still show other reported lines.</Notice>}
    {mix ? <section className="surface-card composition-card"><div className="composition-card-intro"><span className="eyebrow">Where sales came from</span><h3>Sales by category</h3><p>These categories add up to the reported revenue for this period.</p></div><RevenueMix group={mix} compact/></section>
      : <p className="composition-muted">{composition.split_status} The filing may still describe its business in words.</p>}
    <p className="composition-foot">Each revenue split is a separate way to look at the same sales. Do not add product, segment, and geography views together. Values are from the selected SEC filing; calculated steps are identified in Deep dive.</p>
  </div>;
}

function DeepView({ composition }: { composition: CompositionData }) {
  return <div className="composition-deep">
    <section className="surface-card composition-card"><div className="composition-card-intro"><span className="eyebrow">Revenue to net income</span><h3>Income statement bridge</h3><p>Follow the reported lines from sales through direct costs, operating expenses, other items, and taxes. Calculated rows are marked.</p></div>
      {composition.bridge.length ? <MetricTable rows={composition.bridge}/> : <Notice>No reliably matched income statement lines are available for this filing.</Notice>}
      <div className="composition-checks"><strong>Reconciliation checks</strong>{([
        ["Revenue − direct costs = gross profit", composition.reconciliations.gross_profit],
        ["Gross profit − operating expenses = operating income", composition.reconciliations.operating_income],
        ["Income before taxes − tax = net income", composition.reconciliations.net_income],
      ] as const).map(([label, match]) => <span key={label}>{match === true ? "✓" : match === false ? "•" : "—"} {label}: {match === true ? "matches" : match === false ? "other filing-specific items affect this step" : "not enough mapped data"}</span>)}</div>
      <p className="composition-foot">Net nonoperating items = income before taxes minus operating income. It is a calculated net figure, not a single expense category.</p>
    </section>
    <section className="surface-card composition-card"><div className="composition-card-intro"><span className="eyebrow">Operating costs</span><h3>Expense detail</h3><p>Shown categories are selected to avoid counting both an aggregate and its parts. An “other” row is the remainder against reported operating expenses.</p></div>
      {composition.expense_details.length ? <MetricTable rows={composition.expense_details}/> : <Notice>This filing does not provide a nonoverlapping expense breakdown that we can verify.</Notice>}
    </section>
    <section className="surface-card composition-card"><div className="composition-card-intro"><span className="eyebrow">Business mix</span><h3>Reported revenue splits</h3><p>Each group independently reconciles to total revenue for the exact period. They represent different views of the same sales.</p></div>
      {composition.revenue_splits.length ? composition.revenue_splits.map(group => <div key={group.title} className="composition-split"><RevenueMix group={group}/><details><summary>See XBRL member and concept details</summary><div className="table-scroll"><table className="data-table composition-table"><thead><tr><th>Category</th><th>XBRL member</th><th>Revenue concept</th></tr></thead><tbody>{group.items.map(item => <tr key={item.member}><td>{item.label}</td><td>{item.member}</td><td>{item.concept}</td></tr>)}</tbody></table></div></details></div>)
        : <Notice>{composition.split_status}</Notice>}
    </section>
    <p className="composition-foot">All figures use the same {composition.filing.form} and period. SEC Company Facts supplies entity-wide US-GAAP lines; the revenue splits come from the filing's inline XBRL. FilingLens omits a split unless its parts reconcile to reported revenue. <External href={composition.filing.source_url}>Read the original filing <ArrowRight size={13}/></External></p>
  </div>;
}

export function Composition({ data }: { data: CompanyData }) {
  const [form, setForm] = useState<FilingForm>(data.filings.quarterly ? "10-Q" : "10-K");
  const [depth, setDepth] = useState<Depth>("brief");
  const [composition, setComposition] = useState<CompositionData | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const selected = form === "10-Q" ? data.filings.quarterly : data.filings.annual;

  useEffect(() => {
    if (!selected) { setComposition(null); return; }
    let cancelled = false;
    setBusy(true); setError(""); setComposition(null);
    api<CompositionData>(`/api/company/${encodeURIComponent(data.company.ticker)}/composition?form=${form}`)
      .then(result => { if (!cancelled) setComposition(result); })
      .catch(cause => { if (!cancelled) setError(cause instanceof Error ? cause.message : "Could not load this breakdown."); })
      .finally(() => { if (!cancelled) setBusy(false); });
    return () => { cancelled = true; };
  }, [data.company.ticker, form, selected?.accession_number]);

  return <div className="composition-view">
    <div className="composition-controls"><div className="segmented" role="tablist" aria-label="Breakdown filing">
      <button role="tab" aria-selected={form === "10-K"} className={form === "10-K" ? "active" : ""} disabled={!data.filings.annual} onClick={() => setForm("10-K")}>Annual 10-K</button>
      <button role="tab" aria-selected={form === "10-Q"} className={form === "10-Q" ? "active" : ""} disabled={!data.filings.quarterly} onClick={() => setForm("10-Q")}>Latest 10-Q</button>
    </div><div className="segmented" role="tablist" aria-label="Explanation depth">
      <button role="tab" aria-selected={depth === "brief"} className={depth === "brief" ? "active" : ""} onClick={() => setDepth("brief")}>Brief view</button>
      <button role="tab" aria-selected={depth === "deep"} className={depth === "deep" ? "active" : ""} onClick={() => setDepth("deep")}>Deep dive</button>
    </div></div>
    {selected && <div className="financial-note"><ShieldCheck size={17}/> {form === "10-Q" ? "Three-month" : "Full-year"} income figures from the {form} filed {dateLabel(selected.filing_date)}. <External href={selected.source_url}>Open SEC filing</External></div>}
    {busy && <div className="surface-card composition-loading"><BookOpen size={20}/> Reading reported lines and revenue notes…</div>}
    {error && <Notice tone="error">{error}</Notice>}
    {composition && <><div className="composition-period">{composition.basis} · {composition.period_start ? `${dateLabel(composition.period_start)} – ` : ""}{dateLabel(composition.period_end)}</div>
      {depth === "brief" ? <BriefView composition={composition}/> : <DeepView composition={composition}/>}</>}
  </div>;
}
