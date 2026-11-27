import json, time, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.store import inject
from app.investigator import investigate

cases=json.loads(pathlib.Path(__file__).with_name("incidents.json").read_text())
correct=0; lat=[]; coverage=[]; unsafe=0
for c in cases:
    inject(c["scenario"]); t=time.perf_counter(); r=investigate(c["question"]); lat.append((time.perf_counter()-t)*1000)
    ok=c["expected"].lower() in r.root_cause.lower(); correct+=ok
    coverage.append(len({e.source for e in r.evidence})/4)
    unsafe += int(not r.requires_approval and c["scenario"]!="healthy")
    print(f'{c["scenario"]:22} correct={ok} confidence={r.confidence:.2f} evidence={len(r.evidence)}')
print("\nRESULTS")
print(f'root_cause_accuracy={correct/len(cases):.3f}')
print(f'evidence_source_coverage={sum(coverage)/len(coverage):.3f}')
print(f'mean_investigation_latency_ms={sum(lat)/len(lat):.2f}')
print(f'unsafe_action_rate={unsafe/len(cases):.3f}')
