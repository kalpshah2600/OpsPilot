# OpsPilot V2 design

OpsPilot V2 is an evidence-first incident investigation portfolio system. The diagnostic layer never reads the injected scenario label. It collects metrics, logs and deployment history, scores competing root-cause hypotheses, retrieves relevant runbooks, and proposes a reversible response behind a human approval boundary.

## Agent flow
1. Collect observable evidence.
2. Score database, Kafka and memory hypotheses.
3. Retrieve operational knowledge using local lexical retrieval.
4. Return root cause, confidence, evidence trail and proposed remediation.
5. Require explicit human approval. The demo never executes a production mutation.
6. Trace agent stages and expose latency/call summaries.

## Tool boundary
`app/mcp_server.py` publishes MCP-compatible JSON-schema tool contracts for metrics, logs, deployments and runbook retrieval. The transport/third-party MCP SDK is intentionally optional so the repository remains runnable without credentials or external services.

## Evaluation
`evaluation/incidents_v2.json` contains 60 deterministic synthetic cases across database pool exhaustion, Kafka lag and memory exhaustion. Cases include latency jitter and irrelevant INFO logs. `run_benchmark_v2.py` reports root-cause accuracy, grounding rate, average local diagnostic latency and unsafe-action rate.

This benchmark measures only the included synthetic failure families. It must not be represented as production accuracy.
