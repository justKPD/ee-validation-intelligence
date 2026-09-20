export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export async function apiGet<T>(path: string): Promise<T> {
  return handle<T>(await fetch(`${API_URL}${path}`, { cache: "no-store" }));
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  return handle<T>(
    await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

export function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "");
  return entries.length ? `?${new URLSearchParams(entries.map(([k, v]) => [k, String(v)]))}` : "";
}

// ---- response types (mirrors the FastAPI models) ------------------------------------------------
export interface Build {
  id: string;
  sequence: number;
  release_date: string;
  build_family: string;
}
export interface Variant {
  id: string;
  name: string;
  powertrain: string;
  market: string;
  features: string;
}
export interface ComponentRisk {
  component_id: string;
  build_id: string;
  score: number;
  base: number;
  impact: number;
  occurrence: number;
  detectability: number;
  factors: Record<string, number>;
  contributions: Record<string, number>;
  confidence: number;
  past_executions: number;
  past_defects: number;
  flags: string[];
  evidence: string[];
  config_version: string;
}
export interface RequirementRisk {
  requirement_id: string;
  score: number;
  fmea_base: number;
  component_risk: number;
  revised_in_build: boolean;
  critical: boolean;
  component_ids: string[];
}
export type EvidenceStatus = "CURRENT" | "STALE" | "MISSING" | "INCOMPATIBLE" | "FAILED";
export const EVIDENCE_STATUSES: EvidenceStatus[] = ["CURRENT", "STALE", "INCOMPATIBLE", "MISSING", "FAILED"];
export interface CoverageSummary {
  build_id: string;
  requirements_total: number;
  requirements_with_tests: number;
  structural_coverage: number;
  evidence_pairs: number;
  evidence_coverage: number;
  status_counts: Record<EvidenceStatus, number>;
  by_component: Record<string, Partial<Record<EvidenceStatus, number>>>;
}
export interface EvidenceRecord {
  requirement_id: string;
  variant_id: string;
  status: EvidenceStatus;
  test_id: string | null;
  execution_id: string | null;
  evidence_build_id: string | null;
  age_days: number | null;
  reasons: string[];
}
export interface FailureFamily {
  id: string;
  fingerprint: string;
  component_id: string;
  test_family: string;
  error_code: string;
  failure_stage: string;
  occurrences: number;
  defect_ids: string[];
  execution_ids: string[];
  build_ids: string[];
  variant_ids: string[];
  signal_signatures: string[];
  representative_title: string;
  first_seen_build: string;
  last_seen_build: string;
  max_severity: number;
  status: "OPEN" | "RESOLVED";
  recurring: boolean;
}
export interface RankedTest {
  rank: number;
  test_id: string;
  variant_id: string;
  strategy: string;
  score: number;
  duration_min: number;
  cumulative_minutes: number;
  contributions: Record<string, number>;
  learned_probability: number | null;
  critical: boolean;
  requirement_ids: string[];
  component_ids: string[];
  reasons: string[];
  evidence_ids: string[];
}
export interface PlanRecommendation {
  recommendation_id: string;
  rank: number;
  test_id: string;
  variant_id: string;
  score: number;
  duration_min: number;
  expected_coverage_gain: number;
  reasons: string[];
  evidence_ids: string[];
}
export interface PolicyDecisionOut {
  tool: string;
  permission: string;
  decision: string;
  reason: string;
}
export interface AgentResult {
  run_id: string;
  status: "COMPLETED" | "ANSWERED" | "NEEDS_CLARIFICATION" | "REFUSED" | "FAILED";
  response: string;
  clarification_question: string | null;
  build_id: string | null;
  variant_id: string | null;
  recommendations: PlanRecommendation[];
  policy_decisions: PolicyDecisionOut[];
  tool_calls: { tool: string; decision: string; error?: string }[];
  model: { provider: string; name: string; prompt_version: string };
  grounded: boolean;
  latency_ms: number;
  trace: string[];
  answer?: AgentAnswer | null;
}
/** Read-only answers from the agent's question engine, one shape per question kind. */
export interface TestEvidenceAnswer {
  kind: "test_evidence";
  test_id: string;
  build_id: string;
  known: boolean;
  applicable_variants?: string[];
  variants: {
    variant_id: string;
    verdict: "VALID" | "NOT_VALID" | "NO_EVIDENCE" | "NOT_APPLICABLE";
    records: {
      requirement_id: string;
      status: EvidenceStatus;
      execution_id: string | null;
      evidence_build_id: string | null;
      age_days: number | null;
      reasons: string[];
      component_ids: string[];
    }[];
  }[];
}
export interface TestHistoryAnswer {
  kind: "test_history";
  test_id: string;
  build_id: string | null;
  variant_id: string | null;
  verdict_counts: Record<string, number>;
  runs: {
    execution_id: string;
    build_id: string;
    variant_id: string;
    verdict: string;
    date: string;
    defect_id: string | null;
    defect_component: string | null;
    defect_severity: number | null;
  }[];
}
export interface RequirementCoverageAnswer {
  kind: "requirement_coverage";
  requirement_id: string;
  build_id: string;
  title: string;
  severity: number;
  revision: number;
  linked_tests: string[];
  component_ids: string[];
  variants: {
    variant_id: string;
    status: EvidenceStatus;
    test_id: string | null;
    execution_id: string | null;
    evidence_build_id: string | null;
    age_days: number | null;
    reasons: string[];
  }[];
}
export interface ComponentRiskAnswer {
  kind: "component_risk";
  component_id: string;
  build_id: string;
  score: number;
  rank: number;
  of: number;
  contributions: [string, number][];
  impact: number;
  occurrence: number;
  detectability: number;
  confidence: number;
  past_executions: number;
  past_defects: number;
  flags: string[];
  changes: { id: string; change_kind: string; magnitude: number }[];
}
export interface ComponentDefectsAnswer {
  kind: "component_defects";
  component_id: string;
  build_id: string | null;
  defects: { defect_id: string; build_id: string | null; severity: number; error_code: string; title: string }[];
  by_build: Record<string, number>;
  by_severity: Record<string, number>;
}
export interface BuildFailuresAnswer {
  kind: "build_failures";
  build_id: string;
  variant_id: string | null;
  runs: number;
  verdict_counts: Record<string, number>;
  failures: {
    test_id: string;
    variant_id: string;
    execution_id: string;
    defect_id: string | null;
    defect_component: string | null;
    defect_severity: number | null;
  }[];
}
export interface BuildSummary {
  changes: number;
  evidence_pairs: number;
  current_share: number;
  mean_risk: number;
  top_component: string;
  top_score: number;
  runs: number;
  fail: number;
  blocked: number;
  defects: number;
}
export interface RiskMove {
  component_id: string;
  a: number;
  b: number;
  delta: number;
}
export interface BuildComparisonAnswer {
  kind: "build_comparison";
  build_a: string;
  build_b: string;
  variant_id: string | null;
  builds: Record<string, BuildSummary>;
  evidence_lost: number;
  evidence_gained: number;
  risk_up: RiskMove[];
  risk_down: RiskMove[];
}
export interface ComponentTrendAnswer {
  kind: "component_trend";
  build_from: string;
  build_to: string;
  component_id: string | null;
  of: number;
  focus?: "better" | "worse";
  series?: { build_id: string; score: number; rank: number; defects: number }[];
  n_worse?: number;
  n_better?: number;
  worse?: RiskMove[];
  better?: RiskMove[];
  riskiest?: { component_id: string; score: number };
}
export interface AgentRunAnswer {
  kind: "agent_run";
  run_id: string;
  found: boolean;
  status?: string;
  actor?: string;
  created_at?: string;
  user_request?: string;
  response?: string;
  build_id?: string | null;
  variant_id?: string | null;
  policy_version?: string;
  latency_ms?: number;
  model?: { provider: string; name: string };
  recommendations?: {
    recommendation_id: string;
    test_id: string;
    variant_id: string;
    rank: number;
    priority_score: number;
    status: string;
  }[];
  denials?: { tool: string; permission: string; reason: string }[];
}
export interface RecommendationAnswer {
  kind: "recommendation";
  recommendation_id: string;
  found: boolean;
  status?: string;
  run_id?: string;
  build_id?: string;
  variant_id?: string;
  test_id?: string;
  priority_score?: number;
  estimated_minutes?: number;
  expected_coverage_gain?: number;
  reasons?: string[];
  evidence_ids?: string[];
  decisions?: { decision: string; reviewer: string; reason: string; at: string }[];
}
export type AgentAnswer =
  | TestEvidenceAnswer
  | TestHistoryAnswer
  | RequirementCoverageAnswer
  | ComponentRiskAnswer
  | ComponentDefectsAnswer
  | BuildFailuresAnswer
  | BuildComparisonAnswer
  | ComponentTrendAnswer
  | AgentRunAnswer
  | RecommendationAnswer;
