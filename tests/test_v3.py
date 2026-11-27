import os
os.environ['OPSPILOT_REASONER']='rules'
from app.store import inject,reset,STATE
from app.agent import investigate
from ml.anomaly_detector import DETECTOR
from app.mcp_server import catalog

def test_isolation_forest_wired():
    inject('db_pool_exhaustion'); r=investigate('why unhealthy')
    assert any(e.source=='ml_anomaly_detector' for e in r.evidence)
    assert DETECTOR.score(STATE['metrics'])['is_anomaly'] is True

def test_unknown_abstention():
    reset();STATE['metrics'].update({'checkout.p95_ms':2200,'checkout.error_rate':.06});STATE['logs'].append({'ts':'x','service':'x','level':'WARN','message':'CPU throttling'})
    assert investigate('why unhealthy').root_cause_key=='unknown'

def test_mcp_is_real_server_entrypoint():
    c=catalog();assert 'stdio' in c['protocol'];assert 'search_runbooks' in c['tools']
