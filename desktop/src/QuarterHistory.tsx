import { useState } from "react";
import { ArrowUpRight, CalendarRange } from "lucide-react";
import { Notice } from "./visuals";
import { Evidence, ResearchLoading } from "./TimeMachine";
import { currency, periodLabel, shortDate, useResearchData } from "./researchData";
import type { QuarterHistory as QuarterData, QuarterPeriod } from "./researchData";
import type { CompanyData } from "./types";

const groups = {
  performance: [["revenue", "Revenue"], ["gross_profit", "Gross profit"], ["operating_income", "Operating income"], ["net_income", "Net income"]],
  cash: [["operating_cash_flow", "Operating cash flow"], ["capital_expenditures", "Capital expenditures"], ["free_cash_flow", "Free cash flow"]],
  balance: [["cash", "Cash"], ["current_assets", "Current assets"], ["total_assets", "Total assets"], ["current_liabilities", "Current liabilities"], ["total_liabilities", "Total liabilities"], ["long_term_debt", "Long-term debt"], ["stockholders_equity", "Stockholders’ equity"]],
};

function PeriodChart({ periods, metric, label }: { periods: QuarterPeriod[]; metric: string; label: string }) {
  const [activeEnd, setActiveEnd] = useState(periods.at(-1)?.end || "");
  const active = periods.find(period => period.end === activeEnd) || periods.at(-1);
  const values = periods.flatMap(period => period.metrics[metric]?.value == null ? [] : [period.metrics[metric].value!]);
  if (!values.length) return <Notice>No comparable quarterly values are available for {label.toLowerCase()}.</Notice>;
  const low = Math.min(0, ...values), high = Math.max(0, ...values);
  const scale = high - low || 1;
  const y = (value: number) => 20 + (high - value) / scale * 160;
  const step = 560 / periods.length;
  return <section className="surface-card quarter-chart"><div className="card-top"><div><span className="eyebrow">Quarter by quarter · USD</span><h3>{label}</h3></div><div className="chart-reading" aria-live="polite"><strong>{currency(active?.metrics[metric]?.value)}</strong><span>{active ? `Ended ${shortDate(active.end)}` : ""}</span></div></div>
    <svg viewBox="0 0 640 225" role="group" aria-label={`${label}, quarterly values. Focus a bar to inspect its value.`}>
      {[low, low + scale / 2, high].map((value, index) => <g key={index}><line x1={65} x2={630} y1={y(value)} y2={y(value)} className="financial-gridline"/><text x={58} y={y(value) + 4} textAnchor="end" className="financial-y-label">{currency(value)}</text></g>)}
      {periods.map((period, index) => { const value = period.metrics[metric]?.value; const x = 70 + step * index; const width = Math.max(5, step - 10); return <g key={period.end}>
        {value != null ? <rect x={x} y={Math.min(y(value), y(0))} width={width} height={Math.max(2, Math.abs(y(value) - y(0)))} rx={3} className={`quarter-bar ${value < 0 ? "negative" : ""} ${active?.end === period.end ? "active" : ""}`} tabIndex={0} role="img" aria-label={`${label}, ${periodLabel(period.start, period.end)}, ${currency(value, true)}`} onMouseEnter={() => setActiveEnd(period.end)} onFocus={() => setActiveEnd(period.end)}><title>{`${shortDate(period.end)}: ${currency(value, true)}`}</title></rect> : <text x={x + width / 2} y={y(0) - 5} textAnchor="middle" className="financial-x-label">—</text>}
        {(index % Math.ceil(periods.length / 6) === 0 || index === periods.length - 1) && <text x={x + width / 2} y={209} textAnchor="middle" className="financial-x-label">{new Date(`${period.end}T00:00:00`).toLocaleDateString("en-US", { month: "short", year: "2-digit" })}</text>}
      </g>; })}
    </svg><p className="research-copy">Hover over or focus a bar for its value. Missing account values remain blank; sources are available in the table below.</p>
  </section>;
}

