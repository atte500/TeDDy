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
- [x] **Logic** - Update `YamlConfigAdapter._merge_dicts` to prune `None` values.
- [x] **Migration** - Update `src/teddy_executor/resources/config/config.yaml` to set DeepSeek V4 Flash as default and remove the redundant provider.
- [x] **Logic** - Remove proactive shim application from `YamlConfigAdapter`.
- [x] **Logic** - Remove legacy dynamic shim fallback from `YamlConfigAdapter.get_setting`.
- [ ] **Migration** - Update all tests to use strict hierarchical configuration keys.
- [x] **Cleanup** - Delete `tests/suites/unit/adapters/outbound/test_yaml_config_split_brain.py`.

## Implementation Plan
1. **Baseline Update**: Update the bundled `config.yaml` to use DeepSeek V4 Flash and remove the sticky `custom_llm_provider`.
2. **Remove Shims**: Delete both the `_apply_migration_shims` method and the leaf-key fallback logic in `get_setting`.
3. **Test Migration**: Globally update all test setups that use flat keys (identified in Discovery) to use the hierarchical format.
4. **Validation**: Run the full test suite to ensure the system is stable under the strict configuration regime.

## Implementation Notes
- **Pivot to Clean Break**: Initially implemented a proactive shim to resolve the "split-brain" state. However, strategic reflection concluded that hardcoded shims create domain-leaks in infrastructure. Decided to enforce a clean break: remove all legacy shim logic and migrate all baseline/test data to the strict hierarchical format.
- **Recursive Null Pruning**: Enhanced `_merge_dicts` to recursively prune keys set to `None`. This allows users to explicitly "unset" baseline defaults in their local configuration.
- **Baseline Migration**: Updated the bundled `config.yaml` to use `openrouter/deepseek/deepseek-v4-flash`. Removed `custom_llm_provider: "gemini"` to prevent LiteLLM misrouting.
- **Proactive Shim Removal**: Removed `_apply_migration_shims` and its call site. Verified that `get_setting` block lookups no longer automatically include flat root-level overrides, eliminating one half of the "split-brain" configuration state.
- **Dynamic Fallback Removal**: Removed the leaf-key fallback logic in `get_setting`. Hierarchical lookups now strictly require the hierarchical structure to be present in the configuration dictionary.
