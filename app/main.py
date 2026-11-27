from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .models import InvestigationRequest, ApprovalRequest
from .agent import investigate
from .store import STATE, reset, inject, now
from .observability import summary
from .mcp_server import catalog
from .persistence import init_db,save_investigation,save_approval
from .logging_config import configure_logging
configure_logging()

@asynccontextmanager
async def lifespan(app:FastAPI):
    init_db(); yield
app=FastAPI(title="OpsPilot API",version="3.0.0",description="Evidence-grounded incident investigation with deterministic and optional LLM reasoning",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])
@app.get("/health")
def health():return {"status":"ok","scenario":STATE["scenario"]}
@app.get("/telemetry")
def telemetry():return STATE
@app.post("/investigate")
def run_investigation(req:InvestigationRequest):
    result=investigate(req.question); save_investigation(result); return result
@app.post("/demo/reset")
def demo_reset():return reset()
@app.post("/demo/incidents/{scenario}")
def demo_incident(scenario:str):
    try:return inject(scenario)
    except ValueError:raise HTTPException(404,"Supported: db_pool_exhaustion, kafka_lag, memory_leak, thread_pool_exhaustion")
@app.post("/approve")
def approve(req:ApprovalRequest):
    record={"incident_id":req.incident_id,"action":req.action,"approved_by":req.approved_by,"ts":now(),"executed":False,"note":"Approval recorded. This portfolio environment intentionally executes no production mutation."}; STATE["approvals"].append(record);save_approval(record);return record
@app.get("/observability")
def observability():return summary()
@app.get("/tools")
def tools_catalog():return catalog()
