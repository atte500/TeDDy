# Makefile Template

> **⚠️ This is an example template.** Adapt the runner, test commands, and tool-specific details (e.g., `uv run pytest`, pre-commit hook list) to match your project's actual setup. The concrete examples shown may not work verbatim in all environments.

This template defines the standard commands for the commit workflow
and the Debugger's Remote Probing Protocol (RPP). Below are concrete examples adapted for the TeDDy project.

## Usage

### Commit
```shell
make commit MSG="feat(templates): add PROJECT.md template"
```

**What is `.PHONY`?**
`.PHONY` declares `commit`, `push`, `ci-watch`, `probe`, `test`, `logs`, `help`, and the internal `_preflight` gate as targets that name no file. Without it, a file named `commit` in the project root makes Make treat that target as up to date and skip the recipe.

### Help
```shell
make
```

The default goal is `help`, so a bare `make` prints the target list. An unknown goal aborts with its own name instead of an "up to date" line.

### Push
```shell
make push
```

### CI Watch
```shell
make ci-watch
```

**What does `make ci-watch` do?**
`make ci-watch` resolves the commit hash from `HEAD` (or an explicit `COMMIT=<sha>`), polls GitHub Actions to allow for workflow registration lag, watches all running workflows for that commit, prints failing step details, and attributes regressions. It is used by the Developer at slice conclusion to verify remote CI without slowing down routine pushes.

### Test
```shell
make test
```

**What does `make test` run?**
`make test` runs the project's full test suite via the designated runner (e.g. `uv run pytest`). The post-commit hook runs the same suite automatically on every commit; this target exposes it as an on-demand command for agents and developers. If a project's Makefile lacks a `test` target, agents MUST add one following this template.

### Probe
```shell
make probe REASON="investigate windows path handling"
```

**Why does `probe` need a reason?**
The Remote Probing Protocol requires a reason string because it is passed as the `reason` input to the GitHub Actions workflow dispatch command (`gh workflow run debug.yml --field reason="..."`). The reason documents what the probe is investigating and appears in the workflow run metadata.

### Logs
```shell
make logs RUN=12345                   # extract logs for ALL failed steps
make logs RUN=12345 STEP="Run tests"  # extract logs for a specific step (substring match)
```

