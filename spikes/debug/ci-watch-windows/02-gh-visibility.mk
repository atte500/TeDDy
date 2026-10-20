ifeq ($(OS),Windows_NT)
    SHELL := bash.exe
    .SHELLFLAGS := -c
endif

ghcheck:
	@echo "HOME=[$$HOME]"
	@gh auth status || echo "gh auth status FAILED"
	@gh run list -L 3 --json databaseId,workflowName,status,conclusion || echo "gh run list FAILED"
	@echo "SHA=$$(git rev-parse HEAD)"
	@gh run list --commit "$$(git rev-parse HEAD)" --json workflowName --jq '.[].workflowName' | sort -u || echo "no workflows for SHA"