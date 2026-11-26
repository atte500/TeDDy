# Slice: Redundant Test Pruning and Canonical Tree Consolidation
- **Status:** Planned
- **Milestone:** [Milestone 5: Quality Gate & Debt Reconciliation](/docs/project/milestones/05-quality-gate-debt-reconciliation.md)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [TestEnvironment](/docs/architecture/tests/setup/test_environment.md), [TestComposition](/docs/architecture/tests/setup/composition.md)
- **Scope Slug:** `redundant-test-pruning`

## Goal
Leave one case per behaviour in the suite by deleting the acceptance cases whose behaviour a lower tier already pins and folding the two modules that live outside the canonical `tests/suites/` tree into it, so a failure points at the cheapest test that can catch it and a reader finds every test where the directory convention says it is.

## Context
- **The ratio gate is gone (product decision, 2026-11-26):** the tier-ordering gate and its CI step were deleted, along with every reference in the CI and architecture templates. Nothing gates this work, and no ordering target is claimed. The pruning stands on its own merit: a duplicated acceptance case pays a subprocess, a session fixture, and a TTY harness to re-prove what a unit test already localizes.
- **Counts as measured (2026-11-26, `def test_` occurrences):** acceptance 186, integration 164, unit 1912.
- **Two modules live outside the canonical tree:** `tests/unit/core/services/test_action_executor_regression.py` and `tests/integration/adapters/outbound/test_web_scraper_github_scraping.py`. `pyproject.toml` sets `testpaths = ["tests"]`, so CI collects and runs both, while the directory convention (`tests/suites/TEST_TYPE/...`) owns neither. A parallel skeleton is the debt that grows a second home for every new test unless it is closed now.
- **Tier assignment follows the outermost boundary crossed:** no filesystem and no subprocess is unit; a real filesystem fake or a stateful adapter is integration; a subprocess, a TTY, or a CLI entry point is acceptance.
- **An acceptance case has to earn its cost:** `test_console_mode_deprecation.py` and the CLI journeys show the shape — they drive the real boundary through a runner or a subprocess rather than calling a service method.
- **Covering tests must be named:** every deletion lands with the module and test that already pins the behaviour, because a deletion justified as "looks redundant" is how coverage disappears quietly.

## Scenarios

> As a maintainer, I want a duplicated acceptance case deleted rather than tolerated.

```gherkin
Given an acceptance case whose behaviour is pinned by a unit test
When I delete the acceptance case
Then the unit test still passes
And the suite's coverage of that behaviour is unchanged
```

> As a maintainer, I want a demotion instead of a deletion when the entry point is the coverage.

```gherkin
Given an acceptance case driving the CLI for a behaviour also pinned at the service level
When I move it to the integration tier
Then it still drives the CLI entry point
And no assertion is lost
```

> As a maintainer, I want every test to live where the convention says.

```gherkin
Given the modules under tests/unit/ and tests/integration/ that no convention owns
When they move under tests/suites/ at their tiers
Then uv run pytest collects the same number of cases as before
And the parallel skeleton is gone
```

## Edge Cases
- **No lower-tier twin**: If no unit or integration test pins the behaviour, then the acceptance case is the coverage and stays, because deletion to reduce a count would remove the only guard.
- **Different entry point**: If the acceptance case crosses a boundary its apparent twin does not (CLI, subprocess, TTY), then it is demoted rather than deleted, because the entry point is the coverage.
- **Fixture-thin duplicate**: If the acceptance case repeats a unit assertion but not its setup, then delete the acceptance copy, because a unit test localizes the failure.
- **Collection drift**: If a move changes the collection root, then the collected total is asserted identical before and after, because a move is the one change that can silently drop cases.
- **Missing double**: If a demoted case needs a fake that does not exist at the integration tier, then that fake is a deliverable here, not a reason to keep the case at the acceptance tier.
- **Orphaned helper**: If a helper was imported only by deleted cases, then it is pruned in the same commit, because dead test infrastructure outlives its consumers otherwise.

## Key Unknowns
- [ ] [Domain] Which acceptance cases duplicate lower-tier coverage: no mapping exists today. Design Sensitivity: if a whole module turns out to be duplicate → the module is deleted and the acceptance count drops by its size; if only scattered cases are → they are deleted case by case with the covering test named; if a case drives a different entry point → it is demoted to integration, so the acceptance count falls while the total stays constant.

## Impact
1. `[MIGRATE]` `tests/unit/core/services/test_action_executor_regression.py` — moved to `tests/suites/unit/core/services/`.
2. `[MIGRATE]` `tests/integration/adapters/outbound/test_web_scraper_github_scraping.py` — moved to `tests/suites/integration/adapters/outbound/`, with its recorded fixture payload following it.
3. `[PRUNE]` The acceptance cases proven redundant by the mapping pass — deleted with the covering test named.
4. `[MIGRATE]` The acceptance cases that are integration-shaped — reassigned to the integration tier.
5. `[NEW]` Harness doubles for any demoted case whose dependencies were previously satisfied by acceptance-level setup.
6. `[PRUNE]` Test helpers imported only by the deleted cases.
7. `[MIGRATE]` The milestone's recorded counts — replaced with the re-measured values at completion.

## Deliverables
- [ ] **Harness** — Add the doubles the demoted cases need, and assert the collected case total is unchanged across the two module moves.
- [ ] **Migration** — Move the two stray modules into `tests/suites/` at their tiers, delete the redundant acceptance cases with their covering tests named, and demote the integration-shaped remainder.
- [ ] **Cleanup** — Prune the helpers the deleted cases leave behind, and record the re-measured tier counts in the milestone.

## Implementation Notes

## Verification
1. **Moves preserve collection:**
   Record `uv run pytest --collect-only -q | tail -1` before and after the two module moves.
   Verify the total is identical and no test path remains outside `tests/suites/`.
2. **Deletions are covered:**
   For each deleted acceptance case, run the named covering test.
   Verify it passes and asserts the same behaviour.
3. **Demotions keep their boundary:**
   Run the demoted integration cases.
   Verify each still drives the entry point that made it worth keeping.
