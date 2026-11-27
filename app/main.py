from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .models import InvestigationRequest, ApprovalRequest
from .investigator import investigate
from .store import STATE, reset, inject, now
from .observability import summary
from .mcp_server import catalog

app=FastAPI(title="OpsPilot API", version="1.0.0", description="Evidence-grounded AI incident investigation demo")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health(): return {"status":"ok","scenario":STATE["scenario"]}

@app.get("/telemetry")
def telemetry(): return STATE

@app.post("/investigate")
def run_investigation(req: InvestigationRequest): return investigate(req.question)

@app.post("/demo/reset")
def demo_reset(): return reset()

@app.post("/demo/incidents/{scenario}")
def demo_incident(scenario: str):
    try: return inject(scenario)
    except ValueError: raise HTTPException(404, "Supported: db_pool_exhaustion, kafka_lag, memory_leak")

@app.post("/approve")
def approve(req: ApprovalRequest):
    record={"incident_id":req.incident_id,"action":req.action,"approved_by":req.approved_by,"ts":now(),"executed":False,"note":"Demo approval recorded. No production action is executed."}
    STATE["approvals"].append(record); return record


@app.get("/observability")
def observability(): return summary()

@app.get("/tools")
def tools_catalog(): return catalog()