**How does `make logs` work?**
The `RUN` value is the GitHub Actions run ID (as shown by `gh run list`). If `STEP` is omitted, it extracts and formats logs for **all failed steps** using `gh run view --log-failed`. An optional `STEP` value filters down to a specific step using substring matching, stripping ANSI escapes and GitHub boilerplate so you see the failure without noise. See [CI Log Extraction](#ci-log-extraction).

## Probe Script

The Debugger's Remote Probing Protocol pushes a local `spikes/debug/probe.sh` script to the CI runner via a workflow dispatch. The probe script MUST output diagnostics to `spikes/debug/probe_output.txt` so the workflow can upload it as an artifact for retrieval.

### Example

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "Probe running on $(uname -a)"
echo "Python: $(python --version 2>&1)"

mkdir -p spikes/debug
cat > spikes/debug/probe_output.txt <<EOF
=== Probe Result ===
OS: $(uname -s)
Python: $(python --version 2>&1)
Git: $(git --version 2>&1)
EOF
```

**Requirements:**
- The output file MUST be written to `spikes/debug/probe_output.txt` — this path is uploaded as an artifact by the CI workflow.
- The CI workflow running the probe must use a single job with no build matrix. This prevents multiple jobs from overwriting the uploaded artifact (`probe-result`).
- The script must remain minimal and self-contained, using a single heredoc.

## Cross-Platform Design

Always use GNU Make native features for cross-platform compatibility instead of shell-specific constructs:

- **Required input validation:** Reject a missing required input in a parse-time block, not in the recipe. Make runs the check while it reads the file, so it aborts before any prerequisite and before any shell process starts. See [Parse-Time Input Validation](#parse-time-input-validation).
- **Named inputs instead of positional goals:** Pass values as `NAME="value"`, as in `make commit MSG="feat(scope): add thing"`. GNU Make treats a command-line assignment as a variable, so no word of the value can become a goal. Positional capture through `$(MAKECMDGOALS)` is forbidden, because a word that names a real target executes that target.
- **Parse-time goal validation:** Compare `$(MAKECMDGOALS)` against a `_KNOWN_GOALS` list and abort with `$(error ...)` when a goal is unknown or when more than one goal is present. The check runs while Make reads the file, so no recipe line can run first.
- **POSIX shell preflight:** Every POSIX recipe target (`ci-watch`, `probe`, `logs`) depends on the internal `_preflight` target, which verifies `git`, `gh`, `awk`, and `sed` before any network call. It aborts with one actionable message instead of a generic `make: *** Error 1`. A missing required input aborts at parse time, before the tool gate runs.
- **One shell process per command group:** Make spawns one process per recipe line that carries a shell metacharacter, and Windows process creation costs far more than on POSIX. Join a target's independent commands into one backslash-continued block separated by `;`, so the target pays one process instead of one per line.
- **Shell routing for Bash-only commands:** Make spawns a recipe line directly when the line carries no shell metacharacter. That direct spawn bypasses `SHELL`. On Windows it fails for Git Bash-only programs such as `sleep` and for shell builtins such as `echo`. Keep these commands inside a shell block that carries `;`, `&&`, or a variable expansion.
- **Windows shell selection:** Set `SHELL := bash.exe` when `OS` is `Windows_NT`. The assignment covers every target, not only the pipelines, and `_preflight` confirms that the shell is Git Bash rather than the WSL `bash.exe` shim and names the `SHELL=` override when it is not.
- **Portable quoting:** Pass values with double quotes, as in `--field reason="..."`, because Windows `cmd.exe` keeps single quotes literally.
- **ASCII-only output:** Recipe output stays ASCII, because a Windows console turns a non-ASCII dash into mojibake in captured logs.
- **Explicit advisory fallback:** The advisory pre-commit pass consumes its own exit code with `|| echo "<sentence>"`, so a failing run prints one plain sentence. Make's `-` prefix is forbidden here, because it prints a bare `Error 1 (ignored)` line that reads as an unexplained defect.
- **Error transparency:** The first pre-commit pass is advisory, so its non-zero exit is ignored and auto-fixed files are re-staged. Git then runs the same hooks again during `git commit`, and that second run is the blocking local gate. A hook failure there aborts the commit. The post-commit test gate is the final safety net. `make push` runs `git pull --rebase` and `git push` without suppression, so a rebase conflict or push rejection surfaces as a non-zero exit.

### Parse-Time Input Validation

A required input is rejected while Make reads the file, so the check runs before any prerequisite and before any shell process starts. A recipe-level check is forbidden, because it runs after the `_preflight` prerequisite.

```makefile
ifneq ($(filter commit,$(MAKECMDGOALS)),)
ifeq ($(strip $(MSG)),)
$(error Usage: make commit MSG="<type>(<scope>): <description>")
endif
endif
ifneq ($(filter probe,$(MAKECMDGOALS)),)
ifeq ($(strip $(REASON)),)
$(error Usage: make probe REASON="<reason>")
endif
endif
ifneq ($(filter logs,$(MAKECMDGOALS)),)
ifeq ($(strip $(RUN)),)
$(error Usage: make logs RUN=<run-id> [STEP="<step-name>"])
endif
endif
```

## Test Workflow

### Example

```makefile
test:
	uv run pytest
```

**Usage:** `make test`

**Test scope:** declare the tests directory once via `testpaths` in `pyproject.toml`. The `test` target passes no path to `pytest`, so the config stays the single source of truth.

## Commit Workflow

`make commit` is **local-only**: it stages all local changes, runs the pre-commit hooks once (an advisory auto-fix pass that re-stages any auto-formatted files), and commits. It does **not** pull or push — the push is deferred to the session Conclusion via `make push` (see [Push (Deferred to Conclusion)](#push-deferred-to-conclusion)).

`make commit` commits **without** `--no-verify`, so Git's own `pre-commit` hook is the real local gate. The unskippable post-commit test gate (`.githooks/post-commit.py`) runs the full suite on every commit. Running the pre-commit hook twice (the explicit auto-fix pass plus Git's own invocation) is accepted because the local hook set is only formatters + `detect-secrets` + conflict check (see [pre-commit.md](./pre-commit.md)).

**Staging note:** `make commit` stages **all** local changes, including currently unstaged ones (`git add .`), not just the files you intended to commit.

### Example

```makefile
commit:
	git add .
	@uv run pre-commit run || echo "Advisory pre-commit reported issues. Auto-fixed files were re-staged and the commit continues."
	git add .
	git commit -m "$(MSG)"

```

**Usage:**
- `make commit MSG="feat(templates): add PROJECT.md template"`

**Message-input contract:** the message arrives in the named variable `MSG`, so its words are data and never goals. Supported input:

- ✅ **Single-line Conventional Commits in double quotes survive verbatim** — e.g. `make commit MSG="feat(scope): add thing"`. Always use double quotes across all operating systems.
- ✅ **`#` survives** — Make keeps the character inside a quoted command-line value, so `MSG="fix: close #42"` commits that subject.
- ❌ **`$VAR` is swallowed or expanded** — `make` and shells expand `$(...)`/`$X`; avoid `$`.
- ❌ **Backticks trigger command substitution** in POSIX shells when inside double quotes; avoid backticks.
- ❌ **Multiline messages fail hard** (`unexpected EOF`).

**Guard:** keep the commit message to a single line in double quotes, and write plain text without `$`, backticks, or nested quotes.

## Push (Deferred to Conclusion)

`make push` is fast and non-blocking: it runs `git pull --rebase` and pushes local commits to remote. Only include and configure this target if a remote is configured or planned for the project.

### Example

```makefile
push:
	git pull --rebase
	git push
```

**Usage:** `make push`

## CI Watch & Attribution

`make ci-watch` discovers **every** CI run for the target commit (`HEAD` by default, or `COMMIT=<sha>`), waits for and reports each workflow with its jobs. The target depends on `_preflight`, so a missing `gh`, `awk`, or Git Bash shell fails once with an actionable message. Before polling, it rejects an unknown `COMMIT` and a commit that no remote branch contains, because no run can exist for an un-pushed commit. Every blocking verdict prints to stdout for the log and repeats its reason on stderr. It answers ONE question: **did this commit turn a BLOCKING gate red?** Only push-triggered workflows are attributed; a downstream workflow that registers from a `workflow_run` event is not a regression in this commit. Only include and configure this target if a remote CI pipeline is configured or planned for the project.

The pushed RUN's own conclusion is authoritative: it already folds in `continue-on-error`, so a **non-blocking** job (e.g. the CI `Quality Checks` job) can NEVER block the session — it is reported as a triage item instead. Only when the run-level conclusion is `failure` does attribution run, comparing the pushed run's failing-JOB set against the base run's:

- **base green/absent/job-less → new red** = your regression → **exit non-zero** (fix before concluding).
- **base red → new red (subset of the base's failing jobs)** = pre-existing → **report and exit 0** (do not wait, do not duplicate the fix).
- **unknown conclusion** (`timed_out`/`cancelled`/`startup_failure`) = the gate result is unknown → **fail-safe block** → **exit non-zero**.
- **all green / non-blocking** → PASSED → **exit 0**.
- **job-less base** → NOT green: a base run that exists but carries zero jobs (an invalid-workflow failure) is treated as an unknown base and fails safe (block).

When any step fails — blocking or not — the target prints the failing step's name and its run id, then that step's log details (ANSI/timestamp-stripped and indented), bounded to `DETAIL_LINES` lines (default 50), and points to `make logs RUN=<run-id> STEP="<step-name>"` for the full step log when needed.

Attribution is deterministic: SHA → run → run-level + per-job conclusion (never "the latest run").

Key behaviors:

1. **Automatic SHA and BASE resolution.** `SHA` defaults to current `HEAD` (or `COMMIT=<sha>`), and `BASE` resolves per workflow to the most recent ancestor of `SHA` that carries a run for that workflow. The target fetches one bounded list of the workflow's latest runs (`BASE_SCAN`, default 200) and intersects it with the newest `BASE_DEPTH` ancestors (`git rev-list`, default 50), so resolution costs one API call instead of one per ancestor. An explicit `BASE=<sha>` pins the baseline verbatim and skips resolution; if the pinned commit carries no run for the workflow, the target fails safe as an unknown base.
2. **Registration lag is tolerated by a bounded retry.** CI can fail to register a run for the pushed SHA immediately. The target polls `gh run list --commit <sha>` up to `RETRY_POLLS × RETRY_SLEEP` (default 10 × 2s ≈ 20s) before attributing. It fails safe if the run never registers.
3. **No CI is non-blocking.** If the repository has no workflow files under `.github/workflows/` (`*.yml`/`*.yaml`), the target logs `No CI configured - skipping attribution` and exits 0.
4. **Workflow names with spaces stay whole.** The target reads workflow names one line at a time. A name such as `Publish to PyPI` is attributed as one workflow.

### Example

```makefile
RETRY_POLLS ?= 10
RETRY_SLEEP ?= 2
DETAIL_LINES ?= 50
BASE_DEPTH ?= 50
BASE_SCAN ?= 200
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
```

**Usage:**
- `make ci-watch` (watches CI for current `HEAD`)
- `make ci-watch COMMIT=<sha>` (watches CI for a specific commit)
- `make ci-watch BASE=<sha>` (pins the comparison baseline to a commit)

## Remote Probing Protocol (RPP)

### Example

```makefile
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
```

**Usage:** `make probe REASON="investigate windows path handling"`

`make probe` resolves the dispatched run by the pushed SHA inside a bounded retry loop. It reuses `RETRY_POLLS` and `RETRY_SLEEP` from the CI watch section. The dispatch, the run resolution, the watch, and the download stay in one shell block, because a metacharacter-free line would bypass the recipe shell on Windows. The target rejects the probe with a stderr reason when no run registers for that SHA, so a stale run can never be mistaken for the new probe.

## CI Log Extraction

The Debugger's Reproduction phase needs to read CI logs without drowning in the full run output. The `make logs` target wraps the `gh run view` pipeline, strips ANSI escapes, and removes GitHub's `##[group]`/`##[endgroup]` boilerplate.

### Example

```makefile
logs: _preflight
	@if [ -z "$(STEP)" ]; then \
	  gh run view "$(RUN)" --log-failed 2>/dev/null | awk -F'\t' '{ if(j!=$$1||s!=$$2){j=$$1;s=$$2;print "\n["j" > "s"]"} l=$$3; p=index(l,"Z "); if(p>0)l=substr(l,p+2); gsub(/\x1B\[[0-9;]*[a-zA-Z]/,"",l); gsub(/\^\[\[[0-9;]*[a-zA-Z]/,"",l); if(l ~ /^##\[group\]Run /){k=1;next} if(k && l ~ /^##\[endgroup\]/){k=0;next} if(k)next; if(l ~ /^##\[group\]/ || l ~ /^##\[endgroup\]/)next; gsub(/^##\[error\]/,"Error: ",l); print l }'; \
	else \
	  gh run view "$(RUN)" --log 2>/dev/null | awk -F'\t' -v step="$(STEP)" 'index($$2, step) > 0 { if(j!=$$1||s!=$$2){j=$$1;s=$$2;print "\n["j" > "s"]"} l=$$3; p=index(l,"Z "); if(p>0)l=substr(l,p+2); gsub(/\x1B\[[0-9;]*[a-zA-Z]/,"",l); gsub(/\^\[\[[0-9;]*[a-zA-Z]/,"",l); if(l ~ /^##\[group\]Run /){k=1;next} if(k && l ~ /^##\[endgroup\]/){k=0;next} if(k)next; if(l ~ /^##\[group\]/ || l ~ /^##\[endgroup\]/)next; gsub(/^##\[error\]/, "Error: ", l); print l }'; \
	fi

```

**Usage:**
- `make logs RUN=12345` — extract logs for ALL failed steps from run `12345`.
- `make logs RUN=12345 STEP="Run tests"` — extract logs for a specific step (substring match) from run `12345`.

**How it works:**
- `RUN` carries the run ID and `STEP` carries the optional step name. Both arrive as command-line variables, so neither can become a goal.
- When no step name is provided, `gh run view --log-failed` is used so only failed steps are fetched and printed with `[job > step]` headers.
- When a step name is supplied, `index($2, step) > 0` performs substring matching against column 2.
- Timestamps and ANSI escapes are stripped, and `##[error]` lines are prefixed with `Error: `.

## Implementation Notes

- This project uses `uv run` as its designated runner.
- Local pre-commit hooks include only fast auto-fixers (`ruff`) + `detect-secrets` + `check-merge-conflict`; heavier checks (`mypy`, `bandit`, `pip-audit`, and the structural checkers) run non-blocking in CI (see [pre-commit.md](./pre-commit.md)).
- Post-commit hook lives at `.githooks/post-commit.py` and runs the full `uv run pytest` suite.
- Ensure `gh` (GitHub CLI) is authenticated for `make push`, the Remote Probing Protocol, and CI Log Extraction.
- The `make logs` target abstracts the Debugger's CI-log extraction (Phase 1, Step 2). See [CI Log Extraction](#ci-log-extraction).
- `make push` runs in the session Conclusion phase (see [Push (Deferred to Conclusion)](#push-deferred-to-conclusion)); it rebases and pushes.
- `make ci-watch` monitors and attributes CI results for `HEAD` or an explicit commit (see [CI Watch & Attribution](#ci-watch--attribution)).
