.PHONY: commit probe

# commit - VCP workflow: stage, pre-commit, commit, pull, push
# Usage:
#   make commit '<type>(<scope>): <description>'       # normal commit
#   make commit '<type>(<scope>): <description>' no-verify  # bypass pre-commit checks
#
# The '-' prefix on pre-commit, pull, and push tells Make to ignore non-zero exit codes.
# This is cross-platform (works on both POSIX shells and Windows cmd.exe) and avoids
# shell-specific error-suppression operators (||, &&) that behave differently per OS.
# Pre-commit failure does NOT block the commit (it's advisory); the post-commit test
# gate is the real safety net. Pull/push failure does NOT block the local commit.

# Target-specific variables capture positional arguments before recipe execution.
# These are Make variables, not shell variables, so they persist across all recipe lines.
# $(filter-out commit,...) strips the target name from MAKECMDGOALS to get the message.
# $(filter-out NO_VERIFY=%,...) strips the optional bypass flag so it never contaminates
# the commit message. no-verify is a Make variable assignment, not part of MAKECMDGOALS,
# but the filter is defensive against edge cases.
commit: ARGS := $(filter-out no-verify,$(filter-out commit,$(MAKECMDGOALS)))

commit:
	@[ -n "$(ARGS)" ] || { echo "Usage: make commit '<message>' [no-verify]"; exit 1; }
	git add .
	-pre-commit run
	git add .
	git commit -m "$(ARGS)" $(if $(filter no-verify,$(MAKECMDGOALS)),--no-verify,)
	-git pull --rebase
	-git push

# probe - Remote Probing Protocol: push probe, trigger CI workflow, retrieve logs
# Usage:
#   make probe '<reason>'  # reason is required, appears in workflow dispatch metadata
#
# Target-specific variable captures the reason string.
# The first three lines (add, commit, push) are on separate recipe lines because
# error suppression is not needed here — we want failures to be visible.
# The dispatch/watch section uses a combined shell block because $RUN_ID is a
# shell variable that must persist across multiple commands.

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
	gh run download "$$RUN_ID" --name probe-result --dir spikes/debug/probe >/dev/null 2>&1 && \
	cat spikes/debug/probe_output.txt 2>/dev/null || echo "(no output file)"

%:
	@:
