.PHONY: commit probe

# commit - VCP workflow: stage, pre-commit, commit, pull, push
# Usage:
#   make commit '<type>(<scope>): <description>'       # normal commit
#   make commit '<type>(<scope>): <description>' NO_VERIFY=1  # bypass pre-commit checks
#
# The '-' prefix on pre-commit, pull, and push tells Make to ignore non-zero exit codes.
# This is cross-platform (works on both POSIX shells and Windows cmd.exe) and avoids
# shell-specific error-suppression operators (||, &&) that behave differently per OS.
# Pre-commit failure does NOT block the commit (it's advisory); the post-commit test
# gate is the real safety net. Pull/push failure does NOT block the local commit.

commit:
	@args="$(filter-out $@,$(MAKECMDGOALS))"; \
	[ -n "$$args" ] || { echo "Usage: make commit '<message>' [NO_VERIFY=1]"; exit 1; }
	git add .
	-pre-commit run
	git add .
	git commit -m "$$args" $(if $(NO_VERIFY),--no-verify,)
	-git pull --rebase
	-git push

# probe - Remote Probing Protocol: push probe, trigger CI workflow, retrieve logs
# Usage:
#   make probe '<reason>'  # reason is required, appears in workflow dispatch metadata

probe:
	@args="$(filter-out $@,$(MAKECMDGOALS))"; \
	[ -n "$$args" ] || { echo "Usage: make probe '<reason>'"; exit 1; }
	git add -f spikes/debug/remote_probe.sh
	git commit -m 'debug: probe' --no-verify
	git push
	gh workflow run debug.yml --field reason="$$args"
	sleep 10
	RUN_ID=$$(gh run list -w debug.yml -L 1 --json databaseId -q '.[0].databaseId')
	gh run watch $$RUN_ID
	gh run view $$RUN_ID --log

%:
	@:
