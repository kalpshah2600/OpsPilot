import os
os.environ["OPSPILOT_REASONER"] = "rules"
from app.store import inject, reset, STATE
from app.agent import investigate, collect_evidence
from app.reasoners import score_families, verify
from evaluation.benchmark import run, THRESHOLDS


def _with(metrics=None, logs=(), deployments=()):
    reset()
    STATE["metrics"].update(metrics or {})
    STATE["logs"] += [{"ts": "t", "service": s, "level": lvl, "message": m} for s, lvl, m in logs]
    STATE["deployments"] += list(deployments)
    return investigate("why unhealthy")


def test_shared_keyword_does_not_pull_in_familiar_failure():
    inject("thread_pool_exhaustion")
    r = investigate("why unhealthy")
    assert r.root_cause_key == "unknown"
    assert r.requires_approval is False and r.status == "escalated"


def test_symptom_without_corroboration_abstains():
    r = _with({"kafka.consumer_lag": 30000, "checkout.p95_ms": 700},
              [("inventory-consumer", "WARN", "downstream write latency 4.2s, processing slowed")])
    assert r.root_cause_key == "unknown"
    kafka = next(h for h in r.hypotheses if h.key == "kafka_lag")
    assert kafka.qualified is False
    assert any("corroborates" in reason for reason in kafka.rationale)


def test_two_supported_failures_abstain():
    inject("db_pool_exhaustion")
    STATE["metrics"]["checkout.memory_pct"] = 97
    STATE["logs"].append({"ts": "t", "service": "checkout", "level": "ERROR", "message": "container OOMKill observed after memory growth"})
    r = investigate("why unhealthy")
    assert r.root_cause_key == "unknown" and "Multiple plausible causes" in r.root_cause


def test_unexplained_signal_is_flagged_and_lowers_confidence():
    inject("db_pool_exhaustion")
    baseline = investigate("why").confidence
    STATE["metrics"]["kafka.consumer_lag"] = 40000
    r = investigate("why")
    assert r.root_cause_key == "db_pool_exhaustion"
    assert "kafka_lag_ratio" in r.unexplained_signals
    assert r.confidence < baseline


def test_verify_rejects_unsupported_choice():
    inject("kafka_lag")
    evidence, anomaly = collect_evidence()
    candidates = score_families(STATE["metrics"], evidence)
    assert verify("db_pool_exhaustion", candidates, anomaly).key == "unknown"
    assert verify("kafka_lag", candidates, anomaly) is None


def test_benchmark_thresholds():
    _, tally, false_abstain, _ = run()
    for key, threshold in THRESHOLDS.items():
        assert tally[key]["current"] / tally[key]["n"] >= threshold, key
    assert false_abstain["current"] == 0
