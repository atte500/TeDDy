# Bug: Resume Status Displays Unknown Context Window and Session Cost
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
After interrupting a session and running `teddy resume`, the first turn status block displays:

```
• Context: 56.2k / ??? tokens
• Session Cost: $???
```

Expected behavior: the resumed turn displays the persisted maximum context window and cumulative session cost from the interrupted session metadata. The actual behavior replaces both values with `???`.

Minimal reproduction steps:
1. Start a session and complete at least one turn.
2. Interrupt the session with `q`.
3. Resume the session with `teddy resume`.
4. Observe the status block on the first resumed turn.

## Context & Scope
### Regressing Delta
- `17838fba` added `actual_model` carry-over in `SessionService.transition_to_next_turn` to preserve display continuity across turns.
- `4fd6bb70` added the resume-time `meta.pop("actual_model", None)` but did not mark the metadata dirty, so the clear reaches disk only when a model or api_key override changes another field.

### Environmental Triggers
Interactive session resume. Specific operating system and provider are not yet confirmed as relevant.

### Ruled Out
None yet.

## Diagnostic Analysis
### Causal Model
1. `SessionService.transition_to_next_turn` copies `actual_model` from the completed turn into the next turn's `meta.yaml`.
2. On resume, `_sync_and_display_session_meta` loads the latest turn's `meta.yaml` and removes `actual_model` in memory only. Without a model or api_key override, no field changes, so `save_meta` is skipped and the bare served model stays on disk.
3. `PlanningService._display_telemetry` prefers `meta["actual_model"]` over `meta["model"]`. A fresh resume process has not hydrated that bare served model into the LiteLLM registry, so `get_context_window` returns 0.
4. The formatter gates both the context window and the session cost on `context_window > 0`. The first resumed turn therefore renders `???` and `$???`. After the first completion, `update_meta` hydrates the registry and later turns resolve normally.

### Discrepancies
- [x] The first resumed turn shows `???` for the context window. (Resolved: the stale bare `actual_model` is absent from the fresh process registry, so `get_context_window` returns 0.)
- [x] The first resumed turn shows `$???` for the session cost. (Resolved: the cost placeholder shares the same `context_window > 0` gate as the context window placeholder.)

### Investigation History
1. Located the status block formatter in `planning_service.py:219` and `planning_service.py:229`.
2. Found existing tests that accept `$???` in `tests/suites/unit/core/services/test_planning_service.py:209` and `:247`.
3. Found acceptance coverage for cumulative session cost in `tests/suites/acceptance/test_ai_telemetry.py`.
4. Built `spikes/debug/resume-telemetry-placeholders/01-resume-telemetry-placeholders-mre.py`; the real `PlanningService._display_telemetry` with an empty LiteLLM registry and a stale `actual_model` printed `• Context: … / ??? tokens` and `• Session Cost: $???`, confirming the symptom.
5. Ran the resume helper with the real `SessionRepository` over an in-memory file store; without an override `actual_model` stayed on disk and `save_meta` was never called, while a model override persisted the clear. This confirms the unsaved pop.
6. Read `test_model_override_on_resume.py`; the no-override test wraps its assertions in `if repo.save_meta.called:` and its config mock returns `"unknown"`, so `changed` stays False and the guarded block is skipped. The test passes vacuously and never exercises the defect.
7. Built the sandbox replica `replica_session_cli_handlers.py`, which marks the metadata dirty when `actual_model` is removed, and ran `02-verify-replica-fix.py`. The no-override resume persisted the clear, and the following telemetry resolved a numeric window and `$0.0500`.
8. Applied the verified fix to `src/teddy_executor/adapters/inbound/session_cli_handlers.py` and replaced the vacuous guarded assertions in `test_model_override_on_resume.py`. Both resume metadata modules passed with the production fix in place.
9. Cleaned up two pre-existing debts under user approval: removed the unused `actual_model` parameter from `_echo_config_success`, and replaced the guarded block in `test_resume_without_overrides_preserves_meta` with an unconditional `save_meta` not-called assertion.

### Reproduction Artifacts
- [Minimal reproducible example](/spikes/debug/resume-telemetry-placeholders/01-resume-telemetry-placeholders-mre.py)
- [Replica verification](/spikes/debug/resume-telemetry-placeholders/02-verify-replica-fix.py)
- [Sandbox replica](/spikes/debug/resume-telemetry-placeholders/replica_session_cli_handlers.py)

## Solution
### Root Cause
`_sync_and_display_session_meta` removed `actual_model` from the in-memory metadata on resume but did not flag the removal as a change. Without a model or api_key override, `changed` stayed False, so `save_meta` never ran and the stale bare served model stayed on disk. `SessionService` then carried that value into the next turn. `PlanningService._display_telemetry` prefers `actual_model`, and a fresh resume process had not hydrated that bare served ID into the LiteLLM registry, so `get_context_window` returned 0 and both the context window and the session cost rendered as `???` and `$???`. The fix was proven in the sandbox replica and then applied directly to `src/`.

### Affected Components
- `session_cli_handlers.py: _sync_and_display_session_meta`: now sets `changed = True` when it removes `actual_model`, so the clear reaches disk without an override.
- `test_model_override_on_resume.py`: the no-override test now asserts a single `save_meta` call, the absent `actual_model`, the preserved `model`, and the preserved `cumulative_cost` unconditionally.
- `SessionService.transition_to_next_turn`: still carries `actual_model` forward; no change required because the resume helper now clears it.
- `session_cli_handlers.py: _echo_config_success`: removed the unused `actual_model` parameter; resolution is the CLI model override, then the config model.
- `test_session_cli_handlers_resume_meta.py`: `test_resume_without_overrides_preserves_meta` now asserts `save_meta` is not called unconditionally instead of guarding the block.
