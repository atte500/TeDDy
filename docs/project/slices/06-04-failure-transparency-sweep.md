# Slice: Failure-Transparency Sweep over the Measured Catch Inventory
- **Status:** Planned
- **Milestone:** [Milestone 6: Cross-Cutting Consolidation](/docs/project/milestones/06-cross-cutting-consolidation.md)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [OpenRouterMetadataHydrator](/docs/architecture/adapters/outbound/openrouter_hydrator.md), [LiteLLMAdapter](/docs/architecture/adapters/outbound/litellm_adapter.md), [ShellAdapter](/docs/architecture/adapters/outbound/shell_adapter.md), [LocalFileSystemAdapter](/docs/architecture/adapters/outbound/local_file_system_adapter.md)
- **Scope Slug:** `failure-transparency-sweep`

## Goal
Make every swallowed failure either narrowed to what it can legitimately ignore or logged before it disappears, so a network outage, an unreadable file, or a failing cleanup leaves a trace instead of surfacing later as absent data nobody can explain.

## Context
- Measured inventory: 51 broad `except Exception` sites across 16 files in `src/`. The concentrations are `textual_plan_reviewer_editor.py` 7; `update_checker.py`, `session_orchestrator.py`, `session_cli_handlers.py`, and `cli_helpers.py` 5 each; `textual_plan_reviewer_app.py` 4; `litellm_adapter.py`, `console_interactor_ask_loop.py`, and `textual_plan_reviewer_previews.py` 3 each; `session_lifecycle_manager.py`, `execution_orchestrator.py`, `web_scraper_adapter.py`, and `textual_plan_reviewer_execution.py` 2 each; `action_executor.py`, `session_pruning_service.py`, and `session_replanner.py` 1 each.
- The milestone's twelve named modules were wrong in both directions. Seven carry zero broad catches — `local_file_system_adapter.py`, `shell_adapter.py`, `openrouter_hydrator.py`, `yaml_config_adapter.py`, `context_service.py`, `session_repository.py`, and `core/utils/io.py` — while the real concentrations above sit mostly in files the requirement never named.
- Zero broad catches does not mean clean. `OpenRouterMetadataHydrator._fetch_models` catches `requests.RequestException` and `ValueError` and returns an empty catalog with no log line, while the adapter's own persistent-cache path debug-logs its equivalent failure. A network outage is therefore invisible in the logs and reaches the caller only as absent metadata, which is the sharpest gap in the sweep precisely because the catch type is already narrow.
- `session_replanner.py:72` swallows with `except Exception:  # nosec B112` followed by `continue`, so a file the milestone never named is a genuine site and its `nosec` must not survive as the only justification.
- The governing law is the Failure Transparency standard in `docs/architecture/ARCHITECTURE.md`: silent suppression is forbidden, every catch either names its type or logs full context and re-raises, and an empty catch is allowed only with an explicit "safe to ignore" comment. Nothing enforces that law today — the six existing structural hooks cover DI boundaries, architecture imports, encoding, `/tmp`, POSIX-only patches, and raw CLI invocation, not catch blocks.
- Two families must be distinguished before any edit: a **top-level boundary catch** that already reports the failure to the user (the TUI event loop, the CLI command wrapper) versus a **swallow** that continues as if nothing failed. The first keeps its breadth and gains nothing but a clarifying comment; the second is the defect.

## Scenarios

> As a maintainer, I want a provider outage to leave a trace.

```gherkin
Given the OpenRouter catalog endpoint is unreachable
When the hydrator builds its catalog
Then it returns the empty catalog it returns today
And a debug-level line names the failure and the reason
```

> As a maintainer, I want a swallowed filesystem error to say why it was safe to ignore.

```gherkin
Given a cleanup path whose failure cannot affect the run
When the catch runs
Then it carries a debug line or an explicit safe-to-ignore comment naming the reason
And the block is never empty
```

> As a maintainer, I want the rule to be enforced rather than described.

```gherkin
Given a new except Exception block that neither logs nor re-raises
When the structural hook runs
Then it fails naming the file and line
```

## Edge Cases
- **Boundary catch that reports**: If the catch already writes a user-facing message, then it keeps its breadth and gains a comment stating it is a boundary, because narrowing it would convert a reported failure into an unhandled crash.
- **TUI event loop**: If the catch sits inside a Textual callback, then it must keep catching broadly, because letting an exception escape tears down the app and loses the user's unsaved plan review; it logs instead.
- **Interrupt and exit**: If the block currently catches `Exception`, then it must never widen to `BaseException`, because `KeyboardInterrupt` and `SystemExit` carry the quit path this repository depends on.
- **Logging with no logger configured**: If the module has no module-level logger, then the sweep adds one rather than printing, because the CLI's stderr carries the telemetry lines and the interactive cursor state.
- **`nosec B112` residue**: If a narrowed catch no longer needs the suppression, then the `nosec` is deleted in the same edit, because a suppression that outlives its finding hides the next one.
- **Log volume in a retry loop**: If the swallowing site runs per attempt, then it logs at debug without repeating the full payload, because a noisy log is a different way of hiding the signal.
- **Re-raise versus log-and-continue**: If the caller cannot proceed without the value, then the block re-raises after logging, because continuing with a missing value moves the failure further from its cause.
- **Optional dependency probe**: If the catch guards an import probe, then it stays silent with a safe-to-ignore comment, because the absence is the expected outcome rather than a failure.

## Key Unknowns
- [ ] [Technical] Classification of the 19 TUI-side catches (`textual_plan_reviewer_editor.py` 7, `textual_plan_reviewer_app.py` 4, `textual_plan_reviewer_previews.py` 3, `textual_plan_reviewer_execution.py` 2, `console_interactor_ask_loop.py` 3). Design Sensitivity: if they are boundary catches → they each gain a comment and a debug line while keeping their breadth, and the hook exempts a documented boundary list; if some are genuine swallows mid-flow → those narrow, and the exemption list shrinks to the event-loop entry points alone.

## Impact
1. `[MIGRATE]` The 16 files carrying the 51 broad catches — each site classified as boundary or swallow, then narrowed, logged, or annotated accordingly.
2. `[MIGRATE]` `OpenRouterMetadataHydrator._fetch_models` — a debug line naming the failed fetch, matching the adapter's own cache-path precedent.
3. `[MIGRATE]` `session_replanner.py` — the `nosec B112` swallow replaced by a logged, narrowed catch or an explicit safe-to-ignore comment.
4. `[NEW]` `.githooks/check_broad_except_logging.py` — a structural check failing on a broad catch that neither logs nor re-raises, exempting a documented boundary list.
5. `[MIGRATE]` `.pre-commit-config.yaml` and the `manual`-stage step list — register the new hook beside the six existing structural checks.
6. `[NEW]` A unit test for the hook covering a logging catch, a re-raising catch, a boundary-exempt catch, and a bare swallow.
7. `[MIGRATE]` The four component pages above — record each adapter's failure-reporting contract and which catches are boundaries.
8. `[MIGRATE]` `docs/architecture/ARCHITECTURE.md` — point the Failure Transparency bullet at the hook as its enforcement.

## Deliverables
- [ ] **Env** — Add the broad-catch hook, register it in the `manual` stage, and wire it into the structural-check step list.
- [ ] **Harness** — Unit-test the hook against a logging catch, a re-raising catch, an exempt boundary catch, and a bare swallow.
- [ ] **Interface** — Record on the four component pages which catches are boundaries and what each adapter reports on failure.
- [ ] **Core** — Sweep the 16 files: classify, narrow, log, or annotate every site, starting with the hydrator and `session_replanner.py` because their silences hide the sharpest failures.
- [ ] **Cleanup** — Delete the `nosec` suppressions that no longer apply, point the ARCHITECTURE bullet at the hook, and replace the milestone's stale twelve-module list with the measured inventory.

## Implementation Notes

## Verification
1. **Hydrator trace:**
   Point `llm.api_base` at an unreachable endpoint, run a planning turn, and inspect the debug log.
   Verify a line names the failed catalog fetch.
2. **Hook bites:**
   Add a bare `except Exception: pass` to a scratch module and run `uv run python .githooks/check_broad_except_logging.py`.
   Verify it exits non-zero naming the file and line.
3. **No regression in the TUI:**
   Drive the reviewer through a failing preview fetch.
   Verify the app reports the failure and stays open.
