# Makefile Template

> **⚠️ This is an example template.** Adapt the runner, test commands, and tool-specific details (e.g., `uv run pytest`, pre-commit hook list) to match your project's actual setup. The concrete examples shown may not work verbatim in all environments.

This template defines the standard commands for the VCP (Version Control Protocol) commit workflow
and the Debugger's Remote Probing Protocol (RPP). Below are concrete examples adapted for the TeDDy project.

## Usage

### Commit
```shell
make commit 'feat(templates): add PROJECT.md template'
```

**What is `.PHONY`?**
`.PHONY` is a Makefile directive that declares `commit`, `push`, `ci-watch`, `probe`, `test`, and `logs` as phony targets — they do not correspond to actual files. Without `.PHONY`, if a file named `commit` or `probe` existed in the directory (e.g., a script called `commit`), Make would see it as up-to-date and skip the target entirely. By declaring them phony, Make always runs the recipe when you call `make commit`, `make push`, `make ci-watch`, `make probe`, or `make test`.

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
make probe 'investigate windows path handling'
```

**Why does `probe` need a reason?**
The Remote Probing Protocol requires a reason string because it is passed as the `reason` input to the GitHub Actions workflow dispatch command (`gh workflow run debug.yml --field reason='...'`). The reason documents what the probe is investigating and appears in the workflow run metadata.

### Logs
```shell
make logs 12345              # extract logs for ALL failed steps
make logs 12345 'Run tests'  # extract logs for a specific step (substring match)
```

**How does `make logs` work?**
The first argument is the GitHub Actions run ID (as shown by `gh run list`). If invoked without a second argument, it extracts and formats logs for **all failed steps** using `gh run view --log-failed`. An optional second argument filters down to a specific step using substring matching, stripping ANSI escapes and GitHub boilerplate so you see the failure without noise. See [CI Log Extraction](#ci-log-extraction).

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
- The CI workflow running the probe SHOULD be configured with a single job (no build matrix) to avoid multiple jobs overwriting each other's uploaded artifact (`probe-result`).
- The script should be minimal and self-contained (ideally a single heredoc). See the Debugger's rule 11 (Remote Probing Protocol) for full protocol details.

## Cross-Platform Design

The Makefile uses Make's built-in `-` prefix for error suppression (`-pre-commit run`) instead of shell-level `|| true` or `&&`/`||` chaining. This ensures cross-platform compatibility:

- **POSIX shells (bash, sh, zsh):** `-` prefix works because Make handles error suppression natively before passing the recipe line to the shell.
- **Windows (cmd.exe):** `-` prefix works because Make suppresses the exit code check, avoiding shell-specific `||` operators that cmd.exe does not support.
- **Error transparency:** The pre-commit pass is advisory — if it fails, the commit still succeeds locally; the post-commit test gate is the real safety net. `make push` runs `git pull --rebase` and `git push` WITHOUT suppression, so a rebase conflict or push rejection surfaces as a non-zero exit.

## Test Workflow

### Example

```makefile
test:
	uv run pytest
```

**Usage:** `make test`

## VCP Commit Workflow

`make commit` is **local-only**: it stages all local changes, runs the pre-commit hooks once (an advisory auto-fix pass that re-stages any auto-formatted files), and commits. It does **not** pull or push — the push is deferred to the session Conclusion via `make push` (see [Push (Deferred to Conclusion)](#push-deferred-to-conclusion)).

`make commit` commits **without** `--no-verify`, so Git's own `pre-commit` hook is the real local gate. The unskippable post-commit test gate (`.githooks/post-commit.py`) runs the full suite on every commit. Running the pre-commit hook twice (the explicit auto-fix pass plus Git's own invocation) is accepted because the local hook set is only formatters + `detect-secrets` + conflict check (see [pre-commit.md](./pre-commit.md)).

**Staging note:** `make commit` stages **all** local changes, including currently unstaged ones (`git add .`), not just the files you intended to commit.

### Example

```makefile
commit: ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))

commit:
	@[ -n "$(ARGS)" ] || { echo "Usage: make commit '<message>'"; exit 1; }
	git add .
	-pre-commit run
	git add .
	git commit -m "$(ARGS)"

%:
	@:
```

**Usage:**
- `make commit 'feat(templates): add PROJECT.md template'`

**Message-input contract:** the recipe captures the message from the extra `make` goals via `$(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))`. Supported input (verified by the `spikes/debug/make-args/` findings):

- ✅ **Single-line Conventional Commits survive verbatim** — e.g. `make commit 'feat(scope): add thing'`.
- ❌ **`$VAR` is swallowed to empty** — `make` expands `$(...)`/`$X` before the recipe runs; avoid `$`.
- ❌ **Backticks and quotes are stripped** by the shell quoting layer.
- ❌ **Multiline messages fail hard** (`/bin/sh: unexpected EOF`, exit 2).

**Guard:** keep the commit message to a single line and avoid `$` characters.

## Push (Deferred to Conclusion)

`make push` is fast and non-blocking: it runs `git pull --rebase` and pushes local commits to remote.

### Example

```makefile
push:
	git pull --rebase
	git push
