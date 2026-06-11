# Slice: Improve Agent Validation Error Messages
- **Status:** Planned
- **Type:** Feature
- **Milestone:** [Milestone 2](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [Improve Agent Validation Error Messages Task](/docs/project/tasks/improve-agent-validation-error-messages.md)
- **Component Docs:** [PromptManager](/docs/architecture/core/services/prompt_manager.md), [SessionService](/docs/architecture/core/services/session_service.md), [CLI Adapter](/docs/architecture/adapters/inbound/cli.md)
- **Scope Slug:** `agent-validation-errors`

## Business Goal
Improve CLI error messages when users provide invalid agent names, making it clear what valid agents are available. Currently, errors only say "not found" without listing available options, forcing users to guess or manually inspect `.teddy/prompts/`.

## Scenarios

> As a user running `teddy start`, I want to see a list of valid agents when I provide an invalid agent name, so that I can quickly correct my command without inspecting the filesystem.

```gherkin
Given I run `teddy start -a nonexistent`
When the system validates the agent name
Then I see an error message that includes the list of available agents
And I do NOT see the "Please update your configuration at:" hint
```

> As a user running `teddy get-prompt`, I want to see a list of available prompts when I request a nonexistent one, so that I can quickly correct my command.

```gherkin
Given I run `teddy get-prompt nonexistent`
When the system looks up the prompt
Then I see an error message that includes the list of available prompts
```

## Edge Cases
- **Empty prompts directory:** If `.teddy/prompts/` does not exist or is empty, the available agents list should be empty, and the error should simply state the agent is not found without listing anything.
- **Multiple error sources:** If the preflight check finds both an invalid agent AND configuration errors (e.g., missing API key), the error should raise `ConfigurationError` (with config hint) rather than plain `ValueError`.
- **Only agent error:** If the ONLY preflight error is the invalid agent, the error should be a plain `ValueError` (without config hint) since agents come from `.teddy/prompts/`, not `config.yaml`.
- **Session service validation:** The `create_session()` validation in session_service.py uses a different path than the CLI preflight; both must be aligned to list available agents.
- **get-prompt with overrides:** The `get-prompt` command should list prompts from both `.teddy/prompts/` and built-in resources (fallback).
- **Cross-extension prompt files:** Agent prompts may have `.xml` extension or other extensions; the method should strip only `.xml` extension or rely on the file system to determine what constitutes an agent.

## Deliverables
- [ ] **Contract & Logic** - Add `get_available_agents() -> list[str]` to `IPromptManager` and implement in `PromptManager` using `IFileSystemManager` to list `.xml` files in `.teddy/prompts/`
- [ ] **Wiring** - Update preflight check in `session_cli_handlers.py` to call `get_available_agents()` and enrich error message with available agents (differentiating single-agent errors from multi-config errors)
- [ ] **Logic** - Fix `session_service.py` `create_session()` to include available agents in its `ValueError` message
- [ ] **Logic** - Update `get-prompt` command in `__main__.py` and `prompts.py` to list available prompts on error

## Implementation Notes
*(To be filled during implementation)*

## Implementation Plan
The implementation follows the deliverable dependency sequence:
1. **Contract & Logic (Port + Implementation):** Add `get_available_agents()` abstract method to `IPromptManager` AND implement it in `PromptManager` using `IFileSystemManager` to scan `.teddy/prompts/` directory for `.xml` files. These MUST be done together to keep the test suite green.
3. **Wiring (Adapter):** Update `_run_cli_preflight_check()` in `session_cli_handlers.py` to use the new method and differentiate between single-agent errors (ValueError) and multi-config errors (ConfigurationError).
4. **Logic (Service):** Update `create_session()` in `session_service.py` to include available agents in its error message.
5. **Logic (Utility):** Create `list_prompt_names()` helper in `prompts.py` and update `get-prompt` command in `__main__.py`.

All changes are additive (no breaking changes to existing contracts).

## Verification
- [ ] Run `poetry run teddy start -a nonexistent` in a project with `.teddy/prompts/` directory to verify error lists available agents and lacks config hint.
- [ ] Run `poetry run teddy get-prompt nonexistent` to verify it lists available prompts.
- [ ] Run `poetry run pytest` to ensure all existing tests pass.
