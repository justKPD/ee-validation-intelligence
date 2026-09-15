"use client";

import { LineChart } from "@/components/charts";
import { Card, ErrorBox, Loading, PageHeader } from "@/components/ui";
import type { ShadowReport, StrategyMetrics } from "@/lib/api";
import { num, pct, score } from "@/lib/format";
import { useApi } from "@/lib/useApi";

const COLORS: Record<string, string> = {
  risk_based: "var(--series-1)",
  hybrid: "var(--series-2)",
  severity_baseline: "var(--series-3)",
  random_baseline: "var(--series-4)",
};

export default function Shadow() {
  const { data, error } = useApi<ShadowReport>("/benchmarks/shadow");
  if (error) return <><PageHeader title="Shadow Test Planning" /><ErrorBox error={error} /></>;
  if (!data) return <Loading what="benchmark" />;
  const agg = data.aggregate;
  const strategies = Object.keys(agg.at_k);

  const lineFor = (metric: keyof StrategyMetrics) =>
    strategies.map((s) => ({
      key: s,
      label: s.replace(/_/g, " "),
      color: COLORS[s] ?? "var(--status-neutral)",
      points: Object.entries(agg.at_k[s]).map(([k, m]) => ({ x: m.minutes, y: Number(m[metric] ?? 0), note: `K=${k}` })),
    }));

  return (
    <>
      <PageHeader title="Shadow Test Planning Benchmark" subtitle="Each historical build is replayed without future results. Strategies rank tests; hidden ground-truth faults score what each selection would have found. Nothing here is hand-entered." />
      <div className="sentence">{data.sentence}</div>

      <div className="grid cols-2">
        <Card title="Critical defect recall vs test-minutes" subtitle="Mean over builds at K = 5, 10, 20, 50.">
          <LineChart xLabel="Test-minutes" yLabel="Critical defect recall" series={lineFor("critical_defect_recall")} />
        </Card>
        <Card title="Critical risk coverage vs test-minutes" subtitle="Share of severity × impact weight of critical requirement/variant pairs lacking current evidence.">
          <LineChart xLabel="Test-minutes" yLabel="Critical risk coverage" series={lineFor("critical_risk_coverage")} />
        </Card>
      </div>

      <Card title={`At the historical engineers' own budget (${num(agg.engineer_budget_minutes)} min per build)`} subtitle="The equal-cost comparison." style={{ marginTop: 16 }}>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Selection</th><th className="num">Critical defect recall</th><th className="num">Defect recall</th><th className="num">Critical risk coverage</th><th className="num">Minutes to match engineers</th><th className="num">Minutes saved</th></tr></thead>
            <tbody>
              <tr><td>historical engineer</td><td className="num">{pct(agg.engineer.critical_defect_recall)}</td><td className="num">{pct(agg.engineer.defect_recall)}</td><td className="num">{pct(agg.engineer.critical_risk_coverage)}</td><td className="num">—</td><td className="num">—</td></tr>
              {strategies.map((s) => {
                const m = agg.at_engineer_budget[s];
                return (
                  <tr key={s}>
                    <td><span className="swatch" style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: COLORS[s], marginRight: 6 }} />{s.replace(/_/g, " ")}</td>
                    <td className="num">{pct(m.critical_defect_recall)}</td><td className="num">{pct(m.defect_recall)}</td><td className="num">{pct(m.critical_risk_coverage)}</td>
                    <td className="num">{num(m.minutes_to_match_engineer_yield)}</td><td className="num">{pct(m.minutes_saved_share, 0)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Ranking cut-offs" subtitle="Mean over builds. NDCG and MAP use oracle relevance; minutes differ between strategies at the same K." style={{ marginTop: 16 }}>
        <div className="table-wrap">
          <table>
            <thead><tr><th>K</th><th>Strategy</th><th className="num">Critical risk cov.</th><th className="num">Critical defect recall</th><th className="num">Defect recall</th><th className="num">Minutes</th><th className="num">NDCG</th><th className="num">MAP</th></tr></thead>
            <tbody>
              {data.ks.flatMap((k) => strategies.map((s) => {
                const m = agg.at_k[s][String(k)];
                return (
                  <tr key={`${k}-${s}`}>
                    <td className="num">{k}</td><td>{s.replace(/_/g, " ")}</td><td className="num">{pct(m.critical_risk_coverage)}</td>
                    <td className="num">{pct(m.critical_defect_recall)}</td><td className="num">{pct(m.defect_recall)}</td>
                    <td className="num">{num(m.minutes)}</td><td className="num">{score(m.ndcg)}</td><td className="num">{score(m.map)}</td>
                  </tr>
                );
              }))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid cols-2" style={{ marginTop: 16 }}>
        <Card title="Findings: where baselines win" subtitle="Generated from the run; not curated.">
          <ul className="reasons">{data.findings.map((f) => <li key={f}>{f}</li>)}</ul>
        </Card>
        <Card title="Observed replay (no oracle)" subtitle="Only the tests engineers ran, reordered. 0.5 ≈ random order; higher means defects are found earlier.">
          <table>
            <tbody>
              {Object.entries(agg.observed_replay).map(([s, v]) => <tr key={s}><td>{s.replace(/_/g, " ")}</td><td className="num">{score(v)}</td></tr>)}
            </tbody>
          </table>
        </Card>
      </div>
      <p className="muted" style={{ marginTop: 12 }}>{data.disclaimer}</p>
    </>
  );
}
