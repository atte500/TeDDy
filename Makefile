.PHONY: commit push probe test logs

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
	@[ -n "$(ARGS)" ] || { echo "Usage: make commit '<message>'"; exit 1; }
	git add .
	-pre-commit run
	git add .
	git commit -m "$(ARGS)"

# push - VCP workflow (Conclusion phase): rebase, push, then attribute CI results.
# Usage:
#   make push
#
# Runs `git pull --rebase`, pushes, then discovers EVERY CI run for the pushed SHA
# (gh run list --commit <sha>) and waits for and reports each workflow with its jobs.
# CI registration lag is tolerated by a bounded retry (RETRY_POLLS x RETRY_SLEEP,
# default 10 x 1s); if no run registers within the budget the target fails safe.
# It answers ONE question: did this push turn a BLOCKING gate red?
# When any step fails (blocking or NOT) the target also prints that step's log
# details (gh run view --log-failed, ANSI/timestamp-stripped, indented, bounded
# to DETAIL_LINES) so the cause is visible without leaving the session.
# The pushed RUN's own conclusion is authoritative -- it already folds in
# `continue-on-error`, so a non-blocking job (e.g. the CI "Quality Checks" job)
# can NEVER block the session; it is reported as a triage item instead.
# Only when the run-level conclusion is `failure` does attribution run, comparing
# the pushed run's failing-JOB set against the base run's, where the base is
# classified as absent / job-less / red / green (a job-less base is NOT green):
#   - base green/absent/job-less -> new red = your regression -> exit 1
#   - base red -> new red (same jobs)       = pre-existing     -> report and exit 0
#   - all green / non-blocking              = PASSED           -> exit 0
# Attribution is deterministic: SHA -> run -> run-level + per-job conclusion.
# `git pull --rebase` is safe because the post-commit hook skips automated git
# operations (see .githooks/post-commit.py).
RETRY_POLLS ?= 10
RETRY_SLEEP ?= 1
DETAIL_LINES ?= 50

