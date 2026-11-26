# Slice: Green Static-Analysis Baseline
- **Status:** Planned
- **Milestone:** [Milestone 5: Quality Gate & Debt Reconciliation](/docs/project/milestones/05-quality-gate-debt-reconciliation.md)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [PromptManager](/docs/architecture/core/services/prompt_manager.md), [ActionFactory](/docs/architecture/core/services/action_factory.md), [IPdfExtractor](/docs/architecture/core/ports/outbound/pdf_extractor.md), [ConsoleInteractorAdapter](/docs/architecture/adapters/outbound/console_interactor.md)
- **Scope Slug:** `static-analysis-green`

## Goal
Bring every deterministic static check to zero findings on the current dependency set, so the blocking static-analysis job has a green baseline to protect instead of a standing red it must tolerate.

## Context
- `ruff check`: 44 findings today — `TID251` 39, `F841` 2, `F401` 1, `PLR0913` 1, `PLR0915` 1.
- `TID251` distribution: every hit is the banned bare-mock rule, spread over roughly twenty test modules in two clusters — `tests/suites/unit/adapters/outbound/` (ask-loop stdin flush, escape stripping, editor background, console interactor `-m` support) and `tests/suites/unit/adapters/inbound/` (editor process group, flush outside suspend, reviewer app core, label formatting, stdin fileno) — plus core-services suites and one acceptance module (`test_tui_view_plan_robustness.py`, two hits). The findings are therefore per-site migrations, not one config decision.
- Why the rule exists: `tests.harness.setup.mocking.register_mock` returns an auto-specced double, so an undeclared attribute raises instead of silently succeeding. A per-file ignore would re-open exactly the Signature Drift hole the rule closes, which is why [slice 05-02](./05-02-suppression-audit.md) deletes the ignores that already exist rather than adding more.
- `mypy`: 10 errors across 8 files, in three families.
  - Platform-conditional attributes: `msvcrt.kbhit` / `msvcrt.getwch` at `console_interactor_ask_loop.py:85-86` and `textual_plan_reviewer_editor.py:191-192`.
  - Contract defects: `planning_service.py:137` passes `token_usage=` while `IPromptManager.update_meta` declares `_token_usage`; `action_factory.py:133` calls `.extract_text()` on an `IPdfExtractor | None`.
  - Annotation gaps: `textual_plan_reviewer_previews.py:276`, `textual_plan_reviewer_app.py:387`, `action_executor.py:227`, `session_lifecycle_manager.py:127`.
- `bandit -q -r src`: 29 findings — one medium severity, 28 low, all high confidence — so the step exits non-zero regardless of severity.
- Ordering: this slice lands before [05-02](./05-02-suppression-audit.md) (same modules and the same `pyproject.toml` block) and before [05-04](./05-04-ci-gate-split.md), which promotes these checks into a blocking job.
- Bypass policy in force: no new bare suppression; a genuine one-off may carry a narrow inline suppression with a reason; anything repeated belongs in `per-file-ignores` with a reason comment, and 05-02 then audits what remains.

## Scenarios

> As a maintainer, I want a type error to be the exception rather than the standing state.

```gherkin
Given the repository at this slice's merge commit
When I run ruff, mypy, and bandit over src and tests
Then all three exit zero
And no new suppression comment was added
```

> As a maintainer, I want a migrated test double to reject an undeclared attribute.

```gherkin
Given a test that previously built a bare MagicMock for a port
When the test accesses a member the port does not declare
Then it fails with an AttributeError from the spec rather than returning a dynamic mock
```

> As an operator, I want an unavailable PDF extractor to fail loudly rather than silently skip extraction.

```gherkin
Given a READ action on a .pdf file while no IPdfExtractor is registered
When the factory builds the action
Then it raises a TeddyError naming the missing extractor
And the plan is rejected pre-flight instead of executing without content
```

