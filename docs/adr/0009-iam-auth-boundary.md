# ADR 0009: IAM/Auth Boundary

## Status

Accepted

## Context

The foundation MVP previously trusted local `X-Actor-ID` and `X-Actor-Role` headers. That was useful for early RBAC tests, but it is not a production identity boundary and cannot support console login, runtime workers, model gateway calls, or artifact ingestion safely.

## Decision

Protected foundation routes now resolve `ActorContext` from `Authorization: Bearer` access tokens. Access tokens are short-lived HMAC-signed tokens backed by persistent user sessions or service identities. User sessions can be issued by the explicit local development issuer, refreshed with a rotating refresh token, and revoked through logout. Service identities are managed by Admin callers and provide a separate worker/service token path so runtime callbacks and later model/artifact services do not reuse human sessions.

The local development issuer is enabled only with `OPSPILOT_AUTH_DEV_ISSUER=1`. Legacy actor headers are ignored unless `OPSPILOT_AUTH_DEV_HEADERS=1` is explicitly set, and remain only as deprecated compatibility for local development and tests.

Admin, Operator, and Viewer permission semantics stay unchanged:

- Admin controls secrets, GitLab profiles, model/agent/skill control plane, service identities, and destructive/archive actions.
- Operator can run workflows, claim/callback runtime tasks, and perform operational file/VCS actions.
- Viewer remains read-only and cannot access high-risk credential/audit surfaces.

## Consequences

Missing, malformed, expired, or revoked tokens return `401 authentication_required`; valid identities without enough permission return `403 permission_denied`. Session refresh hashes and service identity token hashes persist in memory/MySQL stores, while raw token material is returned only on issue/refresh calls and is not written to normal list responses or audit metadata.

Future console login, runtime worker extraction, model gateway, and artifact/report ingestion should consume this bearer-token contract. Durable worker implementations should use service identities and keep the runtime task `attempt_token` as callback idempotency material, not as an authentication substitute.
