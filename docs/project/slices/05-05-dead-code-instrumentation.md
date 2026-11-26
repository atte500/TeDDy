# Slice: Remove the Dead Execute Helper and Its Debug Print
- **Status:** Planned
- **Milestone:** [Milestone 5: Quality Gate & Debt Reconciliation](/docs/project/milestones/05-quality-gate-debt-reconciliation.md)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [CLI Adapter](/docs/architecture/adapters/inbound/cli.md)
- **Scope Slug:** `dead-code-instrumentation`

## Goal
Delete the unreachable `execute_valid_plan` helper and the stray `DEBUG CLI` line it writes to stderr on every call, so the inbound adapter layer holds only code the CLI actually runs and no run can print diagnostics the operator never asked for.

## Context
- `execute_valid_plan` (`src/teddy_executor/adapters/inbound/cli_helpers.py:209`): Resolves `IRunPlanUseCase`, performs a function-local `import sys`, writes `print(f"DEBUG CLI: Resolved orchestrator: {type(orchestrator)}", file=sys.stderr)`, calls `orchestrator.execute(plan=..., require_approval=..., plan_path=..., plan_content=...)`, and returns the report.
- Proof of deadness: a repository-wide `git grep "execute_valid_plan" -- src` returns exactly one hit, the definition itself. No caller exists by name, and no `__all__` or plugin registry exports the symbol.
- Why the debug line matters even while dead: it is one plausible re-wiring away from printing an internal object type onto a user's terminal on every `execute` run, which is exactly the kind of leftover instrumentation the Failure Transparency standard exists to prevent.
- Neighbours that stay: `handle_report_output` and `prewarm_imports` live in the same module and are live code paths.
- Disposal of the historical confusion: the helper's name suggests it is the `execute` command's body, but the live `execute` path resolves its orchestrator elsewhere, so the name is the only thing that ever made this function look load-bearing.
- Scope exclusion: the `InterruptGuard.enter_waiting` wire-or-remove decision belongs to [slice 04-02](./04-02-waiting-feedback.md), which owns the waiting seam, so this slice does not touch it.
- Precedent: the `begin_waiting` census in the same sweep returned zero hits and confirmed that seam is *unbuilt* rather than dead, which is the opposite conclusion for the opposite reason — an absent implementation is work, an unreferenced one is debt.

## Scenarios

> As a maintainer, I want the adapter module to contain only code the CLI runs.

```gherkin
Given the repository checked out at this slice's merge commit
When I grep for execute_valid_plan
Then no hit remains in src/
And the CLI module still exposes its live helpers
```

> As an operator, I want no internal diagnostics on my terminal.

```gherkin
Given a plan executed through teddy execute
When the run completes
Then stderr carries no DEBUG CLI line
```

> As a maintainer, I want the removal to be provably behaviour-preserving.

```gherkin
Given the full test suite before and after the removal
When I compare the two runs
Then the same tests pass
And no test changes its name or assertion
```

## Edge Cases
- **Dynamic reference**: If any code reaches the helper through `getattr`, a string name, or a plugin registry, then removal breaks it silently at runtime, because a name-based call is invisible to `git grep`. The grep therefore runs over `src/`, `tests/`, `scripts/`, and `docs/` before deletion.
- **Test exercising it directly**: If a unit test targets `execute_valid_plan` itself, then that test is deleted with it, because the helper has no behaviour worth pinning independently of the orchestrator it wraps.
- **Documented reference**: If a component page or spec names the helper as the `execute` entry point, then that sentence is corrected rather than deleted, because the page must point at whichever function actually runs.
- **Shared function-local import**: If `import sys` is used by a neighbouring function in the module, then only the helper's own import is removed, because a module-level import may still be needed elsewhere.
- **Return type**: If a caller is added later, then it constructs its own call to `orchestrator.execute(...)` rather than resurrecting the helper, because the live path already proves that shape.

## Key Unknowns
- None. Deadness is proven by a zero-caller census over every directory that can hold a reference, and the removal has no runtime surface.

## Impact
1. `[PRUNE]` `execute_valid_plan` in `src/teddy_executor/adapters/inbound/cli_helpers.py` — the function body, its `import sys`, and its `DEBUG CLI` print.
2. `[MIGRATE]` Any documentation that names the helper as the `execute` entry point, pointing it at the live path instead.
3. `[NEW]` A regression assertion that `cli_helpers` exposes no unreferenced public function, keeping the module's surface honest as the CLI evolves.

## Deliverables
- [ ] **Harness** — Add a module-surface assertion for `cli_helpers` that fails when a public function has no reference anywhere in `src/`.
- [ ] **Adapter** — Delete `execute_valid_plan` with its function-local import and debug print, and prove the `execute` acceptance tests pass unchanged.
- [ ] **Cleanup** — Correct any page naming the helper as the `execute` entry point, and remove the milestone debt entry that tracked it.

## Implementation Notes

## Verification
1. **No dead symbol:**
   Run `git grep -n "execute_valid_plan" -- src tests scripts docs`.
   Verify no hit remains.
2. **Clean stderr:**
   Run `uv run teddy execute --plan-content <a one-action plan>` and inspect stderr.
   Verify no `DEBUG CLI` line appears.
3. **Suite parity:**
   Run `make test` and confirm the suite is green without test-count or name changes.
