# Slice: 02-01-Resilient Infrastructure

- **Status:** Planned
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [docs/project/specs/stability-and-bugfixes.md](/docs/project/specs/stability-and-bugfixes.md)
- **Component Docs:** [docs/architecture/adapters/outbound/litellm_adapter.md](/docs/architecture/adapters/outbound/litellm_adapter.md), [docs/architecture/core/services/context_service.md](/docs/architecture/core/services/context_service.md)

## Business Goal
Ensure the system remains operational during transient network issues and provides comprehensive context through directory expansion.

## Scenarios
> As a user, I want the LLM client to retry transient errors so that my session doesn't crash on minor network hiccups.
```gherkin
Given a LiteLLMAdapter configured with 3 retries
When a completion request is made
And the first two attempts fail with "SSLV3_ALERT_BAD_RECORD_MAC"
And the third attempt succeeds
Then the completion should return successfully
And the execution report should log the retries
```

> As a user, I want to add an entire directory to context so that I don't have to list every file individually.
```gherkin
Given a directory "src/utils" containing 3 files
When I add "src/utils" to my session context
Then the generated input.md should contain the contents of all 3 files
```

## Edge Cases
- **Exhausted Retries**: If all 3 attempts fail, then raise a `LlmApiError` to inform the user of the persistent failure.
- **Nested Ignores**: If a directory is expanded, then respect `.gitignore` in subdirectories to prevent context pollution.

## Deliverables
- [ ] **Contract** - Update `ILlmClient` if necessary for retry configuration.
- [ ] **Harness** - Create `test_litellm_retries.py` using a mock that yields side-effects.
- [ ] **Harness** - Create `test_context_recursion.py` with mock filesystem.
- [ ] **Logic** - Implement stateful retry loop in `LiteLLMAdapter.get_completion`.
- [ ] **Logic** - Update `ContextService._resolve_files_to_paths` to detect and expand directories.
- [ ] **Refactor** - Move recursive file listing logic into a shared utility or update `IFileSystemManager`.
- [ ] **Wiring** - Ensure `PlanningService` passes correct retry parameters if configurable.

## Implementation Plan
1. **Targeted Integrity Audit**: Audit `LiteLLMAdapter` and `ContextService`.
2. **Retry Loop**: Implement a `for` loop (range 3) in `get_completion`. Catch specific exceptions (`SSLV3_ALERT_BAD_RECORD_MAC`, `TimeoutError`).
3. **Recursive Context**: Update `_resolve_files_to_paths` in `ContextService`. Use `Path.is_dir()` via `IFileSystemManager`.