export function QuarterlyHistory({ company, years }: { company: CompanyData; years: number }) {
  const resource = useResearchData<QuarterData>(`/api/company/${encodeURIComponent(company.company.ticker)}/quarters?years=${years}`, company.source.loaded_at);
  const [group, setGroup] = useState<keyof typeof groups>("performance");
  const [count, setCount] = useState(8);
  const [chartMetric, setChartMetric] = useState("revenue");
  const data = resource.data;
  if (!data) return <ResearchLoading error={resource.error} retry={resource.retry}/>;
  if (!data.periods.length) return <Notice>No reliable standalone quarters are available. The latest 10-Q snapshot and original SEC filings remain available in their own views.</Notice>;
  const periods = data.periods.slice(-count);
  const gaps = periods.slice(1).filter((period, index) => new Date(`${period.start}T00:00:00Z`).getTime() - new Date(`${periods[index].end}T00:00:00Z`).getTime() !== 86400000);
  const metrics = groups[group];
  const chart = metrics.find(([metric]) => metric === chartMetric) || metrics[0];
  return <>
    <div className="financial-note"><CalendarRange size={18}/> Exact reporting dates keep fiscal calendars visible. Income and cash flow below cover standalone quarters; balance-sheet values are quarter-end amounts.</div>
    <section className="ttm-section"><div className="block-heading"><div><span className="eyebrow">The latest twelve months</span><h3>A more current financial picture.</h3></div><span>{data.ttm ? periodLabel(data.ttm.start, data.ttm.end) : "Four consecutive quarters required"}</span></div>
      {data.ttm ? <div className="fact-grid">{[["revenue", "Revenue"], ["operating_income", "Operating income"], ["operating_cash_flow", "Operating cash flow"], ["free_cash_flow", "Free cash flow"]].map(([id, label]) => { const value = data.ttm!.metrics[id]; return <div className="fact-card" key={id}><div className="fact-label">TTM {label}<ArrowUpRight size={15}/></div><div className="fact-value">{currency(value?.value)}</div>{value ? <Evidence sources={value.sources}/> : <span className="research-neutral">Missing or incompatible quarterly inputs</span>}</div>; })}</div> : <Notice>TTM totals are unavailable because four complete, consecutive quarters with compatible inputs could not be established. Annual values are not substituted.</Notice>}
    </section>
    <div className="research-controls"><div className="segmented" role="tablist" aria-label="Quarterly statement">{([["performance", "Performance"], ["cash", "Cash flow"], ["balance", "Balance sheet"]] as const).map(([id, label]) => <button key={id} role="tab" aria-selected={group === id} className={group === id ? "active" : ""} onClick={() => setGroup(id)}>{label}</button>)}</div><label>Quarters shown<select value={count} onChange={event => setCount(Number(event.target.value))}>{[8, 12, 20, 40].filter(value => value <= years * 4 || value === 8).map(value => <option key={value} value={value}>{value} quarters</option>)}</select></label><label>Chart account<select value={chart[0]} onChange={event => setChartMetric(event.target.value)}>{metrics.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label></div>
    {gaps.length > 0 && <Notice tone="warning">This history has gaps or incompatible period boundaries before {gaps.map(period => shortDate(period.start)).join(", ")}. The chart shows available reporting periods in order, with no estimates for missing quarters.</Notice>}
    <p className="research-copy">Scroll the table horizontally for earlier quarters. A dash means a required value is missing, ambiguous, or incompatible with this period.</p>
    <div className="topic-enter" key={`${group}-${chart[0]}-${count}`}><PeriodChart key={`${group}-${chart[0]}`} periods={periods} metric={chart[0]} label={chart[1]}/>
      <section className="surface-card research-table-card"><div className="table-scroll" tabIndex={0} role="region" aria-label="Quarterly financial values, scroll horizontally for earlier quarters"><table className="data-table quarter-history-table"><thead><tr><th>Account</th>{[...periods].reverse().map(period => <th key={period.end}>{shortDate(period.end)}<span className="table-sub">{group === "balance" ? "As of quarter end" : `From ${shortDate(period.start)}`}</span></th>)}</tr></thead><tbody>{metrics.map(([metric, label]) => <tr key={metric}><td>{label}</td>{[...periods].reverse().map(period => { const value = period.metrics[metric]; return <td key={period.end}><strong>{currency(value?.value)}</strong>{value && <><span className="table-sub">{value.origin === "ytd_difference" ? "YTD difference" : value.origin === "calculated" ? "Calculated" : "Reported"}</span><Evidence sources={value.sources}/></>}</td>; })}</tr>)}</tbody></table></div></section>
    </div>
    <p className="method-note">A standalone cash-flow quarter may be calculated as current YTD minus the preceding YTD with the same fiscal start and concept. Fourth quarters may use annual minus nine-month values. TTM sums four contiguous quarters with matching boundaries. Later reported comparative values may revise earlier periods; inspect each source operand.</p>
  </>;
}
