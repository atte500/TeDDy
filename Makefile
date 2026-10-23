.PHONY: ci-watch commit help logs probe push test _preflight

# Print the target list when make runs with no goal.
.DEFAULT_GOAL := help

# Named inputs for the targets that need a value. A command-line assignment
# such as MSG="..." is a variable, never a goal, so no word of a commit
# message can execute another target.
MSG ?=
REASON ?=
RUN ?=
STEP ?=

# Every command-line word is a goal, and Make builds goals in order, so a word
# that names a target (probe, test) would execute it. Reject more than one goal
# and reject a goal that no rule defines.
_KNOWN_GOALS := ci-watch commit help logs probe push test
_UNKNOWN_GOALS := $(filter-out $(_KNOWN_GOALS),$(MAKECMDGOALS))
ifneq ($(words $(MAKECMDGOALS)),0)
ifneq ($(words $(MAKECMDGOALS)),1)
$(error Detected $(words $(MAKECMDGOALS)) goals: $(MAKECMDGOALS). Pass values as NAME="value", as in: make commit MSG="<type>(<scope>): <description>")
endif
endif
ifneq ($(_UNKNOWN_GOALS),)
$(error Unknown target '$(_UNKNOWN_GOALS)'. Run make help for the list of targets.)
endif

# Always use GNU Make native features for cross-platform compatibility.
# On Windows, ensure a POSIX shell is used for pipeline targets (ci-watch, probe, logs).
ifeq ($(OS),Windows_NT)
    SHELL := bash.exe
    .SHELLFLAGS := -c
    # Git Bash reports a MINGW/MSYS kernel; the WSL bash shim reports Linux.
    SHELL_CHECK = uname -s 2>/dev/null | grep -Eq 'MINGW|MSYS'
else
    SHELL_CHECK = true
endif

# _preflight - Verify the tool contract that the POSIX recipes depend on.
#
# ci-watch, probe, and logs are shell pipelines that need a POSIX shell plus
# git, gh, awk, and sed. Running this gate first turns an unmet contract into
# one actionable message instead of a generic 'make: *** Error 1'.
# The commit, push, and test targets stay cmd.exe-safe and do not use this gate.
_preflight:
	@command -v git >/dev/null 2>&1 || { echo "ERROR: git is not on PATH inside the recipe shell." >&2; exit 1; }
	@command -v gh >/dev/null 2>&1 || { echo "ERROR: gh is not on PATH. Install the GitHub CLI, then run gh auth login." >&2; exit 1; }
	@command -v awk >/dev/null 2>&1 || { echo "ERROR: awk is not on PATH inside the recipe shell. Git Bash ships gawk." >&2; exit 1; }
	@command -v sed >/dev/null 2>&1 || { echo "ERROR: sed is not on PATH inside the recipe shell. Git Bash ships sed." >&2; exit 1; }
	@$(SHELL_CHECK) || { echo "ERROR: the recipe shell is not Git Bash. Install Git for Windows, or pass SHELL=\"C:/Program Files/Git/bin/bash.exe\"." >&2; exit 1; }

# commit - VCP workflow (LOCAL ONLY): stage, advisory pre-commit auto-fix pass, commit.
# Usage:
#   make commit MSG="<type>(<scope>): <description>"
#
# This target is LOCAL-ONLY: it does NOT pull or push. The push is deferred to the
# session Conclusion via `make push` (see below).
#
# The advisory pass consumes its own exit code with `|| echo`, so a failing run
# prints one plain sentence instead of Make's bare "(ignored)" marker. The line
# reaches the recipe shell because `||` is a shell metacharacter.
# The hooks run through the project runner (`uv run pre-commit run`), so the pinned
# pre-commit version and its hook environments are the ones that execute.
# This first pre-commit pass is advisory: a non-zero exit is ignored and auto-fixed
# files are re-staged. Git then runs the same hooks again during `git commit` below,
# and that second run is the blocking local gate. The unskippable post-commit test
# gate (.githooks/post-commit.py) remains the final safety net.

