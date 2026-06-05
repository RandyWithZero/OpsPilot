# ADR 0008: Workflow Runtime Dispatch Boundary

## Status

Accepted

## Context

Workflow runs and step runs already preserve immutable execution snapshots, including predecessor node IDs. The next runtime slice needs agents and skills to participate in operational workflows without coupling workflow definitions or domain models to Redis, NATS, model credentials, or a concrete worker process.

## Decision

Add `WorkflowRuntimeTask` as the foundation service runtime outbox boundary. Runtime tasks are generated from ready agent step runs only after their snapshotted predecessors are terminal and manual/approval gates are completed. Each task captures agent, skill, model provider reference ID, attempt metadata, timeout hint, and a sanitized input summary containing binding names only. Credential references, model keys, and sensitive binding values stay outside runtime task and audit payloads. Runtime status/list APIs return public task DTOs without attempt tokens; only the authorized claim path returns the concrete attempt token needed for callback idempotency.

The local implementation is an in-memory/snapshot-backed queue adapter:

- `GET /v1/runtime/tasks` lists queued/running/completed task state for local development and console polling.
- `POST /v1/runtime/tasks/claim` lets a fake worker claim the oldest queued task, optionally filtered by agent.
- `POST /v1/runtime/tasks/{taskID}/callback` accepts running/completed/failed callbacks with an attempt token. Identical terminal callbacks are idempotent; stale tokens and illegal status regressions are rejected. Worker output and token-like error strings are sanitized before they are stored on runtime tasks or step runs.
- `POST /v1/runtime/tasks/{taskID}/timeout` rolls a task timeout into a failed step/run.
- `POST /v1/workflow-runs/{runID}/cancel` cancels active runs and queued/running runtime tasks.

Operators can run workflows and operate runtime callbacks. Admins retain control of high-risk agent, skill, model provider, credential, and destructive configuration. Viewers remain read-only.

## Consequences

The current API keeps workflow version and run snapshot semantics stable while enabling an end-to-end local fake worker. A future Redis/NATS worker can replace the queue adapter behind the runtime task boundary by publishing task IDs and fetching task payloads through the callback/status API. Durable worker extraction should preserve private claim tokens, callback sanitization, validated retry/timeout options, sanitized audit metadata, and manual/approval predecessor gating.
