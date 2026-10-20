# Slice: Defer Interactive Setup to Session Start
- **Status:** Planned
- **Milestone:** Ad-hoc (no milestone)
- **Depends On:** None
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)
- **Prototype:** None
- **Component Docs:** [CLI Adapter](/docs/architecture/adapters/inbound/cli.md), [InitService](/docs/architecture/core/services/init_service.md)
- **Scope Slug:** `setup-deferral`

## Goal
Make `teddy init` and `teddy init config` scaffolding-only commands. The API-key and editor setup runs at `teddy start` and `teddy resume`, where the configured values are used.

## Context
- `__main__._run_init_setup_gates`: A TTY-gated helper that runs `_ensure_api_key_configured` and then `_validate_editor_config`. Both `init_callback` and `init_config` call it.
- `__main__._resolve_setup_api_key`: Returns `isatty() and not pipeline`. The key is required, so this gate is deliberately wide.
- `__main__._resolve_setup_editor`: Adds `interactive or message is None` because the editor is optional.
- `__main__._display_init_drift`: Prints advisory drift advice without prompting. It stays unchanged.
- `InitService.ensure_initialized` and `ensure_config_initialized`: Copy bundled files through the file-system port. They never prompt.
- `InitService._CREATE_ONLY_CONFIG_FILES`: `.env` is create-only, so `teddy init config` already preserves a stored key.
- `README.md` under "Configuration": The first execution of `teddy start` runs the interactive setup.
- `tests/suites/acceptance/test_init_interactive_setup.py`: Asserts that a TTY `teddy init` persists an entered key. This module encodes the behavior being removed.
- `tests/suites/unit/adapters/inbound/test_init_setup_gates.py`: Patches `session_cli_handlers._ensure_api_key_configured` and `_validate_editor_config`, and asserts the gate order.
- `tests/suites/unit/adapters/inbound/test_init_drift_reporting.py`: Its `_neutralize_setup_gates` helper patches the same two helpers. Both helpers remain for `start`, so the patch becomes inert rather than broken.

## Scenarios

> As a developer adding TeDDy to an existing repository, I want `teddy init` to scaffold files without asking questions, so the command is safe to run in any terminal.

```gherkin
Given a terminal is attached and no LLM API key is configured
When I run `teddy init`
Then no prompt appears
And `.teddy/.env` keeps an empty `TEDDY_LLM_API_KEY=`
```

> As a local-model user, I want `teddy init config` to reset defaults without requesting an OpenRouter key, so a keyless backend stays keyless.

```gherkin
Given `llm.model` points at a local server and no key is configured
When I run `teddy init config` on a terminal
Then no prompt appears
And the reset configuration files are written
```

> As a developer starting a session, I want the setup gate at `teddy start`, so the documented first-run flow holds.

```gherkin
Given a terminal is attached and no LLM API key is configured
When I run `teddy start`
Then the LLM API key prompt appears
```

## Edge Cases
- **Non-TTY init**: If stdin is not a terminal, then `init` must prompt for nothing, because automated runs must never block.
- **`.env` preservation**: If `.teddy/.env` exists, then `teddy init config` must leave it untouched and must not prompt, because the reset covers regenerable defaults only.
- **Prompt and template subcommands**: If `teddy init prompts` or `teddy init templates` runs, then it must stay prompt-free, because the callback returns before any setup call.
- **Drift advice survives**: If local prompts drift from the bundled defaults, then bare `init` must still print the advice after the summary, because drift reporting is advisory and independent of setup.
- **Fully specified batch start**: If `teddy start -y` runs on a terminal without `-m`, then the API-key prompt must still fire, because the key is required.

## Key Unknowns
None. The gate call sites, the TTY rules, and the unit-tier test census were resolved through static reading. The acceptance drift module is covered by the test-grep deliverable below.

## Impact
1. `[CONTRACT]` `__main__._run_init_setup_gates` — Delete the helper and its docstring.
2. `[MIGRATE]` `__main__.init_callback` — Drop the trailing setup call and keep `_display_init_drift`.
3. `[MIGRATE]` `__main__.init_config` — Drop the trailing setup call and keep the status echo.
4. `[MIGRATE]` `tests/` — Replace the positive init-prompt coverage with a negative matrix.
5. `[CLEANUP]` `docs/architecture/adapters/inbound/cli.md` — Restate the `init()` postconditions.

## Deliverables
- [ ] **Wiring** - Acceptance test: a TTY `teddy init` and a TTY `teddy init config` persist no environment value and prompt for nothing, while a TTY `teddy start` still prompts.
- [ ] **Cleanup** - Delete `_run_init_setup_gates` and both call sites.
- [ ] **Migration** - Replace `tests/suites/unit/adapters/inbound/test_init_setup_gates.py` with the negative matrix, and delete `tests/suites/acceptance/test_init_interactive_setup.py`.
- [ ] **Cleanup** - Grep `tests/` for `_run_init_setup_gates`, `_neutralize_setup_gates`, and init-tier `_ensure_api_key_configured` patches, then prune every dead patch.
- [ ] **Cleanup** - Update the `init()` postconditions in `docs/architecture/adapters/inbound/cli.md`.

## Implementation Notes
(To be recorded during implementation.)

## Verification
1. **Bare init is silent:**
   In a scratch repository with no key configured, run `teddy init`.
   Verify the output contains `TeDDy initialized in .teddy folder.` and no prompt appears.
2. **Setup moved to start:**
   In the same repository, run `teddy start`.
   Verify the `LLM API Key` block appears.
3. **Config reset is silent:**
   Run `teddy init config`.
   Verify the output contains `Configuration files` and no prompt appears.
