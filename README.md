# OpsPilot

AI operations platform monorepo.

## Backend Foundation

The first backend slice lives in `services/foundation-service`. It is a Python standard-library service with a local, in-memory implementation for:

- identity users and scoped roles
- projects and project membership
- assets with categories, capabilities, tags, file references, and cycle-safe parent asset references
- DEV/QA/QE environments with project, member, project-owned asset, endpoint, and file-reference bindings
- file metadata and local file-service MVP upload/download/list/delete APIs
- credential references with redacted secret handling
- GitLab API profiles, repository discovery sync/search/pagination, and project-to-repository bindings
- GitLab/VCS branch and merge-request operations plus webhook-event ingestion through a VCS adapter boundary
- file upload sessions, completion state, and local download grants
- agent registry and skill catalog metadata
- model provider configuration through safe credential references
- workflow definitions with versioned node/edge models
- workflow run execution records with ordered step runs and manual status transitions
- runtime task outbox, local agent worker, controlled skill adapter, and fake model gateway boundary
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

The current service uses in-memory persistence by default so the backend slice is immediately testable without third-party dependencies. By default, GitLab calls use the local adapter for deterministic development and tests. Set `OPSPILOT_GITLAB_LIVE=1` before `make run-foundation` to use the standard-library GitLab HTTP adapter; token material still stays behind credential references and is not returned in responses or audit events.

### IAM/Auth Boundary

Protected foundation routes require an `Authorization: Bearer ...` access token. Access tokens are short-lived and backed by persistent user sessions or service identities; refresh tokens/session records and service identity token hashes are stored by the foundation store and survive MySQL-backed service restarts. Missing, malformed, expired, or revoked tokens return `401 authentication_required`; authenticated callers with insufficient Admin/Operator/Viewer permissions return `403 permission_denied`.

For local development, enable the replaceable token issuer explicitly:

```sh
OPSPILOT_AUTH_DEV_ISSUER=1 OPSPILOT_AUTH_TOKEN_SECRET='local-dev-secret' make run-foundation
```

Then issue a local Admin session:

```sh
curl -X POST http://localhost:8080/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"actor_id":"usr_000001","role":"Admin","email":"admin@local.opspilot","name":"Local Admin"}'
```

Use the returned `access_token` on protected calls:

```sh
curl http://localhost:8080/v1/projects \
  -H "Authorization: Bearer $OPSPILOT_ACCESS_TOKEN"
```

Refresh and logout use `/v1/auth/refresh` and `/v1/auth/logout`. Runtime workers and future model/artifact services should use service identities rather than human sessions: Admins create `/v1/service-identities`, store the one-time `service_token` securely, and exchange it at `/v1/service-identities/{serviceIdentityID}/token` for short-lived worker access tokens. That exchange authenticates with the `service_token` body field and does not require a human/Admin bearer session.

The old `X-Actor-ID` / `X-Actor-Role` headers are deprecated compatibility headers. They are ignored unless `OPSPILOT_AUTH_DEV_HEADERS=1` is set, and must not be treated as a production contract.

### Agent Worker

The first real worker process lives in `services/agent-worker`. It uses the foundation API boundary only: claim runtime tasks, heartbeat with the claimed `attempt_token`, call a controlled built-in skill adapter, call the fake model gateway by model provider reference, and callback completion/failure. The worker never reads the credential or secret tables directly, and raw model keys do not enter runtime task, worker output, or audit payloads.

Run the foundation service with auth enabled, create a service identity as an Admin, then exchange the one-time `service_token` for a short-lived worker token:

```sh
curl -X POST http://localhost:8080/v1/service-identities \
  -H 'Content-Type: application/json' -H "Authorization: Bearer $OPSPILOT_ACCESS_TOKEN" \
  -d '{"name":"local-agent-worker","role":"Operator","project_ids":["prj_000001"]}'

curl -X POST http://localhost:8080/v1/service-identities/$SERVICE_ID/token \
  -H 'Content-Type: application/json' \
  -d "{\"service_token\":\"$SERVICE_TOKEN\"}"
```

Start the worker:

```sh
OPSPILOT_FOUNDATION_URL=http://localhost:8080 \
OPSPILOT_WORKER_ACCESS_TOKEN="$OPSPILOT_WORKER_ACCESS_TOKEN" \
make run-agent-worker
```

For smoke tests, add `--once` by running the module directly:

