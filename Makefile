.PHONY: test run-foundation run-foundation-minio run-agent-worker run-web-console

test:
	python3 -m unittest discover -s services/foundation-service/tests
	node apps/web-console/check-live-empty.js
	node apps/web-console/check-credential-sanitization.js
	node apps/web-console/check-integration-routes.js

run-foundation:
	cd services/foundation-service && python3 -m opspilot_foundation.server

run-foundation-minio:
	OPSPILOT_MINIO_API_PORT=19000 OPSPILOT_MINIO_CONSOLE_PORT=19001 docker compose -f infra/docker-compose/docker-compose.yml up minio foundation-minio

run-agent-worker:
	cd services/agent-worker && python3 -m opspilot_agent_worker

run-web-console:
	cd apps/web-console && python3 -m http.server 5173
