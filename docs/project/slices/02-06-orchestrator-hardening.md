# Slice: 02-06-Orchestrator Hardening

- **Status:** Planned
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
- [ ] **Hardening (UNIX)** - Refactor `ShellAdapter` to detect `SIGTTIN` in child processes and return `FAILURE: Interactive prompt detected`.
- [ ] **Hardening (Windows)** - Refine `cmd /c` wrapper and timeout logic to return `FAILURE: Interactive prompt detected` for hangs.
- [ ] **Resilience** - Update `MarkdownPlanParser` to ignore and clean up trailing text (e.g., `~~~~~~ trailing text`) within both `~~~~~~` and ` `````` ` delimiters.
- [ ] **Logic** - Implement mid-execution consistency for `EDIT`: verify file hasn't been modified externally since plan start.
- [ ] **Logic** - Update internal plan state (file hashes) after each successful `EDIT` to support sequential changes to the same file.
- [ ] **Hardening (Windows)** - Probe `WaitForInputIdle` in `ShellAdapter` for proactive interactive detection.
- [ ] **Harness** - Create unit tests for parser resilience covering both fence types and thematic breaks.
