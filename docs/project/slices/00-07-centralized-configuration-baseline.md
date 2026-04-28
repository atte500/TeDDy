# Slice: Centralized Configuration Baseline

- **Status:** Planned
- **Milestone:** [10-interactive-session-and-config.md](../milestones/10-interactive-session-and-config.md)
- **Specs:** [interactive-session-workflow.md](../specs/interactive-session-workflow.md)

## Business Goal
Achieve a "Single Source of Truth" for system defaults by bundling a baseline configuration file with the package. This eliminates scattered hardcoded "magic numbers" and ensures consistent behavior across different environments (dev vs. installed).

## Scenarios
> As a developer, I want all system defaults to be defined in a single bundled YAML file so that I can easily update system behavior without hunting through the codebase.

```gherkin
Given the bundled baseline config defines "execution.default_timeout_seconds: 60"
And the user has no .teddy/config.yaml
When I retrieve the "execution.default_timeout_seconds" setting
Then I should receive the value 60
```

> As a user, I want my local configuration to take precedence over the system defaults so that I can customize my experience.

```gherkin
Given the bundled baseline config defines "ui_mode: tui"
And the user's .teddy/config.yaml defines "ui_mode: console"
When I retrieve the "ui_mode" setting
Then I should receive the value "console"
```

## Deliverables
- [ ] **Harness** - Move `config/` directory to `src/teddy_executor/resources/config/`.
- [ ] **Harness** - Create `__init__.py` in `src/teddy_executor/resources/` and `src/teddy_executor/resources/config/` to support resource loading.
- [ ] **Logic** - Add missing defaults to the baseline `config.yaml` (`planning_model`, `web_scraper.user_agent`).
- [ ] **Logic** - Harmonize keys: `max_execute_lines` -> `execution.max_output_lines`, `max_read_lines` -> `read.max_lines`.
- [ ] **Seam** - Update `YamlConfigAdapter` to load the bundled baseline YAML using `importlib.resources` as the base layer.
- [ ] **Refactor** - Update `InitService` to use the new package-relative path for template initialization.
- [ ] **Refactor** - Prune all hardcoded fallbacks from `ActionFactory`, `PlanningService`, `registries/infrastructure.py`, and `registries/reviewer.py`.
- [ ] **Cleanup** - Delete the original `config/` directory at the project root.

## Delta Analysis
- `src/teddy_executor/resources/config/config.yaml`: New home for the baseline.
- `src/teddy_executor/adapters/outbound/yaml_config_adapter.py`: Update `__init__` to perform layered merging of baseline + user config.
- `src/teddy_executor/core/services/init_service.py`: Update `_config_dir` resolution.
- `src/teddy_executor/registries/infrastructure.py`: Remove hardcoded defaults in factory lambdas.
- `src/teddy_executor/core/services/action_factory.py`: Remove defaults in `_handle_execute_protocol` and `_handle_edit_protocol`.
- `src/teddy_executor/core/services/planning_service.py`: Remove default for `planning_model`.

## Guidelines for Implementation
- Use `importlib.resources.files("teddy_executor.resources.config").joinpath("config.yaml")` for robust resource access.
- Ensure the merge logic handles nested dictionaries correctly (deep merge not required for current flat structure, but preferred).
- The `ARCHITECTURE.md` has already been updated to reflect the new standard: all core settings MUST have a corresponding entry in the baseline YAML.
