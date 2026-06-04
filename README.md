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
- GitLab API profiles, repository discovery sync/search/pagination, and project-to-repository bindings
- GitLab/VCS branch and merge-request operations plus webhook-event ingestion through a VCS adapter boundary
- file upload sessions, completion state, and local download grants
- agent registry and skill catalog metadata
- model provider configuration through safe credential references
- workflow definitions with versioned node/edge models
- workflow run execution records with ordered step runs and manual status transitions
- test cases, suites, runs, reports, and quality gates
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

The current service uses in-memory persistence so the backend slice is immediately testable without third-party dependencies. By default, GitLab calls use the local adapter for deterministic development and tests. Set `OPSPILOT_GITLAB_LIVE=1` before `make run-foundation` to use the standard-library GitLab HTTP adapter; token material still stays behind credential references and is not returned in responses or audit events.

GitLab MVP flow:

```sh
curl -X POST http://localhost:8080/v1/credentials \
  -H 'Content-Type: application/json' -H 'X-Actor-ID: usr_000001' -H 'X-Actor-Role: Admin' \
  -d '{"provider":"gitlab","name":"GitLab Ops","secret":"glpat-..."}'

curl -X POST http://localhost:8080/v1/gitlab/profiles \
  -H 'Content-Type: application/json' -H 'X-Actor-ID: usr_000001' -H 'X-Actor-Role: Admin' \
  -d '{"name":"Primary GitLab","base_url":"https://gitlab.example.com","credential_ref_id":"cred_000001","webhook_secret":"gitlab-webhook-secret"}'

curl -X POST http://localhost:8080/v1/gitlab/profiles/glp_000003/repositories/sync \
  -H 'Content-Type: application/json' -H 'X-Actor-ID: usr_000001' -H 'X-Actor-Role: Operator' \
  -d '{"search":"platform","page":1,"per_page":20}'

curl 'http://localhost:8080/v1/gitlab/profiles/glp_000003/repositories?search=platform&page=1&per_page=20'

curl -X POST http://localhost:8080/v1/projects/prj_000010/repositories \
  -H 'Content-Type: application/json' -H 'X-Actor-ID: usr_000001' -H 'X-Actor-Role: Operator' \
  -d '{"provider":"gitlab","profile_id":"glp_000003","repository_id":"100"}'

curl -X POST http://localhost:8080/v1/gitlab/profiles/glp_000003/repositories/100/branches \
  -H 'Content-Type: application/json' -H 'X-Actor-ID: usr_000001' -H 'X-Actor-Role: Operator' \
  -d '{"project_id":"prj_000010","branch":"feature/opspilot","ref":"main"}'

curl -X POST http://localhost:8080/v1/gitlab/profiles/glp_000003/repositories/100/merge-requests \
  -H 'Content-Type: application/json' -H 'X-Actor-ID: usr_000001' -H 'X-Actor-Role: Operator' \
  -d '{"project_id":"prj_000010","source_branch":"feature/opspilot","target_branch":"main","title":"OpsPilot change"}'
```

Repository catalogs are owned by GitLab discovery sync. Project repository bindings store only `provider`, `profile_id`, and `repository_id`; branch/MR calls require a bound `project_id` before the stored GitLab API credential is used. GitLab webhook deliveries should send `X-Gitlab-Token`, which is checked against the profile webhook secret, not the outbound API token.

MySQL migrations and concrete persistence adapters should be added behind the existing repository boundary.
