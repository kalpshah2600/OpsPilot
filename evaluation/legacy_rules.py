"""The V3 rule ranker, kept unchanged so the benchmark can compare it with the current rules.

It scores a family from a single symptom or a shared keyword (for example any log containing
"pool"), which is the behaviour the current rules were changed to avoid.
"""


def legacy_rank(metrics, evidence, anomaly):
    text = " ".join(e.summary.lower() for e in evidence if e.severity != "info")
    scores = {}
    s = 0
    if metrics.get("postgres.connection_pct", 0) >= 95: s += 4
    if any(w in text for w in ["acquiring database connection", "connection slots", "pool"]): s += 3
    if "db_pool_size" in text: s += 2
    scores["db_pool_exhaustion"] = s
    s = 0
    if metrics.get("kafka.consumer_lag", 0) >= 10000: s += 5
    if any(w in text for w in ["rebalancing", "consumer group", "partition assignment"]): s += 3
    scores["kafka_lag"] = s
    s = 0
    if metrics.get("checkout.memory_pct", 0) >= 90: s += 5
    if any(w in text for w in ["oomkill", "memory growth", "out of memory"]): s += 3
    scores["memory_leak"] = s
    key, top = max(scores.items(), key=lambda kv: kv[1])
    if top <= 1:
        return "unknown" if anomaly.get("is_anomaly") else "healthy"
    return key
