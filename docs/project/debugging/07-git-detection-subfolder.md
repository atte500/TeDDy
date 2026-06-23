# Bug: Git Repository Detected in New Subfolder

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

- **Expected:** Running `teddy start` in a newly created empty subdirectory should not claim “Git repository detected” unless that subdirectory itself is a git repository.
- **Actual:** `teddy start` prints “✓ Git repository detected” even in a brand‑new subfolder (e.g., `testium`) created inside the TeDDy project.
- **Steps:**
  1. `cd /path/to/TeDDy`
  2. `mkdir testium && cd testium`
  3. `teddy start`
  4. Observe “✓ Git repository detected”.

## Context & Scope

### Regressing Delta
The bug exists in the current state of the codebase (the behavior has likely been present since `_check_git_initialized` was introduced). No recent commit introduced this; it is a design‑level issue in how git detection is implemented.

### Environmental Triggers
- Must be inside a git repository (parent directory has `.git`).
- Must be in a subdirectory that is not itself a git repo (no local `.git`).
- Git CLI must be available.

### Ruled Out
- The `_ensure_commit_hooks` function is unrelated – it only checks for `.pre-commit-config.yaml`.
- The `start` command’s other startup logic (health checks, pre‑flight checks) does not affect git detection.

## Diagnostic Analysis

### Causal Model
`_check_git_initialized()` uses `subprocess.run(["git", "rev-parse", "--git-dir"])` to test whether the current working directory is inside a git repository. `git rev-parse --git-dir` searches up the directory tree for a `.git` directory. If any ancestor directory contains a `.git`, the command succeeds and the function prints “Git repository detected”. The current directory is only checked indirectly – there is no check to verify that the found `.git` belongs to the current directory itself.

### Discrepancies
- (none yet)

### Investigation History
1. Hypothesized that `_check_git_initialized` uses `git rev-parse --git-dir` which walks up the directory tree. Observed the source code in `session_cli_handlers.py` lines 85-89 confirming the command. Created MRE in `spikes/debug/07-git-detection-subfolder-mre.py` that calls the function from a temp subfolder inside the TeDDy repo. MRE executed and printed "✓ Git repository detected" to stderr. Conclusion: The causal model is confirmed; `git rev-parse --git-dir` finds the parent `.git` directory belonging to the root TeDDy project.
2. Shadow fix: replaced `git rev-parse --git-dir` with `(Path.cwd() / ".git").exists()` in a shadow file. Updated MRE to import from shadow and re-executed. MRE printed "✓ Git repository initialized". Conclusion: The fix works — CWD-only detection correctly fails to find the parent repo and falls through to `git init`.
3. Applied the fix to production code. Regression test and full suite passed. Bug resolved.

## Solution

**Root Cause:** `_check_git_initialized()` used `git rev-parse --git-dir`, which searches up the directory tree for a `.git` directory. When running `teddy start` in a new subfolder inside an existing git repo (e.g., TeDDy project), the command finds the parent `.git` and reports "Git repository detected", misleading users into thinking the new folder itself is a repo.

**Fix:** Replaced the `git rev-parse --git-dir` subprocess call with a simple `(Path.cwd() / ".git").exists()` check. This checks only the current working directory for a `.git` marker (directory or worktree file). If not found, the function falls through to `git init` and prints "Git repository initialized".

**Preventative Measures:**
- The new logic is simpler and more explicit: it checks for the actual `.git` file/directory in CWD rather than relying on git subprocess behavior that implicitly walks parents.
- Any future git detection should use `Path.cwd() / ".git"` existence check rather than `git rev-parse` to avoid parent-walking surprises.
