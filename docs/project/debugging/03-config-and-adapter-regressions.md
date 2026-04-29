# Bug: Configuration and Adapter Regressions

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)

## Symptoms
7 test failures:
1. `similarity_threshold` in `.teddy/config.yaml` is ignored or fails validation.
2. `LiteLLMAdapter` does not override caller-provided models/API keys with config settings.
3. `LiteLLMAdapter.get_token_count` swaps `model` and `messages` arguments.
4. `context` command (via `InitService`) fails to create `.teddy/.gitignore`.

## Context & Scope
### Regressing Delta
Work on Slice 00-07 (Centralized Configuration Baseline) seems to have introduced these issues by changing how configuration is loaded and applied.

### Environmental Triggers
Standard test environment execution.

### Ruled Out
- None so far.

## Diagnostic Analysis
### Causal Model
1. **Config Key Drift:** `similarity_threshold` was moved to `execution.similarity_threshold` in the baseline, but the consumption logic in `ActionFactory` or validators likely still uses the flat key.
2. **LiteLLM Priority Conflict:** `LiteLLMAdapter` prioritizes `kwargs` and `model` arguments over config values, which contradicts the unit tests that expect config to enforce a "system override" (e.g., for cost control).
3. **LiteLLM Signature Mismatch:** `LiteLLMAdapter.get_token_count` implementation swaps the order of `model` and `messages` compared to what the test suite expects from the `ILlmClient` interface.
4. **Missing Template:** The `.gitignore` template was not moved to the new `resources/config/` directory during the Slice 00-07 refactor, causing `InitService` to fail to bootstrap it.

### Discrepancies
- `test_get_token_count_delegates_to_litellm` fails. Call signature is `(messages, model)` in implementation, but test passes `(model, messages)`. (Resolved: Confirmed implementation has `(self, messages, model)`).
- `LiteLLMAdapter` tests fail on model/key overrides. (Resolved: Implementation prioritizes arguments, tests expect config priority).

### Investigation History
1. Initial symptom report from global test run.
2. Verified `LiteLLMAdapter` parameter swap and `InitService` template absence.
3. Applied initial fixes; 4/7 tests passed.
4. Isolated `YamlConfigAdapter` shim failure: Hierarchical resolution was returning baseline defaults before checking flat overrides.
5. Corrected `LiteLLMAdapter` signature mismatch that violated `ILlmClient` port and broke `PlanningService`.
