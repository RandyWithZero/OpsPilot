# ADR 0002: Credential References and GitLab Adapter Boundary

## Status

Accepted

## Context

OpsPilot needs GitLab API key profile management and project-to-repository binding without leaking API keys through logs, responses, audit events, or frontend-facing contracts. The current foundation service is still an in-memory local MVP, so it needs a testable credential-reference pattern that can later be replaced by KMS or a dedicated secret manager.

## Decision

Credential create/update accepts secret material only as write-only request input. The service stores an encrypted local secret value internally and returns only a credential reference, secret reference ID, and short fingerprint. Audit events include provider and fingerprint metadata, never raw secret values.

GitLab integration starts with an adapter boundary exposed as GitLab profiles and repository listing. The local MVP returns configured repository selections, or deterministic stub repositories when no live selection exists. Project repository bindings store provider/profile/repository identity plus denormalized path and URL.

## Consequences

The API can support frontend and workflow development immediately while keeping secret material out of response bodies. A future MySQL/KMS implementation should preserve the same response contract and replace the local encryption/storage internals behind the store boundary.
