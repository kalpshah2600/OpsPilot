const METRICS: Record<string, { label: string; format: (v: number) => string }> = {
  'checkout.p95_ms': { label: 'Checkout p95 latency', format: (v) => `${Math.round(v).toLocaleString()} ms` },
  'checkout.error_rate': { label: 'Checkout error rate', format: (v) => `${(v * 100).toFixed(1)}%` },
  'postgres.connection_pct': { label: 'Postgres connections used', format: (v) => `${Math.round(v)}%` },
  'kafka.consumer_lag': { label: 'Kafka consumer lag', format: (v) => `${Math.round(v).toLocaleString()} msgs` },
  'checkout.memory_pct': { label: 'Checkout memory used', format: (v) => `${Math.round(v)}%` },
};

export function metricLabel(key: string): string {
  return METRICS[key]?.label ?? key;
}

export function metricValue(key: string, value: unknown): string {
  if (typeof value !== 'number') return String(value ?? '');
  return METRICS[key] ? METRICS[key].format(value) : value.toLocaleString(undefined, { maximumFractionDigits: 3 });
}

const RATIOS: Record<string, string> = {
  latency_ratio: 'Latency',
  error_ratio: 'Error rate',
  db_connection_ratio: 'DB connections',
  kafka_lag_ratio: 'Kafka lag',
  memory_ratio: 'Memory',
};

export function ratioLabel(key: string): string {
  return RATIOS[key] ?? key;
}

export function pct(v: number): string {
  return `${Math.round(v * 100)}%`;
}

export function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`;
}

export function ms(v: number): string {
  return v < 1 ? `${v.toFixed(2)} ms` : `${v.toFixed(1)} ms`;
}

/** Split "service: message" log summaries produced by the API. */
export function splitLog(summary: string): { service: string; message: string } {
  const i = summary.indexOf(': ');
  return i === -1 ? { service: '', message: summary } : { service: summary.slice(0, i), message: summary.slice(i + 2) };
}

/** Parse "deploy-841 checkout 1.8.3: DB_POOL_SIZE changed ..." summaries. */
export function splitDeploy(summary: string): { id: string; service: string; version: string; changes: string } {
  const m = summary.match(/^(\S+)\s+(\S+)\s+(\S+):\s*(.*)$/);
  return m ? { id: m[1], service: m[2], version: m[3], changes: m[4] } : { id: '', service: '', version: '', changes: summary };
}

/** Parse "Title (retrieval=0.298): body" runbook summaries. */
export function splitRunbook(summary: string): { title: string; score: number | null; text: string } {
  const m = summary.match(/^(.*?) \(retrieval=([\d.]+)\):\s*(.*)$/s);
  return m ? { title: m[1], score: Number(m[2]), text: m[3] } : { title: 'Runbook', score: null, text: summary };
}
