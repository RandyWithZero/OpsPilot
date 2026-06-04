# ADR 0002: Credential References and GitLab Adapter Boundary

## Status

Accepted

## Context

OpsPilot needs GitLab API key profile management and project-to-repository binding without leaking API keys through logs, responses, audit events, or frontend-facing contracts. The current foundation service is still an in-memory local MVP, so it needs a testable credential-reference pattern that can later be replaced by KMS or a dedicated secret manager.

## Decision

Credential create/update accepts secret material only as write-only request input. The local MVP stores the secret only in an internal volatile secret-store abstraction and returns a credential reference, opaque secret reference ID, and HMAC-SHA256 fingerprint. Audit events include provider metadata only, never raw secret values or fingerprints.

GitLab integration starts with an adapter boundary exposed as GitLab profiles and repository listing. GitLab base URLs and repository URLs are parsed and canonicalized before storage; URLs with userinfo, fragments, or token-like query fields are rejected. The local MVP returns configured repository selections, or deterministic stub repositories when no live selection exists. Project repository bindings store provider/profile/repository identity plus denormalized path and sanitized URL.

## Consequences

The API can support frontend and workflow development immediately while keeping secret material out of response bodies and audit events. A future MySQL/KMS implementation should preserve the same response contract and replace the local volatile secret-store internals behind the store boundary.
