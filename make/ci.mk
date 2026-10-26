# make/ci.mk - CI Monitoring and Log Extraction

ifneq ($(filter logs,$(MAKECMDGOALS)),)
ifeq ($(strip $(RUN)),)
$(error Usage: make logs RUN=<run-id> [STEP="<step-name>"])
endif
endif

.PHONY: ci-watch logs

ci-watch: _preflight
	@SHA=$$(git rev-parse --verify --quiet "$(or $(COMMIT),HEAD)^{commit}") || { \
	  echo "ERROR: '$(or $(COMMIT),HEAD)' is not a known commit. Pass COMMIT=<sha> for a commit that exists locally." >&2; \
	  exit 1; \
	}; \
	if [ -z "$$(ls .github/workflows/*.yml .github/workflows/*.yaml 2>/dev/null)" ]; then \
	  echo "No CI configured - skipping attribution"; \
	  exit 0; \
	fi; \
	if [ -n "$$(git remote)" ] && ! git branch -r --contains "$$SHA" 2>/dev/null | grep -q .; then \
	  echo "CI: commit $$SHA is not on any remote branch, so no run can exist." >&2; \
	  echo "CI: push the commit first, then retry." >&2; \
	  exit 1; \
	fi; \
	STATUS=0; ATTEMPTS=0; WFS=""; \
	while [ -z "$$WFS" ] && [ $$ATTEMPTS -lt $(RETRY_POLLS) ]; do \
	  WFS=$$(gh run list --commit "$$SHA" --json workflowName --jq '.[].workflowName' | sort -u); \
	  [ -n "$$WFS" ] && break; \
	  ATTEMPTS=$$((ATTEMPTS + 1)); \
	  sleep $(RETRY_SLEEP); \
	done; \
	echo "Watching CI for $$SHA after $$ATTEMPTS poll(s)"; \
	if [ -z "$$WFS" ]; then \
	  ELAPSED=$$(( $(RETRY_POLLS) * $(RETRY_SLEEP) )); \
	  echo "CI: no run registered for $$SHA after $${ELAPSED}s - fail-safe block"; \
	  echo "CI: no run registered for $$SHA after $${ELAPSED}s. Wait for CI to start, then retry." >&2; \
	  exit 1; \
	fi; \
	WFLIST=$${TMPDIR:-/tmp}/ci-watch-workflows.$$$$; \
	trap 'rm -f "$$WFLIST"' EXIT; \
	printf '%s\n' "$$WFS" > "$$WFLIST"; \
	while IFS= read -r WF; do \
	  NEW=$$(gh run list --commit "$$SHA" --workflow "$$WF" --json databaseId --jq '.[0].databaseId'); \
	  gh run watch "$$NEW" --exit-status >/dev/null 2>&1 || true; \
	  NEWMETA=$$(gh run view "$$NEW" --json conclusion,jobs --jq '.conclusion, ([.jobs[] | select(.conclusion=="failure") | .name] | sort | join(",")), ([.jobs[] | select(.conclusion=="failure") | .steps[]? | select(.conclusion=="failure") | .name] | sort | join(", "))'); \
	  NEWCONC=$$(printf '%s\n' "$$NEWMETA" | sed -n '1p'); \
	  NEWFAIL=$$(printf '%s\n' "$$NEWMETA" | sed -n '2p'); \
	  NEWSTEPS=$$(printf '%s\n' "$$NEWMETA" | sed -n '3p'); \
	  if [ -n "$$NEWSTEPS" ]; then \
	    echo "$$WF: failing step(s): $$NEWSTEPS (run $$NEW)"; \
	    gh run view "$$NEW" --log-failed 2>/dev/null | awk -F'\t' '{ l=$$3; p=index(l,"Z "); if(p>0)l=substr(l,p+2); gsub(/\x1B\[[0-9;]*[a-zA-Z]/,"",l); gsub(/\^\[\[[0-9;]*[a-zA-Z]/,"",l); if(l ~ /^##\[group\]/ || l ~ /^##\[endgroup\]/) next; gsub(/^##\[error\]/,"Error: ",l); print l }' | tail -n $(DETAIL_LINES) | sed 's/^/    /'; \
	    echo "  view all failed logs: make logs RUN=$$NEW"; \
	    echo "  view specific step:   make logs RUN=$$NEW STEP=\"<step-name>\""; \
	  fi; \
	  if [ "$$NEWCONC" = "success" ]; then \
	    if [ -n "$$NEWFAIL" ]; then \
	      echo "$$WF: PASSED (run=$$NEWCONC) - non-blocking failure(s) [$$NEWFAIL] - triage, does not block"; \
	    else \
	      echo "$$WF: PASSED"; \
	    fi; \
	    continue; \
	  fi; \
	  if [ "$$NEWCONC" != "failure" ]; then \
	    echo "$$WF: BLOCKING (run=$$NEWCONC) - unknown conclusion - fail-safe block"; \
	    echo "$$WF: unknown conclusion '$$NEWCONC' on run $$NEW blocks the session." >&2; \
	    STATUS=1; continue; \
	  fi; \
	  BASE="$(BASE)"; OLD=""; \
	  if [ -n "$$BASE" ]; then \
	    OLD=$$(gh run list --commit "$$BASE" --workflow "$$WF" --json databaseId --jq '.[0].databaseId'); \
	  else \
	    RUNLIST=$${TMPDIR:-/tmp}/ci-watch-runs.$$$$; \
	    gh run list --workflow "$$WF" -L $(BASE_SCAN) --json headSha,databaseId --jq '.[] | "\(.headSha) \(.databaseId)"' > "$$RUNLIST" 2>/dev/null; \
	    for CUR in $$(git rev-list -n $(BASE_DEPTH) "$$SHA^" 2>/dev/null); do \
	      OLD=$$(awk -v sha="$$CUR" '$$1 == sha { print $$2; exit }' "$$RUNLIST"); \
	      if [ -n "$$OLD" ]; then BASE="$$CUR"; break; fi; \
	    done; \
	    rm -f "$$RUNLIST"; \
	  fi; \
	  if [ -z "$$BASE" ]; then \
	    echo "$$WF: BLOCKING failure ($$NEWFAIL) - no run-bearing ancestor (unknown base) - YOUR regression"; \
	    echo "$$WF: no run-bearing ancestor within $(BASE_DEPTH) commits, so the baseline is unknown." >&2; \
	    STATUS=1; continue; \
	  fi; \
	  if [ -z "$$OLD" ]; then \
	    echo "$$WF: BLOCKING failure ($$NEWFAIL) - pinned base has no run (unknown base) - YOUR regression"; \
	    echo "$$WF: pinned base $$BASE carries no run for this workflow." >&2; \
	    STATUS=1; continue; \
	  fi; \
	  OLDMETA=$$(gh run view "$$OLD" --json jobs --jq '(.jobs | length), ([.jobs[] | select(.conclusion=="failure") | .name] | sort | join(","))'); \
	  OLDJOBS=$$(printf '%s\n' "$$OLDMETA" | sed -n '1p'); \
	  if [ "$$OLDJOBS" = "0" ]; then \
	    echo "$$WF: BLOCKING failure ($$NEWFAIL) - base run is job-less (invalid workflow, not green) - YOUR regression"; \
	    echo "$$WF: base run $$OLD carries zero jobs, so it cannot prove a green baseline." >&2; \
	    STATUS=1; continue; \
	  fi; \
	  OLDFAIL=$$(printf '%s\n' "$$OLDMETA" | sed -n '2p'); \
	  SUBSET=$$(awk -v new="$$NEWFAIL" -v old="$$OLDFAIL" 'BEGIN { n=split(new,na,","); m=split(old,oa,","); for (i=1;i<=n;i++) { if (na[i]=="") continue; f=0; for (j=1;j<=m;j++) { if (oa[j]==na[i]) { f=1; break } } if (!f) { print "regression"; exit } } print "pre-existing" }' </dev/null); \
	  if [ "$$SUBSET" = "pre-existing" ]; then \
	    echo "$$WF: pre-existing BLOCKING failure ($$NEWFAIL) - not yours"; \
	  else \
	    echo "$$WF: BLOCKING failure ($$NEWFAIL) - YOUR regression"; \
	    echo "$$WF: YOUR regression - run $$NEW turned these jobs red and base $$BASE did not: $$NEWFAIL" >&2; \
	    STATUS=1; \
	  fi; \
	done < "$$WFLIST"; \
	exit $$STATUS

