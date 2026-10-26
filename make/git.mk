# make/git.mk - Version Control Targets

ifneq ($(filter commit,$(MAKECMDGOALS)),)
ifeq ($(strip $(MSG)),)
$(error Usage: make commit MSG="<type>(<scope>): <description>")
endif
endif

.PHONY: commit push

commit:
	git add .
	@uv run pre-commit run || echo "Pre-commit auto-fixes applied. Staging changes and continuing to commit gate."
	git add .
	git commit -m "$(MSG)"

push:
	git pull --rebase
	git push