push:
	git pull --rebase
	@BASE=$$(git rev-parse origin/main); \
	SHA=$$(git rev-parse HEAD); \
	git push || exit $$?; \
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
	echo "Pushed $$SHA (base $$BASE) after $$ATTEMPTS poll(s)"; \
	if [ -z "$$WFS" ]; then \
	  echo "CI: no run registered for $$SHA after $(RETRY_POLLS) poll(s) - fail-safe block"; \
	  exit 1; \
	fi; \
	for WF in $$WFS; do \
	  NEW=$$(gh run list --commit "$$SHA" --workflow "$$WF" --json databaseId --jq '.[0].databaseId'); \
	  gh run watch "$$NEW" --exit-status >/dev/null 2>&1 || true; \
	  NEWCONC=$$(gh run view "$$NEW" --json conclusion --jq '.conclusion'); \
	  NEWFAIL=$$(gh run view "$$NEW" --json jobs --jq '[.jobs[] | select(.conclusion=="failure") | .name] | sort | join(",")'); \
	  NEWSTEPS=$$(gh run view "$$NEW" --json jobs --jq '[.jobs[] | select(.conclusion=="failure") | .steps[]? | select(.conclusion=="failure") | .name] | sort | join(", ")'); \
	  if [ -n "$$NEWSTEPS" ]; then \
	    echo "$$WF: failing step(s): $$NEWSTEPS"; \
	    gh run view "$$NEW" --log-failed 2>/dev/null | awk -F'\t' '{ l=$$3; p=index(l,"Z "); if(p>0)l=substr(l,p+2); gsub(/\x1B\[[0-9;]*[a-zA-Z]/,"",l); gsub(/\^\[\[[0-9;]*[a-zA-Z]/,"",l); if(l ~ /^##\[group\]/ || l ~ /^##\[endgroup\]/) next; gsub(/^##\[error\]/,"Error: ",l); print l }' | tail -n $(DETAIL_LINES) | sed 's/^/    /'; \
	  fi; \
	  if [ "$$NEWCONC" != "failure" ]; then \
	    if [ -n "$$NEWFAIL" ]; then \
	      echo "$$WF: PASSED (run=$$NEWCONC) — non-blocking failure(s) [$$NEWFAIL] — triage, does not block"; \
	    else \
	      echo "$$WF: PASSED"; \
	    fi; \
	    continue; \
	  fi; \
	  OLD=$$(gh run list --commit "$$BASE" --workflow "$$WF" --json databaseId --jq '.[0].databaseId'); \
	  if [ -z "$$OLD" ]; then \
	    echo "$$WF: BLOCKING failure ($$NEWFAIL) — base has no run (unknown base) — YOUR regression"; \
	    STATUS=1; continue; \
	  fi; \
	  OLDJOBS=$$(gh run view "$$OLD" --json jobs --jq '.jobs | length'); \
	  if [ "$$OLDJOBS" = "0" ]; then \
	    echo "$$WF: BLOCKING failure ($$NEWFAIL) — base run is job-less (invalid workflow, not green) — YOUR regression"; \
	    STATUS=1; continue; \
	  fi; \
	  OLDFAIL=$$(gh run view "$$OLD" --json jobs --jq '[.jobs[] | select(.conclusion=="failure") | .name] | sort | join(",")'); \
	  if [ "$$NEWFAIL" = "$$OLDFAIL" ]; then \
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
	@[ -n "$(REASON)" ] || { echo "Usage: make probe '<reason>'"; exit 1; }
	git add -f spikes/debug/probe.sh
	git commit -m 'debug: probe' --no-verify --allow-empty
	git push
	@gh workflow run debug.yml --field reason='$(REASON)'
	@sleep 5
	@RUN_ID=$$(gh run list --workflow debug.yml -L 1 --json databaseId --jq '.[0].databaseId') && \
	gh run watch "$$RUN_ID" --exit-status >/dev/null 2>&1 && \
	gh run download "$$RUN_ID" --name probe-result --dir spikes/debug >/dev/null 2>&1 && \
	cat spikes/debug/probe_output.txt 2>/dev/null || echo "(no output file)"

# logs - CI Log Extraction: extract a single failed step's logs from a GitHub Actions run.
# Usage:
#   make logs <run-id> '<step-name>'
#
# The run ID comes from `gh run list`; the step name comes from `gh run view <id>`
# (the execution tree). The awk program isolates ONLY that step's output, strips
# ANSI escapes and GitHub's ##[group]/##[endgroup] boilerplate, and prefixes
# ##[error] lines with "Error: ". See docs/templates/makefile.md (CI Log Extraction).

logs: LOGS_RUN := $(word 2,$(MAKECMDGOALS))
logs: LOGS_STEP := $(wordlist 3,99,$(MAKECMDGOALS))

logs:
	@[ -n "$(LOGS_RUN)" ] || { echo "Usage: make logs <run-id> '<step-name>'"; exit 1; }
	@gh run view "$(LOGS_RUN)" --log | awk -F'\t' -v step="$(LOGS_STEP)" '$$2==step { if(j!=$$1){j=$$1; print "\n["j"]"} l=$$3; p=index(l,"Z "); if(p>0)l=substr(l,p+2); gsub(/\x1B\[[0-9;]*[a-zA-Z]/, "", l); gsub(/\^\[\[[0-9;]*[a-zA-Z]/, "", l); if(l ~ /^##\[group\]Run /){k=1;next} if(k && l ~ /^##\[endgroup\]/){k=0;next} if(k)next; if(l ~ /^##\[group\]/ || l ~ /^##\[endgroup\]/)next; gsub(/^##\[error\]/, "Error: ", l); print l }'

# test - Run the full test suite via the project's designated runner (uv).
#
# Usage:
#   make test
#
# The post-commit hook runs this same suite automatically on every commit;
# this target exposes it as an on-demand command for agents and developers.

test:
	uv run pytest

%:
	@:
