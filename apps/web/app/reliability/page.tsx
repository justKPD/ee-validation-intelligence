"use client";

import { HorizontalBarChart, StatTile } from "@/components/charts";
import { Card, ErrorBox, Loading, PageHeader, StatusBadge } from "@/components/ui";
import type { AdversarialReport, ReliabilityReport } from "@/lib/api";
import { pct } from "@/lib/format";
import { useApi } from "@/lib/useApi";

export default function Reliability() {
  const lab = useApi<ReliabilityReport>("/benchmarks/reliability");
  const adv = useApi<AdversarialReport>("/benchmarks/adversarial");
  if (lab.error) return <><PageHeader title="Agent Reliability Lab" /><ErrorBox error={lab.error} /></>;
  if (!lab.data) return <Loading what="reliability results" />;
  const r = lab.data;
  const passK = `pass^${r.k}`;
  const failing = r.outcomes.filter((o) => !o.success && o.repeat === 1);

  return (
    <>
      <PageHeader title="Agent Reliability Lab" subtitle={`${r.scenarios} scenarios × ${r.k} repeated runs (${r.runs} executions) · provider ${r.provider}. A scenario counts toward Pass^${r.k} only if every run succeeds.`} />
      <div className="sentence">{r.sentence}</div>
      <div className="tiles">
        <StatTile label="Task success" value={pct(r.metrics.task_success)} />
        <StatTile label="Policy compliance" value={pct(r.metrics.policy_compliance)} />
        <StatTile label={`Pass^${r.k}`} value={pct(r.metrics[passK])} note={`Pass@1 ${pct(r.metrics.pass_at_1)}`} />
        <StatTile label="Clarification accuracy" value={pct(r.metrics.clarification_accuracy)} note={`false clarifications ${pct(r.metrics.false_clarification_rate)}`} />
        <StatTile label="Hallucination rate" value={pct(r.metrics.hallucination_rate)} note={`premature actions ${pct(r.metrics.premature_action_rate)}`} />
      </div>
      <div className="grid cols-2">
        <Card title={`Pass^${r.k} by scenario category`}>
          <HorizontalBarChart data={Object.entries(r.by_category).map(([c, m]) => ({ label: c.replace(/_/g, " "), value: m[passK] }))} max={1} format={(v) => `${Math.round(v * 100)}%`} />
        </Card>
        <Card title="Adversarial search" subtitle="Mutations of the scenarios: wording, ambiguity, missing or conflicting context, policy-sensitive asks, injection, tool outages.">
          {adv.error ? <p className="muted">Not run yet (<code>uv run ee-adversarial</code>).</p> : adv.data ? (
            <>
              <p>{adv.data.mutants} mutants · {adv.data.failures} failures ({pct(adv.data.failure_rate)}) · regression suite: {adv.data.fixed_regressions} fixed, {adv.data.open_regressions} open</p>
              <HorizontalBarChart data={Object.entries(adv.data.by_axis).map(([a, s]) => ({ label: a.replace(/_/g, " "), value: s.success, detail: <div className="muted">{s.mutants} mutants</div> }))} max={1} format={(v) => `${Math.round(v * 100)}%`} />
              {adv.data.failure_classes.length > 0 && (
                <ul className="reasons">{adv.data.failure_classes.map((c) => <li key={c.key}><span className="mono">{c.mutators.join("+")}</span>: expected {c.expected_status}, got {c.actual_status} ({c.count}×)</li>)}</ul>
              )}
            </>
          ) : <Loading />}
        </Card>
      </div>
      <Card title="Scenario results" subtitle="First run per scenario; offline runs are identical across repeats." style={{ marginTop: 16 }}>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Scenario</th><th>Category</th><th>Request</th><th>Expected</th><th>Got</th><th>Pass^k</th></tr></thead>
            <tbody>
              {r.outcomes.filter((o) => o.repeat === 1).map((o) => (
                <tr key={o.scenario_id}>
                  <td className="mono">{o.scenario_id}</td><td>{o.category.replace(/_/g, " ")}</td><td className="secondary">{o.request}</td>
                  <td><StatusBadge status={o.expected_status} /></td><td><StatusBadge status={o.status} /></td>
                  <td>{r.pass_k[o.scenario_id] ? "✓ pass" : "✕ fail"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {failing.length > 0 && <ul className="reasons">{failing.map((o) => <li key={o.scenario_id}>{o.scenario_id}: {o.failed_checks.join("; ")}</li>)}</ul>}
      </Card>
      <p className="muted" style={{ marginTop: 12 }}>{r.disclaimer}</p>
    </>
  );
}
