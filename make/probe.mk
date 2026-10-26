# make/probe.mk - Remote Probing Protocol (RPP)

ifneq ($(filter probe,$(MAKECMDGOALS)),)
ifeq ($(strip $(REASON)),)
$(error Usage: make probe REASON="<reason>")
endif
endif

.PHONY: probe

probe: _preflight
	git add -f spikes/debug/probe.sh
	git commit -m "debug: probe" --no-verify --allow-empty
	git push
	@SHA=$$(git rev-parse HEAD); \
	gh workflow run debug.yml --field reason="$(REASON)" || { echo "Probe: workflow dispatch failed." >&2; exit 1; }; \
	RUN_ID=""; ATTEMPTS=0; \
	while [ -z "$$RUN_ID" ] && [ $$ATTEMPTS -lt $(RETRY_POLLS) ]; do \
	  RUN_ID=$$(gh run list --workflow debug.yml -L 10 --json databaseId,headSha --jq "[.[] | select(.headSha == \"$$SHA\")][0].databaseId"); \
	  [ -n "$$RUN_ID" ] && break; \
	  ATTEMPTS=$$((ATTEMPTS + 1)); \
	  sleep $(RETRY_SLEEP); \
	done; \
	if [ -z "$$RUN_ID" ]; then \
	  echo "Probe: no run registered for $$SHA after $$(( $(RETRY_POLLS) * $(RETRY_SLEEP) ))s." >&2; \
	  exit 1; \
	fi; \
	echo "Probe: watching run $$RUN_ID for $$SHA"; \
	gh run watch "$$RUN_ID" --exit-status >/dev/null 2>&1 || true; \
	gh run download "$$RUN_ID" --name probe-result --dir spikes/debug >/dev/null 2>&1 || true; \
	cat spikes/debug/probe_output.txt 2>/dev/null || echo "(no output file)"
