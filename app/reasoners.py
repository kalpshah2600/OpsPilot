from __future__ import annotations
import json, os
from dataclasses import dataclass
from .models import Evidence, Hypothesis

@dataclass
class Candidate:
    key:str; label:str; score:float; action:str; rationale:list[str]

ACTIONS={
 "db_pool_exhaustion":"Rollback the suspect pool configuration, then verify connection saturation, error rate and p95 latency recover.",
 "kafka_lag":"Stabilize the consumer group and partition assignment, then verify the backlog drains before scaling further.",
 "memory_leak":"Correlate memory growth with the latest release, capture a memory profile, and use a reversible rollback if release correlation is strong.",
 "healthy":"Continue monitoring; no remediation is recommended.",
 "unknown":"Escalate for human investigation; evidence is insufficient for a safe automated recommendation.",
}
LABELS={"db_pool_exhaustion":"Database connection pool exhaustion","kafka_lag":"Kafka consumer backlog caused by consumer instability","memory_leak":"Checkout service memory exhaustion / probable memory leak","healthy":"No active production incident detected","unknown":"Unknown / insufficient evidence"}

def rule_rank(metrics, evidence, anomaly):
    text=" ".join(e.summary.lower() for e in evidence if e.severity != "info"); out=[]
    def add(key,score,reasons): out.append(Candidate(key,LABELS[key],score,ACTIONS[key],reasons))
    r=[]; s=0
    if metrics.get("postgres.connection_pct",0)>=95:s+=4;r.append("PostgreSQL connections are saturated")
    if any(w in text for w in ["acquiring database connection","connection slots","pool"]):s+=3;r.append("Logs mention DB pool/connection pressure")
    if "db_pool_size" in text:s+=2;r.append("Recent deployment changed DB pool configuration")
    add("db_pool_exhaustion",s,r)
    r=[];s=0
    if metrics.get("kafka.consumer_lag",0)>=10000:s+=5;r.append("Kafka consumer lag is extreme")
    if any(w in text for w in ["rebalancing","consumer group","partition assignment"]):s+=3;r.append("Logs show consumer instability")
    add("kafka_lag",s,r)
    r=[];s=0
    if metrics.get("checkout.memory_pct",0)>=90:s+=5;r.append("Checkout memory is near exhaustion")
    if any(w in text for w in ["oomkill","memory growth","out of memory"]):s+=3;r.append("Logs show OOM/memory growth")
    add("memory_leak",s,r)
    out.sort(key=lambda x:x.score,reverse=True)
    if out[0].score<=1:
        key="unknown" if anomaly.get("is_anomaly") else "healthy"
        return Candidate(key,LABELS[key],1,ACTIONS[key],["No supported root cause has enough evidence"]),out
    return out[0],out

def llm_rank(metrics, evidence, anomaly, baseline):
    from openai import OpenAI
    client=OpenAI(api_key=os.environ["OPENAI_API_KEY"],base_url=os.getenv("OPENAI_BASE_URL") or None)
    payload={"metrics":metrics,"anomaly":anomaly,"evidence":[e.model_dump() for e in evidence],"baseline_hypotheses":[{"key":c.key,"label":c.label,"score":c.score,"rationale":c.rationale} for c in baseline]}
    schema={"type":"object","properties":{"root_cause_key":{"type":"string","enum":["db_pool_exhaustion","kafka_lag","memory_leak","healthy","unknown"]},"confidence":{"type":"number","minimum":0,"maximum":1},"rationale":{"type":"array","items":{"type":"string"}},"alternatives":{"type":"array","items":{"type":"object","properties":{"key":{"type":"string"},"confidence":{"type":"number"}},"required":["key","confidence"]}}},"required":["root_cause_key","confidence","rationale","alternatives"],"additionalProperties":False}
    resp=client.chat.completions.create(model=os.getenv("OPSPILOT_LLM_MODEL","gpt-4o-mini"),temperature=0,messages=[{"role":"system","content":"You are an SRE incident reasoner. Use only supplied evidence. Prefer unknown when evidence is insufficient. Return JSON matching the schema."},{"role":"user","content":json.dumps(payload)}],response_format={"type":"json_schema","json_schema":{"name":"incident_diagnosis","strict":True,"schema":schema}})
    data=json.loads(resp.choices[0].message.content)
    key=data["root_cause_key"]
    hyps=[Hypothesis(key=key,label=LABELS.get(key,key),confidence=data["confidence"],rationale=data["rationale"])]
    for a in data["alternatives"][:3]: hyps.append(Hypothesis(key=a["key"],label=LABELS.get(a["key"],a["key"]),confidence=a["confidence"],rationale=[]))
    return Candidate(key,LABELS.get(key,key),data["confidence"]*10,ACTIONS.get(key,ACTIONS["unknown"]),data["rationale"]),hyps
