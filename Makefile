.PHONY: commit push ci-watch probe test logs

# Always use GNU Make native features for cross-platform compatibility.
# On Windows, ensure a POSIX shell is used for pipeline targets (ci-watch, probe, logs).
ifeq ($(OS),Windows_NT)
    SHELL := bash.exe
    .SHELLFLAGS := -c
endif

# commit - VCP workflow (LOCAL ONLY): stage, advisory pre-commit auto-fix pass, commit.
# Usage:
#   make commit '<type>(<scope>): <description>'
#
# This target is LOCAL-ONLY: it does NOT pull or push. The push is deferred to the
# session Conclusion via `make push` (see below).
#
# The '-' prefix on pre-commit tells Make to ignore a non-zero exit code. This is
# cross-platform (works on both POSIX shells and Windows cmd.exe) and avoids
# shell-specific error-suppression operators (||, &&) that behave differently per OS.
# Pre-commit failure does NOT block the commit (it is an advisory auto-fix pass); the
# post-commit test gate (.githooks/post-commit.py) is the real safety net.

# Target-specific variables capture positional arguments before recipe execution.
# These are Make variables, not shell variables, so they persist across all recipe lines.
# $(wordlist 2,...) drops only the FIRST goal (the target name) and preserves every
# remaining word of the message verbatim -- including the literal word "commit".
#
# `git commit` is invoked WITHOUT `--no-verify`, so Git's own pre-commit hook is the
# real local gate. The local hook set is only formatters + detect-secrets + conflict
# check (see .pre-commit-config.yaml), so running it twice -- this advisory pass plus
# Git's own invocation -- is cheap and accepted.
#
# `git add .` stages ALL local changes, including currently unstaged ones.
commit: ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))

commit:
	$(if $(strip $(ARGS)),,$(error Usage: make commit '<message>'))
	git add .
	-pre-commit run
	git add .
	git commit -m "$(ARGS)"

# push - VCP workflow (Conclusion phase): fast rebase and push.
# Usage:
#   make push
#
# Runs `git pull --rebase` and pushes local commits to remote without blocking on CI.
push:
	git pull --rebase
	git push

# ci-watch - Monitor and attribute CI results for HEAD or an explicit commit.
# Usage:
#   make ci-watch                # watches CI for current HEAD
#   make ci-watch COMMIT=<sha>   # watches CI for a specific commit
#   make ci-watch BASE=<sha>     # pins the comparison baseline to a commit
#
# Attribution answers ONE question: did this push turn a BLOCKING gate red?
# Only push-triggered workflows are attributed. A downstream workflow that
# registers from a workflow_run event is not a regression in this commit.
RETRY_POLLS ?= 10
RETRY_SLEEP ?= 2
DETAIL_LINES ?= 50
BASE_DEPTH ?= 50
BASE ?=

