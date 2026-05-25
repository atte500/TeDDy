# Bug: OpenRouter Timeout & Startup Lag

- **Status:** Resolved
- **Milestone:** 00
- **Vertical Slice:** [docs/project/slices/03-resilient-openrouter-metadata.md](/docs/project/slices/03-resilient-openrouter-metadata.md)
- **Specs:** N/A

## Symptoms
- **Timeout Error**: `Error: Configuration Error: The remote connectivity check timed out after 2 seconds.` even with valid API key.
- **Startup Lag**: Significant delay between execution and the `Checking configurations...` message.

## Context & Scope
### Regressing Delta
Implementation of Slice 03, specifically the 2s timeout for remote checks and the lazy import/preflight refactoring.

### Environmental Triggers
- Network latency affecting `litellm.check_valid_key`.
- Python interpreter and Typer bootstrap overhead.

### Ruled Out
- N/A

## Diagnostic Analysis
### Causal Model
1. **Startup Lag (Phase 1 - Typer/Bootstrap):** Before any command runs, `bootstrap()` is executed. It resolves `IInitUseCase`, which triggers the registration of all infrastructure.
2. **Eager Imports:** If `infrastructure.py` imports heavy adapters (LiteLLM, Trafilatura) at the module level, the `get_container()` call becomes a blocking bottleneck.
3. **Startup Lag (Phase 2 - Preflight):** Commands like `start` call `_run_cli_preflight_check`. This resolves `ILlmClient` and calls `validate_config(include_remote=False)`.
4. **The LiteLLM Bottleneck:** Even for a local check, `validate_config` calls `_get_litellm()`, which performs the heavy `import litellm` (~2.2s). This occurs *after* the user has already waited for the Python interpreter and Typer to load.
5. **Timeout Failure:** `PlanningService` calls `validate_config(include_remote=True)` during Turn 1 generation. The 2.0s timeout is shared between the library's internal initialization (if not already cached) and the actual network request to OpenRouter. On slower connections or "cold" model metadata states, this consistently exceeds 2s.

### Discrepancies
- User sees "Checking configurations..." but there is lag *before* it. (Resolved: The message is printed in the command handler, but `bootstrap()` and Typer loading happen earlier.)
- Remote check times out even for valid keys. (Resolved: 2.0s is likely too aggressive for combined library overhead + OpenRouter latency.)

### Investigation History
1. Initial report: 2s timeout triggered incorrectly; startup lag remains.
2. Profiling identified ~1.2s lag in `validate_config` due to eager `import litellm` during preflight.
3. Identified additional eager imports of `pathspec` (via `LocalRepoTreeGenerator`) and `pyperclip` (via `cli_helpers.py`) in the global bootstrap path.
4. Verified in sandbox that "ultra-lazy" validation reduces local preflight to < 0.01s.
5. Confirmed 2.0s timeout is too aggressive for OpenRouter; verified 10.0s is reliable.

## Solution
1. **Ultra-Lazy Validation**: Refactored `LiteLLMAdapter.validate_config` to perform basic model/key checks against the configuration *before* importing `litellm`. Only provider-specific environment validation or remote connectivity checks now incur the import cost.
2. **Relaxed Timeout**: Increased the remote connectivity timeout from 2.0s to 10.0s to accommodate library initialization and OpenRouter network latency.
3. **Instant UI Feedback**: Moved the "Checking configurations..." message to the very start of the `bootstrap()` callback in `__main__.py`, providing immediate user feedback.
4. **Systemic Laziness**: Applied lazy import patterns to `pathspec` and `pyperclip` to remove the final bottlenecks from the CLI bootstrap sequence.