```

**Usage:** `make push`

## CI Watch & Attribution

`make ci-watch` discovers **every** CI run for the target commit (`HEAD` by default, or `COMMIT=<sha>`), waits for and reports each workflow with its jobs. It answers ONE question: **did this commit turn a BLOCKING gate red?**

The pushed RUN's own conclusion is authoritative: it already folds in `continue-on-error`, so a **non-blocking** job (e.g. the CI `Quality Checks` job) can NEVER block the session — it is reported as a triage item instead. Only when the run-level conclusion is `failure` does attribution run, comparing the pushed run's failing-JOB set against the base run's:

- **base green/absent/job-less → new red** = your regression → **exit 1** (fix before concluding).
- **base red → new red (same jobs)** = pre-existing → **report and exit 0** (do not wait, do not duplicate the fix).
- **all green / non-blocking** → PASSED → **exit 0**.
- **job-less base** → NOT green: a base run that exists but carries zero jobs (an invalid-workflow failure) is treated as an unknown base and fails safe (block).

When any step fails — blocking or not — the target prints the failing step's name and its run id, then that step's log details (ANSI/timestamp-stripped and indented), bounded to `DETAIL_LINES` lines (default 50), and points to `make logs <run-id> '<step-name>'` for the full step log when needed.

Attribution is deterministic: SHA → run → run-level + per-job conclusion (never "the latest run").

Key behaviors:

1. **Automatic SHA and BASE resolution.** `SHA` defaults to current `HEAD` (or `COMMIT=<sha>`), and `BASE` defaults to `HEAD~1`.
2. **Registration lag is tolerated by a bounded retry.** CI may not have registered a run for the pushed SHA immediately; the target polls `gh run list --commit <sha>` up to `RETRY_POLLS × RETRY_SLEEP` (default 10 × 2s ≈ 20s) before attributing, then fails safe if the run never registers.
3. **No CI is non-blocking.** If the repository has no workflow files under `.github/workflows/` (`*.yml`/`*.yaml`), the target logs `No CI configured - skipping attribution` and exits 0.

### Example

```makefile
RETRY_POLLS ?= 10
RETRY_SLEEP ?= 2
DETAIL_LINES ?= 50

ci-watch:
	@SHA=$$(git rev-parse $${COMMIT:-HEAD}); \
	BASE=$$(git rev-parse $${COMMIT:-HEAD}~1 2>/dev/null || echo ""); \
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
	echo "Watching CI for $$SHA (base $${BASE:-none}) after $$ATTEMPTS poll(s)"; \
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
	  if [ "$$NEWCONC" != "failure" ]; then \
	    if [ -n "$$NEWFAIL" ]; then \
	      echo "$$WF: PASSED (run=$$NEWCONC) — non-blocking failure(s) [$$NEWFAIL] — triage, does not block"; \
	    else \
	      echo "$$WF: PASSED"; \
	    fi; \
	    continue; \
	  fi; \
	  if [ -z "$$BASE" ]; then \
	    echo "$$WF: BLOCKING failure ($$NEWFAIL) — no base commit — YOUR regression"; \
	    STATUS=1; continue; \
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
```

**Usage:**
- `make ci-watch` (watches CI for current `HEAD`)
- `make ci-watch COMMIT=<sha>` (watches CI for a specific commit)

## Remote Probing Protocol (RPP)

### Example

```makefile
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
```

**Usage:** `make probe 'investigate windows path handling'`

## CI Log Extraction

The Debugger's Reproduction phase needs to read CI logs without drowning in the full run output. The `make logs` target wraps the `gh run view` pipeline, strips ANSI escapes, and removes GitHub's `##[group]`/`##[endgroup]` boilerplate.

### Example

```makefile
logs: LOGS_RUN := $(word 2,$(MAKECMDGOALS))
logs: LOGS_STEP := $(wordlist 3,99,$(MAKECMDGOALS))

logs:
	@[ -n "$(LOGS_RUN)" ] || { echo "Usage: make logs <run-id> ['<step-name>']"; exit 1; }
	@if [ -z "$(LOGS_STEP)" ]; then \
	  gh run view "$(LOGS_RUN)" --log-failed 2>/dev/null | awk -F'\t' '{ if(j!=$$1||s!=$$2){j=$$1;s=$$2;print "\n["j" > "s"]"} l=$$3; p=index(l,"Z "); if(p>0)l=substr(l,p+2); gsub(/\x1B\[[0-9;]*[a-zA-Z]/,"",l); gsub(/\^\[\[[0-9;]*[a-zA-Z]/,"",l); if(l ~ /^##\[group\]Run /){k=1;next} if(k && l ~ /^##\[endgroup\]/){k=0;next} if(k)next; if(l ~ /^##\[group\]/ || l ~ /^##\[endgroup\]/)next; gsub(/^##\[error\]/,"Error: ",l); print l }'; \
	else \
	  gh run view "$(LOGS_RUN)" --log 2>/dev/null | awk -F'\t' -v step="$(LOGS_STEP)" 'index($$2, step) > 0 { if(j!=$$1||s!=$$2){j=$$1;s=$$2;print "\n["j" > "s"]"} l=$$3; p=index(l,"Z "); if(p>0)l=substr(l,p+2); gsub(/\x1B\[[0-9;]*[a-zA-Z]/,"",l); gsub(/\^\[\[[0-9;]*[a-zA-Z]/,"",l); if(l ~ /^##\[group\]Run /){k=1;next} if(k && l ~ /^##\[endgroup\]/){k=0;next} if(k)next; if(l ~ /^##\[group\]/ || l ~ /^##\[endgroup\]/)next; gsub(/^##\[error\]/, "Error: ", l); print l }'; \
	fi

%:
	@:
```

**Usage:**
- `make logs 12345` — extract logs for ALL failed steps from run `12345`.
- `make logs 12345 'Run tests'` — extract logs for a specific step (substring match) from run `12345`.

**How it works:**
- `$(word 2,$(MAKECMDGOALS))` takes the run ID and `$(wordlist 3,99,$(MAKECMDGOALS))` captures any optional step name.
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
