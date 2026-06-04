# OpsPilot

AI operations platform monorepo.

## Backend Foundation

The first backend slice lives in `services/foundation-service`. It is a Python standard-library service with a local, in-memory implementation for:

- identity users and scoped roles
- projects and project membership
- assets with categories, capabilities, and parent asset references
- DEV/QA/QE environments with project, member, asset, and endpoint bindings
- file metadata with local upload/download grant stubs
- credential references with redacted secret handling
- GitLab API profiles, repository listing stubs, and project-to-repository bindings
- agent registry and skill catalog metadata
- model provider configuration through safe credential references
- workflow definitions with versioned node/edge models
- audit events for create/link actions

API contracts are kept in `packages/contracts/openapi/foundation-service.yaml`.

Secrets are accepted only on credential create/rotate requests. API responses return opaque credential references and HMAC fingerprints, while audit events omit raw secrets and fingerprints. GitLab URLs are canonicalized and token-bearing userinfo/query/fragment values are rejected before storage.

## Local Development

Run the testable foundation service:

```sh
make test
make run-foundation
```

Then call the health endpoint:

```sh
curl http://localhost:8080/healthz
```

Run the first web-console slice in another terminal:

```sh
make run-web-console
```

Open `http://localhost:5173`. The console calls the foundation API at `http://localhost:8080` and falls back to local mock inventory only when the API is unavailable.

Optional local infrastructure placeholders are in `infra/docker-compose/docker-compose.yml`:

```sh
docker compose -f infra/docker-compose/docker-compose.yml up -d
```

The current service uses in-memory persistence so the backend slice is immediately testable without third-party dependencies. MySQL migrations and concrete persistence adapters should be added behind the existing repository boundary.