## Edge Cases
- **`msvcrt` on POSIX**: If the module is imported unconditionally, then the CLI breaks on import under Linux and macOS. The fix is a typed accessor that imports inside a `sys.platform` branch, so mypy sees one typed surface and POSIX never imports the module.
- **Accessor versus ignore**: If the accessor still needs a cast, then the suppression must name `attr-defined` and the platform; a blanket `# type: ignore` is forbidden by policy.
- **`update_meta` keyword**: If the leading underscore marks the parameter as intentionally private, then the port gains a public keyword and both the port and the call site change; renaming only the call site would leave a public method with a private parameter.
- **Optional extractor**: If `IPdfExtractor` is absent because the optional dependency is not installed, then the failure must be a `TeddyError` naming the missing capability, because a silent skip turns a PDF read into an empty resource.
- **`F841` in a hook script**: If the unused variable in `.githooks/check_hardcoded_tmp.py` was meant to be used, then restore the intent rather than deleting the binding, because the script's own check may be incomplete.
- **Bare mock on a module function**: If a `TID251` site patches a module-level function because no seam exists, then that site needs constructor injection first — a module function has no spec to bind to, so auto-speccing cannot substitute for a missing port.
- **Bandit false-positive class**: If a finding is a constant flagged as a hardcoded credential, then the resolution is a config-level `skips` entry with a reason, never an inline `# nosec` scattered per line.
- **Complexity finding**: If the single `PLR0913` or `PLR0915` finding sits in a Typer command signature, then a config-level ignore with a reason is honest, because the framework dictates the parameter count.

## Key Unknowns
- [ ] [Technical] Bandit finding identity: the rule codes behind the 29 findings are unmeasured. Design Sensitivity: if all belong to one false-positive class → a config-level `skips` entry with a reason closes the gate; if any is genuine (`shell=True`, `assert` in `src`, a real credential) → the finding becomes a code fix and, if it needs a design change, its own slice.
- [ ] [Harness] Auto-speccing reach: whether `register_mock` can express the module-function doubles that at least three `TID251` sites need. Design Sensitivity: if it can → all 39 sites migrate within this slice; if not → those sites first gain an injection seam, which adds an Interface deliverable and makes [05-02](./05-02-suppression-audit.md)'s ignore deletion depend on it.

## Impact
1. `[NEW]` A typed platform-conditional terminal-key accessor in `src/teddy_executor/core/utils/` — one surface for `kbhit`/`getwch` behind a `sys.platform` branch, consumed by the ask loop and the reviewer editor.
2. `[MIGRATE]` `planning_service.py` and `IPromptManager.update_meta` — align the keyword so the call site and the port contract agree.
3. `[MIGRATE]` `action_factory.py` — guard the optional extractor and raise a `TeddyError` when a PDF read has no extractor.
4. `[MIGRATE]` The ~20 test modules carrying the 39 `TID251` findings — each bare double replaced by an auto-specced one, or by a newly injected port where no seam exists.
5. `[MIGRATE]` The four annotation-gap sites — explicit narrowing or typed locals so mypy resolves without suppression.
6. `[MIGRATE]` `bandit` configuration — a reasoned `skips` entry only for findings that are false positives by kind.
7. `[MIGRATE]` The affected component pages — record the accessor, the extractor guard, and the `update_meta` keyword.

## Deliverables
- [ ] **Interface** — Add the platform-conditional accessor and settle the `update_meta` keyword and the extractor's failure contract on the pages that own them.
- [ ] **Harness** — Extend `register_mock` coverage to every double shape the 39 sites need, including the module-function cases or their replacement seams.
- [ ] **Core** — Fix both contract defects (the keyword mismatch and the unguarded extractor) with unit tests over each branch.
- [ ] **Migration** — Migrate the 39 `TID251` sites, resolve the four annotation gaps, and remove the three unused bindings, proving the suite stays green throughout.
- [ ] **Cleanup** — Reach zero findings on all three tools, confirm no new suppression was introduced, and record the accessor and extractor guard on their component pages.

## Implementation Notes

## Verification
1. **Gates green:**
   Run `uv run ruff check .`, `uv run mypy src`, and `uv run bandit -q -r src`.
   Verify all three exit zero.
2. **Specced double bites:**
   Temporarily add an undeclared attribute access to one migrated test and run it.
   Verify it fails with an `AttributeError` rather than returning a mock.
3. **Missing extractor:**
   Build a plan with a PDF `READ` while the extractor is unregistered.
   Verify validation rejects the plan naming the missing capability.
