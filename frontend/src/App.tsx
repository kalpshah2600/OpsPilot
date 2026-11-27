import { useCallback, useEffect, useRef, useState } from 'react';
import { api, type Approval, type Evidence, type Investigation, type SpanStats } from './api';
import {
  metricLabel, metricValue, ms, pct, plural, ratioLabel, splitDeploy, splitLog, splitRunbook,
} from './format';

const SCENARIOS = [
  { key: 'db_pool_exhaustion', name: 'Database pool exhaustion', desc: 'A deploy raises DB_POOL_SIZE and saturates Postgres connections.' },
  { key: 'kafka_lag', name: 'Kafka consumer lag', desc: 'The inventory consumer group keeps rebalancing and the backlog grows.' },
  { key: 'memory_leak', name: 'Checkout memory leak', desc: 'Checkout memory climbs until containers are OOMKilled.' },
  { key: 'thread_pool_exhaustion', name: 'Thread pool exhaustion', desc: 'Near miss: looks like a DB pool problem, but Postgres is healthy.' },
] as const;

const QUESTION = 'Why is the production system unhealthy?';

type Conn = 'checking' | 'up' | 'down';

export default function App() {
  const [conn, setConn] = useState<Conn>('checking');
  const [scenario, setScenario] = useState<string>('healthy');
  const [result, setResult] = useState<Investigation | null>(null);
  const [approval, setApproval] = useState<Approval | null>(null);
  const [spans, setSpans] = useState<SpanStats>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const contentRef = useRef<HTMLElement>(null);

  const checkHealth = useCallback(async () => {
    try {
      const h = await api.health();
      setConn('up');
      setScenario(h.scenario);
    } catch {
      setConn('down');
    }
  }, []);

  const loadSpans = useCallback(() => {
    api.observability().then(setSpans).catch(() => {});
  }, []);

  useEffect(() => {
    checkHealth();
    loadSpans();
    const id = setInterval(checkHealth, 5000);
    return () => clearInterval(id);
  }, [checkHealth, loadSpans]);

  async function run<T>(label: string, fn: () => Promise<T>): Promise<T | undefined> {
    setBusy(label);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError(`Could not reach the OpsPilot API (${(e as Error).message}). Is the backend running on port 8000?`);
      setConn('down');
    } finally {
      setBusy(null);
    }
  }

  const select = (key: string) =>
    run(key, async () => {
      await (key === 'healthy' ? api.reset() : api.inject(key));
      setScenario(key);
      setResult(null);
      setApproval(null);
    });

  const investigate = () =>
    run('investigate', async () => {
      const r = await api.investigate(QUESTION);
      setResult(r);
      setApproval(null);
      loadSpans();
      if (window.matchMedia('(max-width: 960px)').matches) {
        requestAnimationFrame(() => contentRef.current?.scrollIntoView({ behavior: 'smooth' }));
      }
    });

  const approve = () =>
    run('approve', async () => {
      if (result) setApproval(await api.approve(result, 'demo-operator'));
    });

  return (
    <div className="shell">
      <TopBar conn={conn} reasoner={result?.reasoner} />

      <div className="layout">
        <aside className="sidebar">
          <section className="panel">
            <h2 className="panel-title">Simulate an incident</h2>
            <p className="muted small">Inject a failure into the synthetic telemetry, then run an investigation.</p>
            <div className="scenarios">
              {SCENARIOS.map((s) => (
                <button
                  key={s.key}
                  className={`scenario ${scenario === s.key ? 'active' : ''}`}
                  onClick={() => select(s.key)}
                  disabled={busy !== null}
                  aria-pressed={scenario === s.key}
                >
                  <span className="scenario-name">{s.name}</span>
                  <span className="scenario-desc">{s.desc}</span>
                </button>
              ))}
            </div>
            <button className="link-btn" onClick={() => select('healthy')} disabled={busy !== null || scenario === 'healthy'}>
              Reset to healthy
            </button>
          </section>

          <button className="btn-primary run" onClick={investigate} disabled={busy !== null || conn === 'down'}>
            {busy === 'investigate' ? <><span className="spinner" /> Investigating</> : 'Run investigation'}
          </button>

          <TracePanel spans={spans} />
        </aside>

        <main className="content" ref={contentRef}>
          {error && <div className="alert">{error}</div>}
          {!result ? (
            <EmptyState scenario={scenario} />
          ) : (
            <>
              <Diagnosis result={result} approval={approval} onApprove={approve} approving={busy === 'approve'} />
              <Hypotheses result={result} />
              <EvidenceView evidence={result.evidence} />
            </>
          )}
        </main>
      </div>
    </div>
  );
}

