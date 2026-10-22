import { useEffect, useRef, useState } from "react";
import { ArrowRight, BookOpen, Download, Plus, X } from "lucide-react";
import { invoke } from "@tauri-apps/api/core";
import { api } from "./api";
import { External, Notice } from "./visuals";
import { readEvidenceReview, saveEvidenceReview } from "./evidenceReviews";
import type { EvidenceAttachment, EvidenceReview, Hypothesis, Judgment } from "./evidenceReviews";
import type { Anomaly, CompanyData, EvidenceMovement, EvidenceObservation, EvidenceTrailData } from "./types";

const date = (value: string) => new Date(`${value}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
const percent = (value: number | null) => value === null ? "Percentage change unavailable (zero or missing prior value)" : `${value >= 0 ? "+" : ""}${(value * 100).toFixed(1)}% versus the prior available observation`;

function Observation({ value }: { value: EvidenceObservation }) {
  return <div className="evidence-observation">
    <div><strong>{value.label} · {value.year}</strong><span>{value.display}</span></div>
    {value.source ? <p>{value.source.form} filed {date(value.source.filed)} · {value.source.start ? `${date(value.source.start)} – ` : "As of "}{date(value.source.end)}<br/>
      <span className="evidence-concept">{value.source.concept} · {value.value?.toLocaleString("en-US", { maximumFractionDigits: 12 })} {value.source.unit}</span>{" "}
      {value.source.url && <External href={value.source.url}>SEC source</External>}</p>
      : value.inputs.length ? <><p>Calculated: {value.formula}</p><div className="evidence-inputs">{value.inputs.map(input => <Observation key={input.id} value={input}/>)}</div></>
        : <p>Source input unavailable. This figure cannot be fully traced here.</p>}
  </div>;
}

function Movement({ movement, primary = false }: { movement: EvidenceMovement; primary?: boolean }) {
  return <section className={`evidence-movement ${primary ? "evidence-primary" : ""}`}>
    <div className="evidence-movement-title"><h4>{movement.label}</h4><span>{primary ? "Selected movement" : "Related movement"}</span></div>
    <div className="evidence-values"><div><span>{movement.prior.year}</span><strong>{movement.prior.display}</strong></div><ArrowRight size={20} aria-hidden="true"/>
      <div><span>{movement.current.year}</span><strong>{movement.current.display}</strong></div></div>
    <p>Change: {movement.change_display} · {percent(movement.percentage_change)}</p>
    <details><summary>Inspect calculation inputs and sources</summary><Observation value={movement.prior}/><Observation value={movement.current}/></details>
  </section>;
}

function observationText(value: EvidenceObservation): string {
  const source = value.source;
  return `${value.label} (${value.year}): ${value.display}; exact value ${value.value ?? "unavailable"}${source ? ` ${source.unit}; ${source.concept}; ${source.start || "instant"} to ${source.end}; filed ${source.filed}; ${source.accession}; ${source.url || "source unavailable"}` : value.formula ? `; ${value.formula}` : "; source unavailable"}${value.inputs.length ? `\n${value.inputs.map(observationText).join("\n")}` : ""}`;
}

function attachments(trail: EvidenceTrailData): EvidenceAttachment[] {
  return [trail.movement, ...trail.related].map(item => ({
    id: item.id, label: `${item.label}: ${item.prior.year} → ${item.current.year}`,
    detail: `${observationText(item.prior)}\n${observationText(item.current)}\n${percent(item.percentage_change)}`,
    url: item.current.source?.url || null,
  })).concat(trail.passages.map(item => ({ id: item.id, label: `${item.form} filed ${item.filed} · ${item.section}`,
    detail: item.text, url: item.url })));
}

function ReviewNotebook({ trail }: { trail: EvidenceTrailData }) {
  const [review, setReview] = useState<EvidenceReview>(() => readEvidenceReview(localStorage, trail.id));
  const [text, setText] = useState("");
  const [saved, setSaved] = useState(true);
  const [exportPath, setExportPath] = useState("");
  const [exportError, setExportError] = useState("");
  const [exportBusy, setExportBusy] = useState(false);
  const options = attachments(trail);

  function update(hypotheses: Hypothesis[]) {
    const next: EvidenceReview = { version: 1, trailId: trail.id, hypotheses };
    setReview(next);
    setSaved(saveEvidenceReview(localStorage, next));
  }
  function change(id: string, fields: Partial<Hypothesis>) {
    update(review.hypotheses.map(item => item.id === id ? { ...item, ...fields } : item));
  }
  function add() {
    if (!text.trim() || review.hypotheses.length >= 20) return;
    update([...review.hypotheses, { id: crypto.randomUUID(), text: text.trim(), judgment: "unresolved", note: "", evidence: [] }]);
    setText("");
  }
  async function download() {
    const lines = [`# ${trail.ticker} — ${trail.movement.label}: ${trail.prior_period} → ${trail.period}`, "", "## Observed movements", "",
      ...[trail.movement, ...trail.related].flatMap(item => [`### ${item.label}`, observationText(item.prior), observationText(item.current), ""]),
      "## Retrieved passages (research leads, not verified explanations)", "",
      ...trail.passages.flatMap(item => [`### ${item.section} — ${item.form} filed ${item.filed}`, item.text, item.url, ""]),
      "## Your hypotheses and judgments", "",
      ...review.hypotheses.flatMap(item => [`### ${item.text}`, `Your judgment: ${item.judgment}`, item.note,
        ...item.evidence.flatMap(source => [`Attached: ${source.label}`, source.detail, source.url || ""]), ""]),
      "## Limitations", ...trail.notices, ...trail.passage_issues];
    const filename = `${trail.ticker}-${trail.metric}-${trail.period}-evidence.md`;
    setExportError(""); setExportBusy(true);
    try {
      if ("__TAURI_INTERNALS__" in window) {
        setExportPath(await invoke<string>("export_investigation", { filename, content: lines.join("\n\n") }));
      } else {
        const url = URL.createObjectURL(new Blob([lines.join("\n\n")], { type: "text/markdown;charset=utf-8" }));
        const link = document.createElement("a"); link.href = url; link.download = filename;
        link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
    } catch (cause) { setExportError(typeof cause === "string" ? cause : "Could not export this investigation. Your notes remain available here."); }
    finally { setExportBusy(false); }
  }
  return <section className="evidence-notebook" aria-label="Your hypotheses">
    <div className="evidence-heading"><div><span className="eyebrow">Your interpretation</span><h3>Keep the question open.</h3></div>
      <button className="button button-outline" onClick={download} disabled={exportBusy}><Download size={15}/> {exportBusy ? "Saving…" : "Export investigation"}</button></div>
    {exportPath && <Notice>Saved: {exportPath}<br/><button className="text-button" onClick={() => invoke("show_investigation_exports").catch(() => setExportError("Could not open Finder. Use the saved path shown above."))}>Show export folder</button></Notice>}
    {exportError && <Notice tone="error">{exportError}</Notice>}
    <p>Write a possible explanation, attach evidence, and record your judgment. Supported and contradicted are your assessments; FilingLens does not verify them. Saved on this Mac for these exact source values.</p>
    {!saved && <Notice tone="warning">Your latest edits could not be saved locally. Keep this window open and export the investigation before leaving.</Notice>}
    <form className="evidence-add" onSubmit={event => { event.preventDefault(); add(); }}>
      <label htmlFor="new-hypothesis">Possible explanation or research question</label>
      <textarea id="new-hypothesis" maxLength={2000} rows={2} value={text} onChange={event => setText(event.target.value)} placeholder="For example: collection timing may be related to the cash-flow change."/>
      <button className="button button-dark" disabled={!text.trim() || review.hypotheses.length >= 20}><Plus size={15}/> Add hypothesis</button>
      {review.hypotheses.length >= 20 && <p>This investigation has reached the limit of 20 hypotheses.</p>}
    </form>
    {review.hypotheses.map(item => <article key={item.id} className="evidence-hypothesis">
      <div className="evidence-heading"><h4>{item.text}</h4><button className="icon-button" aria-label={`Remove hypothesis: ${item.text}`} onClick={() => update(review.hypotheses.filter(value => value.id !== item.id))}><X size={16}/></button></div>
      <label>Your judgment <select value={item.judgment} onChange={event => change(item.id, { judgment: event.target.value as Judgment })}>
        <option value="unresolved">Unresolved</option><option value="supported">Supported</option><option value="contradicted">Contradicted</option>
      </select></label>
      <label>Reasoning and qualifications<textarea rows={2} maxLength={4000} value={item.note} onChange={event => change(item.id, { note: event.target.value })}/></label>
      <details><summary>Attach or inspect evidence ({item.evidence.length})</summary>
        {[...options, ...item.evidence.filter(source => !options.some(option => option.id === source.id))].map(source => {
          const attached = item.evidence.find(value => value.id === source.id);
          return <div className="evidence-attachment" key={source.id}><label><input type="checkbox" checked={Boolean(attached)} onChange={event => change(item.id, { evidence: event.target.checked ? [...item.evidence, source] : item.evidence.filter(value => value.id !== source.id) })}/>{source.label}</label>
            {attached && <><p>{attached.detail}</p>{attached.url && <External href={attached.url}>Attached SEC source</External>}</>}</div>;
        })}
      </details>
    </article>)}
    <p className="evidence-storage-note" role="status">{saved ? "Hypotheses and attached evidence are saved locally as you edit. Source revisions create a separate investigation; your earlier review remains in local storage." : "Unsaved changes — export to preserve them."}</p>
  </section>;
}

