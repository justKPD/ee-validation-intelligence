"use client";

import { useState } from "react";
import { Card, ErrorBox, Loading, PageHeader, StatusBadge } from "@/components/ui";
import { qs, type LedgerEntry, type Recommendation } from "@/lib/api";
import { pct, score, shortHash } from "@/lib/format";
import { useApi } from "@/lib/useApi";

export default function Provenance() {
  const [status, setStatus] = useState("");
  const [entryType, setEntryType] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const verify = useApi<{ valid: boolean; broken_at_seq: number | null }>("/provenance/verify");
  const recs = useApi<Recommendation[]>(`/recommendations${qs({ status, limit: 200 })}`);
  const ledger = useApi<LedgerEntry[]>(`/provenance/ledger${qs({ entry_type: entryType, limit: 200 })}`);
  const record = useApi<Record<string, unknown>>(selected ? `/recommendations/${selected}` : null);

  return (
    <>
      <PageHeader title="Provenance Ledger" subtitle="Every agent run, proposal, human decision and policy denial is appended to a hash-chained ledger. Any later edit to stored history breaks the chain.">
        {verify.data && (
          <span className="badge" style={{ fontSize: 13 }}>
            <span className="dot" style={{ background: verify.data.valid ? "var(--status-good)" : "var(--status-critical)" }} />
            {verify.data.valid ? "✓ Chain verified" : `✕ Chain broken at #${verify.data.broken_at_seq}`}
          </span>
        )}
      </PageHeader>
      {(recs.error || ledger.error) && <ErrorBox error={recs.error || ledger.error || ""} />}
      <div className="filters">
        <label>Recommendation status
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All</option>{["PROPOSED", "APPROVED", "REJECTED", "EXECUTED"].map((s) => <option key={s}>{s}</option>)}
          </select>
        </label>
        <label>Ledger entry type
          <select value={entryType} onChange={(e) => setEntryType(e.target.value)}>
            <option value="">All</option>
            {["AGENT_RUN", "RECOMMENDATION_PROPOSED", "RECOMMENDATION_APPROVED", "RECOMMENDATION_REJECTED", "RECOMMENDATION_EXECUTED", "POLICY_DENIED"].map((s) => <option key={s}>{s}</option>)}
          </select>
        </label>
      </div>
      <div className="grid cols-2">
        <Card title="Recommendations" subtitle="Select one to see its full provenance record.">
          {recs.data ? (recs.data.length ? (
            <div className="table-wrap">
              <table>
                <thead><tr><th>ID</th><th>Build</th><th>Test</th><th>Variant</th><th className="num">Priority</th><th className="num">Gain</th><th>Status</th></tr></thead>
                <tbody>
                  {recs.data.map((r) => (
                    <tr key={r.id} className={`clickable${selected === r.id ? " selected" : ""}`} onClick={() => setSelected(r.id)}>
                      <td className="mono">{r.id}</td><td>{r.build_id}</td><td className="mono">{r.test_id}</td><td>{r.variant_id}</td>
                      <td className="num">{score(r.priority_score)}</td><td className="num">{pct(r.expected_coverage_gain)}</td><td><StatusBadge status={r.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="muted">No recommendations yet. Use the Agentic Test Planner.</p>) : <Loading />}
        </Card>
        <Card title={selected ? `Provenance record ${selected}` : "Provenance record"}>
          {selected ? (record.data ? <pre className="json">{JSON.stringify(record.data, null, 2)}</pre> : <Loading />) : <p className="muted">Select a recommendation.</p>}
        </Card>
      </div>
      <Card title="Ledger" subtitle="Newest first. Each entry's prev hash equals the hash of the entry before it." style={{ marginTop: 16 }}>
        {ledger.data ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th className="num">#</th><th>Type</th><th>Subject</th><th>At (UTC)</th><th>Hash</th><th>Prev</th></tr></thead>
              <tbody>
                {ledger.data.map((e) => (
                  <tr key={e.seq}>
                    <td className="num">{e.seq}</td><td>{e.entry_type === "POLICY_DENIED" ? <StatusBadge status="POLICY_DENIED" /> : e.entry_type}</td>
                    <td className="mono">{e.subject_id}</td><td>{e.at.replace("T", " ")}</td>
                    <td className="mono">{shortHash(e.hash)}</td><td className="mono muted">{shortHash(e.prev_hash)}</td>
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
