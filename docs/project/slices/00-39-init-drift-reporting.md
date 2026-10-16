# Slice: Init Drift Reporting

- **Status:** In Progress
- **Milestone:** Ad-hoc (not tracked in the Roadmap per PROJECT.md)
- **Depends On:** None
- **Specs:** N/A
- **Prototype:** N/A
- **Component Docs:** [cli.md](/docs/architecture/adapters/inbound/cli.md), [init_service.md](/docs/architecture/core/services/init_service.md)
- **Scope Slug:** `init-drift`

## Business Goal

Bare `teddy init` prints `TeDDy initialized in .teddy folder. Config: unchanged. Prompts: unchanged.` The word "unchanged" means "no files were written", but a reader takes it as "your files match the defaults". This slice makes bare `teddy init` flag prompt and template drift after its non-destructive copy, reusing the same advice `teddy start` prints, so the summary cannot mislead.

## Scenarios

> As a user running `teddy init`, I want it to flag drifted prompts and templates, so I know my customizations differ from the current defaults.

```gherkin
Given .teddy/prompts/ contains a stale pathfinder.xml and no pathfinder.md
When I run `teddy init`
Then the output advises `teddy init prompts`
And the shared disable-footer names the fired checks
```

## Edge Cases

- **Fresh init, no `docs/templates/`**: If `docs/templates/` is absent, then the templates channel reports every template as MISSING and the advice names `teddy init templates`, because bare `teddy init` deliberately does not scaffold templates (the reversed contract).
- **User-customized prompts**: If `.teddy/prompts/` holds user-edited `.md` files, then the prompts channel reports them as EDITED, because `ensure_initialized()` is non-destructive and leaves the customizations in place.
- **No drift**: If every prompt and template matches its bundled default, then no advice and no footer print, because `_display_drift_notification` returns no fired keys.
- **Disabled channel**: If `checks.prompts` (or `checks.templates`) is false, then that channel stays silent, because each channel is gated by its own config toggle.
- **Non-TTY run**: If stdin is not a TTY, then the drift advice still prints, because only the setup gates are TTY-gated, not the advice.
- **Destructive subcommands unchanged**: If the user runs `teddy init prompts` or `teddy init templates`, then no drift advice prints, because those subcommands stay out of scope.

## Key Unknowns

**Taxonomy:** `[Domain]` / `[Technical]` / `[Functional]`.

- [x] [Domain] Does the flag belong to bare `teddy init`, the destructive subcommands, or both? Resolution: BARE `teddy init` ONLY (user decision, "only option A"). The destructive subcommands stay unchanged.
- [x] [Technical] Does drift detection already exist? Resolution: YES. `IInitUseCase.check_drift()` plus `_display_drift_notification` and `_display_checks_footer` in `session_cli_handlers.py` already ship on `teddy start` and `teddy resume`. No new capability is needed.
- [x] [Functional] Where must the advice print relative to the summary? Resolution: AFTER the `ensure_initialized()` copy and its summary echo, before the setup gates. The helper prints its own leading blank line, so it separates cleanly from the summary.
- [x] [Technical] How does init reuse the helpers? Resolution: import `_display_drift_notification` and `_display_checks_footer` from `session_cli_handlers` and call them in the bare-init branch, mirroring the existing lazy private-import pattern used by `_run_init_setup_gates`.

## Impact

The change is slice-scoped: one wiring point in `__main__.py`. No port, contract, or harness change; the drift helpers are reused as-is.

1. `[EXPAND]` `__main__.init_callback` — after the summary echo, print the same drift advice as `teddy start`.
2. `[EXPAND]` tests — add an acceptance tracer bullet and an init-seam unit test.

## Deliverables

Ordering follows `docs/templates/vertical-slice.md`. The slice introduces no new boundary, so the Wiring deliverable is the tracer bullet that connects the `teddy init` command to the existing drift helpers.

