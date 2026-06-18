# ADR-0010: Monorepo Tooling Foundation

Date: 2026-06-18

## Status

Accepted

## Context

OpsPilot already contains a Python foundation service, a Python agent worker, static web-console assets, contracts, Docker Compose assets, and ADRs. Upcoming frontend, backend, worker, and AI slices need a consistent automation shell without forcing immediate rewrites of working internals.

## Decision

Adopt pnpm workspaces with Turborepo as the root task runner. Keep existing app/service internals in place and add package manifests that expose standard `dev`, `build`, `lint`, `typecheck`, `test`, `test:integration`, and `test:e2e` scripts. Shared TypeScript, ESLint, and Prettier presets live under `packages/config`; future TypeScript slices should extend those presets.

Local infrastructure has a root `docker-compose.yml` for common development dependencies and the existing `infra/docker-compose` stack remains the release/readiness path for current OpsPilot services.

## Consequences

Engineers and AI agents can use one set of root commands while incrementally migrating or adding TypeScript apps and packages. Current Python/static checks continue to run through existing Makefile targets and Turbo package scripts. CI can block on lint, typecheck, tests, build, Compose validation, dependency audit, and filesystem scanning.

New production-affecting settings are not introduced. Secrets remain in local `.env` files or secret managers and are represented only by committed `.env.example` templates.
