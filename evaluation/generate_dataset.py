import json, random
from pathlib import Path
random.seed(27)
base={
 "db_pool_exhaustion":["Why did checkout errors spike?","Investigate database timeouts","Checkout is slow after a deploy","Why are DB connections saturated?"],
 "kafka_lag":["Why are inventory updates delayed?","Investigate the queue backlog","Why is consumer lag increasing?","Inventory events are stale"],
 "memory_leak":["Why does checkout keep restarting?","Investigate memory pressure","Why are containers being OOM killed?","Checkout memory keeps climbing"]}
rows=[]
for scenario,qs in base.items():
  for i in range(20):
    rows.append({"id":f"{scenario}-{i:02d}","scenario":scenario,"question":qs[i%len(qs)],"expected":scenario,"noise":{"latency_jitter":random.randint(-35,35),"extra_info_logs":i%4}})
Path(__file__).with_name('incidents_v2.json').write_text(json.dumps(rows,indent=2))
print(f"wrote {len(rows)} cases")
