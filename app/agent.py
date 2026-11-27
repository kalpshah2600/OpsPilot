from dataclasses import dataclass
from uuid import uuid4
from .store import STATE
from .models import Evidence, InvestigationResult
from .retrieval import retrieve
from .observability import traced

@dataclass
class Candidate:
    key:str; label:str; score:float; action:str

@traced("collect_evidence")
def collect_evidence():
    m=STATE["metrics"]; logs=STATE["logs"]; deps=STATE["deployments"]
    ev=[]
    for k,v in m.items():
        sev="critical" if (("error_rate" in k and v>.05) or ("connection_pct" in k and v>90) or ("consumer_lag" in k and v>10000) or ("memory_pct" in k and v>90)) else "warning" if ("p95" in k and v>500) else "info"
        ev.append(Evidence(source="metrics",summary=k,value=v,severity=sev))
    for x in logs:
        ev.append(Evidence(source="logs",summary=f'{x["service"]}: {x["message"]}',severity="critical" if x["level"]=="ERROR" else "warning" if x["level"]=="WARN" else "info"))
    for d in deps[-3:]: ev.append(Evidence(source="deployments",summary=f'{d["id"]} {d["service"]} {d["version"]}: {d["changes"]}',severity="warning"))
    return ev

def _contains(text,*words): return any(w in text for w in words)

@traced("diagnose")
def diagnose(evidence):
    m=STATE["metrics"]; text=" ".join(e.summary.lower() for e in evidence)
    candidates=[]
    db=0
    if m.get("postgres.connection_pct",0)>=95: db+=4
    if _contains(text,"acquiring database connection","connection slots","pool"): db+=3
    if _contains(text,"db_pool_size","pool configuration"): db+=2
    candidates.append(Candidate("db_pool_exhaustion","Database connection pool exhaustion",db,"Rollback the suspect pool configuration, then verify connection saturation, error rate and p95 latency recover."))
    kafka=0
    if m.get("kafka.consumer_lag",0)>=10000: kafka+=5
    if _contains(text,"rebalancing","consumer group","partition assignment"): kafka+=3
    candidates.append(Candidate("kafka_lag","Kafka consumer backlog caused by consumer instability",kafka,"Stabilize the consumer group and partition assignment, then verify the backlog drains before scaling further."))
    mem=0
    if m.get("checkout.memory_pct",0)>=90: mem+=5
    if _contains(text,"oomkill","memory growth","out of memory"): mem+=3
    candidates.append(Candidate("memory_leak","Checkout service memory exhaustion / probable memory leak",mem,"Correlate memory growth with the latest release, capture a memory profile, and use a reversible rollback if release correlation is strong."))
    candidates.sort(key=lambda x:x.score,reverse=True)
    top=candidates[0]
    if top.score<=1: return Candidate("healthy","No active production incident detected",1,"Continue monitoring; no remediation is recommended."), candidates
    return top,candidates

@traced("retrieve_runbook")
def ground(candidate,evidence):
    query=candidate.label+" "+" ".join(e.summary for e in evidence if e.severity!="info")
    docs=retrieve(query,2)
    return [Evidence(source="runbook",summary=f"{d['title']} (retrieval={d['score']}): {d['text']}",severity="info") for d in docs]

@traced("investigation")
def investigate(question):
    evidence=collect_evidence(); top, ranked=diagnose(evidence); grounded=ground(top,evidence)
    margin=top.score-(ranked[1].score if len(ranked)>1 else 0)
    confidence=min(.98,.55+.05*top.score+.02*max(margin,0)) if top.key!="healthy" else .86
    return InvestigationResult(incident_id=f"inc-{uuid4().hex[:8]}",question=question,root_cause=top.label,confidence=round(confidence,2),evidence=evidence+grounded,recommended_action=top.action,requires_approval=top.key!="healthy",status="proposed" if top.key!="healthy" else "resolved")