function TopBar({ conn, reasoner }: { conn: Conn; reasoner?: string }) {
  const label = conn === 'up' ? 'API connected' : conn === 'down' ? 'API unreachable' : 'Connecting';
  return (
    <header className="topbar">
      <div className="brand">
        <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden="true">
          <rect width="32" height="32" rx="8" fill="var(--surface-2)" />
          <path d="M7 18h5l3-8 4 14 3-6h3" fill="none" stroke="var(--accent)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="brand-name">OpsPilot</span>
        <span className="tag">Synthetic demo</span>
      </div>
      <div className="topbar-right">
        {reasoner && <span className="tag">Reasoner: {reasoner}</span>}
        <span className={`conn conn-${conn}`}><span className="dot" />{label}</span>
      </div>
    </header>
  );
}

function EmptyState({ scenario }: { scenario: string }) {
  const active = SCENARIOS.find((s) => s.key === scenario);
  return (
    <section className="panel empty">
      <h1>Investigate a production incident</h1>
      <p className="muted">
        OpsPilot collects metrics, logs and deployments, scores them with an IsolationForest anomaly detector,
        ranks root-cause hypotheses, grounds them in runbooks, and holds any remediation for human approval.
      </p>
      <ol className="steps">
        <li><span>1</span>Pick a failure scenario on the left{active ? <> (current: <strong>{active.name}</strong>)</> : null}.</li>
        <li><span>2</span>Run an investigation.</li>
        <li><span>3</span>Review the evidence and approve the proposed action if you agree with it.</li>
      </ol>
    </section>
  );
}

function Diagnosis({ result, approval, onApprove, approving }: {
  result: Investigation; approval: Approval | null; onApprove: () => void; approving: boolean;
}) {
  const tone = result.root_cause_key === 'healthy' ? 'ok' : result.root_cause_key === 'unknown' ? 'warn' : 'crit';
  const heading = { ok: 'No incident detected', warn: 'Escalated: needs human investigation', crit: 'Root cause identified' }[tone];
  const unexplained = result.unexplained_signals ?? [];
  return (
    <section className={`panel diagnosis tone-${tone}`}>
      <div className="diag-head">
        <span className="eyebrow">{heading}</span>
        <span className="mono muted small">{result.incident_id}</span>
      </div>
      <h1 className="diag-title">{result.root_cause}</h1>

      <div className="confidence">
        <div className="confidence-row">
          <span className="muted small">Confidence</span>
          <span className="mono">{pct(result.confidence)}</span>
        </div>
        <div className="bar"><div style={{ width: pct(result.confidence) }} /></div>
      </div>

      {tone === 'warn' && result.rationale.length > 0 && (
        <div className="why">
          <span className="label">Why it escalated</span>
          <ul>{result.rationale.map((r) => <li key={r}>{r}</li>)}</ul>
        </div>
      )}

      {unexplained.length > 0 && (
        <div className="unexplained">
          <span className="label">Not explained by this diagnosis</span>
          <p>
            {unexplained.map(ratioLabel).join(', ')} {unexplained.length === 1 ? 'is' : 'are'} anomalous but not accounted for.
            Confidence was lowered; check for a second issue.
          </p>
        </div>
      )}

      <div className="action">
        <span className="label">Recommended action</span>
        <p>{result.recommended_action}</p>
      </div>

      {result.requires_approval && (
        approval ? (
          <div className="approved">
            <strong>Approved by {approval.approved_by}</strong>
            <span className="muted small"> at {new Date(approval.ts).toLocaleTimeString()}. Recorded only; no production change was executed.</span>
          </div>
        ) : (
          <div className="approve-row">
            <button className="btn-approve" onClick={onApprove} disabled={approving}>
              {approving ? 'Recording' : 'Approve remediation'}
            </button>
            <span className="muted small">Approval is recorded for audit. OpsPilot never executes changes on its own.</span>
          </div>
        )
      )}
    </section>
  );
}

