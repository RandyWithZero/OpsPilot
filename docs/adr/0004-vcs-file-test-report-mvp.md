# ADR 0004: VCS, File, and Test Report MVP

## Status

Accepted

## Context

The platform needs a backend slice for GitLab operations, reusable upload/download primitives, and project QA/test/report records. The current foundation service is intentionally local-testable with in-memory repositories and no external service requirements.

## Decision

Keep this milestone inside the existing foundation-service boundaries:

- Record GitLab VCS operations and webhook events through a local adapter boundary that validates configured GitLab profiles and repository selections.
- Model file upload sessions separately from file metadata so later storage adapters can replace `local://` URLs without changing domain behavior.
- Add project-scoped test cases, suites, runs, reports, and quality gates with reference checks for projects, environments, files, and reports.
- Emit audit events with identifiers and status metadata only; raw credential material remains isolated to credential create/rotate requests.

## Consequences

The MVP remains runnable with `make test` and does not perform live GitLab or object-storage calls. Future persistence and external adapters can implement the same store-facing behavior behind the current API contract.
