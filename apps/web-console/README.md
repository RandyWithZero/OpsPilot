# OpsPilot Web Console

Static first slice for the authenticated operations console. It covers the dense operator workflow from the product handoff:

- authenticated shell with IAM login, bearer token API calls, refresh-token session renewal, primary navigation, global search, project switcher placeholder, refresh, and sign-out
- dashboard setup progress, inventory counts, readiness exceptions, and audit activity
- identity, project, asset, and environment inventory tables with search, filters, detail panels, and create dialogs
- API integration through same-origin `/v1/*`, `/healthz`, and `/readyz` routes. In Compose, Nginx proxies those routes to `foundation:8080` inside the Docker network so the browser does not call `localhost` or a public IP for backend traffic; explicit local mock / development-header fallback remains available for offline checks.

Run locally:

```sh
make run-foundation
make run-web-console
```

Open `http://localhost:5173`. This direct static-server path is for local UI iteration. To exercise the shared test-environment route where the browser and API use one origin, run:

```sh
make compose-test-up
make compose-web-smoke
```

Open `http://localhost:15173`; `/v1/*`, `/healthz`, and `/readyz` are proxied by Nginx to `foundation:8080` inside the Compose network. The shared test override publishes only the web gateway port; foundation, MySQL, and MinIO stay internal to Compose.

Auth notes:

- The default console path uses `/v1/auth/login` with email, role, and password, stores access and refresh tokens in `sessionStorage`, attaches `Authorization: Bearer ...`, refreshes via `/v1/auth/refresh`, and revokes via `/v1/auth/logout`.
- The API base defaults to same-origin. Set `localStorage.opspilot_api_base` only for direct local development against another origin such as `http://localhost:8080`.
- The login form requires a non-empty password and submits the backend contract `password` field. Empty credentials are blocked before the console shell can load.
- The "本地模拟 / 开发头模式" checkbox persists `opspilot_auth_dev_headers=1` in `localStorage` and is the only path that sends deprecated `X-Actor-ID` / `X-Actor-Role` headers.
- GOO-56 contract gap: the current OpenAPI does not expose a profile/me endpoint, so the console derives actor ID and role from the issued access-token payload after login or refresh.

Checks:

```sh
node apps/web-console/check-live-empty.js
node apps/web-console/check-credential-sanitization.js
node apps/web-console/check-integration-routes.js
```
# OpsPilot Web Console

Static browser console for the foundation service.

## Local Smoke Checks

Run the static checks from the repository root:

```sh
make test
```

The scaffold vertical-slice browser path is captured in `playwright-smoke.spec.js`. When `@playwright/test` is available, serve this directory and run:

```sh
cd apps/web-console
python3 -m http.server 5173
PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 npx playwright test playwright-smoke.spec.js
```