ci-watch:
	@SHA=$$(git rev-parse $${COMMIT:-HEAD}); \
	if [ -z "$$(ls .github/workflows/*.yml .github/workflows/*.yaml 2>/dev/null)" ]; then \
	  echo "No CI configured - skipping attribution"; \
	  exit 0; \
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
	  echo "CI: no run registered for $$SHA after $$(( $(RETRY_POLLS) * $(RETRY_SLEEP) ))s - fail-safe block"; \
	  exit 1; \
	fi; \
	for WF in $$WFS; do \
	  NEW=$$(gh run list --commit "$$SHA" --workflow "$$WF" --json databaseId --jq '.[0].databaseId'); \
	  gh run watch "$$NEW" --exit-status >/dev/null 2>&1 || true; \
	  NEWCONC=$$(gh run view "$$NEW" --json conclusion --jq '.conclusion'); \
	  NEWFAIL=$$(gh run view "$$NEW" --json jobs --jq '[.jobs[] | select(.conclusion=="failure") | .name] | sort | join(",")'); \
	  NEWSTEPS=$$(gh run view "$$NEW" --json jobs --jq '[.jobs[] | select(.conclusion=="failure") | .steps[]? | select(.conclusion=="failure") | .name] | sort | join(", ")'); \
	  if [ -n "$$NEWSTEPS" ]; then \
	    echo "$$WF: failing step(s): $$NEWSTEPS (run $$NEW)"; \
	    gh run view "$$NEW" --log-failed 2>/dev/null | awk -F'\t' '{ l=$$3; p=index(l,"Z "); if(p>0)l=substr(l,p+2); gsub(/\x1B\[[0-9;]*[a-zA-Z]/,"",l); gsub(/\^\[\[[0-9;]*[a-zA-Z]/,"",l); if(l ~ /^##\[group\]/ || l ~ /^##\[endgroup\]/) next; gsub(/^##\[error\]/,"Error: ",l); print l }' | tail -n $(DETAIL_LINES) | sed 's/^/    /'; \
	    echo "  view all failed logs: make logs $$NEW"; \
	    echo "  view specific step:   make logs $$NEW '<step-name>'"; \
	  fi; \
	  if [ "$$NEWCONC" = "success" ]; then \
	    if [ -n "$$NEWFAIL" ]; then \
	      echo "$$WF: PASSED (run=$$NEWCONC) — non-blocking failure(s) [$$NEWFAIL] — triage, does not block"; \
	    else \
	      echo "$$WF: PASSED"; \
	    fi; \
	    continue; \
	  fi; \
	  if [ "$$NEWCONC" != "failure" ]; then \
	    echo "$$WF: BLOCKING (run=$$NEWCONC) — unknown conclusion — fail-safe block"; \
	    STATUS=1; continue; \
	  fi; \
	  BASE="$(BASE)"; CUR="$$SHA"; DEPTH=0; \
	  while [ -z "$$BASE" ] && [ $$DEPTH -lt $(BASE_DEPTH) ]; do \
	    CUR=$$(git rev-parse "$$CUR~1" 2>/dev/null) || break; \
	    [ -n "$$CUR" ] || break; \
	    if [ -n "$$(gh run list --commit "$$CUR" --workflow "$$WF" --json databaseId --jq '.[0].databaseId')" ]; then \
	      BASE="$$CUR"; break; \
	    fi; \
	    DEPTH=$$((DEPTH + 1)); \
	  done; \
	  if [ -z "$$BASE" ]; then \
	    echo "$$WF: BLOCKING failure ($$NEWFAIL) — no run-bearing ancestor (unknown base) — YOUR regression"; \
	    STATUS=1; continue; \
	  fi; \
	  OLD=$$(gh run list --commit "$$BASE" --workflow "$$WF" --json databaseId --jq '.[0].databaseId'); \
	  if [ -z "$$OLD" ]; then \
	    echo "$$WF: BLOCKING failure ($$NEWFAIL) — pinned base has no run (unknown base) — YOUR regression"; \
	    STATUS=1; continue; \
	  fi; \
	  OLDJOBS=$$(gh run view "$$OLD" --json jobs --jq '.jobs | length'); \
	  if [ "$$OLDJOBS" = "0" ]; then \
	    echo "$$WF: BLOCKING failure ($$NEWFAIL) — base run is job-less (invalid workflow, not green) — YOUR regression"; \
	    STATUS=1; continue; \
	  fi; \
	  OLDFAIL=$$(gh run view "$$OLD" --json jobs --jq '[.jobs[] | select(.conclusion=="failure") | .name] | sort | join(",")'); \
	  SUBSET=$$(awk -v new="$$NEWFAIL" -v old="$$OLDFAIL" 'BEGIN { n=split(new,na,","); m=split(old,oa,","); for (i=1;i<=n;i++) { if (na[i]=="") continue; f=0; for (j=1;j<=m;j++) { if (oa[j]==na[i]) { f=1; break } } if (!f) { print "regression"; exit } } print "pre-existing" }' </dev/null); \
	  if [ "$$SUBSET" = "pre-existing" ]; then \
	    echo "$$WF: pre-existing BLOCKING failure ($$NEWFAIL) — not yours"; \
	  else \
	    echo "$$WF: BLOCKING failure ($$NEWFAIL) — YOUR regression"; \
	    STATUS=1; \
	  fi; \
	done; \
	exit $$STATUS

