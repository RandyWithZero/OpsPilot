# Security Boundaries

- Secrets belong in local environment files, CI secret stores, or runtime secret managers, never in source control.
- Backend services own database access, privileged third-party API calls, and AI provider calls with production keys.
- Browser clients receive least-privilege, user-scoped data only.
- Authorization is deny-by-default and should be tested at protected resource boundaries.
- Logs, readiness responses, AI traces, and audit events must redact tokens, DSNs, credentials, storage keys, and raw workflow secret material.
- Uploaded files require size/type limits and a malware-scanning hook before production use.
- CI should run dependency audit and filesystem vulnerability scans before merge.
