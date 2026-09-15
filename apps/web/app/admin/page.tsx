"use client";

import { Card, ErrorBox, Loading, PageHeader, StatusBadge } from "@/components/ui";
import { useApi } from "@/lib/useApi";

interface ConfigOut {
  risk: Record<string, unknown> | null;
  ranking: Record<string, unknown> | null;
  ranking_tuned: Record<string, unknown> | null;
  policy: { version: string; permissions: Record<string, boolean>; autonomy: Record<string, string> } | null;
  model: { provider: string; model: string; otel_exporter: string };
  editable: boolean;
  note: string;
}

export default function Admin() {
  const { data, error } = useApi<ConfigOut>("/config");
  const denials = useApi<{ id: number; run_id: string; at: string; tool: string; permission: string; reason: string }[]>("/policy/decisions?decision=POLICY_DENIED&limit=20");
  if (error) return <><PageHeader title="Admin & Policy" /><ErrorBox error={error} /></>;
  if (!data) return <Loading what="configuration" />;

  return (
    <>
      <PageHeader title="Admin: Model, Policy & Configuration" subtitle={data.note} />
      <div className="grid cols-2">
        <Card title={`Agent authority policy ${data.policy?.version ?? ""}`} subtitle="Default deny: anything not listed is refused.">
          <table>
            <thead><tr><th>Permission</th><th>Decision</th></tr></thead>
            <tbody>
              {Object.entries(data.policy?.permissions ?? {}).map(([p, allowed]) => (
                <tr key={p}><td className="mono">{p}</td><td><StatusBadge status={allowed ? "ALLOWED" : "POLICY_DENIED"} /></td></tr>
              ))}
            </tbody>
          </table>
          <h4 style={{ fontSize: 13, margin: "14px 0 4px" }}>Risk-tiered autonomy</h4>
          <table><tbody>{Object.entries(data.policy?.autonomy ?? {}).map(([k, v]) => <tr key={k}><td>{k.replace(/_/g, " ")}</td><td className="mono">{v}</td></tr>)}</tbody></table>
        </Card>
        <Card title="Model adapter" subtitle="The model only writes explanations. Plans come from the deterministic engines.">
          <table>
            <tbody>
              <tr><td>Provider</td><td className="mono">{data.model.provider}</td></tr>
              <tr><td>Model</td><td className="mono">{data.model.model}</td></tr>
              <tr><td>Tracing exporter</td><td className="mono">{data.model.otel_exporter}</td></tr>
            </tbody>
          </table>
          <p className="secondary">Set <code>EE_MODEL_PROVIDER=anthropic</code> on the API to use Claude. Its output is grounding-checked, with the offline explainer as fallback.</p>
          <h4 style={{ fontSize: 13, margin: "14px 0 4px" }}>Recent policy denials</h4>
          {denials.data?.length ? (
            <table><tbody>{denials.data.map((d) => <tr key={d.id}><td className="mono">{d.run_id}</td><td className="mono">{d.permission}</td><td className="secondary">{d.reason}</td></tr>)}</tbody></table>
          ) : <p className="muted">None recorded.</p>}
        </Card>
        <Card title="Risk engine configuration" subtitle="config/risk.toml"><pre className="json">{JSON.stringify(data.risk, null, 2)}</pre></Card>
        <Card title="Ranking configuration" subtitle={data.ranking_tuned ? "config/ranking.toml (default) and config/ranking.tuned.toml (dev-seed tuned)" : "config/ranking.toml (tuning did not beat the default on the held-out seed)"}>
          <pre className="json">{JSON.stringify({ default: data.ranking, tuned: data.ranking_tuned }, null, 2)}</pre>
        </Card>
      </div>
    </>
  );
}
