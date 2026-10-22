import { useLayoutEffect, useRef, useState } from "react";
import type { MetricRow, MetricValue } from "./types";

type Unit = "usd" | "percent" | "multiple";
type Series = Pick<MetricRow, "id" | "label" | "values">;

const colors = ["#176f93", "#c05348", "#3d8c64", "#a4662f", "#805ca1"];
const width = 600;
const height = 270;
const plot = { left: 70, right: 22, top: 20, bottom: 42 };

export function metricUnit(row: MetricRow): Unit {
  if (!row.ratio) return "usd";
  return row.id === "current_ratio" || row.id === "debt_to_equity" ? "multiple" : "percent";
}

function scaled(value: number, unit: Unit) {
  return unit === "percent" ? value * 100 : value;
}

function axisValue(value: number, unit: Unit) {
  if (unit === "usd") {
    return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 }).format(value);
  }
  return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(value)}${unit === "percent" ? "%" : "x"}`;
}

function lineSegments(values: MetricValue[], years: number[], x: (year: number) => number, y: (value: number) => number) {
  const segments: string[] = [];
  let segment: string[] = [];
  for (const year of years) {
    const value = values.find(item => item.year === year)?.value;
    if (value === null || value === undefined || !Number.isFinite(value)) {
      if (segment.length > 1) segments.push(segment.join(" "));
      segment = [];
    } else {
      segment.push(`${x(year)},${y(value)}`);
    }
  }
  if (segment.length > 1) segments.push(segment.join(" "));
  return segments;
}

export function FinancialChart({ series, unit, label }: { series: Series[]; unit: Unit; label: string }) {
  const [hoveredYear, setHoveredYear] = useState<number | null>(null);
  const [focusedYear, setFocusedYear] = useState<number | null>(null);
  const [tooltipPlacement, setTooltipPlacement] = useState<{ year: number; left: number; top: number } | null>(null);
  const chartRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const years = [...new Set(series.flatMap(row => row.values.map(item => item.year)))].sort((a, b) => a - b);
  const numbers = series.flatMap(row => row.values.map(item => item.value)).filter((value): value is number => value !== null && Number.isFinite(value)).map(value => scaled(value, unit));

  const low = Math.min(0, ...numbers);
  const high = Math.max(0, ...numbers);
  const range = high - low || 1;
  const padding = range * 0.08;
  const min = low === 0 ? 0 : low - padding;
  const max = high === 0 ? 0 : high + padding;
  const innerWidth = width - plot.left - plot.right;
  const innerHeight = height - plot.top - plot.bottom;
  const x = (year: number) => plot.left + (years.length === 1 ? innerWidth / 2 : years.indexOf(year) * innerWidth / (years.length - 1));
  const y = (value: number) => plot.top + (max - scaled(value, unit)) * innerHeight / (max - min);
  const activeYear = hoveredYear ?? focusedYear;
  const selectedYear = activeYear !== null && years.includes(activeYear) ? activeYear : null;

  useLayoutEffect(() => {
    if (selectedYear === null) return;
    const chart = chartRef.current;
    const svg = svgRef.current;
    const tooltip = tooltipRef.current;
    if (!chart || !svg || !tooltip) return;

    function placeTooltip() {
      if (!chart || !svg || !tooltip) return;
      const matrix = svg.getScreenCTM();
      if (!matrix) return;
      const chartBounds = chart.getBoundingClientRect();
      const tooltipBounds = tooltip.getBoundingClientRect();
      const screenPoint = (pointX: number, pointY: number) => {
        const point = svg.createSVGPoint();
        point.x = pointX;
        point.y = pointY;
        const transformed = point.matrixTransform(matrix);
        return { x: transformed.x - chartBounds.left, y: transformed.y - chartBounds.top };
      };
      const pointX = screenPoint(x(selectedYear!), 0).x;
      const pointYs = series.flatMap(row => row.values
        .filter(item => item.year === selectedYear && item.value !== null && Number.isFinite(item.value))
        .map(item => screenPoint(0, y(item.value!)).y));
      const topDot = pointYs.length ? Math.min(...pointYs) : screenPoint(0, plot.top).y;
      const bottomDot = pointYs.length ? Math.max(...pointYs) : topDot;
      const plotTop = screenPoint(0, plot.top).y;
      const plotBottom = screenPoint(0, height - plot.bottom).y;
      const gap = 14;
      const tipWidth = tooltipBounds.width;
      const tipHeight = tooltipBounds.height;
      const clamp = (value: number, lower: number, upper: number) => Math.max(lower, Math.min(value, upper));
      let left = clamp(pointX - tipWidth / 2, 4, Math.max(4, chartBounds.width - tipWidth - 4));
      let top: number;
      if (bottomDot + gap + tipHeight <= plotBottom) {
        top = bottomDot + gap;
      } else if (topDot - gap - tipHeight >= plotTop) {
        top = topDot - gap - tipHeight;
      } else if (pointX + gap + tipWidth <= chartBounds.width - 4) {
        left = pointX + gap;
        top = clamp((topDot + bottomDot - tipHeight) / 2, plotTop, Math.max(plotTop, plotBottom - tipHeight));
      } else if (pointX - gap - tipWidth >= 4) {
        left = pointX - gap - tipWidth;
        top = clamp((topDot + bottomDot - tipHeight) / 2, plotTop, Math.max(plotTop, plotBottom - tipHeight));
      } else {
        // A narrow chart may have no side room; keep the box beyond the last dot.
        top = bottomDot + gap;
      }
      setTooltipPlacement(previous => previous?.year === selectedYear && previous.left === left && previous.top === top
        ? previous : { year: selectedYear!, left, top });
    }

    placeTooltip();
    const observer = new ResizeObserver(placeTooltip);
    observer.observe(chart);
    observer.observe(tooltip);
    return () => observer.disconnect();
  }, [selectedYear, series, unit, min, max]);

  if (!numbers.length) return <div className="empty-chart">No reported values are available for this chart.</div>;

  return <div className="financial-chart" ref={chartRef} onMouseLeave={() => setHoveredYear(null)}>
    <svg ref={svgRef} viewBox={`0 0 ${width} ${height}`} aria-label={`${label}: annual ${unit === "usd" ? "USD" : unit === "percent" ? "percentage" : "multiple"} values. Hover over a dot or focus a year to inspect values.`}>
      {Array.from({ length: 5 }, (_, index) => {
        const tick = min + (max - min) * (4 - index) / 4;
        const position = plot.top + index * innerHeight / 4;
        return <g key={index}><line className="financial-gridline" x1={plot.left} x2={width - plot.right} y1={position} y2={position}/><text className="financial-y-label" x={plot.left - 12} y={position + 4} textAnchor="end">{axisValue(tick, unit)}</text></g>;
      })}
      {selectedYear !== null && <line className="financial-guide" x1={x(selectedYear)} x2={x(selectedYear)} y1={plot.top} y2={height - plot.bottom}/>}
      {series.map((row, index) => <g key={row.id}>
        {lineSegments(row.values, years, x, y).map((points, part) => <polyline key={part} points={points} fill="none" stroke={colors[index % colors.length]} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>)}
        {row.values.filter(item => item.value !== null && Number.isFinite(item.value)).map(item => <circle key={item.year} cx={x(item.year)} cy={y(item.value!)} r={selectedYear === item.year ? 6 : 4.5} fill="#fff" stroke={colors[index % colors.length]} strokeWidth="2.8" onMouseEnter={() => setHoveredYear(item.year)} onMouseLeave={() => setHoveredYear(null)}/>)}
      </g>)}
      {years.map((year, index) => {
        const leftEdge = index === 0 ? plot.left - 15 : (x(years[index - 1]) + x(year)) / 2;
        const rightEdge = index === years.length - 1 ? width - plot.right : (x(year) + x(years[index + 1])) / 2;
        return <g key={year}>
          <text className="financial-x-label" x={x(year)} y={height - 12} textAnchor="middle">FY{year}</text>
          <rect x={leftEdge} y={plot.top} width={rightEdge - leftEdge} height={innerHeight} fill="transparent" pointerEvents="none" tabIndex={0} role="button" aria-label={`FY${year}; ${series.map(row => `${row.label}: ${row.values.find(item => item.year === year)?.display || "unavailable"}`).join("; ")}`} onFocus={() => setFocusedYear(year)} onBlur={() => setFocusedYear(null)} onKeyDown={event => {
            if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setFocusedYear(year); }
            if (event.key === "ArrowRight" && index < years.length - 1) { event.preventDefault(); (event.currentTarget.parentElement?.nextElementSibling?.querySelector("rect") as SVGRectElement | null)?.focus(); }
            if (event.key === "ArrowLeft" && index > 0) { event.preventDefault(); (event.currentTarget.parentElement?.previousElementSibling?.querySelector("rect") as SVGRectElement | null)?.focus(); }
          }}/>
        </g>;
      })}
    </svg>
    {selectedYear !== null && <div className="financial-tooltip" ref={tooltipRef} style={tooltipPlacement?.year === selectedYear ? { left: tooltipPlacement.left, top: tooltipPlacement.top } : { left: 0, top: 0, visibility: "hidden" }} role="status">
      <strong>FY{selectedYear}</strong>
      {series.map((row, index) => <div key={row.id}><span className="chart-key" style={{ backgroundColor: colors[index % colors.length] }}/><span>{row.label}</span><b>{row.values.find(item => item.year === selectedYear)?.display || "—"}</b></div>)}
    </div>}
    {series.length > 1 && <div className="financial-legend">{series.map((row, index) => <span key={row.id}><i style={{ backgroundColor: colors[index % colors.length] }}/>{row.label}</span>)}</div>}
  </div>;
}

export function ChartBuilder({ statements }: { statements: Record<string, { rows: MetricRow[] }[]> }) {
  const rows = Object.values(statements).flatMap(sections => sections.flatMap(section => section.rows));
  const [unit, setUnit] = useState<Unit>("usd");
  const [selected, setSelected] = useState<string[]>(() => {
    const defaults = ["revenue", "net_income"].filter(id => rows.some(row => row.id === id && row.values.some(item => item.value !== null)));
    return defaults.length ? defaults : rows.filter(row => metricUnit(row) === "usd" && row.values.some(item => item.value !== null)).slice(0, 2).map(row => row.id);
  });
  const available = rows.filter(row => metricUnit(row) === unit && row.values.some(item => item.value !== null));
  const selectedRows = available.filter(row => selected.includes(row.id));

  function changeUnit(next: Unit) {
    setUnit(next);
    setSelected(rows.filter(row => metricUnit(row) === next && row.values.some(item => item.value !== null)).slice(0, 2).map(row => row.id));
  }

  return <section className="surface-card chart-builder">
    <div className="card-top"><div><span className="eyebrow">Build a comparison</span><h3>Graph your financials</h3></div><span>Annual SEC history</span></div>
    <p>Choose up to five accounts. Hover over a dot or focus a year to see the values together.</p>
    <div className="chart-unit-tabs" role="group" aria-label="Chart units">{([ ["usd", "Dollar values"], ["percent", "Percentages"], ["multiple", "Multiples"] ] as const).map(([value, text]) => <button key={value} type="button" aria-pressed={unit === value} className={unit === value ? "selected" : ""} onClick={() => changeUnit(value)}>{text}</button>)}</div>
    <div className="chart-metric-list" role="group" aria-label="Metrics to graph">{available.map(row => <label key={row.id} className={selected.includes(row.id) ? "selected" : ""}><input type="checkbox" checked={selected.includes(row.id)} disabled={!selected.includes(row.id) && selectedRows.length >= 5} onChange={() => setSelected(current => current.includes(row.id) ? current.filter(id => id !== row.id) : [...current.filter(id => available.some(item => item.id === id)), row.id])}/>{row.label}</label>)}</div>
    {selectedRows.length ? <FinancialChart series={selectedRows} unit={unit} label="Custom financial comparison"/> : <div className="empty-chart">Select an account to draw a graph.</div>}
    <p className="chart-method-note">Series use their reported or calculated annual values. Dollar values, percentages, and multiples have separate scales; missing years are left blank.</p>
  </section>;
}
