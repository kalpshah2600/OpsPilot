export const API_URL: string = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export type Severity = 'info' | 'warning' | 'critical';

export interface AnomalyDetails {
  is_anomaly: boolean;
  isolation_score: number;
  feature_ratios: Record<string, number>;
}

export interface Evidence {
  source: string;
  summary: string;
  value?: string | number | null;
  severity: Severity;
  details?: AnomalyDetails | null;
}

export interface Hypothesis {
  key: string;
  label: string;
  confidence: number;
  rationale: string[];
  qualified: boolean;
}

export interface Investigation {
  incident_id: string;
  question: string;
  root_cause: string;
  root_cause_key: string;
  confidence: number;
  evidence: Evidence[];
  hypotheses: Hypothesis[];
  recommended_action: string;
  requires_approval: boolean;
  status: string;
  reasoner: string;
  unexplained_signals: string[];
  rationale: string[];
}

export interface Approval {
  incident_id: string;
  action: string;
  approved_by: string;
  ts: string;
  executed: boolean;
  note: string;
}

export type SpanStats = Record<string, { calls: number; avg_ms: number; max_ms: number }>;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; scenario: string }>('/health'),
  reset: () => request<unknown>('/demo/reset', { method: 'POST' }),
  inject: (scenario: string) => request<unknown>(`/demo/incidents/${scenario}`, { method: 'POST' }),
  investigate: (question: string) =>
    request<Investigation>('/investigate', { method: 'POST', body: JSON.stringify({ question }) }),
  approve: (inv: Investigation, approvedBy: string) =>
    request<Approval>('/approve', {
      method: 'POST',
      body: JSON.stringify({ incident_id: inv.incident_id, action: inv.recommended_action, approved_by: approvedBy }),
    }),
  observability: () => request<SpanStats>('/observability'),
};
