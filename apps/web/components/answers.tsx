"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { StatusBadge } from "@/components/ui";
import { qs, type AgentAnswer, type RiskMove } from "@/lib/api";

/** Card title for a read-only answer from the question engine. */
export function answerTitle(a: AgentAnswer): string {
  switch (a.kind) {
    case "test_evidence":
      return `Evidence for ${a.test_id} as of ${a.build_id}`;
    case "test_history":
      return `Recorded runs of ${a.test_id}${a.build_id ? ` on ${a.build_id}` : ""}`;
    case "requirement_coverage":
      return `Coverage of ${a.requirement_id} as of ${a.build_id}`;
    case "component_risk":
      return `Why ${a.component_id} scores ${a.score.toFixed(3)} in ${a.build_id}`;
    case "component_defects":
      return `Defects of ${a.component_id}`;
    case "build_failures":
      return `Failed runs in ${a.build_id}${a.variant_id ? ` on ${a.variant_id}` : ""}`;
    case "build_comparison":
      return `${a.build_a} vs ${a.build_b}${a.variant_id ? ` on ${a.variant_id}` : ""}`;
    case "component_trend":
      return a.component_id
        ? `${a.component_id} risk, ${a.build_from} → ${a.build_to}`
        : `Risk movers, ${a.build_from} → ${a.build_to}`;
    case "agent_run":
      return a.found ? `${a.run_id} · ${a.status}` : `${a.run_id} not found`;
    case "recommendation":
      return a.found ? `${a.recommendation_id} · ${a.status}` : `${a.recommendation_id} not found`;
  }
}

const riskLink = (build: string, component: string, extra: Record<string, string> = {}) =>
  `/risk${qs({ build, component, ...extra })}`;

function Row({ children }: { children: ReactNode }) {
  return <div style={{ borderLeft: "3px solid var(--border, #ddd)", paddingLeft: 10, margin: "6px 0" }}>{children}</div>;
}

