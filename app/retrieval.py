import math, re
from collections import Counter
from .knowledge import RUNBOOKS

def _tokens(text): return re.findall(r"[a-z0-9_]+", text.lower())
def _vec(text): return Counter(_tokens(text))
def _cos(a,b):
    common=sum(a[k]*b[k] for k in a.keys() & b.keys())
    na=math.sqrt(sum(v*v for v in a.values())); nb=math.sqrt(sum(v*v for v in b.values()))
    return common/(na*nb) if na and nb else 0.0

def retrieve(query, k=2):
    q=_vec(query)
    scored=[]
    for doc in RUNBOOKS:
        hay=f"{doc['title']} {' '.join(doc['tags'])} {doc['text']}"
        score=_cos(q,_vec(hay))
        scored.append((score,doc))
    return [{**d,"score":round(s,3)} for s,d in sorted(scored,key=lambda x:x[0],reverse=True)[:k]]
