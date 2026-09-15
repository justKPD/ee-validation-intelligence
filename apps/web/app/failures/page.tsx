"use client";

import { useState } from "react";
import { ColumnChart } from "@/components/charts";
import { BuildVariantFilters, Card, ErrorBox, IdList, Loading, PageHeader, StatusBadge } from "@/components/ui";
import { qs, type FailureFamily } from "@/lib/api";
import { useApi } from "@/lib/useApi";

export default function Failures() {
  const [build, setBuild] = useState<string | null>(null);
  const [recurring, setRecurring] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const fams = useApi<FailureFamily[]>(build ? `/builds/${build}/failure-families${qs({ recurring_only: recurring })}` : null);
  const family = fams.data?.find((f) => f.id === selected) ?? fams.data?.[0] ?? null;

  return (
    <>
      <PageHeader title="Failure Intelligence" subtitle="Deterministic fingerprints (component | test family | error code | failure stage) group recurring failures across builds and variants." />
      <BuildVariantFilters build={build} setBuild={setBuild}>
        <label style={{ flexDirection: "row", display: "flex", gap: 6, alignItems: "center" }}>
          <input type="checkbox" checked={recurring} onChange={(e) => setRecurring(e.target.checked)} /> Recurring only
        </label>
      </BuildVariantFilters>
      {fams.error && <ErrorBox error={fams.error} />}
      <div className="grid cols-2">
        <Card title="Occurrences per family" subtitle="Families visible at this build (defects from earlier builds only).">
          {fams.data ? (fams.data.length ? <ColumnChart data={fams.data.slice(0, 16).map((f) => ({ label: f.id, value: f.occurrences, detail: <div className="muted">{f.component_id}</div> }))} /> : <p className="muted">No failure families yet.</p>) : <Loading />}
        </Card>
        <Card title={family ? `Failure family ${family.id}` : "Family detail"} subtitle={family?.fingerprint}>
          {family ? (
            <table>
              <tbody>
                <tr><td>Status</td><td><StatusBadge status={family.status} /></td></tr>
                <tr><td>Representative</td><td>{family.representative_title}</td></tr>
                <tr><td>Occurrences</td><td>{family.occurrences}</td></tr>
                <tr><td>Component</td><td className="mono">{family.component_id}</td></tr>
                <tr><td>Builds</td><td><IdList ids={family.build_ids} /></td></tr>
                <tr><td>Variants</td><td>{family.variant_ids.join(", ")}</td></tr>
                <tr><td>Max severity</td><td>{family.max_severity}</td></tr>
                <tr><td>Signals</td><td>{family.signal_signatures.join("; ")}</td></tr>
                <tr><td>Linked defects</td><td><IdList ids={family.defect_ids} /></td></tr>
              </tbody>
            </table>
          ) : <p className="muted">Select a family.</p>}
        </Card>
      </div>
      <Card title="All families" style={{ marginTop: 16 }}>
        {fams.data ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th>ID</th><th>Component</th><th>Test family</th><th>Error code</th><th>Stage</th><th className="num">Occurrences</th><th>First → last</th><th>Status</th></tr></thead>
              <tbody>
                {fams.data.map((f) => (
                  <tr key={f.id} className={`clickable${family?.id === f.id ? " selected" : ""}`} onClick={() => setSelected(f.id)}>
                    <td className="mono">{f.id}</td><td className="mono">{f.component_id}</td><td>{f.test_family}</td><td className="mono">{f.error_code}</td>
                    <td>{f.failure_stage}</td><td className="num">{f.occurrences}</td><td>{f.first_seen_build} → {f.last_seen_build}</td><td><StatusBadge status={f.status} /></td>
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