# probe - Remote Probing Protocol: push probe, trigger CI workflow, retrieve logs
# Usage:
#   make probe '<reason>'  # reason is required, appears in workflow dispatch metadata
#
# Target-specific variable captures the reason string.
# The first three lines (add, commit, push) are on separate recipe lines because
# error suppression is not needed here — we want failures to be visible.
# The dispatch/watch section uses a combined shell block because $RUN_ID is a
# shell variable that must persist across multiple commands.

probe: REASON := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))

probe:
	$(if $(strip $(REASON)),,$(error Usage: make probe '<reason>'))
	git add -f spikes/debug/probe.sh
	git commit -m 'debug: probe' --no-verify --allow-empty
	git push
	@gh workflow run debug.yml --field reason='$(REASON)'
	@sleep 5
	@RUN_ID=$$(gh run list --workflow debug.yml -L 1 --json databaseId --jq '.[0].databaseId') && \
	gh run watch "$$RUN_ID" --exit-status >/dev/null 2>&1 && \
	gh run download "$$RUN_ID" --name probe-result --dir spikes/debug >/dev/null 2>&1 && \
	cat spikes/debug/probe_output.txt 2>/dev/null || echo "(no output file)"

# logs - CI Log Extraction: extract logs for all failed steps or a specific step.
# Usage:
#   make logs <run-id>                # extracts logs for ALL failed steps
#   make logs <run-id> '<step-name>'  # extracts logs for a specific step (substring match)
#
# If no step name is provided, extracts all failed steps using `gh run view --log-failed`.
# If a step name is given, matches against the step name using substring matching.
# Strips ANSI escapes and GitHub boilerplate, adding clean [job > step] headers.

logs: LOGS_RUN := $(word 2,$(MAKECMDGOALS))
logs: LOGS_STEP := $(wordlist 3,99,$(MAKECMDGOALS))

logs:
	$(if $(strip $(LOGS_RUN)),,$(error Usage: make logs <run-id> ['<step-name>']))
	@if [ -z "$(LOGS_STEP)" ]; then \
	  gh run view "$(LOGS_RUN)" --log-failed 2>/dev/null | awk -F'\t' '{ if(j!=$$1||s!=$$2){j=$$1;s=$$2;print "\n["j" > "s"]"} l=$$3; p=index(l,"Z "); if(p>0)l=substr(l,p+2); gsub(/\x1B\[[0-9;]*[a-zA-Z]/,"",l); gsub(/\^\[\[[0-9;]*[a-zA-Z]/,"",l); if(l ~ /^##\[group\]Run /){k=1;next} if(k && l ~ /^##\[endgroup\]/){k=0;next} if(k)next; if(l ~ /^##\[group\]/ || l ~ /^##\[endgroup\]/)next; gsub(/^##\[error\]/,"Error: ",l); print l }'; \
	else \
	  gh run view "$(LOGS_RUN)" --log 2>/dev/null | awk -F'\t' -v step="$(LOGS_STEP)" 'index($$2, step) > 0 { if(j!=$$1||s!=$$2){j=$$1;s=$$2;print "\n["j" > "s"]"} l=$$3; p=index(l,"Z "); if(p>0)l=substr(l,p+2); gsub(/\x1B\[[0-9;]*[a-zA-Z]/,"",l); gsub(/\^\[\[[0-9;]*[a-zA-Z]/,"",l); if(l ~ /^##\[group\]Run /){k=1;next} if(k && l ~ /^##\[endgroup\]/){k=0;next} if(k)next; if(l ~ /^##\[group\]/ || l ~ /^##\[endgroup\]/)next; gsub(/^##\[error\]/,"Error: ",l); print l }'; \
	fi

# test - Run the full test suite via the project's designated runner (uv).
#
# Usage:
#   make test
#
# The post-commit hook runs this same suite automatically on every commit;
# this target exposes it as an on-demand command for agents and developers.

test:
	uv run pytest

# Empty recipe absorbs extra arguments without invoking a subshell.
# Always use GNU Make native features for cross-platform compatibility.
%: ;
