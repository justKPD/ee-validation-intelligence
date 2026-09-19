"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Decomposition, HorizontalBarChart } from "@/components/charts";
import { BuildVariantFilters, Card, ErrorBox, IdList, Loading, PageHeader, StatusBadge } from "@/components/ui";
import { EVIDENCE_STATUSES, qs, type ComponentRisk, type EvidenceRecord, type RequirementRisk } from "@/lib/api";
import { score } from "@/lib/format";
import { useApi } from "@/lib/useApi";

function RiskExplorer() {
  const params = useSearchParams();
  const [build, setBuild] = useState<string | null>(params.get("build"));
  const [variant, setVariant] = useState(params.get("variant") ?? "");
  const [component, setComponent] = useState<string | null>(params.get("component"));
  const [status, setStatus] = useState(params.get("status") ?? "");
  const [criticalOnly, setCriticalOnly] = useState(true);

  const risks = useApi<ComponentRisk[]>(build ? `/builds/${build}/risk/components` : null);
  const reqs = useApi<RequirementRisk[]>(build ? `/builds/${build}/risk/requirements${qs({ critical_only: criticalOnly })}` : null);
  const evidence = useApi<EvidenceRecord[]>(build ? `/builds/${build}/evidence${qs({ variant_id: variant, status, component_id: component })}` : null);
  useEffect(() => {
    if (!component && risks.data?.length) setComponent(risks.data[0].component_id);
  }, [risks.data, component]);
  const selected = risks.data?.find((r) => r.component_id === component) ?? null;

  return (
    <>
      <PageHeader title="Risk & Coverage Explorer" subtitle="Every score is a documented weighted sum. Select a component to see why it scored as it did and which evidence is current." />
      <BuildVariantFilters build={build} setBuild={setBuild} variant={variant} setVariant={setVariant}>
        <label>
          Evidence status
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            {EVIDENCE_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
      </BuildVariantFilters>
      {risks.error && <ErrorBox error={risks.error} />}

      <div className="grid cols-2">
        <Card title="Adjusted component risk" subtitle="All 40 fictional components. Select a bar.">
          {risks.data ? (
            <HorizontalBarChart
              data={risks.data.map((r) => ({ label: r.component_id, value: r.score }))}
              max={1}
              selected={component}
              onSelect={setComponent}
            />
          ) : <Loading />}
        </Card>

        <Card title={selected ? `${selected.component_id} · risk ${score(selected.score)}` : "Risk decomposition"} subtitle={selected ? `config ${selected.config_version} · ${selected.past_executions} past executions · ${selected.past_defects} past defects` : undefined}>
          {selected ? (
            <>
              <Decomposition parts={selected.contributions} total={selected.score} />
              <table style={{ marginTop: 12 }}>
                <thead><tr><th>Factor</th><th className="num">Value (0–1)</th></tr></thead>
                <tbody>
                  <tr><td>FMEA impact</td><td className="num">{score(selected.impact)}</td></tr>
                  <tr><td>FMEA occurrence</td><td className="num">{score(selected.occurrence)}</td></tr>
                  <tr><td>FMEA detectability</td><td className="num">{score(selected.detectability)}</td></tr>
                  {Object.entries(selected.factors).map(([k, v]) => <tr key={k}><td>{k.replace(/_/g, " ")}</td><td className="num">{score(v)}</td></tr>)}
                  <tr><td>Confidence</td><td className="num">{score(selected.confidence)}</td></tr>
                </tbody>
              </table>
              <p className="secondary">
                Flags: {selected.flags.length ? selected.flags.map((f) => <span key={f} className="badge" style={{ marginRight: 6 }}>⚑ {f.replace(/_/g, " ")}</span>) : "none"}
              </p>
              <p className="secondary">Evidence: {selected.evidence.length ? <IdList ids={selected.evidence} /> : "no changes or defects"}</p>
            </>
          ) : <Loading />}
        </Card>
      </div>

      <Card title={`Evidence records${component ? ` for ${component}` : ""}`} subtitle="Dominant status per requirement × variant: FAILED > CURRENT > STALE > INCOMPATIBLE > MISSING." style={{ marginTop: 16 }}>
        {evidence.data ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Requirement</th><th>Variant</th><th>Status</th><th>Evidence</th><th className="num">Age (d)</th><th>Reason</th></tr></thead>
              <tbody>
                {evidence.data.slice(0, 200).map((r) => (
                  <tr key={`${r.requirement_id}-${r.variant_id}`}>
                    <td className="mono">{r.requirement_id}</td><td>{r.variant_id}</td><td><StatusBadge status={r.status} /></td>
                    <td className="mono">{r.execution_id ? `${r.test_id} · ${r.execution_id}` : "—"}</td>
                    <td className="num">{r.age_days ?? "—"}</td><td className="secondary">{r.reasons.join("; ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {evidence.data.length > 200 && <p className="muted">Showing 200 of {evidence.data.length}. Narrow the filters.</p>}
          </div>
        ) : <Loading />}
      </Card>

      <Card title="Requirement risk" subtitle={<label><input type="checkbox" checked={criticalOnly} onChange={(e) => setCriticalOnly(e.target.checked)} /> Critical only (severity ≥ 4 or FMEA impact ≥ 8)</label>} style={{ marginTop: 16 }}>
        {reqs.data ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Requirement</th><th className="num">Risk</th><th className="num">FMEA base</th><th className="num">Component risk</th><th>Revised in build</th><th>Components</th></tr></thead>
              <tbody>
                {reqs.data.slice(0, 60).map((r) => (
                  <tr key={r.requirement_id}>
                    <td className="mono">{r.requirement_id}{r.critical ? " ★" : ""}</td><td className="num">{score(r.score)}</td>
                    <td className="num">{score(r.fmea_base)}</td><td className="num">{score(r.component_risk)}</td>
                    <td>{r.revised_in_build ? "yes" : "—"}</td><td className="mono">{r.component_ids.join(", ")}</td>
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

export default function RiskPage() {
  return (
    <Suspense fallback={<Loading />}>
      <RiskExplorer />
    </Suspense>
  );
}
