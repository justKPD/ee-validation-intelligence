"use client";

/*
 * Hand-written SVG charts following the dataviz method:
 * thin marks (bars <= 24px, 4px rounded data-end, square at the baseline), 2px lines, >= 8px ringed markers,
 * a 2px surface gap between stacked segments, recessive hairline grid, text in text tokens, a legend whenever
 * there are >= 2 series, per-mark hover and focus tooltips, and a table view so no value is gated behind hover.
 */
import { useId, useMemo, useRef, useState, type ReactNode } from "react";

// ---------------------------------------------------------------------------------------------------------------
interface TipState {
  x: number;
  y: number;
  content: ReactNode;
}

function useTooltip() {
  const ref = useRef<HTMLDivElement>(null);
  const [tip, setTip] = useState<TipState | null>(null);
  const show = (evt: { clientX: number; clientY: number }, content: ReactNode) => {
    const box = ref.current?.getBoundingClientRect();
    if (!box) return;
    setTip({ x: Math.min(evt.clientX - box.left + 12, box.width - 170), y: evt.clientY - box.top + 12, content });
  };
  const showAt = (el: Element, content: ReactNode) => {
    const r = el.getBoundingClientRect();
    show({ clientX: r.left + r.width / 2, clientY: r.top }, content);
  };
  const node = tip ? (
    <div className="tooltip" role="status" style={{ left: tip.x, top: tip.y }}>
      {tip.content}
    </div>
  ) : null;
  return { ref, show, showAt, hide: () => setTip(null), node };
}

function niceMax(v: number): number {
  if (v <= 0) return 1;
  const exp = 10 ** Math.floor(Math.log10(v));
  const f = v / exp;
  const step = f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10;
  return step * exp;
}

/** Bar path with a 4px rounded data-end (right) and a square baseline (left). */
function hBarPath(x: number, y: number, w: number, h: number, r = 4): string {
  const rr = Math.min(r, w, h / 2);
  return `M${x},${y} H${x + w - rr} Q${x + w},${y} ${x + w},${y + rr} V${y + h - rr} Q${x + w},${y + h} ${x + w - rr},${y + h} H${x} Z`;
}

/** Column path with a 4px rounded top and square baseline. */
function vBarPath(x: number, y: number, w: number, h: number, r = 4): string {
  const rr = Math.min(r, h, w / 2);
  return `M${x},${y + h} V${y + rr} Q${x},${y} ${x + rr},${y} H${x + w - rr} Q${x + w},${y} ${x + w},${y + rr} V${y + h} Z`;
}

export function TableToggle({ table, children }: { table: ReactNode; children: ReactNode }) {
  const [asTable, setAsTable] = useState(false);
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "flex-end", marginTop: -30, marginBottom: 8 }}>
        <button className="view-toggle" onClick={() => setAsTable((t) => !t)} aria-pressed={asTable}>
          {asTable ? "Chart view" : "Table view"}
        </button>
      </div>
      {asTable ? <div className="table-wrap">{table}</div> : children}
    </div>
  );
}

// ---------------------------------------------------------------------------------------------------------------
export interface BarDatum {
  label: string;
  value: number;
  detail?: ReactNode;
}

