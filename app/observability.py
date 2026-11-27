from collections import defaultdict
from time import perf_counter
TRACE=[]

def traced(name):
    def deco(fn):
        def wrapped(*args,**kwargs):
            start=perf_counter(); ok=True
            try: return fn(*args,**kwargs)
            except Exception: ok=False; raise
            finally: TRACE.append({"span":name,"latency_ms":round((perf_counter()-start)*1000,3),"ok":ok})
        return wrapped
    return deco

def summary():
    groups=defaultdict(list)
    for x in TRACE: groups[x['span']].append(x['latency_ms'])
    return {k:{"calls":len(v),"avg_ms":round(sum(v)/len(v),3),"max_ms":max(v)} for k,v in groups.items()}
