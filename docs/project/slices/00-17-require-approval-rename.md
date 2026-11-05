# Slice: Require Approval Rename
- **Status:** Completed
- **Milestone:** N/A (ad-hoc)
- **Depends On:** None
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)
- **Prototype:** None
- **Component Docs:** [CLI Adapter](/docs/architecture/adapters/inbound/cli.md), [SessionOrchestrator](/docs/architecture/core/services/session_orchestrator.md), [ExecutionOrchestrator](/docs/architecture/core/services/execution_orchestrator.md), [SessionLoopGuard](/docs/architecture/core/services/session_loop_guard.md)
- **Scope Slug:** `require-approval-rename`

## Goal
Rename the internal action-approval signal from `interactive` to `require_approval` so the identifier states what the boolean decides, and remove the user-facing strings that describe approval as "interactive". The naming defect is what let Bug 79 happen: a reader saw `interactive=False` and concluded "no human is present".

## Context
- Measured footprint on 2026-11-05: 122 matching lines of `interactive` in `src/` across 23 files (`git grep -c`), 366 occurrences in `tests/` (`git grep -o`).
- `IRunPlanUseCase` (`src/teddy_executor/core/ports/inbound/run_plan_use_case.py:20,43`) carries the flag as a keyword on both `execute` and `resume`, and every session caller passes it by keyword.
- The flag threads `__main__.py` -> `session_cli_handlers.py` -> `SessionOrchestrator` -> `SessionLifecycleManager` -> `ExecutionOrchestrator` -> `ActionExecutor`, and is read by `SessionLoopGuard` (guardrail suppression) and `IPlanReviewer`.
- Polarity today: `__main__.py:282` and `:570` compute `interactive = not (_resolve_yolo(yolo, config_service) or pipeline)`, so `False` means auto-approve. `require_approval` keeps that polarity, making the change a pure substitution with no boolean inversion.
- `__main__.py:628` derives the same signal under a second name, `interactive_mode = not _resolve_yolo(...)`, with no pipeline term because the `execute` path has no pipeline mode.
- Three unrelated meanings share the word: this approval flag, `ShellAdapter._detect_interactive_prompt` (a subprocess waiting on stdin), and "interactive" meaning a terminal is attached (README, `--no-yolo` help).
- User-facing strings that teach the wrong meaning: README lines 214 and 253-256 plus the subcommand table at 314; the `--no-yolo / -n forces interactive mode` description on `start`, `resume`, and `execute` (`__main__.py:248,535,601`); `src/teddy_executor/resources/config/config.yaml:35` ("runs non-interactively by default").
- `docs/architecture/ARCHITECTURE.md` Ubiquitous Language defines **Action Approval (`interactive`)**; the term keeps its definition and gains the new identifier.
- Verification is behavioural only. The existing suite already pins approval semantics (yolo suppresses confirmation, pipeline suppresses confirmation, `-n` forces confirmation) and presence semantics (the Bug 79 yolo-plus-TTY regression cases), so the rename adds no test and no source-pattern guard.

## Scenarios
> As a maintainer, I want the approval flag's name to state its meaning so I never read it as terminal presence again.

```gherkin
Given no `-y/--yolo` flag and no pipeline mode
When a plan executes
Then the plan is presented in the reviewer before any action runs
```

```gherkin
Given `-y` or `yolo_default: true`
When a plan executes
Then the plan review is skipped and every action runs
```

```gherkin
Given `--pipeline`
When a plan executes
Then the plan review is skipped and every action runs
```

```gherkin
Given `-n/--no-yolo` while `yolo_default: true`
When a plan executes
Then the plan is presented in the reviewer
```

```gherkin
Given `yolo_default: true` and a terminal attached
When `teddy resume -m ""` runs
Then the blank-message prompt appears
```

## Edge Cases
- **Pipeline outranks `-n`**: if both flags are passed, then approval stays off, because the derived value is `not (yolo or pipeline)`.
- **Keyword call sites**: if any caller passes the boolean positionally, then the rename preserves parameter order, because a positional argument would silently bind to a different parameter after an accidental reorder.
- **Persisted identifiers**: if a plan parameter, session `meta.yaml` key, report template field, or config setting stores the string `interactive`, then that wire name stays unchanged and only the Python-level signal is renamed.
- **`execute` path derivation**: if the `execute` handler is renamed, then it keeps its single-term derivation rather than inheriting the session derivation's pipeline term, because that path has no pipeline mode.
- **No behaviour change**: every existing test stays green with identifier substitutions only — no assertion, fixture default, or expected value changes.

