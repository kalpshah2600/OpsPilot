from __future__ import annotations
import json,os
DATABASE_URL=os.getenv("DATABASE_URL");REDIS_URL=os.getenv("REDIS_URL")
_engine=None;_redis=None
if DATABASE_URL:
    from sqlalchemy import create_engine
    _engine=create_engine(DATABASE_URL,pool_pre_ping=True)
if REDIS_URL:
    from redis import Redis
    _redis=Redis.from_url(REDIS_URL,decode_responses=True)
def init_db():
    if not _engine:return
    from sqlalchemy import text
    with _engine.begin() as c:
        c.execute(text("CREATE TABLE IF NOT EXISTS investigations (incident_id TEXT PRIMARY KEY, payload JSONB NOT NULL, created_at TIMESTAMPTZ DEFAULT now())"));c.execute(text("CREATE TABLE IF NOT EXISTS approvals (id BIGSERIAL PRIMARY KEY, incident_id TEXT, payload JSONB NOT NULL, created_at TIMESTAMPTZ DEFAULT now())"))
def save_investigation(result):
    payload=result.model_dump(mode="json")
    if _redis:_redis.setex(f"incident:{result.incident_id}",3600,json.dumps(payload))
    if _engine:
        from sqlalchemy import text
        with _engine.begin() as c:c.execute(text("INSERT INTO investigations(incident_id,payload) VALUES (:id,CAST(:p AS JSONB)) ON CONFLICT (incident_id) DO UPDATE SET payload=EXCLUDED.payload"),{"id":result.incident_id,"p":json.dumps(payload)})
def save_approval(record):
    if _redis:_redis.setex(f"approval:{record['incident_id']}",3600,json.dumps(record))
    if _engine:
        from sqlalchemy import text
        with _engine.begin() as c:c.execute(text("INSERT INTO approvals(incident_id,payload) VALUES (:id,CAST(:p AS JSONB))"),{"id":record["incident_id"],"p":json.dumps(record)})
