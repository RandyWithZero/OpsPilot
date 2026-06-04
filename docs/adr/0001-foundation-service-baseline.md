# ADR 0001: Foundation Service Baseline

## Status

Accepted

## Context

OpsPilot needs a microservice-oriented monorepo, but the repository started empty. The first implementation slice needs local testability and stable API contracts for identity, projects, assets, environments, and audit events before the platform is split into independently deployable services.

## Decision

Start with a Python standard-library `foundation-service` that models the MVP backend slice behind a single HTTP service. Keep explicit package boundaries for domain models, persistence, and HTTP API handlers. Use an in-memory repository for the first local test harness, while keeping the repository interface shaped for a later MySQL-backed implementation.

The monorepo layout follows the architecture handoff:

- `services/` for deployable services.
- `packages/contracts/openapi/` for API contracts.
- `infra/docker-compose/` for local infrastructure.
- `docs/adr/` for architectural decisions.

## Consequences

The first slice is runnable and testable without infrastructure, which lets later agents add MySQL migrations, auth middleware, and service extraction incrementally. The temporary foundation service should not become a shared domain monolith; each domain package must keep ownership boundaries visible so identity, project, asset, and environment concerns can move into dedicated services.
