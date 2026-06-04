# OpsPilot

AI operations platform monorepo.

## Backend Foundation

The first backend slice lives in `services/foundation-service`. It is a Python standard-library service with a local, in-memory implementation for:

- identity users and scoped roles
- projects and project membership
- assets with categories, capabilities, and parent asset references
- DEV/QA/QE environments with project, member, asset, and endpoint bindings
- file metadata and local file-service MVP upload/download/list/delete APIs
- credential references with redacted secret handling
- GitLab API profiles, repository listing stubs, and project-to-repository bindings
- GitLab/VCS operation records and webhook-event ingestion through a local adapter boundary
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

The current service uses in-memory persistence so the backend slice is immediately testable without third-party dependencies. MySQL migrations and concrete persistence adapters should be added behind the existing repository boundary.

### File Service Storage

The file service stores metadata in the foundation store and file bytes behind an object-storage adapter. Local development uses `LocalFileStorage` and writes objects under `OPSPILOT_FILE_STORAGE_ROOT` when set, otherwise `/tmp/opspilot-foundation-files`.

The storage adapter is selected with `OPSPILOT_OBJECT_STORAGE_ADAPTER`:

- `local` (default): creates the local object root automatically.
- `s3` or `minio`: validates `OPSPILOT_S3_BUCKET` and captures endpoint/region/auto-bucket settings (`OPSPILOT_S3_ENDPOINT_URL`, `OPSPILOT_S3_REGION`, `OPSPILOT_S3_AUTO_CREATE_BUCKET`) as the extension boundary for a future concrete S3 client.

The API never returns internal storage keys. Upload/download grants and upload sessions expose opaque `opspilot://file-capabilities/...` URLs generated at the storage boundary. Business modules should keep only the returned file `id` or reference fields (`owner_id`, `resource_type`, `resource_id`, `module`).

Local MVP uploads accept base64 JSON content up to `OPSPILOT_MAX_FILE_UPLOAD_BYTES` bytes after decode (default 5 MiB). HTTP request bodies are capped by `OPSPILOT_MAX_REQUEST_BODY_BYTES` (default 8 MiB). Non-admin HTTP callers are scoped to their `X-Actor-ID` as `owner_id`; admin callers may filter across owners.
