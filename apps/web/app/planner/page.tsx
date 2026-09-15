"use client";

import { useState } from "react";
import { BuildVariantFilters, Card, ErrorBox, IdList, PageHeader, StatusBadge } from "@/components/ui";
import { apiGet, apiPost, type AgentResult, type Recommendation } from "@/lib/api";
import { num, pct, score } from "@/lib/format";

type Record_ = Record<string, unknown> & { decision?: { status: string; history: { decision: string; reviewer: string; reason: string; at: string }[] } };

export default function Planner() {
  const [build, setBuild] = useState<string | null>(null);
  const [variant, setVariant] = useState("V3");
  const [budget, setBudget] = useState("");
  const [topN, setTopN] = useState(5);
  const [custom, setCustom] = useState("");
  const [reviewer, setReviewer] = useState("engineer_12");
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<AgentResult | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [record, setRecord] = useState<Record_ | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const composed = `Top ${topN} tests for ${build ?? "?"} on ${variant ? variant : "all variants"}${budget ? ` within ${budget} minutes` : ""}`;
  const request = custom.trim() || composed;

  async function plan() {
    setBusy(true);
    setError(null);
    setRecord(null);
    setSelected(null);
    try {
      const r = await apiPost<AgentResult>("/agent/plan", { request, actor: reviewer || "engineer" });
      setResult(r);
      if (r.recommendations.length) await select(r.recommendations[0].recommendation_id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function select(id: string) {
    setSelected(id);
    setRecord(await apiGet<Record_>(`/recommendations/${id}`));
  }

  async function decide(decision: "APPROVED" | "REJECTED") {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await apiPost<Recommendation>(`/recommendations/${selected}/decision`, { decision, reviewer, reason });
      setReason("");
      await select(selected);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const rec = result?.recommendations.find((r) => r.recommendation_id === selected);
  const status = record?.decision?.status;

  return (
    <>
      <PageHeader title="Agentic Test Planner" subtitle="The agent reads evidence, explains risk and proposes tests. It cannot change requirements, test definitions, verdicts or defects. Every proposal waits for an engineer's decision." />
      {error && <ErrorBox error={error} />}
      <div className="grid cols-3">
        <Card title="Request">
          <BuildVariantFilters build={build} setBuild={setBuild} variant={variant} setVariant={setVariant} />
          <div className="filters">
            <label>Top N<input type="number" min={1} max={50} value={topN} onChange={(e) => setTopN(Number(e.target.value))} style={{ width: 80 }} /></label>
            <label>Test budget (min)<input type="number" min={1} value={budget} placeholder="none" onChange={(e) => setBudget(e.target.value)} style={{ width: 110 }} /></label>
          </div>
          <label className="secondary" style={{ display: "grid", gap: 4, fontSize: 12 }}>
            Or ask in your own words
            <textarea rows={4} value={custom} placeholder={composed} onChange={(e) => setCustom(e.target.value)} />
          </label>
          <label className="secondary" style={{ display: "grid", gap: 4, fontSize: 12, marginTop: 10 }}>
            Reviewer
            <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} />
          </label>
          <button className="primary" style={{ marginTop: 12, width: "100%" }} disabled={busy || !build} onClick={plan}>
            {busy ? "Working…" : "Ask the planner"}
          </button>
          <p className="muted" style={{ fontSize: 12 }}>Sends: “{request}”</p>
        </Card>

        <Card title="Proposed plan" subtitle={result ? <>Run <span className="mono">{result.run_id}</span> · <StatusBadge status={result.status} /> · {result.model.provider}/{result.model.name} · {result.latency_ms} ms</> : "Ask the planner to see ranked recommendations."}>
          {result && result.status !== "COMPLETED" && (
            <div className="sentence" style={{ borderLeftColor: result.status === "REFUSED" ? "var(--status-critical)" : "var(--status-warning)" }}>{result.response}</div>
          )}
          {result?.recommendations.length ? (
            <div className="table-wrap">
              <table>
                <thead><tr><th className="num">#</th><th>Test</th><th>Variant</th><th className="num">Priority</th><th className="num">Min</th><th className="num">Coverage gain</th></tr></thead>
                <tbody>
                  {result.recommendations.map((r) => (
                    <tr key={r.recommendation_id} className={`clickable${r.recommendation_id === selected ? " selected" : ""}`} onClick={() => select(r.recommendation_id)}>
                      <td className="num">{r.rank}</td><td className="mono">{r.test_id}</td><td>{r.variant_id}</td>
                      <td className="num">{score(r.score)}</td><td className="num">{num(r.duration_min, 1)}</td><td className="num">+{pct(r.expected_coverage_gain)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          {result?.status === "COMPLETED" && (
            <details style={{ marginTop: 12 }}>
              <summary className="secondary">Agent explanation {result.grounded ? "(grounded)" : "(offline fallback used)"}</summary>
              <pre className="json" style={{ whiteSpace: "pre-wrap" }}>{result.response}</pre>
            </details>
          )}
          {result && (
            <details style={{ marginTop: 8 }}>
              <summary className="secondary">Policy decisions & trace ({result.policy_decisions.length})</summary>
              <table>
                <tbody>
                  {result.policy_decisions.map((d, i) => (
                    <tr key={i}><td className="mono">{d.tool}</td><td><StatusBadge status={d.decision} /></td><td className="secondary">{d.reason}</td></tr>
                  ))}
                </tbody>
              </table>
              <p className="muted">Trace: {result.trace.join(" → ")}</p>
            </details>
          )}
        </Card>

        <Card title={rec ? `${rec.test_id} on ${rec.variant_id}` : "Explanation & provenance"} subtitle={rec ? <>Recommendation <span className="mono">{rec.recommendation_id}</span> · {status && <StatusBadge status={status} />}</> : undefined}>
          {rec ? (
            <>
              <p><strong>Priority {score(rec.score)}</strong> · {num(rec.duration_min, 1)} min · coverage gain +{pct(rec.expected_coverage_gain)}</p>
              <h4 style={{ margin: "8px 0 0", fontSize: 13 }}>Reasons</h4>
              <ul className="reasons">{rec.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
              <h4 style={{ margin: "10px 0 2px", fontSize: 13 }}>Evidence</h4>
              <IdList ids={rec.evidence_ids} />
              <div style={{ display: "grid", gap: 8, marginTop: 14 }}>
                <input placeholder="Reason (required to reject)" value={reason} onChange={(e) => setReason(e.target.value)} />
                <div style={{ display: "flex", gap: 8 }}>
                  <button className="primary" disabled={busy || status !== "PROPOSED"} onClick={() => decide("APPROVED")}>Approve recommendation</button>
                  <button disabled={busy || status !== "PROPOSED" || !reason.trim()} onClick={() => decide("REJECTED")}>Reject</button>
                </div>
              </div>
              {record && (
                <details style={{ marginTop: 12 }} open>
                  <summary className="secondary">Provenance record</summary>
                  <pre className="json">{JSON.stringify(record, null, 2)}</pre>
                </details>
              )}
            </>
          ) : <p className="muted">Select a recommendation.</p>}
        </Card>
      </div>
    </>
  );
}
