"use client";

import Link from "next/link";
import { useState } from "react";
import { ColumnChart, HorizontalBarChart, LineChart, StackedBarChart, StatTile } from "@/components/charts";
import { BuildVariantFilters, Card, ErrorBox, EVIDENCE_COLORS, Loading, PageHeader } from "@/components/ui";
import { EVIDENCE_STATUSES, qs, type ComponentRisk, type CoverageSummary, type FailureFamily, type RankedTest, type ShadowReport } from "@/lib/api";
import { num, pct, score } from "@/lib/format";
import { useApi } from "@/lib/useApi";

const STRATEGY_COLORS: Record<string, string> = {
  risk_based: "var(--series-1)",
  hybrid: "var(--series-2)",
  severity_baseline: "var(--series-3)",
  random_baseline: "var(--series-4)",
};

export default function Dashboard() {
  const [build, setBuild] = useState<string | null>(null);
  const risk = useApi<ComponentRisk[]>(build ? `/builds/${build}/risk/components` : null);
  const coverage = useApi<CoverageSummary>(build ? `/builds/${build}/coverage` : null);
  const families = useApi<FailureFamily[]>(build ? `/builds/${build}/failure-families` : null);
  const ranked = useApi<RankedTest[]>(build ? `/builds/${build}/ranking${qs({ limit: 10 })}` : null);
  const shadow = useApi<ShadowReport>("/benchmarks/shadow");

  const error = risk.error || coverage.error || families.error || ranked.error;
  const critical = (risk.data ?? []).filter((r) => r.score >= 0.5);
  const openFamilies = (families.data ?? []).filter((f) => f.status === "OPEN");
  const failuresByComp = Object.entries(
    (families.data ?? []).reduce<Record<string, number>>((acc, f) => ({ ...acc, [f.component_id]: (acc[f.component_id] ?? 0) + f.occurrences }), {}),
  ).sort((a, b) => b[1] - a[1]).slice(0, 12);

  return (
    <>
      <PageHeader title="Validation Control Tower" subtitle="Risk, evidence and failure picture for a software build, computed by the deterministic engines as of that build (no future results)." />
      <BuildVariantFilters build={build} setBuild={setBuild} />
      {error && <ErrorBox error={error} />}
      <div className="tiles">
        <StatTile label="Current build" value={build ?? "—"} note={coverage.data ? `${num(coverage.data.requirements_total)} requirements` : undefined} />
        <StatTile label="Highest component risk" value={risk.data?.length ? score(risk.data[0].score) : "—"} note={risk.data?.length ? `${risk.data[0].component_id} · ${critical.length} of ${risk.data.length} at ≥ 0.5` : undefined} />
        <StatTile label="Current evidence coverage" value={pct(coverage.data?.evidence_coverage)} note={`structural ${pct(coverage.data?.structural_coverage)}`} />
        <StatTile label="Open failure families" value={families.data ? openFamilies.length : "—"} note={families.data ? `${families.data.length} families total` : undefined} />
        <StatTile label="Top-10 test time" value={ranked.data ? `${num(ranked.data.reduce((s, r) => s + r.duration_min, 0))} min` : "—"} note="risk-based ranking" />
      </div>

      <div className="grid cols-2">
        <Card title="Component risk" subtitle="Top 12 by adjusted risk. Select a bar to open its decomposition.">
          {risk.loading && !risk.data ? <Loading /> : (
            <HorizontalBarChart
              data={(risk.data ?? []).slice(0, 12).map((r) => ({ label: r.component_id, value: r.score, detail: <div className="muted">base {score(r.base)} · confidence {score(r.confidence)}</div> }))}
              max={1}
              format={(v) => v.toFixed(2)}
              onSelect={(c) => { window.location.href = `/risk?build=${build}&component=${c}`; }}
            />
          )}
        </Card>

        <Card title="Evidence state" subtitle="Requirement × variant pairs by evidence status. A linked test counts only if its evidence is CURRENT.">
          {coverage.data ? (
            <StackedBarChart
              rows={[{ label: `${coverage.data.evidence_pairs} pairs`, values: coverage.data.status_counts }]}
              segments={EVIDENCE_STATUSES.map((s) => ({ key: s, label: s, color: EVIDENCE_COLORS[s] }))}
            />
          ) : <Loading />}
          {coverage.data && (
            <div style={{ marginTop: 16 }}>
              <StackedBarChart
                rows={Object.entries(coverage.data.by_component)
                  .sort((a, b) => (b[1].FAILED ?? 0) + (b[1].STALE ?? 0) - ((a[1].FAILED ?? 0) + (a[1].STALE ?? 0)))
                  .slice(0, 8)
                  .map(([comp, counts]) => ({ label: comp, values: counts as Record<string, number> }))}
                segments={EVIDENCE_STATUSES.map((s) => ({ key: s, label: s, color: EVIDENCE_COLORS[s] }))}
              />
            </div>
          )}
        </Card>

        <Card title="Recurring failures by component" subtitle="Defect occurrences across failure-fingerprint families visible at this build.">
          {families.data ? (failuresByComp.length ? <ColumnChart data={failuresByComp.map(([label, value]) => ({ label, value }))} /> : <p className="muted">No defects visible before this build.</p>) : <Loading />}
        </Card>

        <Card title="Shadow planning benchmark" subtitle={shadow.data ? "Critical hidden-defect recall versus test-minutes (mean over replayed builds, K = 5/10/20/50)." : undefined}>
          {shadow.error ? <p className="muted">Benchmark not run yet (<code>uv run ee-shadow</code>).</p> : shadow.data ? (
            <>
              <LineChart
                xLabel="Test-minutes"
                yLabel="Critical defect recall"
                series={Object.entries(shadow.data.aggregate.at_k).map(([s, byK]) => ({
                  key: s,
                  label: s.replace(/_/g, " "),
                  color: STRATEGY_COLORS[s] ?? "var(--status-neutral)",
                  points: Object.entries(byK).map(([k, m]) => ({ x: m.minutes, y: m.critical_defect_recall, note: `K=${k}` })),
                }))}
              />
              <p className="secondary" style={{ marginTop: 8 }}>{shadow.data.sentence} <Link href="/shadow">Details →</Link></p>
            </>
          ) : <Loading />}
        </Card>
      </div>

      <Card title="Recommended next tests" subtitle="Risk-based ranking for this build. Plans for engineer approval are created in the Agentic Test Planner." style={{ marginTop: 16 }}>
        {ranked.data ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th className="num">#</th><th>Test</th><th>Variant</th><th className="num">Priority</th><th className="num">Minutes</th><th>Why</th></tr></thead>
              <tbody>
                {ranked.data.map((r) => (
                  <tr key={`${r.test_id}-${r.variant_id}`}>
                    <td className="num">{r.rank}</td><td className="mono">{r.test_id}</td><td>{r.variant_id}</td>
                    <td className="num">{score(r.score)}</td><td className="num">{num(r.duration_min, 1)}</td>
                    <td className="secondary">{r.reasons.slice(0, 2).join(" · ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Loading />}
      </Card>
    </>
  );
}
