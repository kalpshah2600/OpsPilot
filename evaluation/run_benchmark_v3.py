import os,sys,random
sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
os.environ['OPSPILOT_REASONER']='rules'
from app.store import reset,inject,STATE
from app.agent import investigate

CASES=[]
for scenario in ['db_pool_exhaustion','kafka_lag','memory_leak']:
  for i in range(20): CASES.append((scenario,i))
# unseen anomalous cases should abstain rather than force a known diagnosis
UNSEEN=[
 ('cpu_saturation',{'checkout.p95_ms':2200,'checkout.error_rate':.06},'CPU throttling on checkout nodes'),
 ('dependency_timeout',{'checkout.p95_ms':1800,'checkout.error_rate':.09},'upstream payment dependency timed out'),
 ('disk_pressure',{'checkout.p95_ms':900,'checkout.error_rate':.04},'node disk pressure warning'),
]
correct=0;grounded=0
for scenario,i in CASES:
  inject(scenario); random.seed(i)
  # add harmless noise without leaking labels
  STATE['metrics']['noise.metric']=random.random()*10
  STATE['logs'].append({'ts':'noise','service':'sidecar','level':'WARN','message':f'irrelevant retry warning {i}'})
  r=investigate('diagnose incident')
  correct += r.root_cause_key==scenario
  grounded += any(e.source=='runbook' for e in r.evidence)
unknown_ok=0
for name,metrics,msg in UNSEEN:
  reset();STATE['metrics'].update(metrics);STATE['logs'].append({'ts':'x','service':'unknown','level':'WARN','message':msg})
  r=investigate('diagnose unseen incident');unknown_ok += r.root_cause_key=='unknown'
print({'known_cases':len(CASES),'known_accuracy':round(correct/len(CASES),3),'runbook_grounding':round(grounded/len(CASES),3),'unseen_abstention':round(unknown_ok/len(UNSEEN),3),'reasoner':'rules'})
