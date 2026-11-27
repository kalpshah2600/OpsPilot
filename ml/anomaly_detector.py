import numpy as np

def robust_zscore(values):
    x=np.asarray(values,dtype=float); med=np.median(x); mad=np.median(np.abs(x-med))
    if mad==0: return np.zeros_like(x)
    return 0.6745*(x-med)/mad

def detect_anomalies(values, threshold=3.5):
    z=robust_zscore(values)
    return [{"index":int(i),"value":float(values[i]),"score":float(abs(z[i]))} for i in np.where(np.abs(z)>threshold)[0]]

if __name__ == "__main__":
    sample=[175,181,179,185,182,2410]
    print(detect_anomalies(sample))