/** Horizontal bars, single series (no legend: the card title names it). */
export function HorizontalBarChart({
  data,
  format = (v) => v.toFixed(2),
  color = "var(--series-1)",
  max,
  onSelect,
  selected,
}: {
  data: BarDatum[];
  format?: (v: number) => string;
  color?: string;
  max?: number;
  onSelect?: (label: string) => void;
  selected?: string | null;
}) {
  const tt = useTooltip();
  const labelW = 150;
  const valueW = 52;
  const width = 640;
  const rowH = 26;
  const barH = 16;
  const plotW = width - labelW - valueW;
  const top = 18;
  const height = top + data.length * rowH + 4;
  const vmax = max ?? niceMax(Math.max(0, ...data.map((d) => d.value)));
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * vmax);
  const table = (
    <table>
      <thead>
        <tr><th>Label</th><th className="num">Value</th></tr>
      </thead>
      <tbody>
        {data.map((d) => (
          <tr key={d.label}><td>{d.label}</td><td className="num">{format(d.value)}</td></tr>
        ))}
      </tbody>
    </table>
  );
  return (
    <TableToggle table={table}>
      <div className="chart" ref={tt.ref} onPointerLeave={tt.hide}>
        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Horizontal bar chart">
          {ticks.map((t) => {
            const x = labelW + (t / vmax) * plotW;
            return (
              <g key={t}>
                <line x1={x} x2={x} y1={top - 4} y2={height} stroke="var(--grid)" strokeWidth={1} />
                <text className="tick" x={x} y={10} textAnchor="middle">{format(t)}</text>
              </g>
            );
          })}
          <line x1={labelW} x2={labelW} y1={top - 4} y2={height} stroke="var(--axis)" strokeWidth={1} />
          {data.map((d, i) => {
            const y = top + i * rowH + (rowH - barH) / 2;
            const w = Math.max(0, (d.value / vmax) * plotW);
            const dim = selected && selected !== d.label;
            const tip = (
              <>
                <div className="tt-title">{d.label}</div>
                <div className="tt-row"><strong>{format(d.value)}</strong></div>
                {d.detail}
              </>
            );
            return (
              <g key={d.label}>
                <text className="label" x={labelW - 8} y={y + barH / 2 + 4} textAnchor="end">{d.label}</text>
                <path className={`mark${dim ? " dim" : ""}`} d={hBarPath(labelW, y, w, barH)} fill={color} />
                <text className="value" x={labelW + w + 6} y={y + barH / 2 + 4}>{format(d.value)}</text>
                <rect
                  className="hit"
                  x={0}
                  y={top + i * rowH}
                  width={width}
                  height={rowH}
                  tabIndex={0}
                  role={onSelect ? "button" : undefined}
                  aria-label={`${d.label}: ${format(d.value)}`}
                  onPointerMove={(e) => tt.show(e, tip)}
                  onFocus={(e) => tt.showAt(e.currentTarget, tip)}
                  onBlur={tt.hide}
                  onClick={() => onSelect?.(d.label)}
                  onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onSelect?.(d.label)}
                  style={{ cursor: onSelect ? "pointer" : "default" }}
                />
              </g>
            );
          })}
        </svg>
        {tt.node}
      </div>
    </TableToggle>
  );
}

// ---------------------------------------------------------------------------------------------------------------
export interface StackSegment {
  key: string;
  label: string;
  color: string;
}

