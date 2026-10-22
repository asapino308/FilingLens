import { useRef, useState } from "react";
import { ArrowRight, ChevronLeft, ChevronRight, History, Layers3 } from "lucide-react";
import { External, Notice, SectionHeader } from "./visuals";
import { currency, percent, periodLabel, shortDate, useResearchData } from "./researchData";
import type { Observation, RevisionData, RevisionSeries } from "./researchData";
import type { CompanyData } from "./types";

function impactFormula(metric: string) {
  if (metric === "free_cash_flow") return "Operating cash flow − capital expenditures";
  if (metric.endsWith("_growth")) return "(Current period − prior period) ÷ absolute prior-period value";
  return metric === "operating_income_margin" ? "Operating income ÷ revenue" : "Net income ÷ revenue";
}

export function Evidence({ sources }: { sources: Observation[] }) {
  return <details className="research-evidence"><summary>Inspect sources <span>{sources.length}</span></summary>
    <div className="evidence-items">{sources.map((source, index) => <div key={`${source.accession}-${source.concept}-${index}`}>
      <strong>{currency(source.value, true)}</strong><span>{periodLabel(source.start, source.end)}</span>
      <span>USD · {source.concept}</span><span>Accession {source.accession}</span><External href={source.url}>{source.form} · filed {shortDate(source.filed)}</External>
    </div>)}</div></details>;
}

export function ResearchLoading({ error, retry }: { error?: string; retry: () => void }) {
  return error ? <Notice tone="error">{error} <button className="text-button" onClick={retry}>Try again</button></Notice>
    : <div className="research-loading" role="status"><span className="loading-orbit"/> Reading reported periods and their sources…</div>;
}

function VersionExplorer({ row }: { row: RevisionSeries }) {
  const [selected, setSelected] = useState(row.versions.length - 1);
  const version = row.versions[selected];
  return <section className="tm-explorer surface-card topic-enter" aria-label={`${row.label} reporting trail`}>
    <div className="card-top"><div><span className="eyebrow">Follow the reporting trail</span><h3>{row.label}</h3></div><span>{periodLabel(row.start, row.end)}</span></div>
    <p className="research-copy">Each step is a different value reported for this same period and concept. Repeated unchanged values are grouped together.</p>
    <div className="version-rail" role="group" aria-label="Reported versions">{row.versions.map((item, index) => <button key={`${item.accession}-${index}`} aria-pressed={selected === index} className={selected === index ? "selected" : ""} onClick={() => setSelected(index)}>
      <span className="version-dot"/><small>{index === 0 ? "First available" : `Revision ${index}`}</small><strong>{shortDate(item.filed)}</strong><span>{currency(item.value)}</span>
    </button>)}</div>
    {row.versions.length > 1 && <label className="version-scrubber">Move through reported versions
      <input type="range" min={0} max={row.versions.length - 1} step={1} value={selected} onChange={event => setSelected(Number(event.target.value))} aria-valuetext={`${shortDate(version.filed)}, ${currency(version.value, true)}`}/>
    </label>}
    <div className="tm-selected topic-enter" key={`${row.id}-${selected}`} aria-live="polite">
      <div><span className="eyebrow">Selected reported value</span><strong>{currency(version.value, true)}</strong><span>{version.form} filed {shortDate(version.filed)}</span></div>
      <div><span className="eyebrow">Change from first available</span><strong>{currency(version.value - row.first, true)}</strong><span><External href={version.last_url || version.url}>Value observed through {shortDate(version.last_seen || version.filed)}</External></span></div>
      <External href={version.url} className="button button-outline">Open source filing <ArrowRight size={15}/></External>
    </div>
    <p className="research-concept">USD · {row.concept} · Accession {version.accession}</p>
  </section>;
}

