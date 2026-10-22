import { ArrowUpRight, ChevronDown, ChevronRight, Database, ExternalLink as ExternalIcon } from "lucide-react";
import { openUrl } from "@tauri-apps/plugin-opener";
import { useState } from "react";
import type { MetricRow, MetricValue } from "./types";
import { FinancialChart, metricUnit } from "./FinancialChart";

export function External({ href, children, className = "" }: { href: string; children: React.ReactNode; className?: string }) {
  let safe = false;
  try {
    const url = new URL(href);
    safe = url.protocol === "https:" && !url.username && !url.password && !url.port && !url.hash &&
      ((url.hostname === "www.sec.gov" && url.pathname.startsWith("/Archives/")) ||
       (url.hostname === "data.sec.gov" && (url.pathname.startsWith("/api/xbrl/") || url.pathname.startsWith("/submissions/"))));
  } catch { /* Invalid links remain plain text. */ }
  async function open(event: React.MouseEvent<HTMLAnchorElement>) {
    if (!safe) { event.preventDefault(); return; }
    if ("__TAURI_INTERNALS__" in window) {
      event.preventDefault();
      await openUrl(href);
    }
  }
  if (!safe) return <span className={className}>{children}</span>;
  return <a href={href} target="_blank" rel="noopener noreferrer" className={className} onClick={open}>{children}<ExternalIcon size={13} aria-hidden="true" /></a>;
}

export function Sparkline({ values }: { values: MetricValue[] }) {
  const available = values.filter((item): item is MetricValue & { value: number } => item.value !== null && Number.isFinite(item.value));
  if (available.length < 2) return <span className="muted">—</span>;
  const min = Math.min(...available.map(item => item.value));
  const spread = Math.max(...available.map(item => item.value)) - min || 1;
  const points = values.map((item, index) => item.value === null ? null : {
    item, x: 6 + index / (values.length - 1) * 84, y: 5 + (1 - (item.value - min) / spread) * 20,
  });
  const segments: string[] = [];
  let segment: string[] = [];
  for (const point of points) {
    if (point) segment.push(`${point.x},${point.y}`);
    else { if (segment.length > 1) segments.push(segment.join(" ")); segment = []; }
  }
  if (segment.length > 1) segments.push(segment.join(" "));
  return <svg className="sparkline" viewBox="0 0 96 30" role="img" aria-label="Annual trend sparkline; open row for an interactive chart">{segments.map((coordinates, index) => <polyline key={index} points={coordinates} fill="none" stroke="currentColor" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round" />)}{points.filter(point => point !== null).map(point => <circle key={point.item.year} cx={point.x} cy={point.y} r="3.2" fill="#fff" stroke="currentColor" strokeWidth="1.6"><title>{`FY${point.item.year}: ${point.item.display}`}</title></circle>)}</svg>;
}

export function TrendChart({ row }: { row: MetricRow }) {
  const { values, label } = row;
  const available = values.filter(item => item.value !== null);
  if (!available.length) return <div className="empty-chart">No reported values are available for this trend.</div>;
  return <FinancialChart series={[row]} unit={metricUnit(row)} label={label}/>;
}

export function StatementTable({ title, rows }: { title: string; rows: MetricRow[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const years = rows[0]?.values.map(item => item.year) || [];
  return <section className="statement-section">
    <div className="statement-heading"><h3>{title}</h3><span>{rows.length} accounts</span></div>
    <div className="table-scroll"><table className="statement-table"><thead><tr><th>Account</th><th>Trend</th>{years.map(year => <th key={year}>FY{year}</th>)}<th>Latest change</th></tr></thead><tbody>{rows.map(row => <tr key={row.id} className={expanded === row.id ? "is-expanded" : ""}>
      <td colSpan={years.length + 3} className="statement-cell"><button className="statement-row" style={{ "--years": years.length } as React.CSSProperties} onClick={() => setExpanded(expanded === row.id ? null : row.id)} aria-expanded={expanded === row.id}>
        <span className="account-name">{expanded === row.id ? <ChevronDown size={16}/> : <ChevronRight size={16}/>} {row.label}</span>
        <span className="trend-cell">{row.featured ? <Sparkline values={row.values}/> : <span className="trend-dash">—</span>}</span>
        {row.values.map(item => <span className="value-cell" key={item.year}>{item.display}</span>)}
        <span className="change-cell">{row.latest_change}</span>
      </button>{expanded === row.id && <div className="metric-detail">
        <div className="detail-chart"><div className="eyebrow">Annual series · hover a dot or focus a year</div><TrendChart row={row}/></div>
        <div className="detail-notes"><div className="eyebrow">Understand this account</div>
          {row.formula && <p><strong>Formula:</strong> {row.formula}</p>}
          {row.components.length ? <><p className="small-title">Latest-year composition</p>{row.components.map((component, index) => <div className="component-line" key={index}>{Object.values(component).map((value, part) => <span key={part}>{value}</span>)}</div>)}</> : <p className="muted">No reliable lower-level breakdown is available. The reported total is not estimated.</p>}
          {row.provenance ? <p className="source-note"><Database size={14}/> SEC XBRL: {row.provenance.concept} · filed {row.provenance.filing_date}</p> : <p className="source-note"><Database size={14}/> Calculated from normalized SEC XBRL values.</p>}
        </div>
      </div>}</td>
    </tr>)}</tbody></table></div>
  </section>;
}

export function SectionHeader({ eyebrow, title, description, aside }: { eyebrow: string; title: string; description: string; aside?: React.ReactNode }) {
  return <div className="section-header"><div><div className="eyebrow">{eyebrow}</div><h2 tabIndex={-1}>{title}</h2><p>{description}</p></div>{aside}</div>;
}

export function FactCard({ label, value, note, icon }: { label: string; value: string | number; note?: string | null; icon?: React.ReactNode }) {
  return <div className="fact-card"><div className="fact-label">{label}{icon}</div><div className="fact-value">{value}</div>{note && <div className="fact-note"><ArrowUpRight size={14}/>{note}</div>}</div>;
}

export function Notice({ children, tone = "info" }: { children: React.ReactNode; tone?: "info" | "warning" | "error" }) {
  return <div className={`notice notice-${tone}`}>{children}</div>;
}