export interface Recommendation {
  id: string;
  run_id: string;
  build_id: string;
  variant_id: string;
  test_id: string;
  rank: number;
  priority_score: number;
  estimated_minutes: number;
  expected_coverage_gain: number;
  status: "PROPOSED" | "APPROVED" | "REJECTED" | "EXECUTED";
  reasons: string[];
  evidence_ids: string[];
  created_at: string;
  updated_at: string;
}
export interface LedgerEntry {
  seq: number;
  entry_type: string;
  subject_id: string;
  at: string;
  payload: Record<string, unknown>;
  prev_hash: string;
  hash: string;
}
export interface StrategyMetrics {
  tests_selected: number;
  minutes: number;
  expected_defects: number;
  defect_recall: number;
  critical_defect_recall: number;
  critical_risk_coverage: number;
  coverage_gain: number;
  ndcg?: number;
  map?: number;
  minutes_to_match_engineer_yield?: number | null;
  minutes_saved_share?: number | null;
  match_rate?: number;
}
export interface ShadowReport {
  seed: number;
  ks: number[];
  sentence: string;
  findings: string[];
  disclaimer: string;
  aggregate: {
    at_k: Record<string, Record<string, StrategyMetrics>>;
    at_engineer_budget: Record<string, StrategyMetrics>;
    engineer: StrategyMetrics;
    engineer_budget_minutes: number;
    observed_replay: Record<string, number | null>;
  };
  builds: { build_id: string; live_faults: number; critical_live_faults: number; engineer_budget_minutes: number }[];
}
export interface ReliabilityReport {
  provider: string;
  model: string;
  k: number;
  scenarios: number;
  runs: number;
  metrics: Record<string, number>;
  by_category: Record<string, Record<string, number>>;
  pass_k: Record<string, boolean>;
  outcomes: {
    scenario_id: string;
    category: string;
    repeat: number;
    request: string;
    expected_status: string;
    status: string;
    success: boolean;
    failed_checks: string[];
    response_excerpt: string;
  }[];
  sentence: string;
  disclaimer: string;
}
export interface AdversarialReport {
  provider: string;
  mutants: number;
  failures: number;
  failure_rate: number;
  by_axis: Record<string, { mutants: number; success: number }>;
  failure_classes: { key: string; mutators: string[]; expected_status: string; actual_status: string; count: number; examples: string[] }[];
  open_regressions: number;
  fixed_regressions: number;
}
