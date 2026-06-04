.PHONY: test run-foundation run-web-console

test:
	python3 -m unittest discover -s services/foundation-service/tests
	node apps/web-console/check-live-empty.js

run-foundation:
	cd services/foundation-service && python3 -m opspilot_foundation.server

run-web-console:
	cd apps/web-console && python3 -m http.server 5173
