# Slice: Remove the API Key Command-Line Flag
- **Status:** Planned
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
4. `[CONTRACT]` `SessionMeta` — Remove the `api_key` field.
5. `[CLEANUP]` `SessionPruningService` — Drop the `api_key` entry from the scrub list.
6. `[MIGRATE]` `tests/` — Drop the `api_key=None` arguments.
7. `[CLEANUP]` `docs/project/specs/interactive-session-workflow.md` — Remove `--api-key` and the phantom `--provider`.

## Deliverables
- [ ] **Wiring** - Acceptance test: `teddy start --api-key sk-test` is rejected with a non-zero exit code, and a `TEDDY_LLM_API_KEY` shell value still reaches the adapter.
- [ ] **Contract** - Remove the option and the parameter chain down to `SessionMeta`.
- [ ] **Migration** - Update the test modules that pass `api_key` through the removed seams.
- [ ] **Cleanup** - Drop the prune scrub entry and correct the specification line.

## Implementation Notes
(To be recorded during implementation.)

## Verification
1. **Flag is gone:**
   Run `teddy start --api-key sk-test`.
   Verify the CLI reports an unknown option and exits with a non-zero code.
2. **Environment path still works:**
   Set `TEDDY_LLM_API_KEY` in the shell environment, then run `teddy start -y -m "hi"`.
   Verify no key prompt appears.
