# Makefile Template

This template defines the standard commands for the VCP (Version Control Protocol) commit workflow
and the Debugger's Remote Probing Protocol (RPP). Below are concrete examples adapted for the TeDDy project.

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
