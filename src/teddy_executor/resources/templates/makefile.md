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
`.PHONY` is a Makefile directive that declares `commit`, `push`, `probe`, `test`, and `logs` as phony targets — they do not correspond to actual files. Without `.PHONY`, if a file named `commit` or `probe` existed in the directory (e.g., a script called `commit`), Make would see it as up-to-date and skip the target entirely. By declaring them phony, Make always runs the recipe when you call `make commit`, `make push`, `make probe`, or `make test`.

### Push
```shell
make push
```

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
make logs 12345 'Run tests'
```

**Why does `logs` take two arguments?**
The first argument is the GitHub Actions run ID (as shown by `gh run list`); the second is the exact name of a step in that run's execution tree (as shown by `gh run view <id>`). The target extracts ONLY that step's logs, stripping ANSI escapes and GitHub's group/boilerplate markers so you see the failure without the noise of the full log. See the [CI Log Extraction](#ci-log-extraction) section for the recipe.

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

`make push` runs `git pull --rebase`, captures the base and the pushed SHA, pushes, then discovers **every** CI run for the pushed SHA (`gh run list --commit <sha>`) and waits for and reports each workflow with its jobs. It answers ONE question: **did this push turn a BLOCKING gate red?**

The pushed RUN's own conclusion is authoritative: it already folds in `continue-on-error`, so a **non-blocking** job (e.g. the CI `Quality Checks` job) can NEVER block the session — it is reported as a triage item instead. Only when the run-level conclusion is `failure` does attribution run, comparing the pushed run's failing-JOB set against the base run's:

- **base green/absent/job-less → new red** = your regression → **exit 1** (fix before concluding).
- **base red → new red (same jobs)** = pre-existing → **report and exit 0** (do not wait, do not duplicate the fix).
- **all green / non-blocking** → PASSED → **exit 0**.
- **job-less base** → NOT green: a base run that exists but carries zero jobs (an invalid-workflow failure) is treated as an unknown base and fails safe (block).

Attribution is deterministic: SHA → run → run-level + per-job conclusion (never "the latest run").

Three behaviors make the attribution trustworthy:

1. **The base is captured BEFORE the push.** `BASE=$$(git rev-parse origin/main)` is read immediately after `git pull --rebase` and before `git push`; otherwise the push advances `origin/main` and `BASE` collapses onto the pushed SHA, making every comparison trivially equal (a real regression would be silently misclassified as pre-existing). `git push` is folded into the same shell block behind `|| exit $$?` so a rejected push still aborts the target.
2. **Registration lag is tolerated by a bounded retry.** CI may not have registered a run for the pushed SHA yet; the target polls `gh run list --commit <sha>` up to `RETRY_POLLS × RETRY_SLEEP` (default 10 × 1s ≈ 10s) before attributing, then fails safe if the run never registers.
3. **No CI is non-blocking.** If the repository has no workflow files under `.github/workflows/` (`*.yml`/`*.yaml`), the target logs `No CI configured - skipping attribution` and exits 0 — a CI-less repo is never blocked. This is distinct from a repo WITH CI whose pushed SHA registered no run (that still fail-safe blocks).

### Example

```makefile
RETRY_POLLS ?= 10
RETRY_SLEEP ?= 1

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
	  if [ -n "$$NEWSTEPS" ]; then echo "$$WF: failing step(s): $$NEWSTEPS"; fi; \
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
```

**Usage:** `make push`

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

The Debugger's Reproduction phase needs to read the logs of a specific failed CI step without drowning in the full run log. The `make logs` target wraps the `gh run view <id> --log | awk ...` pipeline that isolates the named step's output, strips ANSI escapes, and removes GitHub's `##[group]`/`##[endgroup]` boilerplate.

### Example

```makefile
logs: LOGS_RUN := $(word 2,$(MAKECMDGOALS))
logs: LOGS_STEP := $(wordlist 3,99,$(MAKECMDGOALS))

logs:
	@[ -n "$(LOGS_RUN)" ] || { echo "Usage: make logs <run-id> '<step-name>'"; exit 1; }
	@gh run view "$(LOGS_RUN)" --log | awk -F'\t' -v step="$(LOGS_STEP)" '$$2==step { if(j!=$$1){j=$$1; print "\n["j"]"} l=$$3; p=index(l,"Z "); if(p>0)l=substr(l,p+2); gsub(/\x1B\[[0-9;]*[a-zA-Z]/, "", l); gsub(/\^\[\[[0-9;]*[a-zA-Z]/, "", l); if(l ~ /^##\[group\]Run /){k=1;next} if(k && l ~ /^##\[endgroup\]/){k=0;next} if(k)next; if(l ~ /^##\[group\]/ || l ~ /^##\[endgroup\]/)next; gsub(/^##\[error\]/, "Error: ", l); print l }'

%:
	@:
```

**Usage:**
- `make logs 12345 'Run tests'` — extract the logs of the step named `Run tests` from run `12345`.
- First discover the run ID and the failed step name with `gh run view 12345` (the execution tree), then pass both to `make logs`.

**How it works:**
- `$(word 2,$(MAKECMDGOALS))` takes the run ID and `$(wordlist 3,99,$(MAKECMDGOALS))` takes the (space-containing) step name; the first goal (the `logs` target itself) is dropped.
- The `awk` program matches rows whose second tab-separated field equals the step name via `-v step=...`, trims the leading timestamp, strips ANSI escape sequences, and removes GitHub's group boilerplate, prefixing `##[error]` lines with `Error: `.
- It reuses the same cross-platform Make constructs as the other targets (see [Cross-Platform Design](#cross-platform-design)); the `%: @:` catch-all prevents the extra `make` goals from being treated as files.

## Implementation Notes

- This project uses `uv run` as its designated runner.
- Local pre-commit hooks include only fast auto-fixers (`ruff`) + `detect-secrets` + `check-merge-conflict`; heavier checks (`mypy`, `bandit`, `pip-audit`, and the structural checkers) run non-blocking in CI (see [pre-commit.md](./pre-commit.md)).
- Post-commit hook lives at `.githooks/post-commit.py` and runs the full `uv run pytest` suite.
- Ensure `gh` (GitHub CLI) is authenticated for `make push`, the Remote Probing Protocol, and CI Log Extraction.
- The `make logs` target abstracts the Debugger's CI-log extraction (Phase 1, Step 2). See [CI Log Extraction](#ci-log-extraction).
- `make push` runs in the session Conclusion phase (see [Push (Deferred to Conclusion)](#push-deferred-to-conclusion)); it rebases, pushes, and reports CI results back.
