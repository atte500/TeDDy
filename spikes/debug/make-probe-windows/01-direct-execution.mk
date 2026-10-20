# Reproduces GNU Make's direct-execution path on Windows.
# A recipe line with no shell metacharacters can bypass SHELL and be spawned
# with CreateProcess, so a Git Bash-only program such as sleep fails with
# "process_begin: CreateProcess(NULL, sleep 1, ...) failed".
ifeq ($(OS),Windows_NT)
    SHELL := bash.exe
    .SHELLFLAGS := -c
endif

.PHONY: bare quoted semicolon via-bash

bare:
	@sleep 1
	@echo BARE-OK

quoted:
	@sleep 1 && echo QUOTED-OK

semicolon:
	@sleep 1;
	@echo SEMICOLON-OK

via-bash:
	@bash.exe -c "sleep 1" && echo VIA-BASH-OK