function Moves({ title, rows, build }: { title: string; rows: RiskMove[]; build: string }) {
  if (!rows.length) return null;
  return (
    <>
      <h4 style={{ margin: "12px 0 4px", fontSize: 13 }}>{title}</h4>
      <table>
        <tbody>
          {rows.map((r) => (
            <tr key={r.component_id}>
              <td><Link href={riskLink(build, r.component_id)}>{r.component_id}</Link></td>
              <td className="num">{r.a.toFixed(3)} → {r.b.toFixed(3)}</td>
              <td className="num" style={{ color: r.delta > 0 ? "var(--status-critical)" : "var(--status-good)" }}>
                {r.delta > 0 ? "+" : ""}{r.delta.toFixed(3)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

/** Details for each question kind; every value comes from the tool result the answer text was written from. */
export function AnswerDetails({ answer: a, latestBuild }: { answer: AgentAnswer; latestBuild: string | null }) {
  switch (a.kind) {
    case "test_evidence":
      if (!a.known) return <p className="muted">This test is not linked to any requirement at {a.build_id}.</p>;
      return (
        <>
          {a.variants.map((v) => (
            <div key={v.variant_id} style={{ marginBottom: 14 }}>
              <p style={{ margin: "0 0 6px" }}><strong>{v.variant_id}</strong> · <StatusBadge status={v.verdict} /></p>
              {v.records.length === 0 && <p className="muted" style={{ margin: 0 }}>{a.test_id} is not defined for {v.variant_id}.</p>}
              {v.records.map((r) => {
                const focus = r.component_ids.find((c) => r.reasons.some((x) => x.includes(c))) ?? r.component_ids[0];
                return (
                  <Row key={r.requirement_id}>
                    <p style={{ margin: 0 }}><span className="mono">{r.requirement_id}</span> · <StatusBadge status={r.status} /></p>
                    <p className="secondary" style={{ margin: "2px 0", fontSize: 13 }}>
                      Latest run: <span className="mono">{r.execution_id ? `${r.execution_id} on ${r.evidence_build_id} (${r.age_days} d before)` : "none"}</span>
                    </p>
                    <ul className="reasons" style={{ margin: "2px 0" }}>{r.reasons.map((x) => <li key={x}>{x}</li>)}</ul>
                    <Link href={riskLink(a.build_id, focus, { variant: v.variant_id, status: r.status })}>See it in Risk & Coverage →</Link>
                  </Row>
                );
              })}
            </div>
          ))}
        </>
      );

    case "requirement_coverage":
      return (
        <>
          <p style={{ marginTop: 0 }}>“{a.title}” · severity {a.severity} · r{a.revision}</p>
          <p className="secondary" style={{ fontSize: 13 }}>Linked tests: <span className="mono">{a.linked_tests.join(", ") || "none"}</span></p>
          {a.variants.map((v) => {
            const focus = a.component_ids.find((c) => v.reasons.some((x) => x.includes(c))) ?? a.component_ids[0];
            return (
              <Row key={v.variant_id}>
                <p style={{ margin: 0 }}><strong>{v.variant_id}</strong> · <StatusBadge status={v.status} /></p>
                <p className="secondary" style={{ margin: "2px 0", fontSize: 13 }}>
                  Best evidence: <span className="mono">{v.execution_id ? `${v.execution_id} from ${v.test_id} on ${v.evidence_build_id} (${v.age_days} d before)` : "none"}</span>
                </p>
                <ul className="reasons" style={{ margin: "2px 0" }}>{v.reasons.map((x) => <li key={x}>{x}</li>)}</ul>
                {focus && <Link href={riskLink(a.build_id, focus, { variant: v.variant_id, status: v.status })}>See it in Risk & Coverage →</Link>}
              </Row>
            );
          })}
        </>
      );

    case "test_history":
      return (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Run</th><th>Build</th><th>Variant</th><th>Verdict</th><th>Date</th><th>Defect</th></tr></thead>
            <tbody>
              {a.runs.map((r) => (
                <tr key={r.execution_id}>
                  <td className="mono">{r.execution_id}</td><td>{r.build_id}</td><td>{r.variant_id}</td>
                  <td><StatusBadge status={r.verdict} /></td><td>{r.date}</td>
                  <td className="mono">{r.defect_id ? `${r.defect_id} (sev ${r.defect_severity})` : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );

    case "component_risk":
      return (
        <>
          <p style={{ marginTop: 0 }}>Rank <strong>{a.rank}</strong> of {a.of} components · confidence {a.confidence.toFixed(2)}</p>
          <table>
            <tbody>
              {a.contributions.map(([name, value]) => (
                <tr key={name}><td>{name === "base" ? "FMEA base" : name.replace(/_/g, " ")}</td><td className="num">+{value.toFixed(3)}</td></tr>
              ))}
              <tr><td><strong>Total</strong></td><td className="num"><strong>{a.score.toFixed(3)}</strong></td></tr>
            </tbody>
          </table>
          {a.changes.length > 0 && (
            <p className="secondary" style={{ fontSize: 13 }}>
              Changed in {a.build_id}: {a.changes.map((c) => `${c.id} (${c.change_kind}, magnitude ${c.magnitude})`).join("; ")}
            </p>
          )}
          {a.flags.length > 0 && <p className="secondary" style={{ fontSize: 13 }}>Flags: {a.flags.join(", ")}</p>}
          <Link href={riskLink(a.build_id, a.component_id)}>See the full breakdown in Risk & Coverage →</Link>
        </>
      );

    case "component_defects":
      return (
        <>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Defect</th><th>Build</th><th className="num">Severity</th><th>Code</th><th>Title</th></tr></thead>
              <tbody>
                {a.defects.map((d) => (
                  <tr key={d.defect_id}>
                    <td className="mono">{d.defect_id}</td><td>{d.build_id}</td><td className="num">{d.severity}</td>
                    <td className="mono">{d.error_code}</td><td className="secondary">{d.title}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {latestBuild && <Link href={riskLink(a.build_id ?? latestBuild, a.component_id)}>See {a.component_id} in Risk & Coverage →</Link>}
        </>
      );

    case "build_comparison": {
      const A = a.builds[a.build_a];
      const B = a.builds[a.build_b];
      const rows: [string, string, string, string][] = [
        ["Changes in the build", `${A.changes}`, `${B.changes}`, `${B.changes - A.changes >= 0 ? "+" : ""}${B.changes - A.changes}`],
        ["Current evidence", `${(A.current_share * 100).toFixed(1)}%`, `${(B.current_share * 100).toFixed(1)}%`, `${((B.current_share - A.current_share) * 100).toFixed(1)} pts`],
        ["Average component risk", A.mean_risk.toFixed(3), B.mean_risk.toFixed(3), `${B.mean_risk - A.mean_risk >= 0 ? "+" : ""}${(B.mean_risk - A.mean_risk).toFixed(3)}`],
        ["Riskiest component", `${A.top_component} ${A.top_score.toFixed(2)}`, `${B.top_component} ${B.top_score.toFixed(2)}`, ""],
        ["Recorded runs", `${A.runs}`, `${B.runs}`, ""],
        ["Failed runs", `${A.fail}`, `${B.fail}`, `${B.fail - A.fail >= 0 ? "+" : ""}${B.fail - A.fail}`],
        ["Defects found", `${A.defects}`, `${B.defects}`, `${B.defects - A.defects >= 0 ? "+" : ""}${B.defects - A.defects}`],
      ];
      return (
        <>
          <table>
            <thead><tr><th /><th className="num">{a.build_a}</th><th className="num">{a.build_b}</th><th className="num">Change</th></tr></thead>
            <tbody>{rows.map(([n, x, y, d]) => <tr key={n}><td>{n}</td><td className="num">{x}</td><td className="num">{y}</td><td className="num">{d}</td></tr>)}</tbody>
          </table>
          <p className="secondary" style={{ fontSize: 13 }}>
            Evidence: {a.evidence_lost} requirement/variant pairs lost current evidence, {a.evidence_gained} gained it.
          </p>
          <Moves title="Risk rose most" rows={a.risk_up} build={a.build_b} />
          <Moves title="Risk fell most" rows={a.risk_down} build={a.build_b} />
        </>
      );
    }

    case "component_trend":
      if (a.component_id && a.series) {
        return (
          <>
            <table>
              <thead><tr><th>Build</th><th className="num">Risk</th><th className="num">Rank</th><th className="num">Defects</th></tr></thead>
              <tbody>
                {a.series.map((x) => (
                  <tr key={x.build_id}>
                    <td>{x.build_id}</td><td className="num">{x.score.toFixed(3)}</td><td className="num">{x.rank} / {a.of}</td><td className="num">{x.defects}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Link href={riskLink(a.build_to, a.component_id)}>See {a.component_id} in Risk & Coverage →</Link>
          </>
        );
      }
      return (
        <>
          <p style={{ marginTop: 0 }}>{a.n_worse} of {a.of} components got riskier, {a.n_better} got safer.</p>
          {a.focus === "better" ? (
            <>
              <Moves title="Improved most" rows={a.better ?? []} build={a.build_to} />
              <Moves title="Got worse most" rows={a.worse ?? []} build={a.build_to} />
            </>
          ) : (
            <>
              <Moves title="Got worse most" rows={a.worse ?? []} build={a.build_to} />
              <Moves title="Improved most" rows={a.better ?? []} build={a.build_to} />
            </>
          )}
        </>
      );

    case "agent_run":
      if (!a.found) return <p className="muted">No run with that id is in the ledger.</p>;
      return (
        <>
          <p style={{ marginTop: 0 }} className="secondary">
            Asked by <span className="mono">{a.actor}</span> · {a.model?.provider}/{a.model?.name} · policy {a.policy_version} · {a.latency_ms} ms
          </p>
          <p>“{a.user_request}”</p>
          {a.denials && a.denials.length > 0 && (
            <p className="secondary" style={{ fontSize: 13 }}>
              Denied: {a.denials.map((d) => `${d.tool} (${d.permission})`).join(", ")}
            </p>
          )}
          {a.recommendations && a.recommendations.length > 0 ? (
            <div className="table-wrap">
              <table>
                <thead><tr><th className="num">#</th><th>Recommendation</th><th>Test</th><th>Variant</th><th className="num">Priority</th><th>Status</th></tr></thead>
                <tbody>
                  {a.recommendations.map((r) => (
                    <tr key={r.recommendation_id}>
                      <td className="num">{r.rank}</td><td className="mono">{r.recommendation_id}</td>
                      <td className="mono">{r.test_id}</td><td>{r.variant_id}</td>
                      <td className="num">{r.priority_score.toFixed(3)}</td><td><StatusBadge status={r.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="muted">This run proposed nothing.</p>}
          <Link href="/provenance">See it in the Provenance Ledger →</Link>
        </>
      );

    case "recommendation":
      if (!a.found) return <p className="muted">No recommendation with that id is in the ledger.</p>;
      return (
        <>
          <p style={{ marginTop: 0 }}>
            <strong>{a.test_id} on {a.variant_id}</strong> · {a.build_id} · priority {a.priority_score?.toFixed(3)} · {a.estimated_minutes?.toFixed(1)} min
          </p>
          <p className="secondary" style={{ fontSize: 13 }}>Proposed by <span className="mono">{a.run_id}</span></p>
          <h4 style={{ margin: "10px 0 2px", fontSize: 13 }}>Reasons</h4>
          <ul className="reasons">{(a.reasons ?? []).map((x) => <li key={x}>{x}</li>)}</ul>
          <h4 style={{ margin: "10px 0 2px", fontSize: 13 }}>Evidence</h4>
          <p className="mono" style={{ margin: 0 }}>{(a.evidence_ids ?? []).join(", ")}</p>
          <h4 style={{ margin: "10px 0 2px", fontSize: 13 }}>Decision</h4>
          {a.decisions && a.decisions.length > 0 ? (
            a.decisions.map((d, i) => (
              <Row key={i}>
                <p style={{ margin: 0 }}><StatusBadge status={d.decision} /> by <span className="mono">{d.reviewer}</span></p>
                <p className="secondary" style={{ margin: "2px 0", fontSize: 13 }}>{d.at.slice(0, 16).replace("T", " ")}{d.reason ? ` — “${d.reason}”` : ""}</p>
              </Row>
            ))
          ) : <p className="muted" style={{ margin: 0 }}>Not decided yet — it stays PROPOSED until an engineer approves or rejects it.</p>}
          <Link href="/provenance">See it in the Provenance Ledger →</Link>
        </>
      );

    case "build_failures":
      return (
        <>
          <p style={{ marginTop: 0 }}>
            {a.runs} runs · {Object.entries(a.verdict_counts).filter(([, n]) => n).map(([v, n]) => `${n} ${v}`).join(", ")}
          </p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Test</th><th>Variant</th><th>Run</th><th>Defect</th><th>Component</th></tr></thead>
              <tbody>
                {a.failures.map((f) => (
                  <tr key={f.execution_id}>
                    <td className="mono">{f.test_id}</td><td>{f.variant_id}</td><td className="mono">{f.execution_id}</td>
                    <td className="mono">{f.defect_id ? `${f.defect_id} (sev ${f.defect_severity})` : ""}</td>
                    <td>{f.defect_component ? <Link href={riskLink(a.build_id, f.defect_component)}>{f.defect_component}</Link> : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      );
  }
}
