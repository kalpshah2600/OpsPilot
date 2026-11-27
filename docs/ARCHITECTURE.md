# Architecture

OpsPilot investigates incidents in a small synthetic commerce system. It collects evidence, scores it, ranks root-cause hypotheses, grounds the result in runbooks, and stops at a human approval step. This document describes how the pieces fit together and why they are built this way.

## Investigation flow

1. **Collect evidence.** `app/agent.py` reads current metrics, recent logs and the last three deployments from the telemetry store. The diagnostic code never reads the injected scenario label.
2. **Score anomalies.** `ml/anomaly_detector.py` runs a scikit-learn `IsolationForest`, trained on a healthy baseline, over the current metrics on every investigation. It also reports each metric's ratio to the baseline median. The result is added to the evidence trail.
3. **Rank hypotheses.** `app/reasoners.py` scores each supported failure family (database pool exhaustion, Kafka consumer lag, memory exhaustion) from metric thresholds and log and deployment signals, and records the reasons for each score.
4. **Abstain when unsure.** If no hypothesis has enough support but the anomaly detector still flags the telemetry, the result is `unknown` and the recommended action is escalation to a human. If nothing is anomalous, the result is `healthy`.
5. **Ground in runbooks.** `app/retrieval.py` retrieves the most relevant runbooks with lexical cosine similarity and attaches them to the evidence.
6. **Propose, then wait.** The API returns the root cause, confidence, ranked hypotheses, evidence trail and a recommended action. `POST /approve` records an approval but executes nothing.
7. **Trace.** Each stage is timed by `app/observability.py` and exposed at `GET /observability`.

## Reasoners

- **`rules` (default).** Deterministic and free to run. Every run gives the same answer on the same evidence, which makes evaluation reproducible and the reasoning easy to inspect.
- **`openai` (optional).** Set `OPSPILOT_REASONER=openai` and `OPENAI_API_KEY`. The model receives the metrics, anomaly output, evidence and the rules baseline, and must answer in a strict JSON schema limited to the known failure keys plus `healthy` and `unknown`. If the call fails, OpsPilot logs the error and falls back to the rules result. The API reports which reasoner produced each diagnosis.

The LLM is never the source of evidence. It can only rank what the tools collected.

## MCP tool server

`python -m app.mcp_server` starts a Model Context Protocol server over stdio using the official `mcp` SDK. It exposes `get_metrics`, `search_logs`, `get_deployments` and `search_runbooks`, so other agents can use the same tools the investigator uses.

## Persistence and logging

- **PostgreSQL** stores investigations and approvals as JSONB when `DATABASE_URL` is set.
- **Redis** caches recent investigations and approvals for one hour when `REDIS_URL` is set.
- Without either variable, the app runs fully in memory, which keeps local development and tests dependency-free.
- Application logs are structured JSON (`app/logging_config.py`).

`docker compose up` starts the API, UI, PostgreSQL and Redis together.

## Safety boundary

Investigation and remediation are separate operations. A diagnosis can recommend a rollback or configuration change, but nothing in the codebase executes one. A production version would add authentication, role-based access control, policy checks and an audit trail before any action could run.

## Evaluation

`evaluation/run_benchmark_v3.py` runs 60 synthetic cases across the three supported failure families, with irrelevant noise added to metrics and logs, and reports root-cause accuracy and runbook grounding. It also runs three unseen anomalous cases (CPU saturation, dependency timeout, disk pressure) and checks that the system abstains instead of forcing a known diagnosis.

These numbers measure behaviour on hand-built synthetic data. They are not a claim of production accuracy.

## Known limitations

- Telemetry is synthetic; there is no connection to real Prometheus, log or deployment systems.
- The rules baseline only knows three failure families.
- Runbook retrieval is lexical, not embedding-based.
- The OpenAI path is not exercised in CI because it needs an API key.

## Production path

Replace the in-memory telemetry with OpenTelemetry or Prometheus, a log store and the deployment provider's API; move to embedding-based retrieval over real runbooks; run investigations on async workers; and put remediation behind RBAC, policy enforcement and canary rollouts.
