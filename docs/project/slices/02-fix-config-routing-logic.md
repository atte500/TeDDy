# Slice: Fix Configuration Routing & Deep Merge Logic

- **Status:** Planned
- **Milestone:** N/A
- **Specs:** [docs/architecture/adapters/outbound/yaml_config_adapter.md](/docs/architecture/adapters/outbound/yaml_config_adapter.py)
- **Case File:** [docs/project/debugging/02-openrouter-deepseek-routing-error.md](/docs/project/debugging/02-openrouter-deepseek-routing-error.md)

## Business Goal

Ensure that TeDDy correctly routes LLM requests when users override models in their local configuration, and resolve internal inconsistencies in the configuration adapter that cause "split-brain" states between scalar and block lookups.

## Scenarios

> As a developer using OpenRouter, I want my model overrides to be respected without interference from baseline provider defaults, so that I can use any LiteLLM-supported model seamlessly.

```gherkin
Scenario: OpenRouter Model Routing
  Given a baseline config with "custom_llm_provider: gemini"
  And a user config with "llm.model: openrouter/deepseek/deepseek-v4-flash"
  When I execute a plan
  Then LiteLLM should NOT receive "custom_llm_provider: gemini"
  And the request should route to OpenRouter
```

> As a developer, I want to override nested configuration using flat keys at the root, so that my local config remains concise and follows the established migration pattern.

```gherkin
Scenario: Inconsistent Shim Propagation
  Given a baseline config with "llm: { model: 'old-model' }"
  And a user config with "model: 'new-model'"
  When I request the "llm" block configuration
  Then the returned block should contain "model: 'new-model'"
```

## Edge Cases
- **Explicit Provider Override**: If a user *manually* sets `custom_llm_provider: "something"`, it should still be respected.
- **Unsetting Keys**: If a user sets a key to `null` in their local config, it must be removed from the final merged configuration.
- **Multiple Shims**: If both `model` and `api_key` are provided as flat overrides, both must propagate into the `llm` block.

## Deliverables
- [x] **Contract** - Update `YamlConfigAdapter` tests to include the "split-brain" failure case.
- [x] **Logic** - Refactor `YamlConfigAdapter._load_layered_config` to apply the migration shim to the dictionary itself.
- [x] **Logic** - Update `YamlConfigAdapter._merge_dicts` to prune `None` values.
- [ ] **Migration** - Update `src/teddy_executor/resources/config/config.yaml` to set DeepSeek V4 Flash as default and remove the redundant provider.
- [ ] **Cleanup** - Remove legacy code in `get_setting` that performs the shim lookup on every call.

## Implementation Plan
1. **Test-First Failure**: Add a unit test to `test_yaml_config_adapter.py` that fails when `get_setting("llm")` doesn't reflect a flat `model` override.
2. **Apply Shim on Load**: In `YamlConfigAdapter`, iterate through the migration shim mapping (e.g., `model` -> `llm.model`) and update the internal `self._config` dictionary if the flat key exists.
3. **Null Pruning**: Modify `_merge_dicts` to `del base[key]` if `value` is `None`.
4. **Baseline Update**: Apply the new default model to the production YAML.

## Implementation Notes
- **Proactive Shim Application**: Migrated the shim logic from a dynamic lookup in `get_setting` to a proactive update of the internal `_config` dictionary during load. This resolves the "split-brain" issue where block lookups (e.g., `get_setting("llm")`) did not reflect flat root-level overrides.
- **Recursive Null Pruning**: Enhanced `_merge_dicts` to recursively prune keys set to `None`. This allows users to explicitly "unset" baseline defaults in their local configuration.
