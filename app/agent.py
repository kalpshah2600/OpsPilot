from __future__ import annotations
import logging, os
from uuid import uuid4
from .store import STATE
from .models import Evidence, InvestigationResult, Hypothesis
from .retrieval import retrieve
from .observability import traced
from .reasoners import rule_rank, llm_rank, verify, UNEXPLAINED_PENALTY
from ml.anomaly_detector import DETECTOR
log=logging.getLogger("opspilot.agent")

@traced("collect_evidence")
def collect_evidence():
    m=STATE["metrics"]; ev=[]
    anomaly=DETECTOR.score(m)
    verdict="anomalous" if anomaly["is_anomaly"] else "within baseline"
    ev.append(Evidence(source="ml_anomaly_detector",summary=f"IsolationForest: telemetry {verdict} (score {anomaly['isolation_score']})",value=anomaly["isolation_score"],severity="warning" if anomaly["is_anomaly"] else "info",details=anomaly))
    for k,v in m.items():
        sev="critical" if (("error_rate" in k and v>.05) or ("connection_pct" in k and v>90) or ("consumer_lag" in k and v>10000) or ("memory_pct" in k and v>90)) else "warning" if ("p95" in k and v>500) else "info"
        ev.append(Evidence(source="metrics",summary=k,value=v,severity=sev))
    for x in STATE["logs"]: ev.append(Evidence(source="logs",summary=f'{x["service"]}: {x["message"]}',severity="critical" if x["level"]=="ERROR" else "warning" if x["level"]=="WARN" else "info"))
    for d in STATE["deployments"][-3:]: ev.append(Evidence(source="deployments",summary=f'{d["id"]} {d["service"]} {d["version"]}: {d["changes"]}',severity="warning"))
    return ev,anomaly

@traced("retrieve_runbook")
def ground(label,evidence):
    docs=retrieve(label+" "+" ".join(e.summary for e in evidence if e.severity!="info"),2)
    return [Evidence(source="runbook",summary=f"{d['title']} (retrieval={d['score']}): {d['text']}",severity="info") for d in docs]

@traced("investigation")
def investigate(question):
    evidence,anomaly=collect_evidence(); top,ranked=rule_rank(STATE["metrics"],evidence,anomaly); reasoner="rules"
    hyps=[Hypothesis(key=c.key,label=c.label,confidence=min(.99,max(0,c.score/10)),rationale=c.rationale,qualified=c.qualified) for c in ranked]
    if os.getenv("OPSPILOT_REASONER","rules").lower()=="openai" and os.getenv("OPENAI_API_KEY"):
        try: top,hyps=llm_rank(STATE["metrics"],evidence,anomaly,ranked); reasoner="openai"
        except Exception as exc: log.exception("llm_reasoner_failed_falling_back",extra={"error":str(exc)})
    override=verify_step(top.key,ranked,anomaly)
    if override: top=override
    grounded=ground(top.label,evidence)
    unexplained=list(top.unexplained)
    if top.key=="healthy": confidence=.86
    elif top.key=="unknown": confidence=.45
    elif reasoner=="rules": confidence=min(.95,.55+.04*top.score)
    else: confidence=min(.99,max(.01,top.score/10))
    if unexplained: confidence=max(.3,confidence-UNEXPLAINED_PENALTY*len(unexplained))
    actionable=top.key not in {"healthy","unknown"}
    result=InvestigationResult(incident_id=f"inc-{uuid4().hex[:8]}",question=question,root_cause=top.label,root_cause_key=top.key,confidence=round(confidence,2),evidence=evidence+grounded,hypotheses=hyps,recommended_action=top.action,requires_approval=actionable,status="proposed" if actionable else ("escalated" if top.key=="unknown" else "resolved"),reasoner=reasoner,unexplained_signals=unexplained,rationale=list(top.rationale))
    log.info("investigation_complete",extra={"incident_id":result.incident_id,"root_cause_key":result.root_cause_key,"confidence":result.confidence,"reasoner":reasoner,"unexplained":unexplained})
    return result

@traced("verify")
def verify_step(key,ranked,anomaly):
    return verify(key,ranked,anomaly)
