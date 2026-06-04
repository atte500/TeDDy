# Slice: Resume Metadata Propagation on Model Change
- **Status:** To De-risk
- **Type:** Bugfix
- **Milestone:** [02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** N/A
- **Prototype:** [13_resume_metadata_mre.py](/spikes/debug/13_resume_metadata_mre.py)
- **Component Docs:** N/A

## Business Goal
Ensure that when a user resumes a TeDDy session with a different model (via `--model`, config, or environment), the session metadata (`meta.yaml`) is updated to reflect the new model immediately. This fixes telemetry display showing a stale model name and context window, and ensures subsequent turns inherit the correct model.

## Scenarios

> As a user, I want to resume a session with a different model via `--model` flag so that the telemetry display shows the correct model and the metadata persists the change.

```gherkin
Given a session exists with `meta.yaml` containing `model: "qwen/qwen3.6-flash"`
When I run `teddy resume --model "openrouter/deepseek/deepseek-v4-flash" -y`
Then the latest turn's `meta.yaml` should contain `model: "openrouter/deepseek/deepseek-v4-flash"`
And the telemetry display should show "Model: openrouter/deepseek/deepseek-v4-flash"
And the cumulative cost should be correctly carried forward
```

> As a user, I want to resume a session without model overrides so that the existing metadata is preserved.

```gherkin
Given a session exists with `meta.yaml` containing `model: "gpt-4o"`
When I run `teddy resume -y`
Then the latest turn's `meta.yaml` should still contain `model: "gpt-4o"`
```

> As a user, I want the resume command to accept `--provider` and `--api-key` overrides that are persisted to metadata.

```gherkin
Given a session exists with `meta.yaml` containing `provider: "openrouter"`
When I run `teddy resume --provider "anthropic" -y`
Then the latest turn's `meta.yaml` should contain `provider: "anthropic"`
```

## Edge Cases
- **No overrides provided:** Must not modify existing metadata (backward compatible).
- **Partial overrides:** Only provided fields (e.g., `--model` without `--provider`) should update only those fields; others remain unchanged.
- **PENDING_PLAN state:** When resuming a session with a pending plan, no new LLM call occurs. The metadata update must happen regardless of state.
- **EMPTY state:** Resume triggers planning which reads meta.yaml. The update must occur before the planning service reads it.
- **API key security:** `--api-key` value is passed in clear on the command line; document this limitation.

## Deliverables
- [ ] **Logic** - Update `handle_resume_session()` to accept and forward model/provider/api_key overrides and update meta.yaml before the turn loop.
- [ ] **Contract** - Extend the `resume()` Typer command signature with `--model`, `--provider`, `--api-key` options.
- [ ] **Harness** - Provide a unit test (`test_handle_resume_session_updates_meta_with_model`) that mocks `ISessionRepository` and verifies `save_meta` is called with the correct model.
- [ ] **Logic** - Update `__main__.py` to pass new parameters to `handle_resume_session()`.
- [ ] **Migration** - Ensure backward compatibility: existing users without `--model` flag continue to work.

## Implementation Notes
(TBD)

## Implementation Plan
1. Add parameters to `resume()` in `__main__.py` (matching `start()` pattern).
2. Add parameters to `handle_resume_session()` in `session_cli_handlers.py`.
3. Inside `handle_resume_session()`, after resolving session path and before `_orchestrate_session_loop()`:
   - Load latest turn's meta.yaml via `session_repository.load_meta()`
   - Update `model`, `provider`, `api_key` if provided
   - Save back via `session_repository.save_meta()`
4. Write regression test that verifies meta.yaml is updated.
5. Run full test suite.
6. Commit.
