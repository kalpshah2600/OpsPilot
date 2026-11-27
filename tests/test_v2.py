from app.store import inject, STATE
from app.agent import investigate
from app.retrieval import retrieve
from app.mcp_server import catalog

def test_agent_does_not_need_scenario_label():
    inject('db_pool_exhaustion')
    STATE['scenario']='redacted-ground-truth'
    r=investigate('why are checkout errors high?')
    assert 'connection pool exhaustion' in r.root_cause.lower()
    assert r.requires_approval

def test_retrieval():
    docs=retrieve('kafka consumer lag rebalancing')
    assert docs[0]['id']=='rb-kafka-lag'

def test_tool_contracts():
    assert len(catalog()['tools'])>=4