function Hypotheses({ result }: { result: Investigation }) {
  if (!result.hypotheses.length) return null;
  return (
    <section className="panel">
      <h2 className="panel-title">Hypotheses considered</h2>
      <p className="muted small hyp-note">
        A cause qualifies only when its required signal and at least one piece of cause-specific evidence are both present.
      </p>
      <ol className="hyps">
        {result.hypotheses.map((h, i) => (
          <li key={h.key} className={i === 0 && h.qualified && result.requires_approval ? 'top' : !h.qualified ? 'ruled-out' : ''}>
            <div className="hyp-head">
              <span className="hyp-rank mono">{i + 1}</span>
              <span className="hyp-label">{h.label}</span>
              {h.confidence > 0 && !h.qualified && <span className="pill pill-muted">Not qualified</span>}
            </div>
            <div className="bar thin"><div style={{ width: pct(h.confidence) }} /></div>
            {h.rationale.length > 0 ? (
              <ul className="rationale">
                {h.rationale.map((r) => <li key={r} className={/^(Missing|No cause)/.test(r) ? 'missing' : ''}>{r}</li>)}
              </ul>
            ) : (
              <p className="muted small rationale-none">No supporting evidence found.</p>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}

function EvidenceView({ evidence }: { evidence: Evidence[] }) {
  const by = (s: string) => evidence.filter((e) => e.source === s);
  const anomaly = by('ml_anomaly_detector')[0];
  const metrics = by('metrics');
  const logs = by('logs');
  const deploys = by('deployments');
  const runbooks = by('runbook');

  return (
    <section className="evidence">
      <h2 className="section-title">Evidence</h2>
      <div className="evidence-grid">
        {anomaly?.details && <AnomalyCard e={anomaly} />}

        <div className="panel">
          <h3 className="panel-title">Metrics</h3>
          <table className="metrics">
            <tbody>
              {metrics.map((m) => (
                <tr key={m.summary}>
                  <td><span className={`sev sev-${m.severity}`} />{metricLabel(m.summary)}</td>
                  <td className="mono num">{metricValue(m.summary, m.value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <h3 className="panel-title">Logs <span className="count">{logs.length}</span></h3>
        <ul className="logs">
          {logs.map((l, i) => {
            const { service, message } = splitLog(l.summary);
            const level = l.severity === 'critical' ? 'ERROR' : l.severity === 'warning' ? 'WARN' : 'INFO';
            return (
              <li key={i} className={`log log-${l.severity}`}>
                <span className="lvl">{level}</span>
                <span className="svc">{service}</span>
                <span className="msg">{message}</span>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="evidence-grid">
        <div className="panel">
          <h3 className="panel-title">Recent deployments</h3>
          <ul className="deploys">
            {[...deploys].reverse().map((d) => {
              const p = splitDeploy(d.summary);
              return (
                <li key={d.summary}>
                  <div className="deploy-head">
                    <span className="mono">{p.id}</span>
                    <span className="muted small">{p.service} v{p.version}</span>
                  </div>
                  <p>{p.changes}</p>
                </li>
              );
            })}
          </ul>
        </div>

        <div className="panel">
          <h3 className="panel-title">Retrieved runbooks</h3>
          <ul className="runbooks">
            {runbooks.map((r) => {
              const p = splitRunbook(r.summary);
              return (
                <li key={r.summary}>
                  <div className="rb-head">
                    <span>{p.title}</span>
                    {p.score !== null && <span className="mono small muted">relevance {p.score.toFixed(2)}</span>}
                  </div>
                  <p>{p.text}</p>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </section>
  );
}

function AnomalyCard({ e }: { e: Evidence }) {
  const d = e.details!;
  const ratios = Object.entries(d.feature_ratios);
  const max = Math.max(3, ...ratios.map(([, v]) => v));
  return (
    <div className="panel">
      <div className="anomaly-head">
        <h3 className="panel-title">Anomaly detection</h3>
        <span className={`pill ${d.is_anomaly ? 'pill-warn' : 'pill-ok'}`}>{d.is_anomaly ? 'Anomalous' : 'Normal'}</span>
      </div>
      <p className="muted small">IsolationForest score <span className="mono">{d.isolation_score.toFixed(3)}</span>. Each bar shows the current value relative to the healthy baseline median.</p>
      <ul className="ratios">
        {ratios.map(([k, v]) => (
          <li key={k} className={v > 2.5 ? 'hot' : ''}>
            <span>{ratioLabel(k)}</span>
            <div className="bar thin"><div style={{ width: `${Math.min(100, (v / max) * 100)}%` }} /></div>
            <span className="mono num">{v.toFixed(1)}×</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function TracePanel({ spans }: { spans: SpanStats }) {
  const rows = Object.entries(spans);
  return (
    <section className="panel">
      <h2 className="panel-title">Pipeline trace</h2>
      {rows.length === 0 ? (
        <p className="muted small">Span timings appear after the first investigation.</p>
      ) : (
        <table className="trace">
          <thead><tr><th>Span</th><th className="num">Calls</th><th className="num">Avg</th></tr></thead>
          <tbody>
            {rows.map(([name, s]) => (
              <tr key={name} title={`${plural(s.calls, 'call')}, max ${ms(s.max_ms)}`}>
                <td className="mono">{name}</td>
                <td className="mono num">{s.calls}</td>
                <td className="mono num">{ms(s.avg_ms)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
