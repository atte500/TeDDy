ifeq ($(OS),Windows_NT)
    SHELL := bash.exe
    .SHELLFLAGS := -c
endif

probe:
	@echo "make SHELL=[$(SHELL)]"
	@command -v bash || echo "bash NOT VISIBLE"
	@command -v gh || echo "gh NOT VISIBLE"
	@command -v git || echo "git NOT VISIBLE"
	@uname -s 2>/dev/null || echo "uname NOT VISIBLE"
	@git rev-parse --show-toplevel || echo "git rev-parse FAILED"
	@gh --version || echo "gh version FAILED"