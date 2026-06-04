# OpsPilot Web Console

Static first slice for the authenticated operations console. It covers the dense operator workflow from the product handoff:

- authenticated shell with primary navigation, global search, project switcher placeholder, refresh, and sign-out
- dashboard setup progress, inventory counts, readiness exceptions, and audit activity
- identity, project, asset, and environment inventory tables with search, filters, detail panels, and create dialogs
- API integration with `http://localhost:8080` foundation endpoints plus local mock fallback for offline development

Run locally:

```sh
make run-foundation
make run-web-console
```

Open `http://localhost:5173`.
