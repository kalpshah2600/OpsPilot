"""Root-cause ranking.

Every supported failure family declares:
  * an anchor: the metric signal that must be present for the family to be diagnosed at all
  * corroborators: cause-specific evidence, at least one of which must also be present
  * the anomalous features it can explain

A family only *qualifies* when its anchor and at least one corroborator are present. This stops a
shared keyword or a single symptom from pulling a rarer failure into a familiar diagnosis. The
``verify`` step applies the same rules to any reasoner's choice, including the LLM's.
"""
from __future__ import annotations
import json, os
from dataclasses import dataclass, field
from .models import Hypothesis

ANOMALY_RATIO = 2.5          # feature ratio vs. healthy baseline that counts as anomalous
AMBIGUITY_RATIO = 0.7        # second qualified family within 70% of the top score -> abstain
UNEXPLAINED_PENALTY = 0.15   # confidence removed per anomalous signal the diagnosis cannot explain

FAMILIES = {
    "db_pool_exhaustion": {
        "label": "Database connection pool exhaustion",
        "action": "Rollback the suspect pool configuration, then verify connection saturation, error rate and p95 latency recover.",
        "anchor": ("postgres.connection_pct", 90, "PostgreSQL connections are saturated"),
        "corroborators": [
            ("logs", ["acquiring database connection", "connection slots", "database connection pool", "db connection pool"], "Logs show database connection pool pressure"),
            ("deployments", ["db_pool_size", "pool configuration"], "Recent deployment changed DB pool configuration"),
        ],
        "explains": {"latency_ratio", "error_ratio", "db_connection_ratio"},
    },
    "kafka_lag": {
        "label": "Kafka consumer backlog caused by consumer instability",
        "action": "Stabilize the consumer group and partition assignment, then verify the backlog drains before scaling further.",
        "anchor": ("kafka.consumer_lag", 10000, "Kafka consumer lag is extreme"),
        "corroborators": [
            ("logs", ["rebalancing", "partition assignment", "consumer group"], "Logs show consumer group instability"),
        ],
        "explains": {"latency_ratio", "error_ratio", "kafka_lag_ratio"},
    },
    "memory_leak": {
        "label": "Checkout service memory exhaustion / probable memory leak",
        "action": "Correlate memory growth with the latest release, capture a memory profile, and use a reversible rollback if release correlation is strong.",
        "anchor": ("checkout.memory_pct", 90, "Checkout memory is near exhaustion"),
        "corroborators": [
            ("logs", ["oomkill", "memory growth", "out of memory"], "Logs show OOM kills or memory growth"),
        ],
        "explains": {"latency_ratio", "error_ratio", "memory_ratio"},
    },
}

ACTIONS = {k: v["action"] for k, v in FAMILIES.items()} | {
    "healthy": "Continue monitoring; no remediation is recommended.",
    "unknown": "Escalate for human investigation; evidence is insufficient for a safe automated recommendation.",
}
LABELS = {k: v["label"] for k, v in FAMILIES.items()} | {
    "healthy": "No active production incident detected",
    "unknown": "Unknown / insufficient evidence",
    "ambiguous": "Multiple plausible causes / needs human review",
}


@dataclass
class Candidate:
    key: str
    label: str
    score: float
    action: str
    rationale: list[str]
    qualified: bool = False
    unexplained: list[str] = field(default_factory=list)


def _text(evidence, source):
    return " ".join(e.summary.lower() for e in evidence if e.source == source and e.severity != "info")


def score_families(metrics, evidence):
    """Score every family. Returns candidates sorted by score, qualified families first."""
    out = []
    for key, fam in FAMILIES.items():
        reasons, missing, score = [], [], 0
        metric, threshold, anchor_reason = fam["anchor"]
        anchor = metrics.get(metric, 0) >= threshold
        if anchor:
            score += 4; reasons.append(anchor_reason)
        else:
            missing.append(f"Missing required signal: {anchor_reason.lower()}")
        corroborated = 0
        for source, phrases, reason in fam["corroborators"]:
            if any(p in _text(evidence, source) for p in phrases):
                score += 3; corroborated += 1; reasons.append(reason)
        if anchor and not corroborated:
            missing.append("No cause-specific evidence corroborates this signal")
        qualified = anchor and corroborated > 0
        # Only list what is missing when something was found; empty families stay quiet.
        rationale = reasons + (missing if reasons else [])
        out.append(Candidate(key, fam["label"], score, fam["action"], rationale, qualified))
    out.sort(key=lambda c: (c.qualified, c.score), reverse=True)
    return out


