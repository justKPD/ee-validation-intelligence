"use client";

import type { ReactNode } from "react";
import type { Build, EvidenceStatus, Variant } from "@/lib/api";
import { useApi } from "@/lib/useApi";

export const EVIDENCE_COLORS: Record<EvidenceStatus, string> = {
  CURRENT: "var(--status-good)",
  STALE: "var(--status-warning)",
  INCOMPATIBLE: "var(--status-serious)",
  FAILED: "var(--status-critical)",
  MISSING: "var(--status-neutral)",
};

const STATUS_ICON: Record<string, string> = {
  CURRENT: "✓", STALE: "◷", INCOMPATIBLE: "≠", FAILED: "✕", MISSING: "∅",
  OPEN: "●", RESOLVED: "✓", PROPOSED: "…", APPROVED: "✓", REJECTED: "✕", EXECUTED: "▶",
  COMPLETED: "✓", ANSWERED: "✓", NEEDS_CLARIFICATION: "?", REFUSED: "⛔", FAILED_RUN: "✕",
  VALID: "✓", NOT_VALID: "✕", NO_EVIDENCE: "∅", NOT_APPLICABLE: "–", PASS: "✓", FAIL: "✕", BLOCKED: "■",
  ALLOWED: "✓", POLICY_DENIED: "⛔",
};
const STATUS_COLOR: Record<string, string> = {
  ...EVIDENCE_COLORS,
  OPEN: "var(--status-critical)", RESOLVED: "var(--status-good)",
  PROPOSED: "var(--status-warning)", APPROVED: "var(--status-good)", REJECTED: "var(--status-critical)", EXECUTED: "var(--series-1)",
  COMPLETED: "var(--status-good)", ANSWERED: "var(--status-good)", NEEDS_CLARIFICATION: "var(--status-warning)", REFUSED: "var(--status-serious)",
  VALID: "var(--status-good)", NOT_VALID: "var(--status-critical)", NO_EVIDENCE: "var(--status-neutral)", NOT_APPLICABLE: "var(--status-neutral)",
  PASS: "var(--status-good)", FAIL: "var(--status-critical)", BLOCKED: "var(--status-neutral)",
  ALLOWED: "var(--status-good)", POLICY_DENIED: "var(--status-critical)",
};

/** Status is never color-alone: dot + icon + text label. */
export function StatusBadge({ status }: { status: string }) {
  return (
    <span className="badge">
      <span className="dot" style={{ background: STATUS_COLOR[status] ?? "var(--status-neutral)" }} />
      <span aria-hidden>{STATUS_ICON[status] ?? ""}</span>
      {status.replace(/_/g, " ")}
    </span>
  );
}

export function PageHeader({ title, subtitle, children }: { title: string; subtitle?: ReactNode; children?: ReactNode }) {
  return (
    <div className="page-header">
      <div>
        <h2>{title}</h2>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

export function Card({ title, subtitle, children, style }: { title?: string; subtitle?: ReactNode; children: ReactNode; style?: React.CSSProperties }) {
  return (
    <section className="card" style={style}>
      {title && <h3>{title}</h3>}
      {subtitle && <p className="card-sub">{subtitle}</p>}
      {children}
    </section>
  );
}

export function Loading({ what = "data" }: { what?: string }) {
  return <p className="muted">Loading {what}…</p>;
}

export function ErrorBox({ error }: { error: string }) {
  return (
    <div className="error" role="alert">
      <strong>Could not load data.</strong> {error}. Is the API running (<code>uv run ee-api</code>)?
    </div>
  );
}

export function BuildVariantFilters({
  build,
  setBuild,
  variant,
  setVariant,
  allowAllVariants = true,
  children,
}: {
  build: string | null;
  setBuild: (b: string) => void;
  variant?: string;
  setVariant?: (v: string) => void;
  allowAllVariants?: boolean;
  children?: ReactNode;
}) {
  const builds = useApi<Build[]>("/builds");
  const variants = useApi<Variant[]>(setVariant ? "/variants" : null);
  if (builds.error) return <ErrorBox error={builds.error} />;
  if (build === null && builds.data?.length) setTimeout(() => setBuild(builds.data![builds.data!.length - 1].id));
  return (
    <div className="filters">
      <label>
        Software build
        <select value={build ?? ""} onChange={(e) => setBuild(e.target.value)}>
          {(builds.data ?? []).map((b) => (
            <option key={b.id} value={b.id}>{b.id} · {b.release_date}</option>
          ))}
        </select>
      </label>
      {setVariant && (
        <label>
          Vehicle variant
          <select value={variant ?? ""} onChange={(e) => setVariant(e.target.value)}>
            {allowAllVariants && <option value="">All variants</option>}
            {(variants.data ?? []).map((v) => (
              <option key={v.id} value={v.id}>{v.id} · {v.name}</option>
            ))}
          </select>
        </label>
      )}
      {children}
    </div>
  );
}

export function IdList({ ids }: { ids: string[] }) {
  return <span className="mono">{ids.join(", ")}</span>;
}