```sh
cd services/agent-worker
OPSPILOT_WORKER_ACCESS_TOKEN="$OPSPILOT_WORKER_ACCESS_TOKEN" python3 -m opspilot_agent_worker --once
```

Claims accept optional `worker_id`, `agent_id`, and `lease_seconds`. Running callbacks act as heartbeats and may renew the lease; if a running task lease expires, the foundation service requeues the task and rotates the attempt token so stale workers cannot complete it later. Skill execution is intentionally limited to deterministic built-in/mock behavior until a signed external skill package loader is designed.

### MySQL Persistence

Set `OPSPILOT_FOUNDATION_MYSQL_DSN` to enable the MySQL-backed foundation store. When the variable is absent or empty, the service falls back to the in-memory store.

Local verification path:

```sh
docker compose -f infra/docker-compose/docker-compose.yml up -d mysql
python3 -m pip install pymysql
OPSPILOT_FOUNDATION_MYSQL_DSN='mysql://opspilot:opspilot@127.0.0.1:3306/opspilot_foundation' make run-foundation
```

The adapter applies SQL migrations from `services/foundation-service/migrations/mysql` at startup, then persists foundation aggregates to normalized InnoDB tables. The docker-compose MySQL service uses a named `mysql_data` volume, so records remain readable after restarting the foundation service or the MySQL container:

```sh
docker compose -f infra/docker-compose/docker-compose.yml restart mysql
OPSPILOT_FOUNDATION_MYSQL_DSN='mysql://opspilot:opspilot@127.0.0.1:3306/opspilot_foundation' make run-foundation
```

Rollback to memory mode by unsetting the DSN:

```sh
unset OPSPILOT_FOUNDATION_MYSQL_DSN
make run-foundation
```

Secrets remain behind the credential boundary. Credential responses include only `secret_ref` and `secret_fingerprint`; audit events store redacted metadata and never include raw secret material. The MySQL schema stores raw secret values only in the `secret_refs` boundary table used by credential and adapter flows.

GitLab MVP flow:

```sh
curl -X POST http://localhost:8080/v1/credentials \
  -H 'Content-Type: application/json' -H "Authorization: Bearer $OPSPILOT_ACCESS_TOKEN" \
  -d '{"provider":"gitlab","name":"GitLab Ops","secret":"glpat-..."}'

curl -X POST http://localhost:8080/v1/gitlab/profiles \
  -H 'Content-Type: application/json' -H "Authorization: Bearer $OPSPILOT_ACCESS_TOKEN" \
  -d '{"name":"Primary GitLab","base_url":"https://gitlab.example.com","credential_ref_id":"cred_000001","webhook_secret":"gitlab-webhook-secret"}'

curl -X POST http://localhost:8080/v1/gitlab/profiles/glp_000003/repositories/sync \
  -H 'Content-Type: application/json' -H "Authorization: Bearer $OPSPILOT_ACCESS_TOKEN" \
  -d '{"search":"platform","page":1,"per_page":20}'

curl 'http://localhost:8080/v1/gitlab/profiles/glp_000003/repositories?search=platform&page=1&per_page=20' \
  -H "Authorization: Bearer $OPSPILOT_ACCESS_TOKEN"

curl -X POST http://localhost:8080/v1/projects/prj_000010/repositories \
  -H 'Content-Type: application/json' -H "Authorization: Bearer $OPSPILOT_ACCESS_TOKEN" \
  -d '{"provider":"gitlab","profile_id":"glp_000003","repository_id":"100"}'

curl -X POST http://localhost:8080/v1/gitlab/profiles/glp_000003/repositories/100/branches \
  -H 'Content-Type: application/json' -H "Authorization: Bearer $OPSPILOT_ACCESS_TOKEN" \
  -d '{"project_id":"prj_000010","branch":"feature/opspilot","ref":"main"}'

curl -X POST http://localhost:8080/v1/gitlab/profiles/glp_000003/repositories/100/merge-requests \
  -H 'Content-Type: application/json' -H "Authorization: Bearer $OPSPILOT_ACCESS_TOKEN" \
  -d '{"project_id":"prj_000010","source_branch":"feature/opspilot","target_branch":"main","title":"OpsPilot change"}'
```

Repository catalogs are owned by GitLab discovery sync. Project repository bindings store only `provider`, `profile_id`, and `repository_id`; branch/MR calls require a bound `project_id` before the stored GitLab API credential is used. GitLab webhook deliveries should send `X-Gitlab-Token`, which is checked against the profile webhook secret, not the outbound API token.

