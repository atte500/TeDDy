# Bug: Windows Default Make Targets Fail without a Diagnosis
- **Status:** Resolved
- **Milestone:** N/A (build tooling)
- **Vertical Slice:** N/A
- **Specs:** [Makefile Template](/docs/templates/makefile.md)

## Symptoms
Expected: `make ci-watch` reports a CI verdict for the pushed commit on Windows, and every default target runs from `cmd.exe`.

Actual: the reported run exited with Make status 2 and printed one generic line on stderr:

```text
make: *** [Makefile:70: ci-watch] Error 1
```

Reproduction steps from the report:

1. Open `cmd.exe` in the repository on Windows 11.
2. Run `make ci-watch` with an authenticated `gh`.

A local reproduction exits 0 for a pushed, green commit, so the failing precondition is not a missing shell, a missing tool, or an unauthenticated `gh`.

## Context & Scope
### Regressing Delta
No regressing commit. The recipe set arrived with slices 00-42 and 00-43, and the `SHELL := bash.exe` guard arrived with the template portability work. `Makefile:70` is the first physical line of the single logical `ci-watch` recipe, so the Make error names the recipe start, not a specific command.

### Environmental Triggers
- Windows 11 build 26100, `cmd.exe`, GNU Make 4.4.1 (ezwinports build from WinGet).
- `PATH` order puts the WSL launcher `C:\Windows\System32\bash.exe` ahead of `C:\Program Files\Git\bin\bash.exe`.
- `gh` 2.96.0 sits at `C:\Program Files\GitHub CLI\gh.exe`, authenticated as account `atte500` with `repo` and `workflow` scopes.
- Trigger condition: the target commit carries no registered workflow run, so the fail-safe branch exits 1.

### Ruled Out
- **CRLF corruption:** the Makefile holds 0 CRLF sequences and 205 LF sequences.
- **Make parse failure:** `make -n ci-watch` expands one logical command with intact continuations.
- **Missing shell:** Make resolves `SHELL` to `C:/Program Files/Git/bin/bash.exe`.
- **WSL bash selection:** `uname -s` reports `MINGW64_NT-10.0-26100` inside the recipe shell.
- **Missing tools:** `gh`, `git`, and `awk` resolve inside the recipe shell.
- **Unauthenticated `gh`:** `gh auth status` reports an active token with `repo` and `workflow` scopes in `cmd.exe` and in the recipe shell.
- **Absent run for the pushed commit:** `gh run list --commit 9e515b73` returns the `CI` and `Publish to PyPI` workflows.
- **Template drift:** `git diff --no-index` reports no difference between the project template copy and the packaged template copy.

### Cross-Platform Target Audit

| Target | Contract observed | Windows status | Finding |
| :----- | :---------------- | :------------- | :------ |
| `commit` | `cmd.exe` or Git Bash | works | Calls bare `pre-commit` instead of `uv run pre-commit`, which violates the runner convention. |
| `push` | `cmd.exe` | works | None. |
| `test` | `cmd.exe` | works | None. |
| `ci-watch` | Git Bash | works on a pushed, green commit | Reason on stdout only. No commit validation. No un-pushed check. Em dashes turn into mojibake in captured logs. |
| `probe` | Git Bash | not run | Single-quoted field value. Bare `sleep`. No shell preflight. |
| `logs` | Git Bash | not run | No shell preflight. Usage guard is Make-native. |

`probe` and `logs` were reviewed statically. `probe` pushes a commit and dispatches a workflow, and `logs` needs a live run id, so neither ran during discovery.

## Diagnostic Analysis
### Causal Model
On Windows, Make runs each recipe through Git Bash. `ci-watch` resolves the target commit, polls `gh run list` for a registered run, and exits 1 when no run registers within the retry window. Make converts any failed recipe into status 2 and writes one generic line to stderr. The recipe writes the reason to stdout only, so a consumer that captures stderr alone loses the diagnosis. The same command exits 0 for a pushed, green commit, so the reported run carried a different precondition. An un-pushed commit matches the no-run fail-safe branch exactly, because no run can exist for it. The recipe also assumes Git Bash without stating that contract, and it accepts an unknown `COMMIT` value without validation.

