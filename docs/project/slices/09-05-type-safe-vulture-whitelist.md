# Slice: Type-Safe Vulture Whitelisting
- **Status:** Planned
- **Milestone:** [09-architectural-debt-reconciliation](../milestones/09-architectural-debt-reconciliation.md)
- **Component Docs:** [docs/architecture/tests/harness/vulture_whitelist.md](../architecture/tests/harness/vulture_whitelist.md)

## Business Goal
Replace the brittle, string-based `ignore_names` list in `pyproject.toml` with a type-safe whitelist module to improve the reliability of dead-code detection and reduce maintenance friction.

## Scenarios

### Scenario 1: Whitelist Generation & Integration
> As a Developer, I want Vulture to ignore my Textual handlers and abstract port methods via a Python whitelist so that I don't have to update the global TOML file.
```gherkin
Given a file "tests/harness/vulture_whitelist.py" simulating usage of "on_mount" and "IUserInteractor"
When I remove "on_mount" and "IUserInteractor" from "pyproject.toml" ignore_names
And I add "tests/harness/vulture_whitelist.py" to Vulture's paths
Then "vulture" MUST NOT report these as unused
And "mypy" MUST pass for the whitelist file
```

## Deliverables
- [x] **Contract** - Create `tests/harness/vulture_whitelist.py` simulating usage of the following: `Plan`, `ActionData`, `IUserInteractor`, `IFileSystemManager`, `IConfigService`, `IEditSimulator`, `total_actions`, `agent_name`, `Document`, `SessionPorts`, `on_mount`, `compose`, `on_input_submitted`, `on_tree_node_selected`, `on_list_view_selected`, `on_descendant_focus`, `on_key`, `action_*`, `async_create_session`, `create_file`, `edit_file`, `confirm_plan_review`, `notify_skipped_action`, `prompt_for_message`.
- [ ] **Configuration** - Add `tests/harness/vulture_whitelist.py` to `tool.vulture.paths` in `pyproject.toml`.
- [ ] **Cleanup** - Remove all method names from `tool.vulture.ignore_names` in `pyproject.toml`.
- [ ] **Cleanup** - Remove all type/class names from `tool.vulture.ignore_names` in `pyproject.toml`.
- [ ] **Cleanup** - Remove manual Vulture hacks (e.g., `_ = agent_name`) from `src/teddy_executor/adapters/inbound/textual_plan_reviewer.py`.
- [ ] **Cleanup** - Verify all quality gates (`vulture`, `mypy`, `ruff`) pass.

## Implementation Notes
### Deliverable: Contract
- Created `tests/harness/vulture_whitelist.py`.
- Mapped all `ignore_names` from `pyproject.toml` to their source definitions.
- Discovered 13+ specific `action_` methods in `textual_plan_reviewer_app.py` and included them in the whitelist to allow removal of the `action_*` wildcard.
- Verified the whitelist remains green via acceptance test.
