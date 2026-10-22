import { useEffect, useRef, useState } from "react";
import { ArrowRight, Columns3, Plus, X } from "lucide-react";
import { post } from "./api";
import { Notice, SectionHeader } from "./visuals";
import { Evidence, ResearchLoading } from "./TimeMachine";
import { currency, percent, periodLabel } from "./researchData";
import type { PeerData } from "./researchData";
import type { SavedCompany } from "./researchPreferences";
import type { CompanyData } from "./types";

const metrics = [
  ["revenue", "Revenue", "usd"], ["revenue_growth", "Revenue growth", "percent"],
  ["operating_margin", "Operating margin", "percent"], ["net_margin", "Net margin", "percent"],
  ["free_cash_flow", "Free cash flow", "usd"], ["free_cash_flow_margin", "Free cash flow margin", "percent"],
  ["current_ratio", "Current ratio", "multiple"], ["debt_to_assets", "Long-term debt / assets", "percent"],
];

export function PeerComparison({ company, years, saved }: { company: CompanyData; years: number; saved: SavedCompany[] }) {
  const [symbols, setSymbols] = useState([company.company.ticker]);
  const [input, setInput] = useState("");
  const [result, setResult] = useState<PeerData | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const request = useRef(0);
  useEffect(() => () => { request.current++; }, []);
  useEffect(() => { request.current++; setResult(null); setBusy(false); }, [company.source.loaded_at]);
  function changeSymbols(next: string[]) { request.current++; setSymbols(next); setResult(null); setBusy(false); setError(""); }
  function add(raw: string) {
    const proposed = raw.toUpperCase().split(/[\s,]+/).filter(Boolean).map(value => value.replaceAll(".", "-"));
    if (!proposed.length || proposed.some(value => !/^[A-Z0-9-]{1,10}$/.test(value))) { setError("Enter a ticker, or several tickers separated by commas."); return; }
    const next = [...new Set([...symbols, ...proposed])];
    if (next.length > 4) { setError("Choose up to four companies for this comparison."); return; }
    changeSymbols(next); setInput("");
  }
  async function compare(year?: number) {
    const id = ++request.current;
    setBusy(true); setError("");
    try {
      const response = await post<PeerData>("/api/peers", { tickers: symbols, years, year: year ?? null });
      if (id === request.current) setResult(response);
    } catch (cause) { if (id === request.current) { setError(cause instanceof Error ? cause.message : "Could not compare these companies."); setResult(null); } }
    finally { if (id === request.current) setBusy(false); }
  }
  return <>
    <SectionHeader eyebrow="Company comparison" title="Put the numbers in perspective." description="Compare two to four companies using a shared annual reporting end-year. Every margin, growth rate, and financial value keeps its underlying SEC sources." aside={<div className="source-pill"><Columns3 size={16}/> Annual fundamentals</div>}/>
    <section className="surface-card peer-builder"><div className="card-top"><div><span className="eyebrow">Build your peer group</span><h3>Who belongs beside {company.company.ticker}?</h3></div><span>{symbols.length} / 4 companies</span></div>
      <div className="peer-chips">{symbols.map(symbol => <span key={symbol}>{symbol}<button aria-label={`Remove ${symbol}`} onClick={() => changeSymbols(symbols.filter(item => item !== symbol))}><X size={14}/></button></span>)}</div>
      <form className="peer-add" onSubmit={event => { event.preventDefault(); add(input); }}><label className="sr-only" htmlFor="peer-ticker">Add peer tickers</label><input id="peer-ticker" value={input} onChange={event => setInput(event.target.value)} placeholder="Add tickers, e.g. MSFT, GOOGL" maxLength={55}/><button className="button button-outline" disabled={symbols.length >= 4 || !input.trim()}><Plus size={16}/> Add</button></form>
      {saved.some(item => !symbols.includes(item.ticker)) && <div className="peer-saved"><span>From saved companies</span>{saved.filter(item => !symbols.includes(item.ticker)).map(item => <button key={item.ticker} disabled={symbols.length >= 4} onClick={() => add(item.ticker)}>{item.ticker}<Plus size={12}/></button>)}</div>}
      <button className="button button-dark" disabled={symbols.length < 2 || busy} onClick={() => compare()}>{busy ? "Comparing SEC financials…" : "Compare companies"}<ArrowRight size={16}/></button>
      {error && <Notice tone="error">{error}</Notice>}
    </section>
    {busy ? <ResearchLoading retry={() => compare()}/> : result ? <div className="topic-enter" key={result.year}>
      {result.errors.map(item => <Notice tone="warning" key={item.ticker}>{item.ticker}: {item.message}</Notice>)}
      {result.companies.length >= 2 ? <>
        <div className="research-controls"><label>Annual reporting end-year<select value={result.year ?? ""} onChange={event => compare(Number(event.target.value))}>{result.years.map(year => <option key={year} value={year}>{year}</option>)}</select></label><span>{result.year === result.years[0] ? "Latest shared reporting end-year" : "Earlier shared reporting end-year"}</span></div>
        <Notice>Companies can have different fiscal calendars. These annual periods end in the same calendar year; check the exact dates below. Business mix and accounting definitions can also differ. Missing inputs remain unavailable.</Notice>
        <section className="surface-card research-table-card"><div className="table-scroll" tabIndex={0} role="region" aria-label="Peer financial comparison, scroll horizontally for all companies"><table className="data-table peer-table"><thead><tr><th>Annual metric</th>{result.companies.map(peer => <th key={peer.company.ticker}><strong>{peer.company.ticker}</strong><span>{peer.company.name}</span><small>{periodLabel(peer.start, peer.end)}</small></th>)}</tr></thead><tbody>{metrics.map(([id, label, unit]) => <tr key={id}><td>{label}</td>{result.companies.map(peer => { const value = peer.metrics[id]; const number = value?.value; return <td key={peer.company.ticker}><strong>{unit === "usd" ? currency(number) : unit === "percent" ? percent(number) : number == null ? "—" : `${number.toFixed(2)}x`}</strong>{value && <Evidence sources={value.sources}/>}</td>; })}</tr>)}</tbody></table></div></section>
        <p className="method-note">Margins use inputs from the same exact reporting period. Revenue growth requires an adjacent prior annual period using the same concept. Leverage here uses mapped long-term debt, not every form of debt. This comparison does not rank investments or use market prices.</p>
      </> : <Notice>No shared annual revenue reporting end-year was found for at least two loaded companies. Try another peer group or a longer history.</Notice>}
    </div> : <div className="peer-empty"><Columns3 size={36}/><h3>A useful comparison starts with a relevant peer.</h3><p>Add a company with a similar business, then compare growth, margins, cash generation, and leverage.</p></div>}
  </>;
}