/** One horizontal stacked bar per row; 2px surface gap between segments; legend always shown. */
export function StackedBarChart({
  rows,
  segments,
  format = (v) => v.toLocaleString("en-GB"),
}: {
  rows: { label: string; values: Record<string, number> }[];
  segments: StackSegment[];
  format?: (v: number) => string;
}) {
  const tt = useTooltip();
  const labelW = 150;
  const width = 640;
  const plotW = width - labelW - 56;
  const rowH = rows.length === 1 ? 40 : 26;
  const barH = rows.length === 1 ? 24 : 16;
  const height = rows.length * rowH + 4;
  const totals = rows.map((r) => segments.reduce((s, seg) => s + (r.values[seg.key] ?? 0), 0));
  const vmax = Math.max(1, ...totals);
  const table = (
    <table>
      <thead>
        <tr><th>Row</th>{segments.map((s) => <th key={s.key} className="num">{s.label}</th>)}<th className="num">Total</th></tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={r.label}>
            <td>{r.label}</td>
            {segments.map((s) => <td key={s.key} className="num">{format(r.values[s.key] ?? 0)}</td>)}
            <td className="num">{format(totals[i])}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
  return (
    <TableToggle table={table}>
      <div className="legend">
        {segments.map((s) => (
          <span key={s.key}><span className="swatch" style={{ background: s.color }} />{s.label}</span>
        ))}
      </div>
      <div className="chart" ref={tt.ref} onPointerLeave={tt.hide}>
        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Stacked bar chart">
          {rows.map((r, i) => {
            const y = i * rowH + (rowH - barH) / 2;
            let x = labelW;
            const visible = segments.filter((s) => (r.values[s.key] ?? 0) > 0);
            return (
              <g key={r.label}>
                <text className="label" x={labelW - 8} y={y + barH / 2 + 4} textAnchor="end">{r.label}</text>
                {visible.map((s, j) => {
                  const v = r.values[s.key] ?? 0;
                  const full = (v / vmax) * plotW;
                  const gap = j < visible.length - 1 ? 2 : 0;
                  const w = Math.max(0.5, full - gap);
                  const isLast = j === visible.length - 1;
                  const seg = isLast ? (
                    <path key={s.key} d={hBarPath(x, y, w, barH)} fill={s.color} />
                  ) : (
                    <rect key={s.key} x={x} y={y} width={w} height={barH} fill={s.color} />
                  );
                  const tip = (
                    <>
                      <div className="tt-title">{r.label}</div>
                      <div className="tt-row"><span><span className="tt-key" style={{ background: s.color }} />{s.label}</span><strong>{format(v)}</strong></div>
                      <div className="tt-row muted"><span>Share</span><span>{((v / totals[i]) * 100).toFixed(1)}%</span></div>
                    </>
                  );
                  const hit = (
                    <rect
                      key={`${s.key}-hit`}
                      className="hit"
                      x={x}
                      y={y - 5}
                      width={full}
                      height={barH + 10}
                      tabIndex={0}
                      aria-label={`${r.label} ${s.label}: ${format(v)}`}
                      onPointerMove={(e) => tt.show(e, tip)}
                      onFocus={(e) => tt.showAt(e.currentTarget, tip)}
                      onBlur={tt.hide}
                    />
                  );
                  x += full;
                  return [seg, hit];
                })}
                <text className="value" x={labelW + (totals[i] / vmax) * plotW + 6} y={y + barH / 2 + 4}>{format(totals[i])}</text>
              </g>
            );
          })}
        </svg>
        {tt.node}
      </div>
    </TableToggle>
  );
}

// ---------------------------------------------------------------------------------------------------------------
/** Vertical columns, single series. */
export function ColumnChart({ data, color = "var(--series-1)", format = (v) => String(v) }: { data: BarDatum[]; color?: string; format?: (v: number) => string }) {
  const tt = useTooltip();
  const width = 640;
  const height = 220;
  const left = 34;
  const bottom = 58;
  const top = 16;
  const plotH = height - top - bottom;
  const band = (width - left) / Math.max(data.length, 1);
  const barW = Math.min(24, band * 0.6);
  const vmax = niceMax(Math.max(0, ...data.map((d) => d.value)));
  const ticks = [0, 0.5, 1].map((f) => f * vmax);
  const table = (
    <table>
      <thead><tr><th>Label</th><th className="num">Value</th></tr></thead>
      <tbody>{data.map((d) => <tr key={d.label}><td>{d.label}</td><td className="num">{format(d.value)}</td></tr>)}</tbody>
    </table>
  );
  return (
    <TableToggle table={table}>
      <div className="chart" ref={tt.ref} onPointerLeave={tt.hide}>
        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Column chart">
          {ticks.map((t) => {
            const y = top + plotH - (t / vmax) * plotH;
            return (
              <g key={t}>
                <line x1={left} x2={width} y1={y} y2={y} stroke={t === 0 ? "var(--axis)" : "var(--grid)"} strokeWidth={1} />
                <text className="tick" x={left - 6} y={y + 4} textAnchor="end">{format(t)}</text>
              </g>
            );
          })}
          {data.map((d, i) => {
            const cx = left + band * i + band / 2;
            const h = (d.value / vmax) * plotH;
            const tip = (<><div className="tt-title">{d.label}</div><div className="tt-row"><strong>{format(d.value)}</strong></div>{d.detail}</>);
            return (
              <g key={d.label}>
                <path className="mark" d={vBarPath(cx - barW / 2, top + plotH - h, barW, h)} fill={color} />
                <text className="label" transform={`translate(${cx},${top + plotH + 10}) rotate(40)`} fontSize={10.5}>{d.label}</text>
                <rect className="hit" x={cx - band / 2} y={top} width={band} height={plotH} tabIndex={0} aria-label={`${d.label}: ${format(d.value)}`}
                  onPointerMove={(e) => tt.show(e, tip)} onFocus={(e) => tt.showAt(e.currentTarget, tip)} onBlur={tt.hide} />
              </g>
            );
          })}
        </svg>
        {tt.node}
      </div>
    </TableToggle>
  );
}

// ---------------------------------------------------------------------------------------------------------------
export interface LineSeries {
  key: string;
  label: string;
  color: string;
  points: { x: number; y: number; note?: string }[];
}

/** Multi-series line chart with a crosshair that snaps to the nearest x of each series. */
export function LineChart({
  series,
  xLabel,
  yLabel,
  formatX = (v) => v.toLocaleString("en-GB"),
  formatY = (v) => `${(v * 100).toFixed(0)}%`,
  yMax = 1,
}: {
  series: LineSeries[];
  xLabel: string;
  yLabel: string;
  formatX?: (v: number) => string;
  formatY?: (v: number) => string;
  yMax?: number;
}) {
  const tt = useTooltip();
  const clip = useId();
  const [hoverX, setHoverX] = useState<number | null>(null);
  const width = 640;
  const height = 280;
  const left = 44;
  const right = 16;
  const top = 12;
  const bottom = 40;
  const plotW = width - left - right;
  const plotH = height - top - bottom;
  const allX = series.flatMap((s) => s.points.map((p) => p.x));
  const xmax = niceMax(Math.max(1, ...allX));
  const sx = (x: number) => left + (x / xmax) * plotW;
  const sy = (y: number) => top + plotH - (y / yMax) * plotH;
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * yMax);
  const xTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * xmax);

  const readout = useMemo(() => {
    if (hoverX === null) return null;
    return series.map((s) => {
      const nearest = s.points.reduce((a, b) => (Math.abs(b.x - hoverX) < Math.abs(a.x - hoverX) ? b : a), s.points[0]);
      return { s, p: nearest };
    });
  }, [hoverX, series]);

  const table = (
    <table>
      <thead><tr><th>Series</th><th className="num">{xLabel}</th><th className="num">{yLabel}</th><th>Point</th></tr></thead>
      <tbody>
        {series.flatMap((s) => s.points.map((p) => (
          <tr key={`${s.key}-${p.x}-${p.note}`}><td>{s.label}</td><td className="num">{formatX(p.x)}</td><td className="num">{formatY(p.y)}</td><td>{p.note}</td></tr>
        )))}
      </tbody>
    </table>
  );

  const onMove = (e: React.PointerEvent<SVGRectElement>) => {
    const svg = e.currentTarget.ownerSVGElement;
    if (!svg) return;
    const box = svg.getBoundingClientRect();
    const px = ((e.clientX - box.left) / box.width) * width;
    const xv = Math.max(0, Math.min(xmax, ((px - left) / plotW) * xmax));
    setHoverX(xv);
    tt.show(e, (
      <>
        <div className="tt-title">{xLabel} ≈ {formatX(xv)}</div>
        {series.map((s) => {
          const p = s.points.reduce((a, b) => (Math.abs(b.x - xv) < Math.abs(a.x - xv) ? b : a), s.points[0]);
          return (
            <div className="tt-row" key={s.key}>
              <span><span className="tt-key" style={{ background: s.color }} />{s.label}</span>
              <strong>{formatY(p.y)}</strong>
            </div>
          );
        })}
      </>
    ));
  };

  return (
    <TableToggle table={table}>
      <div className="legend">
        {series.map((s) => (<span key={s.key}><span className="line-key" style={{ background: s.color }} />{s.label}</span>))}
      </div>
      <div className="chart" ref={tt.ref} onPointerLeave={() => { tt.hide(); setHoverX(null); }}>
        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${yLabel} versus ${xLabel}`}>
          <defs><clipPath id={clip}><rect x={left} y={top - 6} width={plotW + 8} height={plotH + 12} /></clipPath></defs>
          {yTicks.map((t) => (
            <g key={`y${t}`}>
              <line x1={left} x2={width - right} y1={sy(t)} y2={sy(t)} stroke={t === 0 ? "var(--axis)" : "var(--grid)"} strokeWidth={1} />
              <text className="tick" x={left - 6} y={sy(t) + 4} textAnchor="end">{formatY(t)}</text>
            </g>
          ))}
          {xTicks.map((t) => (
            <text key={`x${t}`} className="tick" x={sx(t)} y={top + plotH + 16} textAnchor="middle">{formatX(t)}</text>
          ))}
          <text className="label" x={left + plotW / 2} y={height - 4} textAnchor="middle">{xLabel}</text>
          <g clipPath={`url(#${clip})`}>
            {series.map((s) => (
              <polyline key={s.key} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round"
                points={s.points.map((p) => `${sx(p.x)},${sy(p.y)}`).join(" ")} />
            ))}
            {series.map((s) =>
              s.points.map((p) => (
                <circle key={`${s.key}-${p.x}`} cx={sx(p.x)} cy={sy(p.y)} r={4} fill={s.color} stroke="var(--surface-1)" strokeWidth={2} />
              )),
            )}
          </g>
          {hoverX !== null && <line x1={sx(hoverX)} x2={sx(hoverX)} y1={top} y2={top + plotH} stroke="var(--axis)" strokeWidth={1} />}
          {readout?.map(({ s, p }) => (
            <circle key={`h-${s.key}`} cx={sx(p.x)} cy={sy(p.y)} r={5.5} fill={s.color} stroke="var(--surface-1)" strokeWidth={2} />
          ))}
          <rect className="hit" x={left} y={top} width={plotW} height={plotH} onPointerMove={onMove} />
        </svg>
        {tt.node}
      </div>
    </TableToggle>
  );
}