export function TimeMachine({ company, years }: { company: CompanyData; years: number }) {
  const resource = useResearchData<RevisionData>(`/api/company/${encodeURIComponent(company.company.ticker)}/history?years=${years}`, company.source.loaded_at);
  const [year, setYear] = useState<number | "all">("all");
  const [metric, setMetric] = useState("all");
  const [changedOnly, setChangedOnly] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const explorerRef = useRef<HTMLDivElement>(null);
  const data = resource.data;
  const selectedYear = year === "all" || data?.years.includes(year) ? year : "all";
  const rows = data?.series.filter(row => (selectedYear === "all" || row.year === selectedYear) && (metric === "all" || row.metric === metric) && (!changedOnly || row.revision_count > 0)) || [];
  const active = rows.find(row => row.id === activeId) || rows.find(row => row.revision_count > 0) || rows[0];
  const metrics = [...new Map(data?.series.map(row => [row.metric, row.label]) || []).entries()];
  const impacts = data?.impacts.filter(item => selectedYear === "all" || item.year === selectedYear) || [];
  const yearIndex = selectedYear === "all" ? -1 : data?.years.indexOf(selectedYear) ?? -1;
  function chooseYear(value: number | "all") { setYear(value); setActiveId(null); }
  function inspect(id: string) {
    setActiveId(id);
    requestAnimationFrame(() => {
      explorerRef.current?.focus({ preventScroll: true });
      explorerRef.current?.scrollIntoView({ block: "start", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    });
  }
  return <>
    <SectionHeader eyebrow="Accounting time machine" title="See how the past was reported." description="Explore one year or several. Trace earlier and later values back to their filings, then see what those changes mean for the financial picture." aside={<div className="source-pill"><History size={16}/> {company.company.ticker} · Reported-value history</div>}/>
    {!data ? <ResearchLoading error={resource.error} retry={resource.retry}/> : <>
      <section className="tm-intro"><div><span className="eyebrow">A second look at history</span><h3>A reported number can have a story.</h3><p>Follow changes to the same account, concept, and exact reporting period. A revision may reflect a reclassification or a change in presentation; it does not by itself establish an accounting error.</p></div>
        <div className="tm-count"><strong>{data.revised_series}</strong><span>account-periods with<br/>a changed reported value</span><Layers3 size={28}/></div>
      </section>
      {!data.years.length ? <Notice>No comparable annual USD observations are available for this company.</Notice> : <>
        <div className="tm-period-heading"><div><span className="eyebrow">Choose your perspective</span><p>Annual reporting periods ending in</p></div><div className="tm-arrows"><button className="icon-button" aria-label="Previous reporting year" disabled={yearIndex <= 0} onClick={() => chooseYear(data.years[yearIndex - 1])}><ChevronLeft size={18}/></button><button className="icon-button" aria-label="Next reporting year" disabled={yearIndex < 0 || yearIndex >= data.years.length - 1} onClick={() => chooseYear(data.years[yearIndex + 1])}><ChevronRight size={18}/></button></div></div>
        <div className="year-rail" role="group" aria-label="Reporting years"><button className={selectedYear === "all" ? "selected" : ""} aria-pressed={selectedYear === "all"} onClick={() => chooseYear("all")}><Layers3 size={17}/><strong>All years</strong><span>{data.years.length} years together</span></button>
          {data.years.map(value => { const changed = data.series.filter(row => row.year === value && row.revision_count > 0).length; return <button key={value} className={selectedYear === value ? "selected" : ""} aria-pressed={selectedYear === value} onClick={() => chooseYear(value)}><strong>{value}</strong><span>{changed ? `${changed} changed` : "No changes found"}</span></button>; })}
        </div>
        <div className="research-controls"><label>Account<select value={metric} onChange={event => { setMetric(event.target.value); setActiveId(null); }}><option value="all">All available accounts</option>{metrics.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label><label className="research-checkbox"><input type="checkbox" checked={changedOnly} onChange={event => setChangedOnly(event.target.checked)}/> Changed values only</label><span>{rows.length} account-period{rows.length === 1 ? "" : "s"}</span></div>
        <div className="topic-enter" key={`${selectedYear}-${metric}-${changedOnly}`}>
          <section className="surface-card research-table-card"><div className="table-scroll tm-table-scroll" tabIndex={0} role="region" aria-label="Account reporting history, scroll to explore"><table className="data-table tm-table"><thead><tr><th>Account / period ended</th><th>First available</th><th>Latest value</th><th>Net change</th><th>Reporting trail</th></tr></thead><tbody>{rows.map(row => <tr key={row.id} className={active?.id === row.id ? "research-row-selected" : ""}>
            <td><button className="tm-account" aria-pressed={active?.id === row.id} onClick={() => inspect(row.id)}><strong>{row.label}</strong><span>{shortDate(row.end)} <ChevronRight size={13}/></span></button></td><td>{currency(row.first)}</td><td>{currency(row.latest)}</td><td><span className={row.change ? "revision-chip" : "research-neutral"}>{currency(row.change)}</span></td><td><button className="text-button" onClick={() => inspect(row.id)}>{row.revision_count ? `${row.revision_count} revision${row.revision_count === 1 ? "" : "s"}` : "Unchanged"}<ChevronRight size={14}/></button></td>
          </tr>)}</tbody></table></div>{!rows.length && <div className="research-empty">No account-periods match these filters. Try another account or include unchanged values.</div>}</section>
          <div ref={explorerRef} tabIndex={-1} className="tm-trail-target">{active && <VersionExplorer key={active.id} row={active}/>}</div>
          {!impacts.length && <p className="research-copy">Calculation cards require compatible inputs and a changed first-to-latest result. A value that changes and then returns to its first value can have revisions with no net effect.</p>}
          {impacts.length > 0 && <section className="surface-card tm-impacts"><div className="card-top"><div><span className="eyebrow">What changes with the numbers?</span><h3>The effect on your analysis</h3></div></div><p className="research-copy">Recalculated from the first and latest available values for each input. Each input keeps its own filing date; these are not synchronized historical snapshots.</p><div className="impact-grid">{impacts.map(item => <div className="impact-card" key={`${item.metric}-${item.start}-${item.end}`}><span>{item.label} · ended {shortDate(item.end)}</span><div><strong>{item.unit === "usd" ? currency(item.first) : percent(item.first)}</strong><ArrowRight size={16}/><strong>{item.unit === "usd" ? currency(item.latest) : percent(item.latest)}</strong></div><p className="research-copy">{impactFormula(item.metric)}</p><Evidence sources={item.sources}/></div>)}</div></section>}
        </div>
      </>}
      <Notice>“First available” means the earliest eligible annual observation retained in today’s SEC Company Facts data, not a guaranteed original report. This revision trail is not a complete historical as-of or backtesting database. Different concepts or reporting periods are never treated as revisions of one another. Ambiguous conflicting contexts are omitted.</Notice>
    </>}
  </>;
}
