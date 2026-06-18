COMPOSE_FILE = infra/docker-compose/docker-compose.yml
COMPOSE_SHARED_TEST_FILE = infra/docker-compose/docker-compose.shared-test.yml

.PHONY: test release-check compose-up compose-test-up compose-smoke compose-web-smoke compose-down run-foundation run-foundation-minio run-agent-worker run-web-console pnpm-install pnpm-lint pnpm-typecheck pnpm-build pnpm-test

test:
	python3 -m unittest discover -s services/foundation-service/tests
	node apps/web-console/check-live-empty.js
	node apps/web-console/check-credential-sanitization.js
	node apps/web-console/check-integration-routes.js
	node apps/web-console/check-scaffold-studio.js

release-check: test
	docker compose -f $(COMPOSE_FILE) config >/dev/null
	docker compose -f $(COMPOSE_FILE) -f $(COMPOSE_SHARED_TEST_FILE) --profile web --profile smoke config >/dev/null

compose-up:
	docker compose -f $(COMPOSE_FILE) up -d --build foundation

compose-test-up:
	OPSPILOT_WEB_PORT=15173 docker compose -f $(COMPOSE_FILE) -f $(COMPOSE_SHARED_TEST_FILE) --profile web up -d --build web-console

compose-smoke:
	OPSPILOT_FOUNDATION_PORT=18080 OPSPILOT_MYSQL_PORT=13306 OPSPILOT_MINIO_API_PORT=19000 OPSPILOT_MINIO_CONSOLE_PORT=19001 docker compose -f $(COMPOSE_FILE) --profile smoke up --build --abort-on-container-exit --exit-code-from release-smoke release-smoke

compose-web-smoke:
	OPSPILOT_WEB_PORT=15173 docker compose -f $(COMPOSE_FILE) -f $(COMPOSE_SHARED_TEST_FILE) --profile web --profile smoke up --build --abort-on-container-exit --exit-code-from web-gateway-smoke web-gateway-smoke

compose-down:
	docker compose -f $(COMPOSE_FILE) --profile smoke --profile web --profile worker --profile queue down

run-foundation:
	cd services/foundation-service && python3 -m opspilot_foundation.server

run-foundation-minio:
	OPSPILOT_MINIO_API_PORT=19000 OPSPILOT_MINIO_CONSOLE_PORT=19001 docker compose -f $(COMPOSE_FILE) up --build foundation

run-agent-worker:
	cd services/agent-worker && python3 -m opspilot_agent_worker

run-web-console:
	cd apps/web-console && python3 -m http.server 5173

pnpm-install:
	corepack enable
	pnpm install

pnpm-lint:
	pnpm lint

pnpm-typecheck:
	pnpm typecheck

pnpm-build:
	pnpm build

pnpm-test:
	pnpm test
