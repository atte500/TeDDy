# Root Makefile: Entry point, global configuration, and fragment includes

.DEFAULT_GOAL := help

# Global tunable variables
RETRY_POLLS ?= 10
RETRY_SLEEP ?= 2
DETAIL_LINES ?= 50
BASE_DEPTH ?= 50
BASE_SCAN ?= 200
BASE ?=

# Include modular make fragments
-include make/base.mk
-include make/test.mk
-include make/git.mk
-include make/ci.mk
-include make/probe.mk

.PHONY: help
help:
	@echo "Available Makefile targets:"
	@echo "  make test                           - Run full test suite via pytest"
	@echo "  make commit MSG=\"<type>: <desc>\"    - Run local hooks and commit"
	@echo "  make push                           - Rebase and push to remote"
	@echo "  make ci-watch                       - Watch and attribute remote CI runs"
	@echo "  make probe REASON=\"<reason>\"        - Trigger remote probe workflow"
	@echo "  make logs RUN=<id> [STEP=\"<name>\"]  - Extract failed CI step logs"