- [x] **Wiring** - Wire bare `teddy init` to the existing drift helpers, with an acceptance tracer bullet. In `init_callback`, after `typer.echo(f"TeDDy initialized in .teddy folder. {summary}")` and before `_run_init_setup_gates(container)`, add a small module-level helper `_display_init_drift(container)` that lazily imports `_display_drift_notification` and `_display_checks_footer` from `session_cli_handlers` and calls `_display_checks_footer(_display_drift_notification(container))`. Place the call inside the bare-init branch, after the `ctx.invoked_subcommand is not None` early return. Add `tests/suites/acceptance/test_init_drift_reporting.py` mirroring `test_preflight_drift_notification.py`: create a workspace with a stale `pathfinder.xml` prompt, run bare `teddy init`, and assert the output contains `teddy init prompts` and the shared disable-footer names the fired checks.
- [ ] **Logic** - Add `tests/suites/unit/adapters/inbound/test_init_drift_reporting.py` pinning the init seam: bare `teddy init` invokes the drift helpers (spy on `_display_init_drift`) after the summary; a non-TTY run still invokes them (the advice is not TTY-gated, unlike the setup gates); `teddy init prompts` and `teddy init templates` do NOT invoke them. Keep `tests/suites/unit/test_init_cli_regression.py` green.
- [ ] **Cleanup** - Update `docs/architecture/adapters/inbound/cli.md` (the `init` command section) to document that bare `teddy init` prints the same drift advice as `teddy start` after its summary. Reconcile `docs/architecture/core/services/init_service.md` only if needed; this slice does not change `InitService`.

## Implementation Notes

- **Reuse, not rebuild.** `_display_drift_notification` already resolves `IConfigService` and `IInitUseCase`, calls `check_drift()`, prints one yellow count-aware advice line per enabled-and-drifted channel, and returns the fired keys. `_display_checks_footer` prints the shared silence hint. The init command calls both; no new prompt logic is added.
- **Placement.** The advice prints after the summary echo, inside the bare-init branch (after the `ctx.invoked_subcommand is not None` early return), so the destructive subcommands are untouched.
- **Templates advice on a fresh init.** Bare `teddy init` does not scaffold `docs/templates/`, so a project without that directory always sees the `teddy init templates` advice. This is consistent with `teddy start` and useful: it guides the user to scaffold templates.
- **Import pattern.** The lazy import of the two private helpers mirrors `_run_init_setup_gates`, which already lazily imports `_ensure_api_key_configured` and `_validate_editor_config` from the same module. If the Developer prefers a named public seam, a `display_drift_advice(container)` wrapper in `session_cli_handlers.py` is an acceptable alternative, but the preflight keeps its combined drift-plus-update footer, so the wrapper would serve only the init path.
- **Out of scope.** The destructive subcommands (`init prompts`, `init templates`) stay unchanged; rewording the `unchanged` summary stays out of scope.
- **Wiring as-built.** Added the module-level `_display_init_drift(container)` helper to `__main__.py` (after `_run_init_setup_gates`). It lazily imports the two shared helpers and calls `_display_checks_footer(_display_drift_notification(container))`. The call sits inside the bare-init branch after the summary echo and before `_run_init_setup_gates`, so the destructive subcommands are untouched. The acceptance tracer bullet `tests/suites/acceptance/test_init_drift_reporting.py` passes, and the full suite is green (1781 passed, 5 skipped).

## Verification

- [ ] **Drifted prompt:**
    Run `teddy init` in a workspace whose `.teddy/prompts/` holds a customized prompt.
    Verify the output contains `teddy init prompts` and the disable-footer names `checks.prompts`.
- [ ] **Missing templates:**
    Run `teddy init` in a workspace with no `docs/templates/`.
    Verify the output contains `teddy init templates`.
- [ ] **No drift:**
    Run `teddy init templates`, then run `teddy init` again with default prompts.
    Verify no drift advice and no disable-footer print.
