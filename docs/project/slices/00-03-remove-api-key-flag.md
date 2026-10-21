# Slice: Remove the API Key Command-Line Flag
- **Status:** In Progress
- **Milestone:** Ad-hoc (no milestone)
- **Depends On:** [00-01](/docs/project/slices/00-01-defer-interactive-setup-to-session-start.md)
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)
- **Prototype:** None
- **Component Docs:** [CLI Adapter](/docs/architecture/adapters/inbound/cli.md), [PlanningService](/docs/architecture/core/services/planning_service.md), [SessionService](/docs/architecture/core/services/session_service.md)
- **Scope Slug:** `api-key-flag`

## Goal
Remove `--api-key` from `start` and `resume` and delete the parameter chain it fed. The interactive prompt and `TEDDY_LLM_API_KEY` remain the only key paths.

## Context
- `__main__.start` and `__main__.resume`: Each declares `api_key` as a `typer.Option`.
- `session_cli_handlers.handle_new_session` and `handle_resume_session`: Accept `api_key` and forward it.
- `session_cli_handlers._sync_and_display_session_meta`: Writes `meta["api_key"]`.
- `planning_service.generate_plan` and `_perform_generation_with_retry`: Read `meta.get("api_key")` and pass it as a completion keyword argument.
- `litellm_adapter._prepare_completion_params`: Applies call keyword arguments first, then `params.update(llm_config)`, then deletes a blank key. The bundled `config.yaml` always declares `llm.api_key: "${TEDDY_LLM_API_KEY}"`, so the override is overwritten or deleted. The flag is a silent no-op today.
- `README.md` under "Optional Flags": The list omits `--api-key`.
- `docs/project/specs/interactive-session-workflow.md`: Advertises `--model`, `--provider`, and `--api-key`. The CLI declares no `--provider` flag either.
- `tests`: Every `api_key=` occurrence passes `None`. The single non-null value calls `get_completion` directly and never touches the CLI.
- `git log -S`: The flag arrived with `feat(cli): implement start command flags and metadata persistence`, so it was incidental plumbing.
- `TEDDY_LLM_API_KEY`: Interpolated into `llm.api_key` and layered under `os.environ`, so a shell value already wins over the `.env` value.
- A key on argv is readable from shell history and from process listings, and it is written in plaintext into the session `meta.yaml`.

## Scenarios

> As a developer supplying a key from a password manager, I want one documented path, so the secret never reaches shell history.

```gherkin
Given no key in `.teddy/.env`
When I set `TEDDY_LLM_API_KEY` in the shell environment and run `teddy start`
Then the session uses that key
And no key prompt appears
```

> As a user who mistypes an override, I want a loud rejection, so I never run with an unintended credential.

```gherkin
Given `start` declares no `--api-key` option
When I run `teddy start --api-key sk-test`
Then the CLI reports an unknown option
And the exit code is non-zero
```

## Edge Cases
- **Legacy session metadata**: If an old session carries `meta["api_key"]`, then pruning no longer scrubs it. This is accepted because `.teddy/` is gitignored and local.
- **Legacy metadata loading**: If a stored `meta.yaml` still carries `api_key`, then loading must tolerate the extra key rather than fail, because old sessions stay readable.
- **Blank-key guard**: If the configuration resolves the key to an empty string, then the adapter must still drop the blank value, because forwarding an empty string raises an authentication error.
- **Model override**: If `--model` is passed, then it must keep working, because it arrives as a named parameter rather than a keyword argument.

## Key Unknowns
None. The flag origin, its documentation status, its test coverage, and the precedence defect were all resolved through grep and commit history reading.

## Impact
1. `[MIGRATE]` `__main__.start` and `__main__.resume` — Remove the option declaration.
2. `[CONTRACT]` `handle_new_session`, `handle_resume_session`, `_sync_and_display_session_meta` — Remove the parameter.
3. `[CONTRACT]` `PlanningService.generate_plan` and `_perform_generation_with_retry` — Remove the `api_key` read and keyword argument.
4. `[CONTRACT]` `SessionOptions` — Remove the `api_key` field.
5. `[CLEANUP]` `SessionService` — Drop the `api_key` entry from the metadata carry-over list at line 489.
6. `[MIGRATE]` `tests/` — Drop the `api_key=None` arguments.
7. `[CLEANUP]` `docs/project/specs/interactive-session-workflow.md` — Remove `--api-key` and the phantom `--provider`.

## Deliverables
- [▶] **Wiring** - Atomic CLI-surface removal: add an acceptance test proving `teddy start --api-key sk-test` is rejected with a non-zero exit code and that a resolved `TEDDY_LLM_API_KEY` value still starts a session without a prompt, drop the `--api-key` argument and persisted `api_key` assertions from the context-flag scenario, then delete the two Typer options and their two `api_key=api_key` forwards. The handler parameters stay optional, so the suite stays green.
- [ ] **Migration** - Remove `api_key` from `handle_new_session`, `handle_resume_session`, and `_sync_and_display_session_meta`, drop the `SessionOptions(api_key=...)` keyword, and remove every `api_key=None` argument and parametrized stub in the inbound handler test modules while `SessionOptions.api_key` still exists.
- [ ] **Contract** - Remove the `SessionOptions.api_key` field, the `SessionService` metadata write, and the `PlanningService` `meta.get("api_key")` read with the `_perform_generation_with_retry` keyword argument.
- [ ] **Cleanup** - Drop the `api_key` entry from the `SessionService` carry-over list and remove `--api-key` plus the phantom `--provider` from the interactive-session specification.

## Implementation Notes
- Re-partitioned during Orientation. The original order placed Contract before Migration, which cannot keep the suite green: removing `SessionOptions.api_key` first breaks the `handle_new_session` construction, and dropping the handler parameters before their call sites are adapted breaks three inbound test modules. The recorded order is now Wiring, Migration, Contract, Cleanup.

## Verification
1. **Flag is gone:**
   Run `teddy start --api-key sk-test`.
   Verify the CLI reports an unknown option and exits with a non-zero code.
2. **Environment path still works:**
   Set `TEDDY_LLM_API_KEY` in the shell environment, then run `teddy start -y -m "hi"`.
   Verify no key prompt appears.
