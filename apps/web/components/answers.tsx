"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { StatusBadge } from "@/components/ui";
import { qs, type AgentAnswer } from "@/lib/api";

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
  }
}

const riskLink = (build: string, component: string, extra: Record<string, string> = {}) =>
  `/risk${qs({ build, component, ...extra })}`;

function Row({ children }: { children: ReactNode }) {
  return <div style={{ borderLeft: "3px solid var(--border, #ddd)", paddingLeft: 10, margin: "6px 0" }}>{children}</div>;
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
