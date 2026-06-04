# Bug: OpenRouter Shortcuts Break Context Cost Gathering
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
**Expected:** When using a model string with OpenRouter shortcut (e.g., `openrouter/deepseek/deepseek-v4-flash:nitro`), the context token count and session cost should display the correct numeric values.
**Actual:** Context and cost show `???` instead of numeric values.
**Reproduction Steps:**
1. Configure a session or plan with a model string containing `:nitro` or `:floor` shortcut (e.g., `openrouter/deepseek/deepseek-v4-flash:nitro`).
2. Execute a turn that triggers cost/context reporting.
3. Observe that context token count and session cost display `???`.

## Context & Scope
### Regressing Delta
[To be determined – likely introduced when shortcut syntax was implemented without updating cost lookup logic.]

### Environmental Triggers
- Occurs whenever the model string includes a colon-based shortcut suffix (`:nitro`, `:floor`).
- Not platform-specific.

### Ruled Out
[Nothing ruled out yet.]

## Diagnostic Analysis
### Causal Model
1. The user configures a model string containing an OpenRouter routing shortcut suffix (e.g., `:nitro` or `:floor`), e.g., `openrouter/deepseek/deepseek-v4-flash:nitro`.
2. `LiteLLMAdapter` uses this raw model string (with shortcut) when calling `get_context_window()` and `get_completion_cost()`.
3. `get_context_window()` looks up the model in `litellm.model_cost` dict – the key `"deepseek/deepseek-v4-flash:nitro"` does not exist; the registry only has the base model ID.
4. If that fails and a `hydrator` is provided, `get_context_window()` calls `hydrator.get_metadata()`, which also fails because `OpenRouterMetadataHydrator.get_metadata()` only strips trailing numeric suffixes (e.g., `-20240525`) but does NOT strip colon-based suffixes (`:nitro`, `:floor`).
5. Similarly, `get_completion_cost()` attempts `litellm.completion_cost()`; litellm raises `"This model isn't mapped yet"` for unknown model strings. The fallback path calls `hydrator.get_metadata()` which again fails to strip the colon suffix, returning `None`, leading to a `0.0` cost fallback.
6. The session cost display (via `planning_service.py` and `session_loop_guard.py`) calls `get_completion_cost()` which returns 0.0, and context window shows ??? because 0 is interpreted as "unknown".

### Discrepancies
- Current hydrator strips numeric suffixes (`-\d{8,12}`) but NOT colon-based routing shortcuts. This contradicts the Causal Model's assumption that all model ID suffixes are handled. (resolved: Shadow file with colon-stripping logic in `get_metadata()` (`re.sub(r":[^/:]+$", "", clean_id)`) was verified via MRE; all three lookup paths now return correct values for `:nitro` models.)
- The `get_completion_cost` fallback to hydrator only triggers if `litellm.completion_cost` raises the "not mapped" error. If litellm silently returns 0.0 for unknown models, the hydrator fallback is never attempted. (resolved: probe confirmed litellm raises "This model isn't mapped yet" for unmapped models, so the fallback path is correctly triggered.)

### Investigation History
1. Probe (12-openrouter-shortcuts-probe.py) created but not executed (failed due to missing `python` command). Hypothesized that `:nitro`/`:floor` suffixes are not stripped in `OpenRouterMetadataHydrator.get_metadata()` nor in `LiteLLMAdapter.get_context_window()`/`get_completion_cost()`, causing fallback to `0`/`0.0`.
2. Grep for `completion_cost` in `core/services/` revealed that `planning_service.py` calls `self._llm_client.get_completion_cost()` to accumulate turn costs, and `session_loop_guard.py` reads the `max_session_cost` guardrail from config. This confirms the call chain: model string with shortcut → `get_completion_cost()` → fallback → 0.0 → session displays `???`.
3. Probe re-executed (fixed mock) with `poetry run python`. All three test functions passed cleanly (exit code 0):
   - `test_shortcut_lookup`: Hydrator returns `None` for `:nitro` models, succeeds for clean model.
   - `test_context_window_failure`: `get_context_window()` returns `0` for shortcut model, `128000` for clean.
   - `test_get_completion_cost_shortcut`: `get_completion_cost()` returns `0.0` (fallback) for shortcut model.
   Root cause confirmed: colon-based routing shortcuts (`:nitro`, `:floor`) are not stripped anywhere in the lookup path (hydrator `get_metadata()`, context window lookup, cost lookup).
4. Shadow verification (spikes/debug/shadow_openrouter_hydrator.py) with colon-stripping fix (added `re.sub(r":[^/:]+$", "", clean_id)` in `get_metadata()` after prefix removal). MRE updated to import shadow file. All three tests passed with exit code 0:
   - `test_shortcut_lookup`: Hydrator now returns valid metadata for `:nitro` models (context_window=128000).
   - `test_context_window_failure`: Context window returns `128000` for shortcut models (same as clean).
   - `test_get_completion_cost_shortcut`: Cost for `:nitro` model is now non-zero (0.001, successfully hydrated).
   Fix proven: colon-based routing shortcuts are now correctly stripped before model ID lookup.

## Solution
### Root Cause
OpenRouter routing shortcuts (`:nitro`, `:floor`, and any colon-based suffix) appended to model IDs (e.g., `openrouter/deepseek/deepseek-v4-flash:nitro`) are not stripped before model metadata lookup. The hydrator (`OpenRouterMetadataHydrator.get_metadata()`) only strips numeric version suffixes (`-\d{8,12}`) and does not handle colon-based qualifiers. This causes:
- `get_context_window()` to return 0 (unknown) because `litellm.model_cost` does not contain the shortcut-keyed entry.
- `get_completion_cost()` to return 0.0 (fallback) because the hydrator fallback also fails to find the model.

### Fix (Proven via Shadow File)
Add a regex stripping step in `OpenRouterMetadataHydrator.get_metadata()` immediately after removing the `openrouter/` prefix:
```python
clean_id = re.sub(r":[^/:]+$", "", clean_id)
```
This removes any colon-based suffix (e.g., `:nitro`, `:floor`) from the model ID before performing the lookup against the OpenRouter catalog. The fix is generic: it strips any `:xxx` token at the end of the model ID, covering all OpenRouter routing shortcuts.

### Preventative Measures
- **Systemic Check**: Search `litellm.model_cost` and hydrator lookup paths for any other potential model ID transformations that might strip or normalize strings, and ensure they all handle colon-based suffixes. (Completed: systemic audit confirmed no other normalization paths exist in the codebase; the only model ID processing is the `removeprefix("openrouter/")` and the numeric suffix regex in `openrouter_hydrator.py`, plus the `_hydrate_all_candidates` method in `litellm_adapter.py` which delegates to the hydrator. No other paths need updating.)
- **Documentation**: Add a note in the `openrouter_hydrator.py` docstring that model IDs may contain provider-specific qualifiers (numeric suffixes, routing shortcuts) that must be stripped before lookup.
- **Test Coverage**: Add a unit test in the OpenRouter hydrator test suite (`test_openrouter_hydrator.py`) that verifies colon-based routing shortcuts (`:nitro`, `:floor`) are correctly stripped before lookup. Also add a test in `test_litellm_adapter_telemetry.py` that verifies `get_context_window()` and `get_completion_cost()` work correctly with shortcut-qualified model strings.
