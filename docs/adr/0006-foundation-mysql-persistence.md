# ADR 0006: Foundation MySQL Persistence Boundary

## Status

Accepted

## Context

The foundation service started with `MemoryStore` to keep the first API slices deterministic and dependency-light. The next backend slices need data to survive service restarts and need a stable schema boundary for assets/environments, runtime orchestration, files, workflows, reports, quality gates, and audit records.

## Decision

Add an optional MySQL adapter selected by `OPSPILOT_FOUNDATION_MYSQL_DSN`. The default remains `MemoryStore` when the DSN is absent.

The adapter preserves the existing store-facing API:

- HTTP handlers keep calling store methods and do not import MySQL driver details.
- Domain validation, credential redaction, file access filters, workflow predecessor snapshots, and audit event creation stay in the existing store behavior.
- The MySQL adapter hydrates state on startup, delegates domain mutations to the store boundary, and persists the resulting snapshot to normalized InnoDB tables.

The first migration creates concrete tables for users/roles, projects/members/repository bindings, assets, environments, files/upload sessions, credential refs and secret boundary records, GitLab profiles/repositories/VCS operations/webhooks, agents/skills/model providers, workflows/versions/runs/step runs, tests/reports/quality gates, and audit events. JSON payload columns preserve the public contract while indexed relational columns provide stable query and foreign-reference boundaries for later adapters.

## Consequences

- Local development remains dependency-free unless MySQL persistence is explicitly enabled.
- MySQL startup applies migrations automatically before loading state.
- Docker Compose uses a named MySQL volume so persisted records can be read after service or container restart.
- Secret material is stored only in the `secret_refs` boundary table and never in audit payloads or normal API responses.
- A later performance pass can replace snapshot persistence with per-aggregate upserts without changing handlers or OpenAPI.
