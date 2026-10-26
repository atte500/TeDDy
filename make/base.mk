# make/base.mk - Shell configuration, goal validation, and internal preflight checks

# Named inputs for targets that require values. Passing values as NAME="..."
# ensures words in descriptions or reasons never execute as goals.
MSG ?=
REASON ?=
RUN ?=
STEP ?=

# Goal validation: Make builds goals in order, so an arbitrary command-line word
# could trigger unintended execution. Reject multiple goals and unknown goals.
_KNOWN_GOALS := ci-watch commit help logs probe push test
_UNKNOWN_GOALS := $(filter-out $(_KNOWN_GOALS),$(MAKECMDGOALS))
ifneq ($(words $(MAKECMDGOALS)),0)
ifneq ($(words $(MAKECMDGOALS)),1)
$(error Detected $(words $(MAKECMDGOALS)) goals: $(MAKECMDGOALS). Pass values as NAME="value", as in: make commit MSG="<type>(<scope>): <description>")
endif
endif
ifneq ($(_UNKNOWN_GOALS),)
$(error Unknown target '$(_UNKNOWN_GOALS)'. Run make help for the list of targets.)
endif

# Cross-platform shell configuration:
# On Windows every target runs through Git Bash so quoting and fallbacks tokenize identically.
ifeq ($(OS),Windows_NT)
    SHELL := bash.exe
    .SHELLFLAGS := -c
    SHELL_CHECK = uname -s 2>/dev/null | grep -Eq 'MINGW|MSYS'
else
    SHELL_CHECK = true
endif

# _preflight - Verify tools required by POSIX pipelines before network or CI calls.
.PHONY: _preflight
_preflight:
	@command -v git >/dev/null 2>&1 || { echo "ERROR: git is not on PATH inside the recipe shell." >&2; exit 1; }; \
	command -v gh >/dev/null 2>&1 || { echo "ERROR: gh is not on PATH. Install the GitHub CLI, then run gh auth login." >&2; exit 1; }; \
	command -v awk >/dev/null 2>&1 || { echo "ERROR: awk is not on PATH inside the recipe shell. Git Bash ships gawk." >&2; exit 1; }; \
	command -v sed >/dev/null 2>&1 || { echo "ERROR: sed is not on PATH inside the recipe shell. Git Bash ships sed." >&2; exit 1; }; \
	$(SHELL_CHECK) || { echo "ERROR: the recipe shell is not Git Bash. Install Git for Windows, or pass SHELL=\"C:/Program Files/Git/bin/bash.exe\"." >&2; exit 1; }
