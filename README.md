# OpsPilot V3 — Evidence-grounded incident investigation

OpsPilot is a portfolio-grade incident investigation system that collects telemetry evidence, runs an **IsolationForest** anomaly detector, retrieves operational runbooks, ranks root-cause hypotheses, traces the investigation, and keeps remediation behind explicit human approval.

## Demo

[![OpsPilot demo video](docs/demo/opspilot-cover.png)](https://github.com/kalpshah2600/opspilot/raw/main/docs/demo/opspilot-demo.mp4)

[Watch or download the 58-second demo (MP4, 1080p)](https://github.com/kalpshah2600/opspilot/raw/main/docs/demo/opspilot-demo.mp4): injecting a database pool exhaustion and a Kafka consumer lag incident, reviewing ranked hypotheses and evidence, and approving the proposed remediation.

It has two reasoning modes:

- `rules` (default): deterministic, free, reproducible baseline.
- `openai`: a **real optional OpenAI structured-output adapter** that receives metrics, anomaly output, logs, deployments, retrieved evidence and baseline hypotheses, then returns a constrained diagnosis. If the provider fails, OpsPilot logs the failure and falls back to the deterministic baseline.

The project intentionally does **not** claim that an LLM is required for incident response. The point is to compare a transparent baseline with an LLM-assisted reasoning path on the same evidence.

## What is actually implemented

- FastAPI API and React + TypeScript UI
- Evidence collection from metrics, logs and deployment history
- scikit-learn `IsolationForest` invoked on every investigation
- lexical runbook retrieval with evidence grounding
- deterministic hypothesis baseline with an `unknown` abstention path
- optional OpenAI structured-output hypothesis ranker
- a real MCP server over stdio (`python -m app.mcp_server`) exposing metrics, log search, deployments and runbook search
- PostgreSQL persistence for investigations/approvals when `DATABASE_URL` is configured
- Redis incident/approval cache when `REDIS_URL` is configured
- structured JSON application logs
- human approval records; the portfolio environment intentionally executes **no production mutation**
- Docker Compose for API, UI, PostgreSQL and Redis
- GitHub Actions for backend tests/benchmark and frontend production build

## Run locally

### Docker Compose
```bash
docker compose up --build
```
Open `http://localhost:5173`.

### Python only
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm ci
npm run dev
# production verification
npm run build
```

## LLM reasoning (optional)
The default works without any API key.

```bash
export OPSPILOT_REASONER=openai
export OPENAI_API_KEY=...
export OPSPILOT_LLM_MODEL=gpt-4o-mini
PYTHONPATH=. uvicorn app.main:app --reload
```

`app/reasoners.py` contains the provider call and strict JSON schema. The API response reports which reasoner actually produced the diagnosis.

## MCP
Run the MCP server over stdio:
```bash
PYTHONPATH=. python -m app.mcp_server
```
Tools: `get_metrics`, `search_logs`, `get_deployments`, `search_runbooks`.

## Evaluation
```bash
PYTHONPATH=. python evaluation/run_benchmark_v3.py
```
The benchmark has 60 noisy **known synthetic incidents** across the three implemented demo families plus unseen anomalous cases. Known-case accuracy is reported separately from **unseen abstention**. This is a controlled synthetic benchmark, not production accuracy.

This design avoids a misleading claim that 60/60 on three hand-authored failure families demonstrates general incident intelligence.

## Tests
```bash
PYTHONPATH=. pytest -q
```

## Architecture
```text
React/TypeScript -> FastAPI -> evidence collector
                              |-> IsolationForest
                              |-> logs / metrics / deployments
                              |-> runbook retrieval
                              |-> rules baseline
                              `-> optional OpenAI structured reasoner
                                      |
                               diagnosis + alternatives
                                      |
                               human approval boundary
                                      |
                              PostgreSQL + Redis

MCP stdio server -> metrics / logs / deployments / runbooks
```

## Honest limitations
- The included telemetry is synthetic; this is not connected to a real production environment.
- Runbook retrieval is lexical, not vector/embedding retrieval.
- The deterministic baseline explicitly knows three demo incident families.
- The OpenAI path requires the user's API key and is not exercised by CI.
- PostgreSQL/Redis are optional infrastructure paths; Python-only development can run without them.
- Approval is recorded, but remediation is deliberately not executed.

These constraints are intentional and documented so the repository can be evaluated on what the code actually does.
