# OpsPilot Web Console

Static first slice for the authenticated operations console. It covers the dense operator workflow from the product handoff:

- authenticated shell with IAM login, bearer token API calls, refresh-token session renewal, primary navigation, global search, project switcher placeholder, refresh, and sign-out
- dashboard setup progress, inventory counts, readiness exceptions, and audit activity
- identity, project, asset, and environment inventory tables with search, filters, detail panels, and create dialogs
- API integration with `http://localhost:8080` foundation endpoints plus explicit local mock / development-header fallback for offline checks

Run locally:

```sh
make run-foundation
make run-web-console
```

Open `http://localhost:5173`.

Auth notes:

- The default console path uses `/v1/auth/login`, stores access and refresh tokens in `sessionStorage`, attaches `Authorization: Bearer ...`, refreshes via `/v1/auth/refresh`, and revokes via `/v1/auth/logout`.
- The "本地模拟 / 开发头模式" checkbox persists `opspilot_auth_dev_headers=1` in `localStorage` and is the only path that sends deprecated `X-Actor-ID` / `X-Actor-Role` headers.
- GOO-56 contract gap: the current OpenAPI does not expose a profile/me endpoint, so the console derives actor ID and role from the issued access-token payload after login or refresh.

Checks:

```sh
node apps/web-console/check-live-empty.js
node apps/web-console/check-credential-sanitization.js
node apps/web-console/check-integration-routes.js
```
