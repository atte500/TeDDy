# Slice: 02-06-Orchestrator Hardening

- **Status:** In Progress
- **Type:** Refactor
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [docs/project/specs/stability-and-bugfixes.md](/docs/project/specs/stability-and-bugfixes.md)

## Business Goal
Ensure plan execution is resilient to mid-plan changes and provides immediate feedback for irreversible or interactive failures.

## Scenarios
> As a user, I want EDIT actions to fail gracefully if an EXECUTE action in the same plan changed the file, so that I don't corrupt my code with stale diffs.
```gherkin
Given a plan with:
  1. EXECUTE "sed -i 's/a/b/g' file.py"
  2. EDIT file.py (based on original content 'a')
When I run the plan
Then the EDIT action should return FAILURE with a "File content modified during execution" message.
```

> As a user, I want the CLI to fail fast if an EXECUTE command triggers an interactive prompt, so that I don't hang indefinitely in YOLO mode.
```gherkin
Given a plan with an EXECUTE that prompts for input (e.g. "read -p")
When I run with --yolo
Then execution should fail immediately with an "Interactive prompt detected" error.
```

## Deliverables
- [x] **Harness** - Unit tests for `ShellAdapter` UNIX interactive prompt detection (SIGTTIN scenario).
- [ ] **Logic** - Implement SIGTTIN detection in `ShellAdapter` to return `FAILURE: Interactive prompt detected`.
- [ ] **Harness** - Unit tests for `ShellAdapter` Windows interactive prompt detection (`cmd /c` wrapper, timeout logic).
- [ ] **Logic** - Implement Windows interactive prompt detection in `ShellAdapter`.
- [ ] **Harness** - Unit tests for `MarkdownPlanParser` trailing-text cleanup within fences and thematic breaks.
- [ ] **Logic** - Implement trailing-text and thematic-break cleanup in `MarkdownPlanParser`.
- [ ] **Harness** - Unit tests for mid-execution `EDIT` consistency (file hash tracking and modification detection).
- [ ] **Logic** - Implement mid-execution `EDIT` consistency: hash tracking after each successful edit and verification against external modifications.
- [ ] **Wiring** - Acceptance test for `EXECUTE` fail-fast scenario (interactive prompt detected → `FAILURE`).
- [ ] **Wiring** - Acceptance test for `EDIT` mid-execution consistency scenario (file modified externally → `FAILURE`).

## Implementation Notes
- **Plan Audit (Orientation):** Deliverables reordered into Dependency Sequence (Harness → Logic → Wiring). Combined "Hardening" deliverables split into Harness/Logic pairs. Added two Wiring deliverables for the Gherkin scenarios. No breaking changes identified — all port signatures remain unchanged.

### Deliverable 1: ShellAdapter UNIX Interactive Prompt Detection
- **Approach:** Used pattern-based detection via `_detect_interactive_prompt` static method checking stderr for EOFError/input patterns. Integration happens in `_process_execution_results` after the `FAILED_COMMAND:` marker block, overriding stdout with `"FAILURE: Interactive prompt detected"` when patterns match and `return_code != 0`.
- **Test Strategy:** Two unit tests: (1) positive case using `python -c "input('> ')"` with stdin=DEVNULL (triggers EOFError), (2) negative sanity check with `echo hello`. Both tests pass green.
- **Key Design Decision:** Exposed `INTERACTIVE_PROMPT_MESSAGE` as a class constant (`ShellAdapter.INTERACTIVE_PROMPT_MESSAGE`) for reuse by downstream consumers (e.g., Windows detection adapter or Wiring acceptance tests).
- **Scope Heuristic:** No refactoring needed; DI purity maintained (direct constructor injection), no magic numbers, no global patching.
