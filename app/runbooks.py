RUNBOOKS = {
"db_pool_exhaustion": "Database pool exhaustion: confirm connection saturation, inspect recent pool-size/config changes, reduce per-replica pool or increase DB capacity safely, then verify latency and error recovery.",
"kafka_lag": "Kafka consumer lag: inspect lag and rebalance logs, verify consumer health and partition assignment, scale consumers only when partitioning permits, and validate backlog recovery.",
"memory_leak": "Memory pressure: confirm sustained memory growth/OOM events, compare recent releases, capture heap/profile evidence, rollback risky release when appropriate, then verify memory stabilization.",
}
