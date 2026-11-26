# Slice: Reserve `assert` for Contracts and Narrow the Bandit Skip
- **Status:** Planned
- **Milestone:** [Milestone 5: Quality Gate & Debt Reconciliation](/docs/project/milestones/05-quality-gate-debt-reconciliation.md)
- **Depends On:** [05-01-static-analysis-green](./05-01-static-analysis-green.md)
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [PlanValidator](/docs/architecture/core/services/plan_validator.md), [ActionFactory](/docs/architecture/core/services/action_factory.md)
- **Scope Slug:** `assert-scope-rule`

## Goal
Make the contract-versus-input distinction executable: `assert` stays a strippable contract statement, untrusted plan content is rejected with a raised `TeddyError`, and the repository-wide bandit `B101` skip shrinks to the contract sites that legitimately carry a reasoned inline suppression.

## Context
- `[tool.bandit] skips = ["B101"]` in `pyproject.toml` disables bandit's assert check for the entire repository, so nothing currently distinguishes a pre/post-condition from an input-validation guard.
- `docs/architecture/ARCHITECTURE.md` makes `assert` the Design-by-Contract mechanism and records that assertions vanish under `python -O`. The repository does not run under `-O` today, so the exposure is latent rather than active — which is exactly why it decays unnoticed.
- The untrusted input that matters is LLM-supplied: plan Markdown, action parameters, and metadata lists arrive from the model and are validated before execution. An `assert` on that path is a guard that disappears under optimisation, which the Failure-Transparency standard forbids.
- `PlanValidator` and `ActionFactory` already reject malformed plans, so the audit's question is which of those rejections are currently `assert` statements rather than raises.
- Bandit reports 29 findings in `src` today; whether any `B101` hits are hidden behind the global skip is unmeasured at the source, because the skip suppresses them before reporting.
- Ordering: `Depends On` 05-01 because both edit the `[tool.bandit]` block, and a concurrent run would conflict inside the same table.

## Scenarios

> As a maintainer, I want an input-validation guard that survives optimisation.

```gherkin
Given a plan whose action parameter is malformed
When validation runs under python -O
Then the plan is rejected with a TeddyError naming the parameter
And the rejection does not depend on an assert
```

> As a maintainer, I want a contract assertion to stay a one-line statement.

```gherkin
Given a service method documenting a precondition
When a test drives it with the precondition violated
Then an AssertionError surfaces carrying the precondition text
And no TeddyError is raised for a programming defect
```

> As a maintainer, I want the assert skip to name its sites rather than the repository.

```gherkin
Given the narrowed bandit configuration
When bandit runs over src
Then every remaining B101 finding carries an inline reasoned suppression
And no repository-wide skip remains for B101
```

## Edge Cases
- **Test-only assert**: If an `assert` lives inside `tests/`, then it stays unconstrained, because a shipped-code rule must not create test busywork.
- **Dataclass invariant**: If an `assert` sits in `__post_init__`, then it is a contract position and keeps its message, because construction is where an invariant is cheapest to catch.
- **Bare assert without a message**: If a contract `assert` names nothing, then it gains a message stating the violated precondition, because a stripped or surfaced assertion must explain itself.
- **Typing-only assert**: If the `assert x is not None` exists solely to narrow a type, then it becomes an explicit guard and raise, because narrowing and input validation happen to share a spelling but not an intent.
- **Adapter translating external payload**: If an `assert` guards a remote response shape, then it becomes a raise, because remote data is untrusted exactly like plan content.
- **Assert under a `-O`-free suite**: If the suite never runs optimised, then the conversion cannot be proven by execution alone; the structural hook is therefore the proof, failing on an `assert` inside the parse, validate, or create modules.
- **Skip overlap with 05-01**: If 05-01 adds `skips` entries for genuine false positives, then this slice must not re-add `B101` under a different spelling, because that would restore the repository-wide hole.
- **Lasagne of responsibilities**: If a converted site's `TeddyError` subclass does not exist yet, then it inherits the root base for now and the hierarchy slice assigns it a proper subclass later, because inventing a one-off subclass here would fork the taxonomy.

## Key Unknowns
- None. The census measured 21 `assert` statements in `src`: `session_lifecycle_manager.py` 9, `action_factory.py` 2, `web_scraper_adapter.py` 2, `local_repo_tree_generator.py` 2, and one each in `web_content_service.py`, `session_pruning_service.py`, `execution_orchestrator.py`, `context_service.py`, `plan.py`, and `config_schema.py`. Only `action_factory.py` and `plan.py` sit on the untrusted-plan path, so the conversion is small and localised and the hook keeps its narrow scope; the remaining sites are contract positions that keep their `assert` and gain a message stating the violated precondition. `[tool.bandit] skips = ["B101"]` is confirmed at `pyproject.toml:160`.

## Impact
1. `[MIGRATE]` `[tool.bandit]` in `pyproject.toml` — drop the global `B101` skip, keeping only the skips 05-01 justified.
2. `[MIGRATE]` Every untrusted-input `assert` on the plan path — replaced by an explicit `TeddyError` raise naming the offending value.
3. `[MIGRATE]` Every contract `assert` — carries a message stating the violated precondition, plus an inline reasoned suppression where bandit must keep reporting it.
4. `[NEW]` `.githooks/check_assert_scope.py` — a structural check failing on an `assert` inside the plan-parsing, validation, or action-creation modules.
5. `[MIGRATE]` `.pre-commit-config.yaml` — register the hook in the `manual` stage beside the other structural checks.
6. `[MIGRATE]` `docs/architecture/ARCHITECTURE.md` — restate the Design-by-Contract law with the executable assert-versus-raise boundary.
7. `[MIGRATE]` The `PlanValidator` and `ActionFactory` component pages — record the raise contract for malformed input.

## Deliverables
- [ ] **Env** — Add the assert-scope hook, register it in the `manual` stage, and wire it into the structural-check step list.
- [ ] **Harness** — Unit-test the hook against an assert in a parser module, an assert in a test module, and an assert carrying a reasoned suppression.
- [ ] **Interface** — Record on the two component pages which rejections are input validation and therefore raised, and which are preconditions and therefore asserted.
- [ ] **Core** — Convert the untrusted-input asserts on the plan path into raises, with a unit test per converted branch proving the rejection survives `-O`.
- [ ] **Migration** — Narrow the bandit skip to the contract sites, and confirm the remaining findings each carry a reasoned suppression.
- [ ] **Cleanup** — Restate the ARCHITECTURE boundary, and remove the milestone bullet that describes the `B101` skip as repository-wide by design.

## Implementation Notes

## Verification
1. **Rejection survives optimisation:**
   Build a plan with a malformed action parameter and run its validator test with `python -O`.
   Verify the plan is still rejected, naming the parameter.
2. **Skip narrowed:**
   Run `uv run bandit -q -r src` and inspect the configuration.
   Verify no repository-wide `B101` skip remains and every remaining assert finding is inline-suppressed with a reason.
3. **Hook bites:**
   Add an `assert` to `markdown_plan_parser.py` on a scratch branch and run `uv run python .githooks/check_assert_scope.py`.
   Verify it exits non-zero naming the file and line.
