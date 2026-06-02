# Slice: 02-06-Orchestrator Hardening

- **Status:** Planned
- **Type:** Feature
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
- [ ] **Seam** - Add `get_file_hash` to `IFileSystemManager`.
- [ ] **Logic** - Update `ActionExecutor` to snapshot file hashes before plan start and verify them before every `EDIT` dispatch.
- [ ] **Logic** - Update `ShellAdapter` to detect signs of interactive prompts (TTY requests or specific stdout patterns) and fail-fast.
- [ ] **Logic** - Update `MarkdownPlanParser` and `ActionParserStrategies` to ignore and clean up unforeseen codeblocks, thematic breaks (`---`), or trailing text within codeblock delimiters (e.g., `~~~~~~ trailing text`) without triggering validation errors.
- [ ] **Harness** - Create integration test involving a shell command that modifies a file followed by an `EDIT` in the same plan.
- [ ] **Harness** - Create unit tests in `test_parser_resilience.py` specifically for thematic breaks and trailing delimiter text between actions.