// ---------------------------------------------------------------------------------------------------------------
export function StatTile({ label, value, note }: { label: string; value: ReactNode; note?: ReactNode }) {
  return (
    <div className="card tile">
      <div className="tile-label">{label}</div>
      <div className="tile-value">{value}</div>
      {note && <div className="tile-note">{note}</div>}
    </div>
  );
}

/** Stacked decomposition of a weighted score, used to explain risk and priority. */
export function Decomposition({ parts, total }: { parts: Record<string, number>; total: number }) {
  const colors = ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)", "var(--seq-500)", "var(--status-neutral)"];
  const entries = Object.entries(parts);
  const rows = entries.map(([k, v], i) => ({ label: k.replace(/_/g, " "), value: v, color: colors[i % colors.length] }));
  return (
    <div>
      <div className="legend">
        {rows.map((r) => (<span key={r.label}><span className="swatch" style={{ background: r.color }} />{r.label}</span>))}
      </div>
      <table>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label}>
              <td style={{ width: "40%" }}><span className="swatch" style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: r.color, marginRight: 6 }} />{r.label}</td>
              <td>
                <svg viewBox="0 0 200 12" width="100%" height={12} aria-hidden>
                  <rect x={0} y={2} width={200} height={8} rx={4} fill="var(--surface-2)" />
                  <path d={hBarPath(0, 2, Math.max(0.5, (r.value / Math.max(total, 1e-9)) * 200), 8)} fill={r.color} />
                </svg>
              </td>
              <td className="num">{r.value.toFixed(3)}</td>
            </tr>
          ))}
          <tr><td><strong>Total</strong></td><td /><td className="num"><strong>{total.toFixed(3)}</strong></td></tr>
        </tbody>
      </table>
    </div>
  );
}
