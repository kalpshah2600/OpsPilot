from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)

def test_health(): assert client.get("/health").status_code==200

def test_incident_and_investigation():
    assert client.post("/demo/incidents/db_pool_exhaustion").status_code==200
    r=client.post("/investigate",json={"question":"Why did checkout fail?"})
    assert r.status_code==200
    body=r.json(); assert "pool exhaustion" in body["root_cause"].lower(); assert body["requires_approval"] is True

def test_unknown_incident(): assert client.post("/demo/incidents/nope").status_code==404