def unexplained_signals(key, anomaly):
    explains = FAMILIES.get(key, {}).get("explains", set())
    return [k for k, v in anomaly.get("feature_ratios", {}).items() if v > ANOMALY_RATIO and k not in explains]


def decide(candidates, anomaly):
    """Pick a diagnosis from scored candidates, abstaining when the evidence does not support one."""
    qualified = [c for c in candidates if c.qualified]
    if not qualified:
        if anomaly.get("is_anomaly"):
            partial = [r for c in candidates for r in c.rationale if not r.startswith(("Missing", "No cause"))]
            why = ["Telemetry is anomalous but no supported failure family has both its required signal and corroborating evidence"]
            return Candidate("unknown", LABELS["unknown"], 1, ACTIONS["unknown"], why + partial)
        return Candidate("healthy", LABELS["healthy"], 1, ACTIONS["healthy"], ["No anomaly and no supported failure signature"])
    top = qualified[0]
    if len(qualified) > 1 and qualified[1].score >= AMBIGUITY_RATIO * top.score:
        why = [f"Competing causes are both supported: {top.label} and {qualified[1].label}"]
        return Candidate("unknown", LABELS["ambiguous"], 1, ACTIONS["unknown"], why)
    top.unexplained = unexplained_signals(top.key, anomaly)
    return top


def verify(key, candidates, anomaly):
    """Apply the evidence rules to a diagnosis chosen by any reasoner."""
    if key in ("healthy", "unknown"):
        return None
    match = next((c for c in candidates if c.key == key), None)
    if match is None or not match.qualified:
        return Candidate("unknown", LABELS["unknown"], 1, ACTIONS["unknown"],
                         [f"Reasoner proposed '{LABELS.get(key, key)}' but its required evidence is not present"])
    return None


def rule_rank(metrics, evidence, anomaly):
    candidates = score_families(metrics, evidence)
    return decide(candidates, anomaly), candidates


def llm_rank(metrics, evidence, anomaly, baseline):
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=os.getenv("OPENAI_BASE_URL") or None)
    payload = {"metrics": metrics, "anomaly": anomaly, "evidence": [e.model_dump() for e in evidence],
               "baseline_hypotheses": [{"key": c.key, "label": c.label, "score": c.score, "qualified": c.qualified, "rationale": c.rationale} for c in baseline]}
    schema = {"type": "object", "properties": {
        "root_cause_key": {"type": "string", "enum": [*FAMILIES, "healthy", "unknown"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "rationale": {"type": "array", "items": {"type": "string"}},
        "alternatives": {"type": "array", "items": {"type": "object", "properties": {"key": {"type": "string"}, "confidence": {"type": "number"}}, "required": ["key", "confidence"], "additionalProperties": False}}},
        "required": ["root_cause_key", "confidence", "rationale", "alternatives"], "additionalProperties": False}
    resp = client.chat.completions.create(
        model=os.getenv("OPSPILOT_LLM_MODEL", "gpt-4o-mini"), temperature=0,
        messages=[{"role": "system", "content": "You are an SRE incident reasoner. Use only supplied evidence. A failure family needs its required signal and cause-specific corroboration. Prefer unknown when evidence is insufficient or two causes are equally supported. Return JSON matching the schema."},
                  {"role": "user", "content": json.dumps(payload)}],
        response_format={"type": "json_schema", "json_schema": {"name": "incident_diagnosis", "strict": True, "schema": schema}})
    data = json.loads(resp.choices[0].message.content)
    key = data["root_cause_key"]
    hyps = [Hypothesis(key=key, label=LABELS.get(key, key), confidence=data["confidence"], rationale=data["rationale"])]
    for a in data["alternatives"][:3]:
        hyps.append(Hypothesis(key=a["key"], label=LABELS.get(a["key"], a["key"]), confidence=a["confidence"], rationale=[]))
    top = Candidate(key, LABELS.get(key, key), data["confidence"] * 10, ACTIONS.get(key, ACTIONS["unknown"]), data["rationale"],
                    qualified=key in FAMILIES)
    top.unexplained = unexplained_signals(key, anomaly)
    return top, hyps