### File Service Storage

The file service stores metadata in the foundation store and file bytes behind an object-storage adapter. Local development uses `LocalFileStorage` and writes objects under `OPSPILOT_FILE_STORAGE_ROOT` when set, otherwise `/tmp/opspilot-foundation-files`.

The storage adapter is selected with `OPSPILOT_OBJECT_STORAGE_ADAPTER`:

- `local` (default): creates the local object root automatically.
- `s3` or `minio`: uses the optional boto3 S3 client against AWS S3 or any MinIO-compatible endpoint. Install it with `python3 -m pip install boto3` before running the service with this adapter. Set `OPSPILOT_S3_BUCKET`, optionally `OPSPILOT_S3_ENDPOINT_URL`, `OPSPILOT_S3_REGION`, and `OPSPILOT_S3_AUTO_CREATE_BUCKET=false` when the bucket must already exist. The local docker-compose MinIO service is reachable at `http://localhost:9000` with root credentials `opspilot` / `opspilot-secret`.

Local MinIO smoke:

```bash
docker compose -f infra/docker-compose/docker-compose.yml up -d minio
python3 -m pip install boto3
OPSPILOT_OBJECT_STORAGE_ADAPTER=minio \
OPSPILOT_S3_ENDPOINT_URL=http://localhost:9000 \
OPSPILOT_S3_BUCKET=opspilot-artifacts \
AWS_ACCESS_KEY_ID=opspilot \
AWS_SECRET_ACCESS_KEY=opspilot-secret \
make run-foundation
```

The API never returns internal storage keys. Upload/download grants and upload sessions expose opaque `opspilot://file-capabilities/...` URLs generated at the storage boundary. Business modules should keep only the returned file `id` or reference fields (`owner_id`, `resource_type`, `resource_id`, `module`). Asset and environment topology records attach files through `file_ids` only.

Test-run artifact ingestion is available at `POST /v1/test-runs/{runID}/artifacts` for Admin/Operator users and service identities. The body accepts one or more base64 artifacts (`junit`, `json`, `html`, or `log`). The service stores each artifact as a `test_run`/`reports` file ref, parses JUnit XML or JSON summaries when present, creates a report, updates the test run status/results, and upserts the `Automated Test Report Gate`. Parser failures keep the raw artifact and create a failed report with `summary.parse_errors`.

```bash
curl -X POST http://localhost:8080/v1/test-runs/trn_000001/artifacts \
  -H 'Content-Type: application/json' -H "Authorization: Bearer $OPSPILOT_ACCESS_TOKEN" \
  -d '{"artifacts":[{"filename":"junit.xml","content_type":"application/xml","artifact_type":"junit","content_base64":"PHRlc3RzdWl0ZSB0ZXN0cz0iMSIgZmFpbHVyZXM9IjAiLz4="}]}'
```

### Asset And Environment Topology

Assets are addressable by `category`, `status`, `parent_id`, `capability`, `tag`, `project_id`, and `environment_id` filters on `GET /v1/assets`. Parent-child assembly rejects self-parenting and indirect cycles, so component assets such as GPUs can be mounted under workstations without creating ambiguous topology graphs.

Environments are project-owned DEV/QA/QE scopes. `GET /v1/environments` supports `project_id`, `type`, `status`, `asset_id`, and `member_id` filters. Environment members must already belong to the project, and environment assets must first be bound to that project through `/v1/projects/{projectID}/assets/{assetID}`. Environment asset/member/file bindings can then be operated through nested `/v1/environments/{environmentID}/...` routes. Environment file binding requires the actor to belong to the project and own the file; exact environment-scoped files are accepted, unbound files are claimed atomically, and files bound to other resources are rejected. Deleting an asset or file removes its references from projects/environments; retiring, archiving, or deletion-marking an asset also clears project/environment asset references.

Local MVP uploads accept base64 JSON content up to `OPSPILOT_MAX_FILE_UPLOAD_BYTES` bytes after decode (default 5 MiB). HTTP request bodies are capped by `OPSPILOT_MAX_REQUEST_BODY_BYTES` (default 8 MiB). Non-admin HTTP callers are scoped to the authenticated actor ID as `owner_id`; admin callers may filter across owners.

MySQL migrations and the concrete persistence adapter live behind the existing repository boundary; HTTP handlers continue to call the store-facing API and do not depend on MySQL driver details.
