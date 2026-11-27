from ml.anomaly_detector import detect_anomalies

def test_outlier():
    out=detect_anomalies([100,101,99,102,98,1000])
    assert out and out[-1]["index"]==5
