# Slice: Require Approval Rename
- **Status:** Planned
- **Milestone:** N/A (ad-hoc)
- **Depends On:** None
- **Specs:** [Interactive Session Workflow](/docs/project/specs/interactive-session-workflow.md)
- **Prototype:** None
- **Component Docs:** [CLI Adapter](/docs/architecture/adapters/inbound/cli.md), [SessionOrchestrator](/docs/architecture/core/services/session_orchestrator.md), [ExecutionOrchestrator](/docs/architecture/core/services/execution_orchestrator.md), [SessionLoopGuard](/docs/architecture/core/services/session_loop_guard.md)
- **Scope Slug:** `require-approval-rename`

## Goal
Rename the internal action-approval signal from `interactive` to `require_approval` so the identifier states what the boolean decides, and remove the user-facing strings that describe approval as "interactive". The naming defect is what let Bug 79 happen: a reader saw `interactive=False` and concluded "no human is present".

## Context
- Measured footprint on 2026-11-05: 123 occurrences of `interactive` in `src/` across 23 files, 315 in `tests/`.
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
Given no automatic-approval flag and no pipeline mode
When a plan executes
Then each action requires confirmation before it runs
```

```gherkin
Given `-y` or `yolo_default: true`
When a plan executes
Then no action requires confirmation
```

```gherkin
Given `--pipeline`
When a plan executes
Then no action requires confirmation
```

```gherkin
Given `-n/--no-yolo` while `yolo_default: true`
When a plan executes
Then each action requires confirmation
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
- [ ] [Technical] Persisted contracts: whether any stored artifact (plan parameter name, session `meta.yaml` key, report template variable, config setting) uses the identifier `interactive`. Design sensitivity: if one exists, the wire name is preserved and only the code signal is renamed, keeping the slice non-breaking; if none exists, the rename stays confined to code and docs.

## Impact
1. `[MIGRATE]` `IRunPlanUseCase.execute` / `.resume` — rename the keyword to `require_approval`, keeping the contract shape and parameter order identical.
2. `[MIGRATE]` Core services — `SessionOrchestrator`, `SessionLifecycleManager`, `ExecutionOrchestrator`, `ActionExecutor`, `ProductionSessionLoopGuard` / `ISessionLoopGuard`, and `IPlanReviewer` rename the parameter and their internal reads.
3. `[MIGRATE]` Inbound adapters — `__main__.py` (three derivation sites), `session_cli_handlers.py` (three handler signatures), and `cli_helpers.py` adopt the new name, and the `execute` path drops the `interactive_mode` alias.
4. `[MIGRATE]` Tests — identifier substitution across the affected modules; no assertion changes.
5. `[MIGRATE]` User-facing text — the README flag table and usage examples, the three typer `--no-yolo` descriptions, and the `config.yaml` comment are reworded so `-n` reads as requiring per-action confirmation and `-y` as auto-approving actions. The user-facing flag names `-y/--yolo` and `-n/--no-yolo` do not change.
6. `[MIGRATE]` `docs/architecture/ARCHITECTURE.md` — the Action Approval entry names `require_approval` and records `interactive` as the former name that invited the conflation.
7. `[PRUNE]` `interactive_mode` — the duplicate local name in the `execute` handler is removed.

## Deliverables
- [ ] **Refactor** - Rename the internal approval signal to `require_approval` across ports, services, and adapters, preserving polarity, parameter order, and every existing behaviour.
- [ ] **Migration** - Update all callers, handler signatures, and test doubles to the new keyword without touching any assertion.
- [ ] **Cleanup** - Rewrite the user-facing strings and the glossary entry so approval is never described as "interactive", and confirm no persisted contract carried the old identifier.

## Implementation Notes
Planned; no implementation notes yet.

## Verification
1. **Interactive approval:**
   Run `teddy start -a assistant -m "list the files in this repository"`.
   Confirm TeDDy asks for confirmation before the shell action runs.
2. **Auto-approval:**
   Run `teddy start -y -a assistant -m "list the files in this repository"`.
   Confirm the action runs with no confirmation prompt.
3. **Forced approval:**
   With `yolo_default: true` in `.teddy/config.yaml`, run `teddy start -n -a assistant -m "list the files in this repository"`.
   Confirm the confirmation prompt appears.
4. **Resume prompt preserved:**
   With `yolo_default: true`, run `teddy resume -m ""` at a terminal.
   Confirm the blank-message prompt appears.
5. **Help wording:**
   Run `teddy start --help` and `teddy resume --help`.
   Confirm `-n/--no-yolo` reads as requiring per-action confirmation and no flag description says "interactive mode".
