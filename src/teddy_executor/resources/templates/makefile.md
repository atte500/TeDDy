# Makefile Template

This template defines the standard commands for the VCP (Version Control Protocol) commit workflow
and the Debugger's Remote Probing Protocol (RPP). Below are concrete examples adapted for the TeDDy project.

## Usage

### Commit
```shell
make commit 'feat(templates): add PROJECT.md template'
make commit 'fix(tests): resolve flaky assertion' --no-verify
```

**What is `.PHONY`?**
`.PHONY` is a Makefile directive that declares `commit` and `probe` as phony targets — they do not correspond to actual files. Without `.PHONY`, if a file named `commit` or `probe` existed in the directory (e.g., a script called `commit`), Make would see it as up-to-date and skip the target entirely. By declaring them phony, Make always runs the recipe when you call `make commit` or `make probe`.

### Probe
```shell
make probe 'investigate windows path handling'
```

**Why does `probe` need a reason?**
The Remote Probing Protocol requires a reason string because it is passed as the `reason` input to the GitHub Actions workflow dispatch command (`gh workflow run debug.yml --field reason='...'`). The reason documents what the probe is investigating and appears in the workflow run metadata.

## VCP Commit Workflow

### Example (TeDDy Project)

```makefile
.PHONY: commit probe

commit:
	args="$(filter-out $@,$(MAKECMDGOALS))"; \
	case "$$args" in \
		*--no-verify*) \
			message=$$(echo "$$args" | sed 's/ --no-verify//'); \
			no_verify="--no-verify";; \
		*) \
			message="$$args"; \
			no_verify="";; \
	esac; \
	[ -n "$$message" ] || { echo "Usage: make commit '<message>' [--no-verify]"; exit 1; }; \
	git add .; \
	pre-commit run || true; \
	git add .; \
	git commit -m "$$message" $$no_verify; \
	git pull --rebase && git push || [ -z "$$(git remote)" ]

%:
	@:
## Remote Probing Protocol (RPP)

### Example (TeDDy Project)

```makefile
probe:
	git add -f spikes/debug/remote_probe.sh
	git commit -m 'debug: probe' --no-verify
	git push
	gh workflow run debug.yml --field reason='$(REASON)'
	sleep 10
	$(eval RUN_ID := $(shell gh run list -w debug.yml -L 1 --json databaseId -q '.[0].databaseId'))
	gh run watch $(RUN_ID)
	gh run view $(RUN_ID) --log | awk -F'\t' '...'
```

**Usage:** `make probe REASON='investigate windows path handling'`

## Implementation Notes

- This project uses `uv run` as its designated runner.
- Pre-commit hooks include: ruff, mypy, detect-secrets, pip-audit.
- Post-commit hook lives at `.githooks/post-commit.py` and runs the full `uv run pytest` suite.
- Ensure `gh` (GitHub CLI) is authenticated for Remote Probing.
- Refer to the Debugger's rule 11 in the agent XML for the exact awk command to extract CI logs.