export function EvidenceTrail({ data, anomaly, years, onClose }: { data: CompanyData; anomaly: Anomaly; years: number; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [trail, setTrail] = useState<EvidenceTrailData | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);
  const request = useRef(0);
  const path = `/api/company/${encodeURIComponent(data.company.ticker)}/evidence?metric=${encodeURIComponent(anomaly.metric)}&period=${anomaly.period}&years=${years}`;

  useEffect(() => {
    const element = dialog.current;
    const previous = document.activeElement as HTMLElement | null;
    element?.showModal();
    return () => { element?.close(); previous?.focus(); };
  }, []);

  useEffect(() => {
    const sequence = ++request.current;
    setTrail(null); setError("");
    api<EvidenceTrailData>(path).then(result => { if (request.current === sequence) setTrail(result); })
      .catch(cause => { if (request.current === sequence) setError(cause instanceof Error ? cause.message : "Could not load this evidence trail."); });
    return () => { request.current++; };
  }, [path, retry, data.source.loaded_at]);

  async function findPassages() {
    const sequence = ++request.current;
    setBusy(true); setError("");
    try {
      const result = await api<EvidenceTrailData>(`${path}&include_passages=true`);
      if (request.current === sequence) setTrail(result);
    } catch (cause) {
      if (request.current === sequence) setError(cause instanceof Error ? cause.message : "Could not find passages. Your numerical evidence remains available.");
    } finally { if (request.current === sequence) setBusy(false); }
  }
  return <dialog className="evidence-dialog" ref={dialog} aria-labelledby="evidence-title" onCancel={event => { event.preventDefault(); onClose(); }}>
    <div className="evidence-dialog-header"><div><span className="eyebrow">{data.company.ticker} · {anomaly.severity} movement</span><h2 id="evidence-title">From anomaly to evidence.</h2><p>{anomaly.label} · Period ended in {anomaly.period}</p></div>
      <button className="icon-button" autoFocus onClick={onClose} aria-label="Close evidence trail"><X size={22}/></button></div>
    {!trail && !error && <p role="status">Loading source values and calculation inputs…</p>}
    {error && <><Notice tone="error">{error}</Notice>{!trail && <button className="button button-outline" onClick={() => setRetry(value => value + 1)}>Retry evidence</button>}</>}
    {trail && <>
      <section className="evidence-section"><div className="evidence-heading"><div><span className="eyebrow">01 · What changed</span><h3>Start with the numbers.</h3></div><span className="evidence-screen">{trail.method}</span></div>
        <Movement movement={trail.movement} primary/>
        <details className="evidence-limitations"><summary>Comparison limits</summary>{trail.notices.map(notice => <p key={notice}>{notice}</p>)}</details>
        {trail.period - trail.prior_period !== 1 && <Notice tone="warning">This comparison spans {trail.prior_period} to {trail.period}; it is not a consecutive-year change.</Notice>}
      </section>
      <section className="evidence-section"><span className="eyebrow">02 · Related observations</span><h3>Follow the accounting context.</h3>
        <p>These movements use the same comparison years. Their relationship to the selected change still needs investigation.</p>
        <div className="evidence-related">{trail.related.map(item => <Movement key={item.id} movement={item}/>)}</div>
        {!trail.related.length && <Notice>No related mapped metrics are available for these comparison years.</Notice>}
      </section>
      <section className="evidence-section"><div className="evidence-heading"><div><span className="eyebrow">03 · Filing evidence</span><h3>Read before explaining.</h3></div>
        <button className="button button-outline" disabled={busy} onClick={findPassages}><BookOpen size={15}/>{busy ? "Reading filings…" : trail.passage_status === "not_requested" ? "Find filing passages" : "Find passages again"}</button></div>
        <p>Search the annual filings tied to these source facts. Results are research leads ranked by matching words; they have not been verified as explanations. Figures reported in later filings may include revisions.</p>
        {busy && <p role="status">Reading the matching SEC documents. Your notes remain available below.</p>}
        {trail.passage_issues.map(issue => <Notice key={issue} tone="warning">{issue}</Notice>)}
        {trail.passage_status === "no_matches" && <Notice>No matching passages were found. This does not establish that the filing omits an explanation.</Notice>}
        {trail.filings.length > 0 && <p className="evidence-file-list">Documents searched: {trail.filings.map((filing, index) => <span key={filing.accession_number}>{index > 0 ? " · " : ""}<External href={filing.source_url}>{filing.form} filed {date(filing.filing_date)} (report ended {date(filing.report_date)})</External></span>)}</p>}
        <div className="evidence-passages">{trail.passages.map((passage, index) => <article key={passage.id} className="evidence-passage"><span className="eyebrow">Passage {index + 1} · Research lead</span><h4>{passage.section}</h4>
          <p className="evidence-passage-date">{passage.form} filed {date(passage.filed)} · {passage.accession}</p><blockquote>{passage.text}</blockquote><External href={passage.url}>Read the SEC filing</External></article>)}</div>
      </section>
      <ReviewNotebook key={trail.id} trail={trail}/>
    </>}
  </dialog>;
}
