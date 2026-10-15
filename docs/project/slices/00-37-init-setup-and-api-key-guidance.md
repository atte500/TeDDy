# Slice: Init Interactive Setup and API Key Guidance

- **Status:** In Progress
- **Milestone:** N/A (ad-hoc task; source: initial user request)
- **Specs:** N/A
- **Prototype:** N/A
- **Component Docs:** [cli.md](/docs/architecture/adapters/inbound/cli.md)
- **Scope Slug:** `init-setup`

## Business Goal

Guide the user to a working setup without hand-editing files: the API-key prompt names OpenRouter as the default provider and tells the user to change `llm.model` in `.teddy/config.yaml`, and `teddy init` runs the same API-key and editor setup as `teddy start`, re-prompting after `teddy init config` resets the config.

## Scenarios

> As a first-time user, I want the setup prompts to say OpenRouter is the default and how to change it, so I paste the right key and can switch providers without guessing.

```gherkin
Given a project with no LLM API key configured
And the configured model requires a provider key
And the run is interactive (stdin is a TTY, not --pipeline)
When the preflight prompts for the LLM API key
Then the warning names OpenRouter as the default provider
And the warning tells the user to change llm.model in .teddy/config.yaml to use a different provider
And the prompt still reads the key with hidden input and persists it unchanged
```

> As a user running `teddy init`, I want the same API-key and editor setup as `teddy start`, so I can finish setup in one command.

```gherkin
Given a fresh project and an interactive terminal
When I run `teddy init`
Then it scaffolds .teddy/ and prompts for the LLM API key when the key is missing and the model requires one
And it prompts for the editor when no editor is configured
And a non-interactive run (stdin is not a TTY) prompts for neither
```

> As a user re-running `teddy init config`, I want to be re-prompted for anything the overwrite reset, so my setup stays complete.

```gherkin
Given an interactive terminal and an existing .teddy/config.yaml
When I run `teddy init config`
Then config.yaml is overwritten with defaults (editor reset to empty)
And .teddy/.env is preserved (create-only)
And it re-prompts for the editor because it was reset
And it re-prompts for the LLM API key only when the key is missing
```

## Edge Cases

- **Keyless local model**: If the configured model needs no API key (e.g. `lm_studio`, `vllm`), then no API-key prompt is shown, because key-requiredness is delegated to litellm.
- **Editor disabled**: If `editor` is the `disabled` sentinel, then no editor prompt is shown, because `_validate_editor_config` returns early.
- **Non-interactive run**: If stdin is not a TTY, then neither `teddy init` nor `teddy init config` prompts, because the gates are TTY-gated.
- **`.env` preserved**: If `teddy init config` runs and `.env` already holds a key, then the API-key prompt is skipped, because the key resolves and `.env` is create-only.
- **stderr-only**: If a prompt is shown, then all guidance stays on stderr, because stdout must stay clean for piped output.
- **Empty/EOF input**: If the user submits empty input or aborts, then nothing is persisted, because the prompt returns without raising.

## Key Unknowns

**Taxonomy:** `[Domain]` / `[Technical]` / `[Functional]`.

- [x] [Functional] Should the guidance name OpenRouter only, or also point at `config.yaml`? Resolution: BOTH.
- [x] [Functional] Is the warning text asserted by any test? Resolution: NO; `test_session_cli_handlers_api_key_gate.py` asserts only the GREEN confirmation.
- [x] [Technical] Where do the setup gates live? Resolution: `_prompt_for_api_key` and `_validate_editor_config` in `session_cli_handlers.py`; the API-key gate is `setup_api_key and _is_llm_api_key_missing(...) and _llm_model_requires_api_key(...)`.
- [x] [Technical] Does `teddy init config` reset the editor? Resolution: YES; it overwrites `config.yaml`, whose bundled default is `editor: ""`. `.env` is create-only and preserved.
- [x] [Functional] How does the TTY gate behave in tests? Resolution: The harness `ISystemEnvironment.isatty()` double defaults to False and `with_tty(value)` toggles it.

## Scope & Impact

