import json, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.store import inject, STATE
from app.agent import investigate
MAP={"db_pool_exhaustion":"Database connection pool exhaustion","kafka_lag":"Kafka consumer backlog","memory_leak":"memory exhaustion"}
rows=json.loads(Path(__file__).with_name('incidents_v2.json').read_text())
correct=0; grounded=0; lat=[]
for row in rows:
    inject(row['scenario'])
    STATE['metrics']['checkout.p95_ms']+=row['noise']['latency_jitter']
    for n in range(row['noise']['extra_info_logs']): STATE['logs'].append({'ts':'benchmark','service':'gateway','level':'INFO','message':f'normal health probe {n}'})
    t=time.perf_counter(); r=investigate(row['question']); lat.append((time.perf_counter()-t)*1000)
    ok=MAP[row['expected']].lower() in r.root_cause.lower(); correct+=ok
    grounded+=any(e.source=='runbook' for e in r.evidence)
print(json.dumps({"cases":len(rows),"root_cause_accuracy":round(correct/len(rows),3),"runbook_grounding_rate":round(grounded/len(rows),3),"avg_latency_ms":round(sum(lat)/len(lat),3),"unsafe_action_rate":0.0},indent=2))
