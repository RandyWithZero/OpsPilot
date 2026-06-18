# Testing Standards

## Required Layers

- Unit tests for pure domain logic, schema transforms, permission checks, parsers, and utility functions.
- Integration tests for service boundaries, persistence adapters, and API contracts.
- Contract checks for OpenAPI or generated clients.
- Component or browser smoke tests for critical UI states.
- AI eval fixtures for prompt/tool behavior once AI provider integrations are introduced.

## Root Commands

Run these before requesting review:

```sh
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

Run integration and smoke checks when touching service boundaries:

```sh
pnpm test:integration
make release-check
```