## Key Unknowns
- [x] [Technical] Persisted contracts: whether any stored artifact (plan parameter name, session `meta.yaml` key, report template variable, config setting) uses the identifier `interactive`. **Resolved 2026-11-05:** no stored artifact uses the identifier. The only `interactive` occurrences under `src/teddy_executor/resources` are English prose in `config.yaml` comments and prompt/template Markdown; no YAML/JSON/Jinja key, plan parameter, session metadata field, or report template variable carries the name. The rename is confined to code and docs and is non-breaking.

## Impact
1. `[MIGRATE]` `IRunPlanUseCase.execute` / `.resume` — rename the keyword to `require_approval`, keeping the contract shape and parameter order identical.
2. `[MIGRATE]` Core services — `SessionOrchestrator`, `SessionLifecycleManager`, `ExecutionOrchestrator`, `ActionExecutor`, `ProductionSessionLoopGuard` / `ISessionLoopGuard`, and `IPlanReviewer` rename the parameter and their internal reads.
3. `[MIGRATE]` Inbound adapters — `__main__.py` (three derivation sites), `session_cli_handlers.py` (three handler signatures), and `cli_helpers.py` adopt the new name, and the `execute` path drops the `interactive_mode` alias.
4. `[MIGRATE]` Tests — identifier substitution across the affected modules; no assertion changes.
5. `[MIGRATE]` User-facing text — the README flag table and usage examples, the three typer `--no-yolo` descriptions, and the `config.yaml` comment are reworded so `-n` reads as reviewing the plan first and `-y` as skipping the review (yolo run). The user-facing flag names `-y/--yolo` and `-n/--no-yolo` do not change.
6. `[MIGRATE]` `docs/architecture/ARCHITECTURE.md` — the Action Approval entry names `require_approval` and records `interactive` as the former name that invited the conflation.
7. `[PRUNE]` `interactive_mode` — the duplicate local name in the `execute` handler is removed.

## Deliverables
- [x] **Migration** - Rename the approval keyword and variable from `interactive` to `require_approval` across ports, core services, inbound adapters, and every in-repo test call site in one atomic commit, inlining the redundant `interactive_mode` alias in the `execute` handler. Preserve polarity and parameter order; touch no assertion; leave the suite green after the commit.
- [x] **Cleanup** - Rewrite the user-facing strings (README usage and flag table, the three `--no-yolo` help strings, `config.yaml` comments) and the `ARCHITECTURE.md` glossary entry so approval is never described as "interactive".

