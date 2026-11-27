"""Deterministic synthetic benchmark cases.

Categories
  known      supported failure families with randomized severity, partial evidence and noise
  near_miss  failures that share symptoms or keywords with a known family but have a different cause
  unseen     anomalous failures from families the system does not model
  compound   two supported failures at once (no single safe diagnosis)
  unexplained a supported failure plus an anomalous signal it cannot explain
  healthy    normal telemetry with jitter and benign noise
  edge       hard cases chosen to expose the limits of the current rules (reported, not thresholded)

Each case is a dict: id, category, expected key, metrics overrides, logs, deployments.
"""
import random

BASE_METRICS = {"checkout.p95_ms": 180.0, "checkout.error_rate": 0.007, "postgres.connection_pct": 42.0,
                "kafka.consumer_lag": 18.0, "checkout.memory_pct": 48.0}

NOISE_LOGS = [
    ("gateway", "INFO", "health probe ok"),
    ("checkout", "INFO", "request completed normally"),
    ("gateway", "WARN", "slow client closed connection early"),
    ("search", "INFO", "index refresh completed"),
    ("auth", "WARN", "token refresh retried once"),
]


def log(service, level, message):
    return {"ts": "bench", "service": service, "level": level, "message": message}


def deploy(i, changes, service="checkout"):
    return {"id": f"deploy-{900 + i}", "service": service, "version": f"2.{i % 10}.0", "ts": "bench", "changes": changes}


def noise(rng):
    return [log(*rng.choice(NOISE_LOGS)) for _ in range(rng.randint(0, 3))]


def symptoms(rng, p95=(800, 2500), err=(0.03, 0.12)):
    return {"checkout.p95_ms": round(rng.uniform(*p95)), "checkout.error_rate": round(rng.uniform(*err), 3)}


def nonempty_subset(rng, items):
    while True:
        picked = [x for x in items if rng.random() < 0.6]
        if picked:
            return picked


# ---------- generators ----------

def db_pool(rng, i):
    m = symptoms(rng, (1500, 2800), (0.06, 0.15)) | {"postgres.connection_pct": rng.choice([93, 96, 98, 100])}
    corr = nonempty_subset(rng, ["log_acquire", "log_slots", "deploy"])
    logs, deps = noise(rng), []
    if "log_acquire" in corr: logs.append(log("checkout", "ERROR", "timeout acquiring database connection from pool"))
    if "log_slots" in corr: logs.append(log("postgres", "WARN", "remaining connection slots are reserved"))
    if "deploy" in corr: deps.append(deploy(i, f"DB_POOL_SIZE changed from 20 to {rng.choice([60, 80, 100])} per replica"))
    return m, logs, deps


def kafka(rng, i):
    m = symptoms(rng, (600, 950), (0.02, 0.05)) | {"kafka.consumer_lag": rng.randint(12000, 60000)}
    msg = rng.choice(["consumer group is rebalancing repeatedly", "partition assignment changed 14 times in 5 minutes",
                      "consumer group inventory-consumer lost members during rebalance"])
    return m, noise(rng) + [log("inventory-consumer", "WARN", msg)], []


def memory(rng, i):
    m = symptoms(rng, (900, 1500), (0.05, 0.10)) | {"checkout.memory_pct": rng.randint(91, 99)}
    msg = rng.choice(["container OOMKill observed after memory growth", "out of memory: killed process 4121 (java)",
                      "heap memory growth of 40MB/min since last release"])
    return m, noise(rng) + [log("checkout", "ERROR", msg)], []


KNOWN = {"db_pool_exhaustion": db_pool, "kafka_lag": kafka, "memory_leak": memory}


def near_misses(rng, i):
    """Each returns (name, metrics, logs, deployments). Expected answer for all: unknown."""
    return [
        ("thread_pool_exhaustion", symptoms(rng, (1500, 2600), (0.06, 0.12)),
         noise(rng) + [log("checkout", "ERROR", "worker thread pool exhausted, rejecting requests")],
         [deploy(i, "enable synchronous fraud check on payment path")]),
        ("db_lock_contention", symptoms(rng, (1500, 2600), (0.05, 0.10)) | {"postgres.connection_pct": rng.randint(92, 99)},
         noise(rng) + [log("postgres", "ERROR", "lock wait timeout exceeded on orders table")], []),
        ("kafka_slow_downstream", symptoms(rng, (600, 900), (0.02, 0.04)) | {"kafka.consumer_lag": rng.randint(12000, 40000)},
         noise(rng) + [log("inventory-consumer", "WARN", "downstream write latency 4.2s, processing slowed")], []),
        ("kafka_producer_backfill", symptoms(rng, (550, 800), (0.02, 0.04)) | {"kafka.consumer_lag": rng.randint(15000, 30000)},
         noise(rng) + [log("orders-producer", "WARN", "backfill job publishing 2M historical events")], []),
        ("memory_cache_warmup", symptoms(rng, (600, 900), (0.02, 0.04)) | {"checkout.memory_pct": rng.randint(90, 94)},
         noise(rng) + [log("checkout", "WARN", "cache warm-up after release, heap usage high")], []),
    ]


