.PHONY: test run-foundation

test:
	python3 -m unittest discover -s services/foundation-service/tests

run-foundation:
	cd services/foundation-service && python3 -m opspilot_foundation.server