- `[MIGRATE]` `session_cli_handlers._prompt_for_api_key` - replace the yellow warning text to name OpenRouter and tell the user to change `llm.model` in `.teddy/config.yaml`.
- `[EXPAND]` `session_cli_handlers` - extract the API-key gate into a shared helper reused by `_run_cli_preflight_check` and the init command.
- `[EXPAND]` `__main__.init_callback` and `__main__.config` - run the API-key and editor setup gates, gated on `ISystemEnvironment.isatty()`.
- `[EXPAND]` tests - add the warning-guidance assertion and init-time prompt coverage.

## Deliverables

- [x] **Logic** - Update the yellow warning in `_prompt_for_api_key` to name OpenRouter as the default provider and tell the user to change `llm.model` in `.teddy/config.yaml`. Keep the leading `No LLM API key configured.` sentence, the stderr channel, and the hidden-input prompt. Proposed wording (stderr, yellow):

  ```
  ⚠ No LLM API key configured. OpenRouter is the default provider. Paste your key below.
  To use a different provider, change llm.model in .teddy/config.yaml.
  ```
- [x] **Logic** - Extend `tests/suites/unit/adapters/inbound/test_session_cli_handlers_api_key_gate.py` to assert the warning names OpenRouter and mentions `llm.model` in `.teddy/config.yaml` (capture the warning via the existing `_capture_secho` helper).
- [x] **Refactor** - Extract the API-key gate (`_is_llm_api_key_missing` + `_llm_model_requires_api_key` + `_prompt_for_api_key`) into a shared helper in `session_cli_handlers.py`, called from `_run_cli_preflight_check`. Keep the preflight ordering: the API-key prompt still runs before `ILlmClient` is resolved.
- [x] **Wiring** - Wire bare `teddy init` and `teddy init config` to the shared API-key helper and `_validate_editor_config`, gated on `ISystemEnvironment.isatty()`. Run the gates after scaffolding/overwrite so `init config` re-prompts for the reset editor. Reuse the existing helpers; add no new prompt logic.
- [x] **Logic** - Add init-time prompt coverage (e.g. `tests/suites/unit/adapters/inbound/test_init_interactive_setup.py`): bare `init` on a TTY prompts for the API key (when missing and required) and the editor (when unconfigured); a non-TTY init prompts for neither; `init config` re-prompts for the editor.
- [x] **Cleanup** - Review `docs/architecture/adapters/inbound/cli.md` and `docs/architecture/core/services/init_service.md`; update only if they document the prompt wording or the init command's behavior.

## Implementation Notes

No new port, contract, or harness work: the prompt helpers already exist and are reused. The only new seam is the TTY gate in the `init` command, mirroring the `setup_editor` / `setup_api_key` gates in `start` / `resume`.

### Deliverables 1 & 2 (warning wording + test)

The yellow warning in `_prompt_for_api_key` now reads (stderr, yellow): "⚠ No LLM API key configured. OpenRouter is the default provider. Paste your key below.\nTo use a different provider, change llm.model in .teddy/config.yaml." The leading `No LLM API key configured.` sentence, the stderr channel, and the hidden-input prompt are unchanged. The new unit test `test_prompt_for_api_key_warning_names_openrouter_and_config_path` in `test_session_cli_handlers_api_key_gate.py` pins the wording via the existing `_capture_secho` helper. Red confirmed the assertion failed against the old literal; Green made the gate file 19 passed; `make test` stayed green (1756 passed, 5 skipped).

### Deliverable 3 (shared API-key gate helper)

The three-part gate previously inlined in `_run_cli_preflight_check` now lives in a single module-level helper `_ensure_api_key_configured(config_service, setup_api_key)`, called from `_run_cli_preflight_check` in the SAME position (before `ILlmClient` is resolved). Behavior is unchanged: it fires `_prompt_for_api_key` only when `setup_api_key` is truthy, `llm.api_key` is missing, and the model requires a key; the three sub-helpers are untouched. A new composite truth table in `test_session_cli_handlers_api_key_gate.py` pins the helper directly (prompt fires once when enabled + missing + required; gate stays closed for a falsy signal or an already-present key; a keyless local model never prompts). Red confirmed a collection-time `ImportError`; Green made the gate file 24 passed; `make test` stayed green (1761 passed, 5 skipped).