UNSEEN = [
    ("cpu_saturation", "checkout", "CPU throttling at 98% of quota"),
    ("dependency_timeout", "payment-gateway", "upstream payment provider timed out after 5000ms"),
    ("disk_pressure", "node-7", "disk pressure detected, evicting pods"),
    ("dns_failure", "checkout", "DNS resolution failed for inventory.internal"),
    ("tls_expiry", "payment-client", "TLS handshake failed: certificate expired"),
    ("provider_rate_limit", "payment-client", "429 Too Many Requests from payment provider"),
]


def build_cases(seed=7):
    rng = random.Random(seed)
    cases = []

    def add(cid, category, expected, metrics, logs, deps, **extra):
        cases.append({"id": cid, "category": category, "expected": expected, "metrics": metrics,
                      "logs": logs, "deployments": deps, **extra})

    for key, gen in KNOWN.items():
        for i in range(20):
            add(f"{key}-{i:02d}", "known", key, *gen(rng, i))

    for i in range(4):
        for name, m, logs, deps in near_misses(rng, i):
            add(f"{name}-{i}", "near_miss", "unknown", m, logs, deps)

    for name, svc, msg in UNSEEN:
        for i in range(3):
            add(f"{name}-{i}", "unseen", "unknown", symptoms(rng), noise(rng) + [log(svc, rng.choice(["ERROR", "WARN"]), msg)], [])

    for i in range(5):
        m1, l1, d1 = db_pool(rng, i)
        m2, l2, _ = memory(rng, i)
        add(f"compound-db-memory-{i}", "compound", "unknown", m1 | {"checkout.memory_pct": m2["checkout.memory_pct"]}, l1 + l2[-1:], d1)

    for i in range(5):
        m, logs, deps = db_pool(rng, i)
        add(f"db-plus-unexplained-lag-{i}", "unexplained", "db_pool_exhaustion",
            m | {"kafka.consumer_lag": rng.randint(20000, 50000)}, logs, deps, must_flag="kafka_lag_ratio")

    for i in range(10):
        m = {"checkout.p95_ms": rng.randint(172, 190), "checkout.error_rate": round(rng.uniform(0.005, 0.009), 3),
             "postgres.connection_pct": rng.randint(38, 46), "kafka.consumer_lag": rng.randint(12, 28),
             "checkout.memory_pct": rng.randint(45, 51)}
        add(f"healthy-{i}", "healthy", "healthy", m, noise(rng), [deploy(i, "routine dependency update")] if i % 2 else [])

    # Edge cases: written to show where the stricter rules trade recall for safety, or still fail.
    for i in range(5):
        m = symptoms(rng, (1200, 2200), (0.05, 0.10)) | {"postgres.connection_pct": rng.randint(84, 89)}
        add(f"edge-db-below-threshold-{i}", "edge", "db_pool_exhaustion", m,
            noise(rng) + [log("checkout", "ERROR", "timeout acquiring database connection from pool")], [],
            note="Real pool exhaustion, but Postgres sits just under the 90% anchor")
    for i in range(5):
        m = symptoms(rng, (550, 800), (0.02, 0.04)) | {"kafka.consumer_lag": rng.randint(7000, 9800)}
        add(f"edge-kafka-below-threshold-{i}", "edge", "kafka_lag", m,
            noise(rng) + [log("inventory-consumer", "WARN", "consumer group is rebalancing repeatedly")], [],
            note="Real consumer instability, but lag is under the 10,000 anchor")
    for i in range(5):
        m = symptoms(rng, (1500, 2600), (0.05, 0.10)) | {"postgres.connection_pct": rng.randint(95, 100)}
        add(f"edge-lock-contention-fills-pool-{i}", "edge", "unknown", m,
            noise(rng) + [log("postgres", "ERROR", "lock wait timeout exceeded on orders table"),
                          log("postgres", "WARN", "remaining connection slots are reserved")], [],
            note="Lock contention is the cause, but it also produces pool-exhaustion evidence")

    return cases