### Discrepancies
- [x] Expected a failed `ci-watch` to state its blocking reason in the captured report. Observed only the generic Make error line. (Resolved: every blocking verdict now repeats its reason on stderr, and an un-pushed commit is rejected before polling. The exact trigger of the reported run stays unconfirmed.)
- [x] Expected every default target to run from `cmd.exe` on Windows. Observed three targets that require Git Bash plus `awk`, `sed`, and `sleep`. (Resolved: the recipes embed POSIX programs, and the shell contract stays implicit.)
- [x] Expected run commands to use the designated runner. Observed `commit` calling bare `pre-commit`. (Resolved: the recipe predates the `uv run` convention.)
- [x] Expected `probe` quoting to hold on every shell. Observed a single-quoted `--field reason='...'` value that cmd.exe passes literally. (Resolved: the quoting was copied from a POSIX example.)
- [x] Expected a runless commit to produce an actionable message. Observed a generic Make error. (Resolved: every fail-safe branch prints to stdout only, and every blocking verdict now repeats its reason on stderr.)
- [x] Expected a captured watch run to retain its output. Observed empty captures on Windows. (Resolved: an ad-hoc Python capture decoded UTF-8 CI log content as cp1252 and lost the stream, while the command itself exited 0. The direct `gh` query is the authoritative verdict, and the stderr duplication keeps blocking reasons readable under a stderr-only capture.)

### Investigation History
1. Inventoried the toolchain with `make --version` and `where` in `cmd.exe`. Observed GNU Make 4.4.1 for Windows32 and the WSL launcher ahead of Git Bash on `PATH`. This fixed the shell candidates that the guard can select.
2. Ran `spikes/debug/ci-watch-windows/01-shell-resolution.mk`. Observed `SHELL=[C:/Program Files/Git/bin/bash.exe]`, `MINGW64_NT`, and visible `gh` 2.96.0 and `git`. This ruled out a shell launch failure and a missing-tool failure.
3. Inspected the Makefile bytes with Python. Observed zero CRLF sequences and 205 LF sequences, and line 70 assigns `SHA` from `git rev-parse`. This ruled out line-ending corruption.
4. Expanded the recipe with `make -n ci-watch`. Observed one logical command with intact continuations. This ruled out a Make parse failure.
5. Checked `gh` outside Make with `gh auth status` and `gh run list -L 5`. Observed an active account and five recent runs on `main`. This ruled out an authentication seam.
6. Ran `spikes/debug/ci-watch-windows/02-gh-visibility.mk` inside the recipe shell. Observed the same account and both workflows for `HEAD`. This ruled out a missing run for the pushed commit.
7. Reproduced the target with `make ci-watch`. Observed exit code 0 and no captured stdout in the report. The same command therefore succeeds for a pushed, green commit, so the reported exit 1 came from a different precondition.
8. Read every blocking branch of the recipe. Observed five branches that write the reason to stdout, set `STATUS=1`, and exit. Make prints its own generic line to stderr, so a caller that captures stderr alone loses the reason.
9. Compared the two template copies with `git diff --no-index`. Observed no difference. Both copies carry the same POSIX recipes, so every project that bootstraps from the template inherits the surface.
10. Verified the fix on the pushed commit `dd2ecdfd` by querying `gh run list --commit <sha>`. Observed the `CI` run 39433037406 and the `Publish to PyPI` run 39433206187 conclude `success`, and the re-run `make ci-watch` exit 0, which confirms the target reports a green verdict on a pushed commit. An ad-hoc Python capture decoded UTF-8 CI log content as cp1252 and lost the stream, so the direct `gh` query is the authoritative verdict.

## Solution
### Root Cause
The verified root cause is a diagnostic and contract defect, not an attribution defect. `ci-watch` writes every blocking reason to stdout, and Make reports the failure on stderr as one generic line. A consumer that captures stderr alone cannot separate an un-pushed commit from an unknown baseline or a real regression. The recipe also requires Git Bash without verifying that shell, and it accepts an unknown `COMMIT` value. The reported exit 1 matches the no-run fail-safe branch, which an un-pushed commit triggers. That trigger stays unconfirmed because the diagnostic gap is the only reproducible defect. The fix is applied to the project Makefile and both template copies, and a structural unit test now guards the cross-platform contract so the defect cannot return silently.

### Affected Components
- `Makefile`: `ci-watch` gains a shell preflight, a commit validation, an un-pushed check, and a stderr reason on every blocking branch. `probe` and `logs` gain the shell preflight and quote fixes. `commit` switches to `uv run pre-commit`. Emitted verdict text drops non-ASCII dashes.
- `docs/templates/makefile.md`: mirrors every recipe change and documents the shell contract, the `SHELL=` override remedy, and the audit result.
- `src/teddy_executor/resources/templates/makefile.md`: stays byte-identical to the project template copy.
- `tests/suites/acceptance/test_ci_watch_attribution.py`: removed, because the project does not test environment scripts. The structural unit guard below holds the contract instead.
- `tests/harness/setup/ci_watch_fake_gh.py`: removed with its only consumer, because the fake `gh` test double existed solely to drive that environment-script test.
- `tests/suites/unit/test_default_make_targets.py` (new): guards target presence, the shell preflight, the cmd-safe recipe surface, and the template lockstep.
- `spikes/debug/ci-watch-windows/`: retained as the diagnostic record, consistent with the other `spikes/debug/` cases.