# The message arrives in MSG, so its words never become goals.
#
# `git commit` is invoked WITHOUT `--no-verify`, so Git's own pre-commit hook is the
# real local gate. The local hook set is only formatters + detect-secrets + conflict
# check (see .pre-commit-config.yaml), so running it twice -- this advisory pass plus
# Git's own invocation -- is cheap and accepted.
#
# `git add .` stages ALL local changes, including currently unstaged ones.
commit:
	$(if $(strip $(MSG)),,$(error Usage: make commit MSG="<type>(<scope>): <description>"))
	git add .
	@uv run pre-commit run || echo "Advisory pre-commit reported issues. Auto-fixed files were re-staged and the commit continues."
	git add .
	git commit -m "$(MSG)"

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
#
# Every blocking verdict prints to stdout for the log and repeats the reason on
# stderr, so a caller that captures stderr alone still reads the diagnosis.
# Before polling, the target rejects a commit that is not resolvable locally and
# a commit that no remote branch contains, because no run can exist for it.
RETRY_POLLS ?= 10
RETRY_SLEEP ?= 2
DETAIL_LINES ?= 50
BASE_DEPTH ?= 50
BASE ?=

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
	  NEWCONC=$$(gh run view "$$NEW" --json conclusion --jq '.conclusion'); \
	  NEWFAIL=$$(gh run view "$$NEW" --json jobs --jq '[.jobs[] | select(.conclusion=="failure") | .name] | sort | join(",")'); \
	  NEWSTEPS=$$(gh run view "$$NEW" --json jobs --jq '[.jobs[] | select(.conclusion=="failure") | .steps[]? | select(.conclusion=="failure") | .name] | sort | join(", ")'); \
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
	    echo "$$WF: BLOCKING failure ($$NEWFAIL) - no run-bearing ancestor (unknown base) - YOUR regression"; \
	    echo "$$WF: no run-bearing ancestor within $(BASE_DEPTH) commits, so the baseline is unknown." >&2; \
	    STATUS=1; continue; \
	  fi; \
	  OLD=$$(gh run list --commit "$$BASE" --workflow "$$WF" --json databaseId --jq '.[0].databaseId'); \
	  if [ -z "$$OLD" ]; then \
	    echo "$$WF: BLOCKING failure ($$NEWFAIL) - pinned base has no run (unknown base) - YOUR regression"; \
	    echo "$$WF: pinned base $$BASE carries no run for this workflow." >&2; \
	    STATUS=1; continue; \
	  fi; \
	  OLDJOBS=$$(gh run view "$$OLD" --json jobs --jq '.jobs | length'); \
	  if [ "$$OLDJOBS" = "0" ]; then \
	    echo "$$WF: BLOCKING failure ($$NEWFAIL) - base run is job-less (invalid workflow, not green) - YOUR regression"; \
	    echo "$$WF: base run $$OLD carries zero jobs, so it cannot prove a green baseline." >&2; \
	    STATUS=1; continue; \
	  fi; \
	  OLDFAIL=$$(gh run view "$$OLD" --json jobs --jq '[.jobs[] | select(.conclusion=="failure") | .name] | sort | join(",")'); \
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

# probe - Remote Probing Protocol: push probe, trigger CI workflow, retrieve logs
# Usage:
#   make probe REASON="<reason>"  # reason is required, appears in workflow dispatch metadata
#
# The reason arrives in REASON, so its words never become goals.
# The first three lines (add, commit, push) call git.exe, which exists on every
# platform, and their failures must stay visible.
# The dispatch/watch section is ONE shell block. A recipe line without a shell
# metacharacter can be spawned directly by Make and bypass SHELL, which fails on
# Windows for Git Bash-only programs such as sleep. Every line in the block
# therefore carries a variable expansion, a ';', or a '&&', so all of it runs
# through the recipe shell.
# The run is resolved by the pushed SHA inside a bounded retry loop, because
# workflow registration lags and a bare 'gh run list -L 1' can match a stale run.
# The reason travels in double quotes so a cmd.exe caller and a Git Bash caller
# pass the same value. Keep the reason free of $, backticks, and nested quotes.

probe: _preflight

probe:
	$(if $(strip $(REASON)),,$(error Usage: make probe REASON="<reason>"))
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

# logs - CI Log Extraction: extract logs for all failed steps or a specific step.
# Usage:
#   make logs RUN=<run-id>                # extracts logs for ALL failed steps
#   make logs RUN=<run-id> STEP="<step>"  # extracts logs for a specific step (substring match)
#
# If no step name is provided, extracts all failed steps using `gh run view --log-failed`.
# If a step name is given, matches against the step name using substring matching.
# Strips ANSI escapes and GitHub boilerplate, adding clean [job > step] headers.

logs: _preflight

logs:
	$(if $(strip $(RUN)),,$(error Usage: make logs RUN=<run-id> [STEP="<step-name>"]))
	@if [ -z "$(STEP)" ]; then \
	  gh run view "$(RUN)" --log-failed 2>/dev/null | awk -F'\t' '{ if(j!=$$1||s!=$$2){j=$$1;s=$$2;print "\n["j" > "s"]"} l=$$3; p=index(l,"Z "); if(p>0)l=substr(l,p+2); gsub(/\x1B\[[0-9;]*[a-zA-Z]/,"",l); gsub(/\^\[\[[0-9;]*[a-zA-Z]/,"",l); if(l ~ /^##\[group\]Run /){k=1;next} if(k && l ~ /^##\[endgroup\]/){k=0;next} if(k)next; if(l ~ /^##\[group\]/ || l ~ /^##\[endgroup\]/)next; gsub(/^##\[error\]/,"Error: ",l); print l }'; \
	else \
	  gh run view "$(RUN)" --log 2>/dev/null | awk -F'\t' -v step="$(STEP)" 'index($$2, step) > 0 { if(j!=$$1||s!=$$2){j=$$1;s=$$2;print "\n["j" > "s"]"} l=$$3; p=index(l,"Z "); if(p>0)l=substr(l,p+2); gsub(/\x1B\[[0-9;]*[a-zA-Z]/,"",l); gsub(/\^\[\[[0-9;]*[a-zA-Z]/,"",l); if(l ~ /^##\[group\]Run /){k=1;next} if(k && l ~ /^##\[endgroup\]/){k=0;next} if(k)next; if(l ~ /^##\[group\]/ || l ~ /^##\[endgroup\]/)next; gsub(/^##\[error\]/, "Error: ", l); print l }'; \
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

# help - Print the target list.
#
# No catch-all rule exists. The goal check above aborts on an unknown word, so
# Make never prints an "up to date" line for a typo or for a stray argument.
help:
	@echo "Usage: make <target> [NAME=\"value\"]"
	@echo ""
	@echo "  commit MSG=\"<type>(<scope>): <description>\""
	@echo "  push"
	@echo "  test"
	@echo "  ci-watch [COMMIT=<sha>] [BASE=<sha>]"
	@echo "  probe REASON=\"<reason>\""
	@echo "  logs RUN=<run-id> [STEP=\"<step-name>\"]"
