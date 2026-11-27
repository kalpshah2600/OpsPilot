from datetime import datetime, timezone

STATE = {
    "scenario": "healthy",
    "metrics": {},
    "logs": [],
    "deployments": [],
    "approvals": [],
}

def now(): return datetime.now(timezone.utc).isoformat()

def reset():
    STATE["scenario"] = "healthy"
    STATE["metrics"] = {
        "checkout.p95_ms": 180.0, "checkout.error_rate": 0.007,
        "postgres.connection_pct": 42.0, "kafka.consumer_lag": 18.0,
        "checkout.memory_pct": 48.0,
    }
    STATE["logs"] = [
        {"ts": now(), "service":"checkout", "level":"INFO", "message":"request completed normally"},
        {"ts": now(), "service":"postgres", "level":"INFO", "message":"connection pool healthy"},
    ]
    STATE["deployments"] = [{"id":"deploy-840", "service":"checkout", "version":"1.8.2", "ts":now(), "changes":"routine dependency update"}]
    return STATE

def inject(scenario: str):
    reset(); STATE["scenario"] = scenario
    if scenario == "db_pool_exhaustion":
        STATE["metrics"].update({"checkout.p95_ms":2410.0,"checkout.error_rate":0.124,"postgres.connection_pct":100.0})
        STATE["logs"] += [
          {"ts":now(),"service":"checkout","level":"ERROR","message":"timeout acquiring database connection from pool"},
          {"ts":now(),"service":"postgres","level":"WARN","message":"remaining connection slots are reserved"},]
        STATE["deployments"].append({"id":"deploy-841","service":"checkout","version":"1.8.3","ts":now(),"changes":"DB_POOL_SIZE changed from 20 to 100 per replica"})
    elif scenario == "kafka_lag":
        STATE["metrics"].update({"checkout.p95_ms":710.0,"checkout.error_rate":0.031,"kafka.consumer_lag":42000.0})
        STATE["logs"].append({"ts":now(),"service":"inventory-consumer","level":"WARN","message":"consumer group is rebalancing repeatedly"})
    elif scenario == "memory_leak":
        STATE["metrics"].update({"checkout.p95_ms":1300.0,"checkout.error_rate":0.082,"checkout.memory_pct":97.0})
        STATE["logs"].append({"ts":now(),"service":"checkout","level":"ERROR","message":"container OOMKill observed after memory growth"})
    else: raise ValueError("unknown scenario")
    return STATE
reset()
