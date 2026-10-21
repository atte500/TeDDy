# Slice: Defer Interactive Setup to Session Start
- **Status:** Completed
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
- [x] **Wiring** - Atomic removal: rewrite the init acceptance coverage to the negative scenario (a TTY `teddy init` and `teddy init config` persist no environment value and prompt for nothing; the existing `test_api_key_setup_wiring.py` already proves a TTY `teddy start` still prompts), delete `_run_init_setup_gates` and both call sites, and replace `test_init_setup_gates.py` with seam-level negative invariants. One commit keeps the suite green.
- [x] **Cleanup** - Prune the now-inert `_neutralize_setup_gates` helper and its calls in `test_init_drift_reporting.py`, plus any dead init-tier `_ensure_api_key_configured` patch.
- [x] **Cleanup** - Update the `init()` postconditions in `docs/architecture/adapters/inbound/cli.md`.

## Implementation Notes
- Re-partitioned during Orientation. The original deliverable order was not green-preserving: the negative acceptance test passes only after the call sites are removed, and removing them breaks the old positive acceptance and unit tests. The behavior change and the retirement of its obsolete tests are inseparable, so they form one atomic Wiring deliverable.
- The drift-reporting module keeps passing after the removal because its `_neutralize_setup_gates` patches target helpers that still exist for `start`; the patch becomes inert and is pruned in a later Cleanup deliverable.
- `teddy start` prompt coverage already exists in `test_api_key_setup_wiring.py`, so the new acceptance test does not duplicate it.
- Wiring implemented atomically. The acceptance module `test_init_interactive_setup.py` now asserts that both `teddy init` and `teddy init config` persist no environment value and prompt for nothing on a TTY. A new seam module `test_init_defers_setup_to_start.py` pins the removed helper and the gate-spy invariant. The obsolete `test_init_setup_gates.py` is deleted.
- Red produced exactly five failures: the helper-removal invariant, both acceptance prompt assertions, and both gate spies. Green turned all nine targeted tests green.
- Three stale references were corrected: the drift-advice docstring in `__main__.py` and two gate comments in `session_cli_handlers.py`.
- Integration confirmed the atomic removal is systemically safe: `make test` reported 1983 passed and 5 skipped.
- Pruned the inert `_neutralize_setup_gates` helper, its single call site, and the orphaned `session_cli_handlers` import in `test_init_drift_reporting.py`. The targeted run reported 9 passed across the drift, seam, and negative acceptance modules, and the grep printed `absent-confirmed`. Integration reconfirmed the full suite green at 1983 passed and 5 skipped.
- Restated the `### init()` postconditions in `cli.md` to the as-built scaffolding-only behavior and named `teddy start`/`teddy resume` as the deferred setup location. The `phrase-absent` grep confirmed the stale "interactive setup gates" wording is gone from `docs`, `src`, and `tests`, and the corrected line printed. Integration reconfirmed the full suite green at 1983 passed and 5 skipped. The CLI Adapter component doc keeps `Status: Implemented`, because this was an as-built wording correction rather than a new capability.

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
