# Makefile Template

> **⚠️ This is an example template.** Adapt the runner, test commands, and tool-specific details (e.g., `uv run pytest`, pre-commit hook list) to match your project's actual setup. The concrete examples shown may not work verbatim in all environments.

This template defines the standard commands for the VCP (Version Control Protocol) commit workflow
and the Debugger's Remote Probing Protocol (RPP). Below are concrete examples adapted for the TeDDy project.

## Usage

### Commit
```shell
make commit 'feat(templates): add PROJECT.md template'
make commit 'fix(tests): resolve flaky assertion' no-verify
```

**What is `.PHONY`?**
`.PHONY` is a Makefile directive that declares `commit` and `probe` as phony targets — they do not correspond to actual files. Without `.PHONY`, if a file named `commit` or `probe` existed in the directory (e.g., a script called `commit`), Make would see it as up-to-date and skip the target entirely. By declaring them phony, Make always runs the recipe when you call `make commit` or `make probe`.

### Probe
```shell
make probe 'investigate windows path handling'
```

**Why does `probe` need a reason?**
The Remote Probing Protocol requires a reason string because it is passed as the `reason` input to the GitHub Actions workflow dispatch command (`gh workflow run debug.yml --field reason='...'`). The reason documents what the probe is investigating and appears in the workflow run metadata.

## Cross-Platform Design

The Makefile uses Make's built-in `-` prefix for error suppression (`-pre-commit run`, `-git pull --rebase`, `-git push`) instead of shell-level `|| true` or `&&`/`||` chaining. This ensures cross-platform compatibility:

- **POSIX shells (bash, sh, zsh):** `-` prefix works because Make handles error suppression natively before passing the recipe line to the shell.
- **Windows (cmd.exe):** `-` prefix works because Make suppresses the exit code check, avoiding shell-specific `||` operators that cmd.exe does not support.
- **Error transparency:** If pre-commit, pull, or push fail, the commit still succeeds locally. The post-commit test gate is the real safety net; remote failures appear as non-zero exit codes in the terminal output.

## VCP Commit Workflow

### Example

```makefile
commit: ARGS := $(filter-out no-verify,$(filter-out commit,$(MAKECMDGOALS)))

commit:
	@[ -n "$(ARGS)" ] || { echo "Usage: make commit '<message>' [no-verify]"; exit 1; }
	git add .
	-pre-commit run
	git add .
	git commit -m "$(ARGS)" $(if $(filter no-verify,$(MAKECMDGOALS)),--no-verify,)
	-git pull --rebase
	-git push

%:
	@:
```

**Usage:**
- `make commit 'feat(templates): add PROJECT.md template'`
- `make commit 'fix(tests): resolve flaky assertion' no-verify`

## Remote Probing Protocol (RPP)

### Example

```makefile
probe: REASON := $(filter-out probe,$(MAKECMDGOALS))

probe:
	@[ -n "$(REASON)" ] || { echo "Usage: make probe '<reason>'"; exit 1; }
	git add -f spikes/debug/probe.sh
	git commit -m 'debug: probe' --no-verify --allow-empty
	git push
	@gh workflow run debug.yml --field reason='$(REASON)'
	@sleep 5
	@RUN_ID=$$(gh run list --workflow debug.yml -L 1 --json databaseId --jq '.[0].databaseId') && \
	gh run watch "$$RUN_ID" --exit-status >/dev/null 2>&1 && \
	gh run download "$$RUN_ID" --name probe-result --dir spikes/debugging/probe >/dev/null 2>&1 && \
	cat spikes/debugging/probe/probe_output.txt 2>/dev/null || echo "(no output file)"
```

**Usage:** `make probe 'investigate windows path handling'`

## Implementation Notes

- This project uses `uv run` as its designated runner.
- Pre-commit hooks include: ruff, mypy, detect-secrets, pip-audit.
- Post-commit hook lives at `.githooks/post-commit.py` and runs the full `uv run pytest` suite.
- Ensure `gh` (GitHub CLI) is authenticated for Remote Probing.
- Refer to the Debugger's rule 11 in the agent XML for the exact awk command to extract CI logs.