logs: _preflight
	@if [ -z "$(STEP)" ]; then \
	  gh run view "$(RUN)" --log-failed 2>/dev/null | awk -F'\t' '{ if(j!=$$1||s!=$$2){j=$$1;s=$$2;print "\n["j" > "s"]"} l=$$3; p=index(l,"Z "); if(p>0)l=substr(l,p+2); gsub(/\x1B\[[0-9;]*[a-zA-Z]/,"",l); gsub(/\^\[\[[0-9;]*[a-zA-Z]/,"",l); if(l ~ /^##\[group\]Run /){k=1;next} if(k && l ~ /^##\[endgroup\]/){k=0;next} if(k)next; if(l ~ /^##\[group\]/ || l ~ /^##\[endgroup\]/)next; gsub(/^##\[error\]/,"Error: ",l); print l }'; \
	else \
	  gh run view "$(RUN)" --log 2>/dev/null | awk -F'\t' -v step="$(STEP)" 'index($$2, step) > 0 { if(j!=$$1||s!=$$2){j=$$1;s=$$2;print "\n["j" > "s"]"} l=$$3; p=index(l,"Z "); if(p>0)l=substr(l,p+2); gsub(/\x1B\[[0-9;]*[a-zA-Z]/,"",l); gsub(/\^\[\[[0-9;]*[a-zA-Z]/,"",l); if(l ~ /^##\[group\]Run /){k=1;next} if(k && l ~ /^##\[endgroup\]/){k=0;next} if(k)next; if(l ~ /^##\[group\]/ || l ~ /^##\[endgroup\]/)next; gsub(/^##\[error\]/, "Error: ", l); print l }'; \
	fi
