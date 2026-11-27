from .store import STATE
from .runbooks import RUNBOOKS
from .models import Evidence

def metrics_tool():
    out=[]
    for k,v in STATE["metrics"].items():
        sev="critical" if ("error_rate" in k and v>0.05) or ("connection_pct" in k and v>90) or ("consumer_lag" in k and v>10000) or ("memory_pct" in k and v>90) else "warning" if ("p95" in k and v>500) else "info"
        out.append(Evidence(source="metrics", summary=k, value=v, severity=sev))
    return out

def logs_tool():
    return [Evidence(source="logs", summary=f'{x["service"]}: {x["message"]}', severity="critical" if x["level"]=="ERROR" else "warning" if x["level"]=="WARN" else "info") for x in STATE["logs"]]

def deployments_tool():
    return [Evidence(source="deployments", summary=f'{d["id"]} {d["service"]} {d["version"]}: {d["changes"]}', severity="warning") for d in STATE["deployments"][-2:]]

def runbook_tool(topic):
    text=RUNBOOKS.get(topic,"No matching runbook")
    return [Evidence(source="runbook", summary=text, severity="info")]