### Deliverable 4 (init setup gates wiring)

A single module-level helper `_run_init_setup_gates(container)` in `__main__.py` now runs the SAME one-time setup as `teddy start`: it returns early unless `ISystemEnvironment.isatty()` is true, then resolves `IConfigService` and calls the shared `_ensure_api_key_configured(config_service, setup_api_key=True)` followed by `_validate_editor_config(container)` — the exact preflight order. It is called after `init_use_case.ensure_initialized()` in `init_callback` (bare `teddy init`) and after `init_use_case.ensure_config_initialized(overwrite=True)` in `config` (`teddy init config`), so a reset editor re-prompts. Both gates are the untouched production helpers (no new prompt logic), imported lazily to match the file's convention. A new acceptance tracer bullet `tests/suites/acceptance/test_init_interactive_setup.py::test_bare_init_on_tty_prompts_for_missing_api_key` drives bare `teddy init` via `CliTestAdapter` on a TTY with a missing key and a key-requiring model, asserting `set_env_variable("TEDDY_LLM_API_KEY", "entered-value")` fired once. Red confirmed `set_env_variable` was called 0 times (exit 0); Green made it 1 passed; `make test` stayed green (1762 passed, 5 skipped). The existing non-TTY init acceptance tests stay green because the harness pins `isatty()` to False, so `_run_init_setup_gates` returns early and neither prompt fires.

### Deliverable 5 (init-time prompt coverage)

`tests/suites/unit/adapters/inbound/test_init_setup_gates.py` fills the init-time prompt matrix left open by the acceptance tracer bullet, with four scenarios: a non-TTY run returns early so NEITHER gate fires; on a TTY the gates run in preflight order (API key, then editor); a TTY bare `teddy init` discovers and persists an `nvim` editor when none is configured; and `teddy init config` re-runs the gates, re-prompting for the reset editor. Tests 1-2 drive the `_run_init_setup_gates` seam directly with the two helpers spied (pinning the TTY gate and the call order); tests 3-4 drive the real commands through `CliTestAdapter`, reusing the existing preflight `_validate_editor_config` gate (no new prompt logic). The API-key-through-init path is deliberately not duplicated here — the acceptance bullet already pins it. The file reported 4 passed on the first run — the expected outcome for a coverage deliverable, since the deliverable-4 wiring already implemented the behavior; `make test` stayed green (1766 passed, 5 skipped).

### Deliverable 6 (init docs cleanup)

Only `docs/architecture/adapters/inbound/cli.md` needed reconciling; `docs/architecture/core/services/init_service.md` documents `InitService`, which this slice did not change, and carries no prompt wording, so it was deliberately left untouched. The `cli.md` `init` section was updated to as-built reality: the summary line now says the command "runs the same one-time interactive setup gates as `teddy start` (LLM API key + editor) when a terminal is attached" instead of the obsolete "auto-launches `teddy login` if no credentials exist", and the stale step ("Checks `.teddy/credentials.yaml` … auto-launches the OAuth login browser flow") was replaced by the TTY-gated API-key + editor description, noting that `teddy init config` re-runs the gates after overwriting `config.yaml`. The API-key prompt wording is NOT documented in `docs/` (only in `src` and the tests), so deliverable 1 required no doc change. The doc-only change kept `make test` green (1766 passed, 5 skipped, identical to the turn-30 baseline).

## Verification

- [ ] Run `uv run pytest tests/suites/unit/adapters/inbound/test_session_cli_handlers_api_key_gate.py tests/suites/unit/adapters/inbound/test_init_interactive_setup.py -q` and verify they pass.
- [ ] Manual smoke: with a missing key and a cloud model, run `teddy start` on a TTY and verify the warning names OpenRouter and points to `llm.model` in `.teddy/config.yaml`.
- [ ] Manual smoke: run `teddy init` on a TTY in a fresh project and verify it prompts for the API key and editor; run `teddy init config` and verify it re-prompts for the editor.
- [ ] Run `uv run pytest` and verify the full suite is green.