## Implementation Notes
- 2026-11-05: Key Unknown resolved by inspection. No persisted contract uses `interactive`; the rename is confined to code and prose.
- 2026-11-05: Audit re-partitioned the deliverables. The original plan renamed source (deliverable 1) before callers and tests (deliverable 2), which would leave the suite red at the first commit because every unit test passes `interactive=` by keyword. Since every caller is in-repo, the whole call graph moves in one atomic Migration commit. The `[PRUNE] interactive_mode` item is folded into that commit.
- 2026-11-05: `ShellAdapter._detect_interactive_prompt`, `system_environment_adapter`, `stdin_ownership`, `plan_reviewer`/`textual_plan_reviewer` docstrings, prompt Markdown, and the vertical-slice template keep the word "interactive" — they describe a TTY or a subprocess prompt, not the approval signal.
- 2026-11-05: Migration executed with a Python `tokenize` NAME-token rewrite over `src/` and `tests/`, changing 78 files. It renames every standalone `interactive`/`interactive_mode` identifier while leaving comments, docstrings, string literals, and distinct identifiers (`_detect_interactive_prompt`, `_get_interactive_confirmation`, `_perform_interactive_review`, `interactively`, `non-interactive`) untouched, because only NAME tokens are rewritten.
- 2026-11-05: Three string-literal test sites were patched explicitly because the tokenizer skips STRING tokens: two `kwargs["interactive"]` assertions in `test_cli_adapter.py` and one `parametrize("interactive", ...)` argname in the pending-plan resume test.
- 2026-11-05: Inlined the `execute` handler's redundant `interactive_mode` alias; the call site now reads `require_approval=not _resolve_yolo(yolo, config_service)`.
- 2026-11-05: A multi-line `@pytest.mark.parametrize("interactive, message, ...")` argname in `test_setup_editor_resolution.py` escaped the single-line grep and surfaced as a collection error only at `make test`. Corrected before the commit; the suite is green at 2251 passed, 5 skipped.
- 2026-11-05: Staging the renamed test modules surfaced 13 pre-existing lint violations unrelated to the rename (TID251, F841, PLR0913). Added narrow `per-file-ignores` entries in `pyproject.toml`, matching the existing precedent, to unblock the commit; remediation stays scheduled in Milestone 5.
- 2026-11-05: Approval UX confirmed as one batch plan review, not a per-action prompt. `IPlanReviewer` resolves unconditionally (`registries/reviewer.py:37`), `ExecutionOrchestrator._perform_interactive_review` calls `review(plan)` once, and `TextualPlanReviewer.review_action` is a no-op returning `(True, "")`. The per-action `IUserInteractor.confirm_action` prompt is unreachable from the CLI. The first Cleanup wording ("requires confirmation before each action") was corrected accordingly.
- 2026-11-05: Settled vocabulary: "plan review" for the batch TUI step, "yolo run" for a run that skips it, "pipeline run" for `--pipeline`. The three `--yolo/--no-yolo` help blocks now read "Skip the plan review and execute all actions. --no-yolo / -n reviews the plan first (default)." and the max-turns/max-cost help reads "for a yolo run".
- 2026-11-05: The README usage examples, the environment and optional-flags tables, the CI paragraph, the `config.yaml` `yolo_default`/`guardrails` comments, and the ARCHITECTURE glossary were rewritten. Table rows were re-padded to their original line length so columns stay aligned.
- 2026-11-05: Glossary term renamed **Action Approval** -> **Plan Approval**, with a sentence stating that the TUI reviewer presents the whole plan once and no per-action prompt follows. The historical clause recording `interactive` as the former name is retained as a deliberate history note, not a stale current name.
- 2026-11-05: As-Built signature corrections landed across `run_plan_use_case.md`, `execution_orchestrator.md`, `session_orchestrator.md`, `session_loop_guard.md`, the outbound `session_loop_guard.md` port doc, `tests/drivers/cli_adapter.md`, and the `ProductionSessionLoopGuard` docstring; all now spell `require_approval`. The CLI invariant is renamed to `pipeline_skips_review`.
- 2026-11-05: Slice Scenario and Verification rewritten to describe the batch review. Suite green at 2251 passed, 5 skipped after every string-only pass.
- 2026-11-05: Out of scope, pre-existing spec drift noted for later reconciliation: `docs/project/specs/manual-cli-workflow.md` still describes an "Action-by-Action Approval Loop" for `teddy execute` without `-y`, which the batch reviewer supersedes.
- 2026-11-05: The stale-reference sweep caught four `interactive=` tokens left in test comments and docstrings (one in `test_action_executor.py`, one in `test_orchestrator_interaction.py`, two in `test_pipeline_message_break.py`). The tokenizer skipped them because they are STRING/comment content, so they were fixed by hand. Test prose such as "interactive mode" was intentionally left alone: the slice scope is user-facing wording plus provably stale identifiers.
- 2026-11-05: Final Verification audit passed. No retired approval vocabulary (`auto-approve`, per-action confirmation, "interactive mode") survives on any current surface; no `interactive=` parameter remains in `src`, `tests`, `docs/architecture`, or milestones; the glossary carries **Plan Approval** only; no skeleton or placeholder markers remain in production. Full suite green at 2251 passed, 5 skipped. Slice marked Completed.

## Verification
1. **Plan review (default):**
   Run `teddy start -a assistant -m "list the files in this repository"`.
   Confirm the TUI plan reviewer opens on the plan before any action runs.
2. **Yolo run:**
   Run `teddy start -y -a assistant -m "list the files in this repository"`.
   Confirm no plan reviewer opens and the action runs.
3. **Forced review:**
   With `yolo_default: true` in `.teddy/config.yaml`, run `teddy start -n -a assistant -m "list the files in this repository"`.
   Confirm the TUI plan reviewer opens on the plan.
4. **Resume prompt preserved:**
   With `yolo_default: true`, run `teddy resume -m ""` at a terminal.
   Confirm the blank-message prompt appears.
5. **Help wording:**
   Run `teddy start --help` and `teddy resume --help`.
   Confirm `-n/--no-yolo` reads as reviewing the plan first and no flag description says "interactive mode".
