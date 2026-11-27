from __future__ import annotations
import numpy as np
from sklearn.ensemble import IsolationForest

METRIC_NAMES=["checkout.p95_ms","checkout.error_rate","postgres.connection_pct","kafka.consumer_lag","checkout.memory_pct"]
BASELINE=np.array([
 [170,.006,38,15,45],[185,.008,44,22,49],[176,.005,40,12,46],[192,.009,47,28,51],
 [181,.007,42,18,48],[188,.006,41,20,47],[174,.008,45,17,50],[183,.007,39,25,46],
 [179,.006,43,14,49],[190,.009,46,30,52],[172,.005,37,11,44],[186,.007,42,19,48],
],dtype=float)

class TelemetryAnomalyDetector:
    def __init__(self):
        self.model=IsolationForest(n_estimators=100,contamination=.08,random_state=42).fit(BASELINE)
    def score(self, metrics:dict[str,float]):
        row=np.array([[float(metrics.get(k,0)) for k in METRIC_NAMES]])
        raw=float(-self.model.score_samples(row)[0])
        pred=int(self.model.predict(row)[0])
        ratios={
          "latency_ratio": row[0,0]/np.median(BASELINE[:,0]),
          "error_ratio": row[0,1]/np.median(BASELINE[:,1]),
          "db_connection_ratio": row[0,2]/np.median(BASELINE[:,2]),
          "kafka_lag_ratio": row[0,3]/np.median(BASELINE[:,3]),
          "memory_ratio": row[0,4]/np.median(BASELINE[:,4]),
        }
        return {"is_anomaly":bool(pred==-1 or max(ratios.values())>2.5),"isolation_score":round(raw,4),"feature_ratios":{k:round(float(v),2) for k,v in ratios.items()}}

DETECTOR=TelemetryAnomalyDetector()


def robust_zscore(values):
    x=np.asarray(values,dtype=float); med=np.median(x); mad=np.median(np.abs(x-med))
    if mad==0:return np.zeros_like(x)
    return 0.6745*(x-med)/mad

def detect_anomalies(values,threshold=3.5):
    z=robust_zscore(values)
    return [{"index":int(i),"value":float(values[i]),"score":float(abs(z[i]))} for i in np.where(np.abs(z)>threshold)[0]]
