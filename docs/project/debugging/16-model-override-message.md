# Bug: Configuration Check Message Ignores `--model` Override
- **Status:** Resolved
- **Milestone:** [N/A](/docs/project/milestones/02-stability-and-polish.md)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
When starting a session with `--model openrouter/deepseek/deepseek-v4-pro:nitro`, the "Checking configurations..." message prints a different model (e.g., `openrouter/deepseek/deepseek-v4-flash:nitro`). The session later correctly uses the overridden model, confirming the override works for execution but not for the startup message.

Expected: `API key valid! Model: openrouter/deepseek/deepseek-v4-pro:nitro | Agent: pathfinder`
Actual: `API key valid! Model: openrouter/deepseek/deepseek-v4-flash:nitro | Agent: pathfinder`

## Context & Scope
### Regressing Delta
The bug is in the `_echo_config_success` function in `src/teddy_executor/adapters/inbound/session_cli_handlers.py`. The function retrieves the model from `config_service.get_setting("llm.model", "unknown")` instead of using any passed override.

The function signature (line 149):
```python
def _echo_config_success(container: Container, agent: Optional[str] = None) -> None:
```

It has no `model` parameter. Both call sites (`handle_new_session` at line 101 and `handle_resume_session` at line 257) have access to a `model` parameter from CLI parsing but do not pass it through.

### Environmental Triggers
- Triggered by any invocation of `teddy start --model <override>` or `teddy resume --model <override>`

### Ruled Out
- The session execution correctly uses the override model (confirmed by the session metadata display).
- The config service itself correctly handles overrides (the bug is only in the display function).

## Diagnostic Analysis
### Causal Model
The startup sequence in `handle_new_session`:
1. CLI parses `model` from `--model` flag
2. `_echo_config_success(container, agent)` is called — but `model` override is NOT passed
3. Inside `_echo_config_success`, `config_service.get_setting("llm.model", "unknown")` retrieves the **config file** value, not the override
4. The override is correctly stored in `SessionOptions` and used for session creation, but the display message uses the stale config value

### Discrepancies
- `_echo_config_success` does not accept a `model` parameter despite having callers that possess the override value. (Resolved: root cause identified.)
- `handle_resume_session` also fails to pass its `model` parameter to `_echo_config_success`. (Resolved: same root cause.)

### Investigation History
1. Grep for "Checking configurations" found source in `session_cli_handlers.py` at lines 99 and 254.
2. Read `session_cli_handlers.py` and traced `_echo_config_success` — confirmed the function retrieves model from config service instead of using CLI override parameter.
3. Confirmed both call sites (`handle_new_session` and `handle_resume_session`) receive `model: Optional[str] = None` but do not pass it through.

## Solution
### Root Cause
`_echo_config_success` in `src/teddy_executor/adapters/inbound/session_cli_handlers.py` reads the model from the static config file via `config_service.get_setting("llm.model", "unknown")` instead of accepting an optional model override parameter from the CLI. Both call sites (`handle_new_session` and `handle_resume_session`) receive `model: Optional[str] = None` from CLI parsing but never pass it through.

### Fix Applied
1. **`_echo_config_success` signature updated** (line 149): Added `model: Optional[str] = None` parameter.
2. **`_echo_config_success` body updated**: If `model` is provided, use it directly; otherwise, fall back to `config_service.get_setting("llm.model", "unknown")`.
3. **`handle_new_session` call site updated** (line 101): Now calls `_echo_config_success(container, agent, model=model)`.
4. **`handle_resume_session` call site updated** (line 257): Now calls `_echo_config_success(container, model=model)`.

### Verification
- **MRE**: `spikes/debug/16-model-override-mre.py` reproduces the bug and verifies the fix via shadow file.
- **Regression test**: `tests/suites/unit/adapters/inbound/test_bug_16_model_override_message.py` passes (GREEN).
- **Full test suite**: 831 passed, 3 skipped — no regressions.

### Preventative Measures
- All display/echo functions should respect CLI override parameters. Currently, `_echo_config_success` is the only such function and is now fixed.
- For future development, consider a "resolved settings" pattern where CLI overrides, config file values, and defaults are consolidated into a single resolved settings object before being passed through the system, rather than allowing multiple code paths to read from different sources.
