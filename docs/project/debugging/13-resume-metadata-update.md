# Bug: Session Metadata Not Updated on Resume with Different Model
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
When resuming an existing session using `teddy resume -y` (or similar) with a different model than the one originally used, the session metadata (model name, max context tokens) is not updated to reflect the new model. The display during resume still shows the old model and potentially incorrect context limits.

**Example from user report:**
- Session originally created with `qwen/qwen3.6-flash`
- Resumed with `openrouter/deepseek/deepseek-v4-flash`
- Display shows: `• Model: qwen/qwen3.6-flash` (incorrect, expected `openrouter/deepseek/deepseek-v4-flash`)
- Expected: Metadata should be updated to reflect the new model being used for resumed execution.

## Context & Scope
### Regressing Delta
The `resume` CLI command in `__main__.py` was defined without `--model`, `--provider`, or `--api-key` parameters, unlike the `start` command which fully supports these overrides. Additionally, `handle_resume_session` in `session_cli_handlers.py` lacks these parameters in its signature.

**Components altered (current codebase):**
- `src/teddy_executor/__main__.py` - `resume()` function (missing CLI options)
- `src/teddy_executor/adapters/inbound/session_cli_handlers.py` - `handle_resume_session()` (missing function parameters and forwarding logic)

**Impact:** The metadata (meta.yaml) is never updated with the new model during resume. The telemetry display shows stale model name and context window. The actual LLM call uses the correct model due to config fallback in `PlanningService`, but the display and persisted metadata are wrong.

### Environmental Triggers
- User has an existing session with a model stored in meta.yaml
- User runs `teddy resume` (with or without `-y` flag) after changing the active model via config or environment
- The system reads the stale `model` from meta.yaml instead of the current config for the telemetry display
- Only the telemetry display is affected; the actual LLM call uses the correct model due to the fallback chain `meta.get("model") or config_service.get_setting("llm.model")` in `planning_service.py`

### Ruled Out
- The `start` command (model parameters work correctly for session creation)
- `PlanningService.generate_plan()` (model resolution logic is correct - it uses config fallback via `meta.get("model") or config_service.get_setting("llm.model")`)
- `PromptManager.update_meta()` (writes model correctly from the LLM response object)
- `SessionService.create_session()` (correctly writes initial model to meta.yaml)
- The actual LLM execution (uses correct model via fallback, only the display is wrong)

## Diagnostic Analysis
### Causal Model
1. The `resume` CLI command (`__main__.py:225-254`) does NOT accept `--model`, `--provider`, or `--api-key` parameters. These overrides are silently ignored.
2. `handle_resume_session()` (`session_cli_handlers.py:239-285`) does NOT accept or forward model/provider/api_key to the orchestrator.
3. When `SessionLifecycleManager.resume()` executes, it delegates to `PlanningService.generate_plan()`, which reads model from `meta.get("model") or config_service.get_setting("llm.model")`.
4. The `meta` dict comes from the stale `meta.yaml` (original session model). Since the meta.yaml is never overwritten during resume, the stale model is used for telemetry.
5. `PromptManager.update_meta()` writes the model from the LLM response object back to meta.yaml, but this happens AFTER telemetry display and only if a plan is generated (not for resuming a PENDING_PLAN session).
6. Result: The telemetry display shows wrong model/context window, and the meta.yaml persists the stale model between turns unless a new LLM generation occurs.

### Discrepancies
- (To be filled)

### Investigation History
1. **Grep search for resume definitions.** Found the resume flow: `__main__.py` -> `handle_resume_session()` -> `_orchestrate_session_loop()` -> `orchestrator.resume()` -> `SessionLifecycleManager.resume()`. **Confirmed the code path.**
2. **Read handler and lifecycle manager.** The `handle_resume_session()` function does NOT accept model/provider/api_key parameters. The lifecycle manager never updates meta.yaml with new model overrides. **Confirmed the gap in model propagation.**
3. **Read `__main__.py` resume signature.** The `resume()` Typer command at line 225 has 9 parameters but does NOT include `--model`, `--provider`, or `--api-key`. Compare with `start()` which has all three. **Regressing delta identified.**
4. **MRE execution (inspect.signature).** Verified that `resume` function lacks `model`, `provider`, `api_key` params. `handle_resume_session` also lacks them. **Bug reproduced via static signature analysis.**

## Solution

### Root Cause
The `resume` CLI command (`__main__.py:225-254`) and its handler (`handle_resume_session` in `session_cli_handlers.py:239-285`) were defined without `--model`, `--provider`, or `--api-key` parameters. Unlike the `start` command which accepts and forwards these overrides to `SessionOptions`, the `resume` path had no mechanism to propagate model configuration changes. As a result, the session's `meta.yaml` was never updated with the new model, causing:

1. The telemetry display to show the stale (original session) model name and context window
2. The `meta.yaml` persisted the incorrect model until a new LLM generation occurred

### Fix Strategy
1. Add `--model`, `--provider`, `--api-key` Typer options to the `resume()` function in `__main__.py` (matching the pattern used in `start()`).
2. Add corresponding `model`, `provider`, `api_key` parameters to `handle_resume_session()`.
3. In `handle_resume_session()`, after resolving the session path and before entering the turn loop, update the latest turn's `meta.yaml` if any override is provided:
   - If `model` is provided, set `meta["model"] = model`
   - If `provider` is provided, set `meta["provider"] = provider`
   - If `api_key` is provided, set `meta["api_key"] = api_key`
   - Persist the updated meta.yaml via `session_repository.save_meta()`

### Preventative Measures
- Audit all Typer commands to ensure they consistently support model/provider/api_key overrides where semantically appropriate
- Add a unit test that verifies the resume flow propagates model overrides to meta.yaml
- Add an acceptance test that simulates a full CLI resume with `--model` and verifies the model is persisted correctly
