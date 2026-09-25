import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Activity, ArrowRight, BookOpen, Bookmark, ChartNoAxesCombined, Check, ChevronRight, CircleHelp, Clock3, Database, FileSearch, FileText, KeyRound, Menu, RefreshCw, Search, Settings2, ShieldCheck, Sparkles, X } from "lucide-react";
import { api, post } from "./api";
import { approaches, compareSnapshots, makeSnapshot, readApproach, readSavedCompanies, readSnapshot, saveApproach, saveCompanies, saveSnapshot, suggestedQuestions } from "./researchPreferences";
import { External, FactCard, Notice, SectionHeader, StatementTable } from "./visuals";
import { Composition } from "./Composition";
import type { Answer, Anomaly, AppSettings, Brief, CompanyData, Filing, FilingIndex, InsiderData, Provider } from "./types";
import type { ResearchApproach, ResearchChange, SavedCompany } from "./researchPreferences";

type View = "overview" | "financials" | "research" | "signals" | "settings";
type Statement = "income" | "balance" | "cash" | "ratios";
type ResearchTab = "filing" | "ask" | "brief";
type FilingForm = "10-K" | "10-Q";
const navigation: { id: View; label: string; icon: React.ReactNode }[] = [
  { id: "overview", label: "Overview", icon: <ChartNoAxesCombined size={19}/> },
  { id: "financials", label: "Financials", icon: <Activity size={19}/> },
  { id: "research", label: "Filings & research", icon: <FileSearch size={19}/> },
  { id: "signals", label: "Signals", icon: <Sparkles size={19}/> },
  { id: "settings", label: "Settings", icon: <Settings2 size={19}/> },
];
const statements: { id: Statement; label: string }[] = [
  { id: "income", label: "Income statement" }, { id: "balance", label: "Balance sheet" },
  { id: "cash", label: "Cash flow" }, { id: "ratios", label: "Ratios & growth" },
];
const impactOrder = ["Strongly favorable", "Moderately favorable", "Lightly favorable", "Lightly unfavorable", "Moderately unfavorable", "Strongly unfavorable"];
const rawOrder = ["Strong gain", "Moderate gain", "Light gain", "Light loss", "Moderate loss", "Strong loss"];
const dollars = (value: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 2 }).format(value);
const multipleMetrics = new Set(["current_ratio", "debt_to_equity"]);
const percentageMetrics = new Set(["debt_to_assets", "return_on_assets", "return_on_equity"]);
const anomalyValue = (metric: string, value: number | null) => {
  if (value == null) return "—";
  if (multipleMetrics.has(metric)) return `${value.toFixed(2)}x`;
  if (metric.endsWith("_growth") || metric.endsWith("_margin") || percentageMetrics.has(metric)) return `${(value * 100).toFixed(1)}%`;
  return dollars(value);
};
const dateLabel = (value: string | null | undefined) => value ? new Date(`${value}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "Unavailable";
const messageOf = (error: unknown) => error instanceof Error ? error.message : "An unexpected error occurred.";

function SourceList({ sources }: { sources: Answer["sources"] }) {
  if (!sources.length) return null;
  return <div className="source-list"><h4>Supporting passages</h4>{sources.map((source, index) => <details key={source.chunk_id} className="source-passage"><summary><span className="source-number">{index + 1}</span><span>{source.form ? `${source.form} · ` : ""}{source.section}</span><ChevronRight size={15}/></summary><p>{source.text}</p><External href={source.url}>Open SEC filing</External></details>)}</div>;
}

function AnswerView({ answer }: { answer: Answer }) {
  return <div className="answer-view">{answer.status === "out_of_scope" ? <Notice tone="warning">{answer.answer}</Notice> : <div className="markdown-body"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{ a: ({ children }) => <span>{children}</span>, img: () => null }}>{answer.answer}</ReactMarkdown></div>}<SourceList sources={answer.sources}/></div>;
}

function FilingPicker({ data, selected, onSelect }: { data: CompanyData; selected: FilingForm; onSelect: (form: FilingForm) => void }) {
  return <div className="filing-picker" role="group" aria-label="Filing to research">{(["10-K", "10-Q"] as const).map(form => {
    const filing = form === "10-K" ? data.filings.annual : data.filings.quarterly;
    return <button key={form} type="button" aria-pressed={selected === form} className={selected === form ? "selected" : ""} disabled={!filing} onClick={() => onSelect(form)}><strong>{form}</strong><span>{filing ? `Filed ${dateLabel(filing.filing_date)}` : "Unavailable"}</span></button>;
  })}</div>;
}

function AskPanel({ data, provider, model, canAsk, onAsk, answer, busy, error, compact = false, approach = "explore", filingForm, onSelectFiling }: {
  data: CompanyData; provider: string; model: string; canAsk: boolean;
  onAsk: (question: string) => void; answer: Answer | null; busy: boolean; error: string;
  compact?: boolean; approach?: ResearchApproach; filingForm: FilingForm; onSelectFiling: (form: FilingForm) => void;
}) {
  const selectedFiling = filingForm === "10-K" ? data.filings.annual : data.filings.quarterly;
  const [question, setQuestion] = useState(compact ? suggestedQuestions[approach][0] : "What are the major risks facing this company?");
  useEffect(() => {
    if (compact) setQuestion(current => Object.values(suggestedQuestions).flat().includes(current) ? suggestedQuestions[approach][0] : current);
  }, [approach, compact]);
  return <div className={compact ? "ask-panel compact" : "ask-panel"}>
    <div className="panel-title"><Sparkles size={18}/><div><strong>{compact ? "Ask about this company" : "Ask the filing"}</strong><span>Grounded in the selected filing and verified metrics</span></div></div>
    {compact && <FilingPicker data={data} selected={filingForm} onSelect={onSelectFiling}/>}
    <form onSubmit={event => { event.preventDefault(); onAsk(question); }}>
      <label className="sr-only" htmlFor={compact ? "overview-question" : "filing-question"}>Question</label>
      <textarea id={compact ? "overview-question" : "filing-question"} value={question} onChange={event => setQuestion(event.target.value)} rows={compact ? 2 : 4} placeholder="Ask about the business, risks, cash flow, or management discussion" />
      {compact && <div className="question-prompts" aria-label="Suggested research questions">{suggestedQuestions[approach].map(prompt => <button key={prompt} type="button" onClick={() => setQuestion(prompt)}>{prompt}</button>)}</div>}
      <div className="form-bottom"><span>{selectedFiling ? `Evidence: ${selectedFiling.form} filed ${dateLabel(selectedFiling.filing_date)}` : `No ${filingForm} available`} · {model ? `${provider} / ${model}` : "AI model not selected"}</span><button className="button button-dark" disabled={!canAsk || busy || !question.trim()}>{busy ? "Researching…" : "Ask question"}<ArrowRight size={16}/></button></div>
    </form>
    {!canAsk && <Notice tone="warning">Choose a connected AI model in Settings. Financial data and filing links still work without AI.</Notice>}
    {error && <Notice tone="error">{error}</Notice>}
    {answer && <AnswerView answer={answer}/>}
  </div>;
}

function Overview({ data, onView, askProps, provenance, loadProvenance, provenanceBusy, approach, onApproachChange, saved, onToggleSaved, previousCheck, changes }: {
  data: CompanyData; onView: (view: View, researchTab?: ResearchTab) => void;
  askProps: Omit<React.ComponentProps<typeof AskPanel>, "data" | "compact">;
  provenance: Record<string, unknown>[] | null; loadProvenance: () => void; provenanceBusy: boolean;
  approach: ResearchApproach; onApproachChange: (value: ResearchApproach) => void;
  saved: boolean; onToggleSaved: () => void; previousCheck: string | null; changes: ResearchChange[];
}) {
  const { company, filings, latest_year: year } = data;
  const quarterHighlights = data.quarterly?.groups.find(group => group.title === "Quarter income statement")?.rows
    .filter(row => ["revenue", "operating_income", "net_income"].includes(row.id)) || [];
  const trails: Record<ResearchApproach, { title: string; detail: string; view: View; tab?: ResearchTab }[]> = {
    explore: [
      { title: "Understand the business", detail: "Start with the company's own description.", view: "research", tab: "filing" },
      { title: "See the financial picture", detail: "Compare reported figures across years.", view: "financials" },
      { title: "Read the risk factors", detail: "Ask a question grounded in the latest filing.", view: "research", tab: "ask" },
    ],
    evaluate: [
      { title: "Examine cash and debt", detail: "Check the statements and calculation details.", view: "financials" },
      { title: "Investigate unusual moves", detail: "Open the screen and its underlying numbers.", view: "signals" },
      { title: "Test your reading", detail: "Look for risks and missing evidence in the filing.", view: "research", tab: "ask" },
    ],
    follow: [
      { title: "Review new filings", detail: "Open the latest SEC report.", view: "research", tab: "filing" },
      { title: "Check financial changes", detail: "Compare annual figures and source concepts.", view: "financials" },
      { title: "Watch reported activity", detail: "Inspect movement screens and Forms 4.", view: "signals" },
    ],
  };
  return <>
    <SectionHeader eyebrow="Company workspace" title="The big picture, in context." description={`A sourced starting point for ${company.name}. Follow a number or filing into its detail view.`} aside={<div className="source-pill"><Database size={15}/> Annual SEC/XBRL · FY{year ?? "—"}</div>}/>
    <section className="hero-card"><div className="hero-copy"><span className="hero-kicker">Research snapshot</span><h3>{company.name}</h3><p>Official filings, computed financials, and evidence-linked analysis in one workspace.</p><div className="hero-actions"><button className="button button-light" onClick={() => onView("financials")}>Explore financials <ArrowRight size={16}/></button><button className="button button-ghost" onClick={() => onView("research", "filing")}>Read filings <ArrowRight size={16}/></button></div></div><div className="hero-monogram" aria-hidden="true">{company.ticker.slice(0, 2)}</div></section>
    <section className="research-start surface-card"><div className="card-top"><div><span className="eyebrow">Your research approach</span><h3>Where would you like to start?</h3></div><button className={`button ${saved ? "button-outline" : "button-dark"}`} onClick={onToggleSaved}><Bookmark size={15} fill={saved ? "currentColor" : "none"}/>{saved ? "Saved company" : "Save company"}</button></div>
      <div className="approach-options" role="group" aria-label="Research approach">{approaches.map(item => <button key={item.id} className={approach === item.id ? "selected" : ""} aria-pressed={approach === item.id} onClick={() => onApproachChange(item.id)}><strong>{item.label}</strong><span>{item.description}</span></button>)}</div>
      <div className="research-trail">{trails[approach].map((step, index) => <button key={step.title} onClick={() => onView(step.view, step.tab)}><span className="trail-number">0{index + 1}</span><span><strong>{step.title}</strong><small>{step.detail}</small></span><ArrowRight size={15}/></button>)}</div>
      <p className="card-foot">This preference changes where research starts. It does not assess whether a security suits you.</p>
    </section>
    <section className="surface-card check-in"><div className="card-top"><div><span className="eyebrow">Since your last check</span><h3>What changed in the SEC data?</h3></div><span>{previousCheck ? `Previously checked ${dateLabel(previousCheck.slice(0, 10))}` : "First check"}</span></div>
      {!previousCheck ? <p>This is your starting point. FilingLens will compare filings and headline figures the next time you open or refresh this company.</p> : changes.length ? <div className="change-list">{changes.map((item, index) => <div className="change-line" key={`${item.label}-${index}`}><div><strong>{item.label}</strong><span>{item.detail}</span></div>{item.url && <External href={item.url}>Source</External>}</div>)}</div> : <p>No new annual or quarterly filing or changed headline figure was found in the currently loaded SEC data.</p>}
      <p className="card-foot">Compares this device's previous snapshot with the current loaded data. Refresh SEC data to check for newer records.</p>
    </section>
    <div className="block-heading"><div><span className="eyebrow">Performance</span><h3>At a glance</h3></div><span>FY{year ?? "—"} · annual figures</span></div>
    <div className="fact-grid">{data.hero.map(item => <FactCard key={item.id} label={item.label} value={item.value} note={item.change}/>)}</div>
    {data.quarterly && <section className="surface-card quarterly-preview"><div className="card-top"><div><span className="eyebrow">Latest quarterly filing</span><h3>{data.quarterly.filing.form} · period ended {dateLabel(data.quarterly.filing.report_date)}</h3></div><button className="text-button" onClick={() => onView("financials")}>Quarterly details <ArrowRight size={15}/></button></div>
      <p>Filed {dateLabel(data.quarterly.filing.filing_date)}. These three-month results are separate from the annual figures above.</p>
      {quarterHighlights.length ? <div className="quarter-highlight-list">{quarterHighlights.map(row => <div key={row.id}><span>{row.label}</span><strong>{row.display}</strong></div>)}</div> : <Notice>No reliably matched three-month income figures are available for this 10-Q.</Notice>}
      <div className="page-source">Source: <External href={data.quarterly.filing.source_url}>Official SEC 10-Q</External></div>
    </section>}
    <div className="overview-grid">
      <section className="surface-card ratio-card"><div className="card-top"><div><span className="eyebrow">Ratios</span><h3>Performance lens</h3></div><button className="text-button" onClick={() => onView("financials")}>View all <ArrowRight size={15}/></button></div><div className="ratio-list">{data.ratios.map(item => <div key={item.id}><span>{item.label}</span><strong>{item.value}</strong></div>)}</div><p className="card-foot">Calculated from normalized annual SEC facts. Unavailable values are not estimated.</p></section>
      <section className="surface-card signal-card"><div className="card-top"><div><span className="eyebrow">Signals</span><h3>Movements worth a look</h3></div><button className="text-button" onClick={() => onView("signals")}>Investigate <ArrowRight size={15}/></button></div><div className="signal-count"><span>{data.flags.total}</span><div>latest-period flags<br/><small>{data.flags.significant} significant · {data.flags.notable} notable</small></div></div><p className="card-foot">Unusual-change screens are not findings of misconduct or investment merit.</p></section>
    </div>
    <div className="overview-grid lower-grid"><section className="surface-card filings-card"><div className="card-top"><div><span className="eyebrow">Source documents</span><h3>Recent SEC filings</h3></div><button className="text-button" onClick={() => onView("research", "filing")}>Explore <ArrowRight size={15}/></button></div>{([filings.annual, filings.quarterly] as const).map((filing, index) => filing ? <div className="filing-line" key={filing.accession_number}><div className="filing-icon"><FileText size={19}/></div><div><strong>{index === 0 ? "Annual report" : "Quarterly report"}</strong><span>{filing.form} · filed {dateLabel(filing.filing_date)}</span></div><External href={filing.source_url}>SEC</External></div> : <div className="filing-line" key={index}>No {index === 0 ? "annual" : "quarterly"} filing available</div>)}</section>
      <section className="surface-card provenance-card"><div><span className="eyebrow">Data integrity</span><h3>Trace every value</h3><p>FilingLens keeps the reported SEC concept, filing date, and accession behind each annual value. Calculated ratios remain separate from reported facts.</p></div><button className="button button-outline" onClick={loadProvenance} disabled={provenanceBusy}>{provenanceBusy ? "Loading…" : provenance ? "Refresh provenance" : "Inspect value provenance"}<ArrowRight size={16}/></button></section></div>
    {provenance && <section className="surface-card provenance-results"><div className="card-top"><h3>Value provenance</h3><span>{provenance.length} reported values</span></div><div className="table-scroll"><table className="data-table"><thead><tr><th>Metric</th><th>Fiscal year</th><th>Value</th><th>XBRL concept</th><th>Filed</th></tr></thead><tbody>{provenance.slice(-100).reverse().map((fact, index) => <tr key={index}><td>{String(fact.metric)}</td><td>FY{String(fact.fiscal_year)}</td><td>{dollars(Number(fact.value))}</td><td>{String(fact.xbrl_concept)}</td><td>{dateLabel(String(fact.filing_date))}</td></tr>)}</tbody></table></div></section>}
    <div className="overview-ask"><AskPanel data={data} compact {...askProps} approach={approach}/></div>
    <div className="page-source">Source: <External href={data.source.url}>{data.source.label}</External> · Cached {data.source.cache_updated_at ? new Date(data.source.cache_updated_at).toLocaleDateString() : "date unavailable"} · Refresh SEC data to check for newer filings · Educational use only.</div>
  </>;
}

function Financials({ data }: { data: CompanyData }) {
  const [statement, setStatement] = useState<Statement>("income");
  const [period, setPeriod] = useState<"annual" | "quarterly" | "composition">("annual");
  useEffect(() => { if (!data.quarterly) setPeriod("annual"); }, [data.quarterly]);
  const sections = data.statements[statement] || [];
  return <><SectionHeader eyebrow="Reported financials" title="Financials, without the clutter." description="Compare annual history, inspect the latest quarter, or see what makes up sales and profit. Choose a quick explanation or a detailed filing view." aside={<div className="source-pill"><Database size={15}/> SEC Company Facts</div>}/>
    <div className="segmented" role="tablist" aria-label="Financial view"><button role="tab" aria-selected={period === "annual"} className={period === "annual" ? "active" : ""} onClick={() => setPeriod("annual")}>Annual history</button><button role="tab" aria-selected={period === "quarterly"} className={period === "quarterly" ? "active" : ""} disabled={!data.quarterly} onClick={() => setPeriod("quarterly")}>Latest 10-Q</button><button role="tab" aria-selected={period === "composition"} className={period === "composition" ? "active" : ""} disabled={!data.filings.annual && !data.filings.quarterly} onClick={() => setPeriod("composition")}>What makes up the numbers?</button></div>
    {period === "composition" ? <Composition data={data}/> : period === "annual" ? <>
      <div className="segmented" role="tablist" aria-label="Financial statement">{statements.map(item => <button key={item.id} role="tab" aria-selected={statement === item.id} className={statement === item.id ? "active" : ""} onClick={() => setStatement(item.id)}>{item.label}</button>)}</div>
      <div className="financial-note"><ShieldCheck size={17}/> Values come from normalized annual SEC/XBRL facts. Missing or ambiguous accounts remain unavailable.</div>
      {sections.length ? sections.map(section => <StatementTable key={`${statement}-${section.title}`} title={section.title} rows={section.rows}/>) : <Notice>No reliable mapped values are available for this statement.</Notice>}
      <div className="page-source">Source: <External href={data.source.url}>{data.source.label}</External> · Cached {data.source.cache_updated_at ? new Date(data.source.cache_updated_at).toLocaleDateString() : "date unavailable"} · Ratios and growth are calculated by FilingLens.</div>
    </> : data.quarterly && <>
      <div className="financial-note"><ShieldCheck size={17}/> Latest {data.quarterly.filing.form}, filed {dateLabel(data.quarterly.filing.filing_date)}. Income figures cover three months; cash-flow figures cover the fiscal year to date. Missing values are not estimated.</div>
      {data.quarterly.groups.length ? data.quarterly.groups.map(group => <section className="statement-section" key={group.title}><div className="statement-heading"><h3>{group.title}</h3><span>{group.basis === "As of quarter end" ? `As of ${dateLabel(data.quarterly!.filing.report_date)}` : `${group.basis} · ended ${dateLabel(data.quarterly!.filing.report_date)}`}</span></div><div className="surface-card quarterly-table"><div className="table-scroll"><table className="data-table"><thead><tr><th>Account</th><th>Reported value</th><th>Period</th><th>US-GAAP concept</th></tr></thead><tbody>{group.rows.map(row => <tr key={row.id}><td><strong>{row.label}</strong></td><td>{row.display}</td><td>{row.period_start ? `${dateLabel(row.period_start)} – ${dateLabel(row.period_end)}` : `As of ${dateLabel(row.period_end)}`}</td><td>{row.concept}</td></tr>)}</tbody></table></div></div></section>) : <Notice>No reliably matched US-GAAP figures are available from this 10-Q. Read the filing directly.</Notice>}
      <div className="page-source">Source: <External href={data.quarterly.filing.source_url}>Official SEC {data.quarterly.filing.form}</External> · Report period ended {dateLabel(data.quarterly.filing.report_date)}. These figures are separate from annual history.</div>
    </>}
  </>;
}

function Research({ data, researchTab, setResearchTab, filingForm, onSelectFiling, filing, filingBusy, filingError, loadFiling, askProps, brief, briefBusy, briefError, generateBrief, canGenerateBrief }: {
  data: CompanyData; researchTab: ResearchTab; setResearchTab: (tab: ResearchTab) => void;
  filingForm: FilingForm; onSelectFiling: (form: FilingForm) => void;
  filing: FilingIndex | null; filingBusy: boolean; filingError: string; loadFiling: () => void;
  askProps: Omit<React.ComponentProps<typeof AskPanel>, "data">;
  brief: Brief | null; briefBusy: boolean; briefError: string; generateBrief: () => void; canGenerateBrief: boolean;
}) {
  const selected = filingForm === "10-K" ? data.filings.annual : data.filings.quarterly;
  const currentFiling = filing?.filing.accession_number === selected?.accession_number ? filing : null;
  const available = [data.filings.annual, data.filings.quarterly].filter((item): item is Filing => item !== null);
  function downloadBrief() {
    if (!brief) return;
    const url = URL.createObjectURL(new Blob([brief.text], { type: "text/markdown" }));
    const link = document.createElement("a"); link.href = url; link.download = `${data.company.ticker}_FilingLens_brief.md`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <>
    <SectionHeader eyebrow="Primary-source research" title="Read, question, understand." description="Choose the latest 10-K or 10-Q for reading and questions. The brief brings both filings together when available."/>
    {researchTab !== "brief" && <FilingPicker data={data} selected={filingForm} onSelect={onSelectFiling}/>}
    <div className="filing-spotlight"><div className="filing-icon big"><BookOpen size={22}/></div><div><span className="eyebrow">{researchTab === "brief" ? "Brief sources" : "Current evidence source"}</span>
      {researchTab === "brief" ? <><strong>{available.length ? available.map(item => item.form).join(" + ") : "No 10-K or 10-Q available"}</strong><span>{available.map(item => `${item.form} filed ${dateLabel(item.filing_date)}`).join(" · ")}</span></> : <><strong>{selected ? `${selected.form} · filed ${dateLabel(selected.filing_date)}` : `No recent ${filingForm} available`}</strong><span>{selected ? `Report period ${dateLabel(selected.report_date)} · accession ${selected.accession_number}` : "Choose an available filing."}</span></>}
    </div>{researchTab !== "brief" && selected && <External href={selected.source_url} className="button button-outline">Open on SEC.gov</External>}</div>
    <div className="segmented" role="tablist" aria-label="Research tool"><button role="tab" aria-selected={researchTab === "filing"} className={researchTab === "filing" ? "active" : ""} onClick={() => setResearchTab("filing")}>Read filing</button><button role="tab" aria-selected={researchTab === "ask"} className={researchTab === "ask" ? "active" : ""} onClick={() => setResearchTab("ask")}>Ask the filing</button><button role="tab" aria-selected={researchTab === "brief"} className={researchTab === "brief" ? "active" : ""} onClick={() => setResearchTab("brief")}>Analyst brief</button></div>
    {researchTab === "filing" && <div className="research-grid"><section className="surface-card"><div className="card-top"><div><span className="eyebrow">Latest {filingForm}</span><h3>Filing sections</h3></div>{currentFiling && <span>{currentFiling.chunk_count} searchable passages</span>}</div><p>Read the cleaned filing here or follow its official SEC link. Sections are indexed locally for questions and briefs.</p>
      {!currentFiling && <button className="button button-dark" onClick={loadFiling} disabled={filingBusy || !selected}>{filingBusy ? "Indexing filing…" : `Load ${filingForm} sections`}<ArrowRight size={16}/></button>}
      {filingError && <Notice tone="error">{filingError}</Notice>}
      {currentFiling && <div className="filing-sections">{currentFiling.sections.map((section, index) => <details key={`${section.title}-${index}`}><summary>{section.title}<ChevronRight size={16}/></summary><p>{section.text}</p></details>)}</div>}
    </section><aside className="surface-card research-aside"><span className="eyebrow">Recent filings</span><h3>Document shelf</h3>{data.filings.recent.length ? data.filings.recent.map(item => <div className="shelf-item" key={item.accession_number}><FileText size={16}/><div><strong>{item.form}</strong><span>{dateLabel(item.filing_date)}</span></div><External href={item.source_url}>SEC</External></div>) : <p>No recent filings found.</p>}</aside></div>}
    {researchTab === "ask" && <div className="research-grid"><AskPanel data={data} {...askProps}/><aside className="surface-card research-aside"><span className="eyebrow">How it works</span><h3>Evidence first</h3><ol><li>FilingLens indexes the selected {filingForm} locally.</li><li>It retrieves passages related to your question.</li><li>Your selected model answers using those passages and clearly labeled verified metrics.</li></ol><p>Out-of-scope questions and price predictions are declined. Check cited passages before relying on an answer.</p></aside></div>}
    {researchTab === "brief" && <div className="research-grid"><section className="surface-card brief-panel"><div className="panel-title"><FileText size={20}/><div><strong>Analyst brief</strong><span>Annual and latest-quarter evidence, when available</span></div></div><p>Combines available 10-K and 10-Q passages with separately labeled annual and quarterly financial figures. It does not make a buy or sell recommendation.</p>
      <button className="button button-dark" disabled={!canGenerateBrief || briefBusy} onClick={generateBrief}>{briefBusy ? "Generating brief…" : "Generate analyst brief"}<ArrowRight size={16}/></button>
      {!canGenerateBrief && <Notice tone="warning">Choose a connected AI model in Settings and a company with a recent 10-K or 10-Q.</Notice>}
      {briefError && <Notice tone="error">{briefError}</Notice>}
      {brief && <><p className="brief-source-note">Sources: {brief.filings.map(item => `${item.form} filed ${dateLabel(item.filing_date)}`).join(" · ")}</p><div className="brief-actions"><button className="button button-outline" onClick={downloadBrief}>Download Markdown</button><button className="button button-outline" onClick={() => navigator.clipboard.writeText(brief.text)}>Copy text</button></div><div className="markdown-body brief-output"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{ a: ({ children }) => <span>{children}</span>, img: () => null }}>{brief.text}</ReactMarkdown></div><SourceList sources={brief.sources}/></>}
    </section><aside className="surface-card research-aside"><span className="eyebrow">In this brief</span><h3>What you receive</h3><p>Business overview, annual financial performance, a latest-quarter update when available, liquidity, risks, and questions for further research. Filing claims should cite numbered sources.</p><Notice>Generation can take several minutes with a local model.</Notice></aside></div>}
  </>;
}

function Signals({ data, insiders, insidersBusy, insidersError, loadInsiders }: { data: CompanyData; insiders: InsiderData | null; insidersBusy: boolean; insidersError: string; loadInsiders: (count: number) => void }) {
  const [tab, setTab] = useState<"anomalies" | "insiders">("anomalies");
  const [severity, setSeverity] = useState("Significant,Notable");
  const [mode, setMode] = useState<"impact" | "raw" | "off">("raw");
  const [direction, setDirection] = useState<"best" | "worst">("best");
  const [selected, setSelected] = useState<Anomaly | null>(null);
  const [filingCount, setFilingCount] = useState(20);
  const [category, setCategory] = useState("all");
  const anomalies = useMemo(() => data.anomalies.filter(item => severity.split(",").includes(item.severity)).sort((a, b) => {
    const order = mode === "impact" ? impactOrder : rawOrder;
    const first = order.indexOf(mode === "impact" ? a.impact_direction : a.raw_direction);
    const second = order.indexOf(mode === "impact" ? b.impact_direction : b.raw_direction);
    return (direction === "best" ? 1 : -1) * (first - second || b.period - a.period);
  }), [data.anomalies, severity, mode, direction]);
  const transactions = (insiders?.transactions || []).filter(row => category === "all" || (category === "purchases" && row.transaction_code === "P") || (category === "sales" && row.transaction_code === "S") || (category === "other" && row.transaction_code !== "P" && row.transaction_code !== "S"));
  function intensity(item: Anomaly) {
    if (mode === "off") return "";
    const signed = mode === "impact" ? item.impact_signed : item.percentage_change;
    if (signed == null || signed === 0) return "";
    const degree = Math.abs(signed) >= .4 ? "deep" : Math.abs(signed) >= .2 ? "medium" : "light";
    return `${signed > 0 ? "good" : "bad"}-${degree}`;
  }
  return <><SectionHeader eyebrow="Research signals" title="Changes that deserve context." description="Surface unusual financial movements and recent insider filings, then open the underlying evidence before drawing conclusions."/>
    <div className="segmented" role="tablist" aria-label="Signals"><button className={tab === "anomalies" ? "active" : ""} role="tab" aria-selected={tab === "anomalies"} onClick={() => setTab("anomalies")}>Anomaly analysis</button><button className={tab === "insiders" ? "active" : ""} role="tab" aria-selected={tab === "insiders"} onClick={() => setTab("insiders")}>Insider activity</button></div>
    {tab === "anomalies" ? <><Notice tone="warning">This is an unusual-change screen, not fraud detection. The optional “likely impact” view uses a simple directional heuristic, not a judgment about investment merit.</Notice><div className="filter-row"><label>Severity <select value={severity} onChange={event => setSeverity(event.target.value)}><option value="Significant,Notable">Significant & notable</option><option value="Significant">Significant only</option><option value="Notable">Notable only</option><option value="Significant,Notable,Normal">All changes</option></select></label><label>Color meaning <select value={mode} onChange={event => setMode(event.target.value as typeof mode)}><option value="raw">Raw increase / decrease</option><option value="impact">Likely financial impact</option><option value="off">No color</option></select></label><label>Direction order <select value={direction} onChange={event => setDirection(event.target.value as typeof direction)}><option value="best">{mode === "impact" ? "Most favorable heuristic first" : "Largest increases first"}</option><option value="worst">{mode === "impact" ? "Least favorable heuristic first" : "Largest decreases first"}</option></select></label></div><div className="surface-card anomaly-table-wrap"><div className="card-top"><h3>Annual movement screen</h3><span>{anomalies.length} results</span></div>{anomalies.length ? <div className="table-scroll"><table className="data-table anomaly-table"><thead><tr><th>Account</th><th>Year</th><th>Prior</th><th>Current</th><th>Change</th><th>Direction</th><th>Severity</th><th></th></tr></thead><tbody>{anomalies.map((item, index) => <tr key={`${item.metric}-${item.period}-${index}`}><td>{item.label}</td><td>FY{item.period}</td><td>{anomalyValue(item.metric, item.prior)}</td><td>{anomalyValue(item.metric, item.current)}</td><td><span className={`direction-chip ${intensity(item)}`}>{item.percentage_change == null ? "—" : `${item.percentage_change >= 0 ? "+" : ""}${(item.percentage_change * 100).toFixed(1)}%`}</span></td><td><span className={`direction-chip ${intensity(item)}`}>{mode === "impact" ? item.impact_direction : item.raw_direction}</span></td><td>{item.severity}</td><td><button className="icon-button" aria-label={`Read explanation for ${item.label} FY${item.period}`} onClick={() => setSelected(item)}><ChevronRight size={17}/></button></td></tr>)}</tbody></table></div> : <p>No changes match this filter.</p>}</div><p className="method-note">Notable ≥20% and significant ≥40% year-over-year; robust change scores also use median absolute deviation. Light, medium, and deep shades reflect movement magnitude.</p>{selected && <div className="modal-backdrop" onClick={() => setSelected(null)}><div className="detail-modal" role="dialog" aria-modal="true" aria-label="Anomaly explanation" onClick={event => event.stopPropagation()}><button className="icon-button close" onClick={() => setSelected(null)} aria-label="Close"><X size={18}/></button><span className="eyebrow">FY{selected.period} · {selected.severity}</span><h3>{selected.label}</h3><p>{selected.explanation}</p><div className="modal-meta">{mode === "impact" ? "Heuristic direction" : "Raw direction"}: {mode === "impact" ? selected.impact_direction : selected.raw_direction}<br/>Method: {selected.method}</div></div></div>}</> : <><Notice tone="warning">Insider filings are research signals, not trade recommendations. Sales can reflect taxes, diversification, or pre-arranged plans. Read Form 4 footnotes.</Notice><div className="insider-controls"><label>Recent Forms 4 to review <select value={filingCount} onChange={event => setFilingCount(Number(event.target.value))}>{[5, 10, 20, 30, 40, 50].map(value => <option key={value} value={value}>{value}</option>)}</select></label><button className="button button-dark" onClick={() => loadInsiders(filingCount)} disabled={insidersBusy}>{insidersBusy ? "Loading filings…" : "Load insider activity"}<ArrowRight size={16}/></button></div>{insidersError && <Notice tone="error">{insidersError}</Notice>}{insiders && <><div className="fact-grid insider-grid"><FactCard label="Open-market purchases" value={dollars(insiders.summary.purchases)}/><FactCard label="Open-market sales" value={dollars(insiders.summary.sales)}/><FactCard label="Net open-market value" value={dollars(insiders.summary.net)}/><FactCard label="Reporting insiders" value={insiders.summary.insiders}/></div><p className="method-note">Reviewed {insiders.filings_reviewed} filings. Totals use only non-amended open-market purchase (P) and sale (S) rows with reported value. {insiders.failures.length ? `${insiders.failures.length} filing(s) could not be parsed.` : ""}</p><div className="filter-row"><label>Transaction type <select value={category} onChange={event => setCategory(event.target.value)}><option value="all">All transactions</option><option value="purchases">Open-market purchases</option><option value="sales">Open-market sales</option><option value="other">Awards, gifts & other</option></select></label></div><div className="surface-card"><div className="card-top"><h3>Reported transactions</h3><span>{transactions.length} rows</span></div><div className="table-scroll"><table className="data-table"><thead><tr><th>Transaction</th><th>Insider</th><th>Type</th><th>Shares</th><th>Estimated value</th><th>Plan</th><th>Source</th></tr></thead><tbody>{transactions.map((row, index) => <tr key={index}><td>{String(row.transaction_date || "—")}</td><td><strong>{String(row.insider_name || "—")}</strong><span className="table-sub">{String(row.insider_role || "")}</span></td><td>{String(row.transaction_type || row.transaction_code || "—")}</td><td>{row.shares == null ? "—" : Number(row.shares).toLocaleString()}</td><td>{row.transaction_value == null ? "—" : dollars(Number(row.transaction_value))}</td><td>{row.plan_10b5_1 ? "10b5-1" : "—"}</td><td><External href={String(row.source_url)}>SEC</External></td></tr>)}</tbody></table></div></div></>}</>}
  </>;
}

function SettingsPage({ settings, onSave, saveBusy, saveError, providers, providerId, setProviderId, model, setModel, showPaid, setShowPaid, refreshProviders }: {
  settings: AppSettings | null; onSave: (agent: string, keys: Record<string, string>, removed: string[]) => Promise<boolean>; saveBusy: boolean; saveError: string;
  providers: Provider[]; providerId: string; setProviderId: (id: string) => void; model: string; setModel: (model: string) => void;
  showPaid: boolean; setShowPaid: (show: boolean) => void; refreshProviders: () => void;
}) {
  const [agent, setAgent] = useState(settings?.sec_user_agent || "");
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [removed, setRemoved] = useState<string[]>([]);
  useEffect(() => { if (settings) setAgent(settings.sec_user_agent); }, [settings]);
  const selected = providers.find(item => item.id === providerId);
  const shownModels = selected?.id === "ollama_cloud" && !showPaid && selected.free_models.length ? selected.free_models : selected?.models || [];
  const cloudKeys = [
    { id: "ollama_cloud", label: "Ollama Cloud", saved: settings?.ollama_cloud_key_saved },
    { id: "openai", label: "OpenAI", saved: settings?.openai_key_saved },
    { id: "anthropic", label: "Anthropic", saved: settings?.anthropic_key_saved },
  ];
  return <><SectionHeader eyebrow="Preferences & connectivity" title="Keep your research local and in control." description="SEC data is public. AI is optional: choose a local service or a cloud provider. Cloud keys are kept in macOS Keychain."/>
    <div className="settings-grid"><section className="surface-card settings-card"><div className="settings-icon"><Database size={21}/></div><h3>SEC data access</h3><p>The SEC asks automated tools to identify themselves with a contact email. This value is sent only in SEC requests.</p><label>SEC User-Agent<input value={agent} onChange={event => setAgent(event.target.value)} placeholder="FilingLens/1.0 you@example.com" /></label><p className="muted tiny">Cache: {settings?.cache_dir || "Loading…"}</p></section>{cloudKeys.map(provider => <section key={provider.id} className="surface-card settings-card"><div className="settings-icon"><KeyRound size={21}/></div><h3>{provider.label} key</h3><p>When selected, questions, verified metrics, and retrieved filing passages are sent to {provider.label}. Usage may incur charges.</p><label>API key<input type="password" value={keys[provider.id] || ""} onChange={event => { setKeys(current => ({ ...current, [provider.id]: event.target.value })); setRemoved(current => current.filter(item => item !== provider.id)); }} placeholder={provider.saved ? "Key already saved — enter to replace" : `Paste ${provider.label} API key`}/></label><div className="key-status">{provider.saved ? <><Check size={15}/> Saved in macOS Keychain</> : "No key saved"}</div>{provider.saved && <button className="text-button danger" onClick={() => { setRemoved(current => [...new Set([...current, provider.id])]); setKeys(current => ({ ...current, [provider.id]: "" })); }}>Remove saved key</button>}</section>)}</div>
    {removed.length > 0 && <Notice tone="warning">Selected keys will be removed when you save settings.</Notice>}{saveError && <Notice tone="error">{saveError}</Notice>}<button className="button button-dark settings-save" onClick={async () => { if (await onSave(agent, keys, removed)) { setKeys({}); setRemoved([]); } }} disabled={saveBusy}>{saveBusy ? "Saving…" : "Save settings"}<ArrowRight size={16}/></button>
    <section className="surface-card provider-card"><div className="card-top"><div><span className="eyebrow">Model connection</span><h3>Choose how AI runs</h3></div><button className="text-button" onClick={refreshProviders}><RefreshCw size={15}/> Check again</button></div><div className="provider-options">{providers.map(provider => <button key={provider.id} className={`provider-option ${providerId === provider.id ? "chosen" : ""}`} onClick={() => setProviderId(provider.id)}><span className="provider-check">{providerId === provider.id && <Check size={15}/>}</span><span><strong>{provider.label}</strong><small>{provider.status}</small></span></button>)}</div>{selected && <div className="model-row"><label>Model <select value={shownModels.includes(model) ? model : ""} onChange={event => setModel(event.target.value)}><option value="" disabled>{model ? `${model} is unavailable in this list` : "Choose a model"}</option>{shownModels.map(item => <option key={item} value={item}>{item}</option>)}</select></label>{selected.id === "ollama_cloud" && selected.free_models.length > 0 && <label className="checkbox-label"><input type="checkbox" checked={showPaid} onChange={event => setShowPaid(event.target.checked)}/> Show models that may require paid credits</label>}</div>}<p className="card-foot">Local LM Studio or Ollama must be running separately. Cloud requests may incur provider charges.</p></section>
    <section className="surface-card methodology"><span className="eyebrow">Methodology</span><h3>How FilingLens works</h3><div className="method-columns"><div><span>01</span><strong>Official data</strong><p>SEC submissions, XBRL Company Facts, Forms 4, and filing documents are cached with their source links.</p></div><div><span>02</span><strong>Deterministic analytics</strong><p>Python calculates financial statements, ratios, year-over-year changes, and robust anomaly screens.</p></div><div><span>03</span><strong>Grounded language</strong><p>The selected model interprets retrieved filing passages and verified metrics. It does not calculate the figures.</p></div></div><p className="card-foot">Educational financial-analysis software. Not investment advice.</p></section>
  </>;
}

export default function App() {
  const [view, setView] = useState<View>("overview");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [approach, setApproach] = useState<ResearchApproach>(readApproach);
  const [savedCompanies, setSavedCompanies] = useState<SavedCompany[]>(readSavedCompanies);
  const [previousCheck, setPreviousCheck] = useState<string | null>(null);
  const [researchChanges, setResearchChanges] = useState<ResearchChange[]>([]);
  const [tickerInput, setTickerInput] = useState(localStorage.getItem("fl:ticker") || "AAPL");
  const [ticker, setTicker] = useState(localStorage.getItem("fl:ticker") || "AAPL");
  const [suggestions, setSuggestions] = useState<{ ticker: string; name: string; cik: string }[]>([]);
  const [years, setYears] = useState(() => Math.max(3, Math.min(10, Number(localStorage.getItem("fl:years") || 5) || 5)));
  const [data, setData] = useState<CompanyData | null>(null);
  const [companyBusy, setCompanyBusy] = useState(false);
  const [companyError, setCompanyError] = useState("");
  const [providers, setProviders] = useState<Provider[]>([]);
  const [providerId, setProviderId] = useState(localStorage.getItem("fl:provider") || "lmstudio");
  const [model, setModelState] = useState("");
  const [showPaid, setShowPaid] = useState(false);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [saveBusy, setSaveBusy] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [askBusy, setAskBusy] = useState(false);
  const [askError, setAskError] = useState("");
  const [researchTab, setResearchTab] = useState<ResearchTab>("filing");
  const [filingForm, setFilingForm] = useState<FilingForm>("10-K");
  const [filing, setFiling] = useState<FilingIndex | null>(null);
  const [filingBusy, setFilingBusy] = useState(false);
  const [filingError, setFilingError] = useState("");
  const [brief, setBrief] = useState<Brief | null>(null);
  const [briefBusy, setBriefBusy] = useState(false);
  const [briefError, setBriefError] = useState("");
  const [insiders, setInsiders] = useState<InsiderData | null>(null);
  const [insidersBusy, setInsidersBusy] = useState(false);
  const [insidersError, setInsidersError] = useState("");
  const [provenance, setProvenance] = useState<Record<string, unknown>[] | null>(null);
  const [provenanceBusy, setProvenanceBusy] = useState(false);
  const requestId = useRef(0);
  const filingChoiceTicker = useRef("");
  useEffect(() => {
    if (!settings?.sec_user_agent) { setSuggestions([]); return; }
    if (tickerInput.trim().length < 2) { setSuggestions([]); return; }
    let cancelled = false;
    const timer = setTimeout(() => {
      api<{ ticker: string; name: string; cik: string }[]>(`/api/search?q=${encodeURIComponent(tickerInput.trim())}`)
        .then(results => { if (!cancelled) setSuggestions(results); })
        .catch(() => { if (!cancelled) setSuggestions([]); });
    }, 250);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [tickerInput, settings?.sec_user_agent]);

  const refreshProviders = useCallback(() => { api<Provider[]>("/api/providers").then(setProviders).catch(() => setProviders([])); }, []);
  useEffect(() => { refreshProviders(); api<AppSettings>("/api/settings").then(current => { setSettings(current); if (!current.sec_user_agent) setView("settings"); }).catch(() => {}); }, [refreshProviders]);
  useEffect(() => {
    const selected = providers.find(item => item.id === providerId);
    const stored = localStorage.getItem(`fl:model:${providerId}`) || "";
    const preferred = selected?.id === "ollama_cloud" && selected.free_models.length ? selected.free_models : selected?.models || [];
    setModelState(stored || preferred[0] || "");
    localStorage.setItem("fl:provider", providerId);
  }, [providers, providerId]);
  function setModel(value: string) { setModelState(value); localStorage.setItem(`fl:model:${providerId}`, value); }
  const activeProvider = providers.find(item => item.id === providerId);
  const selectedFiling = filingForm === "10-K" ? data?.filings.annual : data?.filings.quarterly;
  const modelReady = Boolean(model && activeProvider?.models.includes(model) &&
    (providerId !== "ollama_cloud" || showPaid || !activeProvider.free_models.length || activeProvider.free_models.includes(model)));
  const canAsk = Boolean(selectedFiling && modelReady);
  const canGenerateBrief = Boolean((data?.filings.annual || data?.filings.quarterly) && modelReady);

  const loadCompany = useCallback(async (symbol: string, count: number, refresh = false) => {
    const id = ++requestId.current;
    setCompanyBusy(true); setCompanyError("");
    try {
      const result = await api<CompanyData>(`/api/company/${encodeURIComponent(symbol)}?years=${count}${refresh ? "&refresh=true" : ""}`);
      if (id !== requestId.current) return;
      const current = makeSnapshot(result);
      const previous = readSnapshot(result.company.ticker);
      setPreviousCheck(previous?.checkedAt || null);
      setResearchChanges(compareSnapshots(previous, current, result));
      saveSnapshot(result.company.ticker, current);
      if (filingChoiceTicker.current !== result.company.ticker) {
        filingChoiceTicker.current = result.company.ticker;
        setFilingForm(result.filings.quarterly && (!result.filings.annual || result.filings.quarterly.filing_date > result.filings.annual.filing_date) ? "10-Q" : "10-K");
      }
      setData(result);
    } catch (error) {
      if (id !== requestId.current) return;
      setData(null); setCompanyError(messageOf(error));
    } finally { if (id === requestId.current) setCompanyBusy(false); }
  }, []);
  useEffect(() => { if (settings?.sec_user_agent) loadCompany(ticker, years); }, [ticker, years, loadCompany, settings?.sec_user_agent]);
  function changeTicker(event: React.FormEvent) {
    event.preventDefault();
    const entered = tickerInput.trim().toUpperCase().replace(".", "-");
    const normalized = suggestions.find(item => item.ticker === entered)?.ticker ||
      (entered.length > 10 ? suggestions[0]?.ticker : entered);
    if (!normalized) return;
    chooseTicker(normalized);
  }
  function chooseTicker(normalized: string) {
    requestId.current += 1;
    localStorage.setItem("fl:ticker", normalized);
    setTicker(normalized); setTickerInput(normalized); setSuggestions([]);
    setView("overview"); setAnswer(null); setBrief(null); setFiling(null); setInsiders(null); setProvenance(null);
    setPreviousCheck(null); setResearchChanges([]);
    setAskBusy(false); setBriefBusy(false); setFilingBusy(false); setInsidersBusy(false);
    if (normalized === ticker) loadCompany(normalized, years);
  }
  function changeYears(count: number) {
    requestId.current += 1;
    setYears(count);
    localStorage.setItem("fl:years", String(count));
    setAnswer(null); setBrief(null); setFiling(null); setInsiders(null); setProvenance(null);
    setAskBusy(false); setBriefBusy(false); setFilingBusy(false); setInsidersBusy(false);
  }
  function changeView(next: View, tab?: ResearchTab) { setView(next); if (tab) setResearchTab(tab); setMobileOpen(false); window.scrollTo({ top: 0, behavior: "smooth" }); }
  function selectFiling(form: FilingForm) {
    if (form === filingForm) return;
    requestId.current += 1;
    setFilingForm(form); setFiling(null); setFilingError(""); setFilingBusy(false);
    setAnswer(null); setAskError(""); setAskBusy(false);
    setBrief(null); setBriefError(""); setBriefBusy(false);
  }
  function changeApproach(value: ResearchApproach) { setApproach(value); saveApproach(value); }
  function toggleSavedCompany() {
    if (!data) return;
    const company = { ticker: data.company.ticker, name: data.company.name };
    const next = savedCompanies.some(item => item.ticker === company.ticker)
      ? savedCompanies.filter(item => item.ticker !== company.ticker)
      : [...savedCompanies, company];
    setSavedCompanies(next); saveCompanies(next);
  }
  function removeSavedCompany(symbol: string) {
    const next = savedCompanies.filter(item => item.ticker !== symbol);
    setSavedCompanies(next); saveCompanies(next);
  }
  async function ask(question: string) {
    if (!canAsk) return;
    const activeRequest = requestId.current;
    setAskBusy(true); setAskError(""); setAnswer(null);
    try { const response = await post<Answer>("/api/ask", { ticker, question, provider: providerId, model, years, filing_form: filingForm }); if (activeRequest === requestId.current) setAnswer(response); }
    catch (error) { if (activeRequest === requestId.current) setAskError(messageOf(error)); }
    finally { if (activeRequest === requestId.current) setAskBusy(false); }
  }
  async function loadFiling() {
    const activeRequest = requestId.current;
    setFilingBusy(true); setFilingError("");
    try { const response = await api<FilingIndex>(`/api/company/${encodeURIComponent(ticker)}/filing?years=${years}&form=${filingForm}`); if (activeRequest === requestId.current) setFiling(response); }
    catch (error) { if (activeRequest === requestId.current) setFilingError(messageOf(error)); }
    finally { if (activeRequest === requestId.current) setFilingBusy(false); }
  }
  async function generateBrief() {
    if (!canGenerateBrief) return;
    const activeRequest = requestId.current;
    setBriefBusy(true); setBriefError(""); setBrief(null);
    try { const response = await post<Brief>("/api/brief", { ticker, provider: providerId, model, years }); if (activeRequest === requestId.current) setBrief(response); }
    catch (error) { if (activeRequest === requestId.current) setBriefError(messageOf(error)); }
    finally { if (activeRequest === requestId.current) setBriefBusy(false); }
  }
  async function loadInsiders(count: number) {
    const activeRequest = requestId.current;
    setInsidersBusy(true); setInsidersError("");
    try { const response = await api<InsiderData>(`/api/company/${encodeURIComponent(ticker)}/insiders?max_filings=${count}`); if (activeRequest === requestId.current) setInsiders(response); }
    catch (error) { if (activeRequest === requestId.current) setInsidersError(messageOf(error)); }
    finally { if (activeRequest === requestId.current) setInsidersBusy(false); }
  }
  async function loadProvenance() {
    setProvenanceBusy(true);
    try { setProvenance(await api<Record<string, unknown>[]>(`/api/company/${encodeURIComponent(ticker)}/provenance?years=${years}`)); }
    catch (error) { setCompanyError(messageOf(error)); }
    finally { setProvenanceBusy(false); }
  }
  async function saveSettings(agent: string, keys: Record<string, string>, removed: string[]): Promise<boolean> {
    setSaveBusy(true); setSaveError("");
    try { const updated = await post<AppSettings>("/api/settings", { sec_user_agent: agent,
      ollama_cloud_key: keys.ollama_cloud || null, remove_ollama_cloud_key: removed.includes("ollama_cloud"),
      openai_api_key: keys.openai || null, remove_openai_api_key: removed.includes("openai"),
      anthropic_api_key: keys.anthropic || null, remove_anthropic_api_key: removed.includes("anthropic") });
      setSettings(updated); refreshProviders(); if (!data) setView("overview"); return true; }
    catch (error) { setSaveError(messageOf(error)); return false; }
    finally { setSaveBusy(false); }
  }
  const askProps = { provider: providerId, model, canAsk, onAsk: ask, answer, busy: askBusy, error: askError, filingForm, onSelectFiling: selectFiling };
  const currentNav = navigation.find(item => item.id === view)!;
  const latestReport = data?.filings.quarterly && (!data.filings.annual || data.filings.quarterly.filing_date > data.filings.annual.filing_date)
    ? data.filings.quarterly : data?.filings.annual;
  return <div className="app-shell">
    <aside className={`sidebar ${mobileOpen ? "mobile-open" : ""}`}>
      <div className="brand"><div className="brand-mark"><FileSearch size={24}/></div><div><strong>FilingLens</strong><span>Company intelligence</span></div></div>
      <div className="sidebar-label">WORKSPACE</div>
      <div className="search-wrap"><form className="ticker-search" onSubmit={changeTicker}><Search size={17}/><input aria-label="Company name or ticker" value={tickerInput} onChange={event => setTickerInput(event.target.value)} maxLength={60} placeholder="Company or ticker"/><button type="submit" aria-label="Search company"><ArrowRight size={17}/></button></form>
        {suggestions.length > 0 && tickerInput.toUpperCase() !== ticker && <div className="search-suggestions">{suggestions.map(item => <button key={item.ticker} onClick={() => chooseTicker(item.ticker)}><strong>{item.ticker}</strong><span>{item.name}</span></button>)}</div>}
      </div>
      <nav aria-label="Main navigation">{navigation.map(item => <button key={item.id} onClick={() => changeView(item.id)} className={view === item.id ? "nav-active" : ""}>{item.icon}<span>{item.label}</span>{view === item.id && <span className="nav-dot"/>}</button>)}</nav>
      <div className="saved-shelf"><div className="sidebar-label">SAVED COMPANIES</div>{savedCompanies.length ? <div className="saved-list">{savedCompanies.map(item => <div className="saved-row" key={item.ticker}><button className={ticker === item.ticker ? "current" : ""} title={item.name} onClick={() => chooseTicker(item.ticker)}><Bookmark size={14}/><span>{item.ticker}</span><small>{item.name}</small></button><button className="saved-remove" title={`Remove ${item.ticker} from saved companies`} aria-label={`Remove ${item.ticker} from saved companies`} onClick={() => removeSavedCompany(item.ticker)}><X size={13}/></button></div>)}</div> : <p>Save a company on Overview to return to it quickly.</p>}</div>
      <div className="sidebar-bottom"><div className="period-select"><span>Historical periods</span><select value={years} onChange={event => changeYears(Number(event.target.value))}>{[3, 4, 5, 6, 7, 8, 9, 10].map(value => <option key={value} value={value}>{value} years</option>)}</select></div><div className="service-status"><span className={activeProvider?.models.length ? "status-dot good" : "status-dot"}/><div><strong>{activeProvider?.label || "AI optional"}</strong><small>{activeProvider?.models.length ? `${activeProvider.models.length} model(s) available` : "Check connection in Settings"}</small></div></div><p>Educational analysis · Not investment advice</p></div>
    </aside>
    {mobileOpen && <button className="mobile-scrim" aria-label="Close menu" onClick={() => setMobileOpen(false)}/>}
    <div className="main-shell"><header className="topbar"><button className="mobile-menu icon-button" onClick={() => setMobileOpen(true)} aria-label="Open menu"><Menu size={21}/></button><div className="breadcrumb"><span>Workspace</span><ChevronRight size={15}/><strong>{currentNav.label}</strong></div><div className="topbar-actions"><span className="ticker-badge">{data?.company.ticker || ticker}</span><button className="icon-button" title="Refresh official SEC data" aria-label="Refresh SEC data" onClick={() => loadCompany(ticker, years, true)} disabled={companyBusy}><RefreshCw size={18}/></button><button className="icon-button" title="Settings" aria-label="Settings" onClick={() => changeView("settings")}><CircleHelp size={18}/></button></div></header>
      <main className="content"><div className="workspace-meta"><span><span className="meta-dot"/> LOCAL RESEARCH WORKSPACE</span><span><Clock3 size={14}/> {latestReport ? `Latest ${latestReport.form} filed ${dateLabel(latestReport.filing_date)}` : "Official SEC data"}</span></div>
        {companyError && <div className="load-error"><Notice tone="error">{companyError}</Notice><button className="button button-outline" onClick={() => changeView("settings")}>Review SEC settings <ArrowRight size={15}/></button></div>}
        {view === "settings" && <SettingsPage settings={settings} onSave={saveSettings} saveBusy={saveBusy} saveError={saveError} providers={providers} providerId={providerId} setProviderId={setProviderId} model={model} setModel={setModel} showPaid={showPaid} setShowPaid={setShowPaid} refreshProviders={refreshProviders}/>}
        {companyBusy && view !== "settings" && <div className="loading-state"><span className="loading-orbit"/><h2>Gathering official filings for {ticker}…</h2><p>The first load may take a moment. Previously downloaded data is reused locally.</p></div>}
        {!companyBusy && data && view !== "settings" && <>
          {view === "overview" && <Overview data={data} onView={changeView} askProps={askProps} provenance={provenance} loadProvenance={loadProvenance} provenanceBusy={provenanceBusy} approach={approach} onApproachChange={changeApproach} saved={savedCompanies.some(item => item.ticker === data.company.ticker)} onToggleSaved={toggleSavedCompany} previousCheck={previousCheck} changes={researchChanges}/>}
          {view === "financials" && <Financials data={data}/>}
          {view === "research" && <Research data={data} researchTab={researchTab} setResearchTab={setResearchTab} filingForm={filingForm} onSelectFiling={selectFiling} filing={filing} filingBusy={filingBusy} filingError={filingError} loadFiling={loadFiling} askProps={askProps} brief={brief} briefBusy={briefBusy} briefError={briefError} generateBrief={generateBrief} canGenerateBrief={canGenerateBrief}/>}
          {view === "signals" && <Signals data={data} insiders={insiders} insidersBusy={insidersBusy} insidersError={insidersError} loadInsiders={loadInsiders}/>}
        </>}
      </main><footer className="footer"><span>FilingLens · Local-first filing intelligence</span><span>Sources are public SEC filings. Verify before acting.</span></footer></div>
  </div>;
}
