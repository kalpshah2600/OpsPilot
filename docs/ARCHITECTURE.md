# Architecture decisions

## Deterministic core first
The demo works without an LLM key. Evidence collection and incident classification are deterministic, making evaluation reproducible. An LLM can later be added for planning/synthesis without granting it authority to invent evidence.

## Evidence before conclusion
Every investigation calls metrics, logs, deployment history, and runbook retrieval. The result exposes the evidence trail instead of returning an opaque answer.

## Human-in-the-loop
Investigation and remediation are separate operations. A diagnosis can propose rollback/configuration changes but cannot execute them. This is the right boundary for a portfolio demonstration of agentic actions.

## Production extensions
Replace the in-memory store with Prometheus/OpenTelemetry, Loki/CloudWatch, PostgreSQL, GitHub deployment APIs, and a vector database. Add OAuth/RBAC, policy enforcement, secrets management, audit logs, retries/timeouts, tracing, and canary remediation.
