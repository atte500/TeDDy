# Slice: Test-Suite Integrity — Flakes, Latency Budgets, and Conformance Doubles
- **Status:** Planned
- **Milestone:** [Milestone 7: Runtime Reliability & Boundary Purity](/docs/project/milestones/07-runtime-reliability.md)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [TestEnvironment](/docs/architecture/tests/setup/test_environment.md), [TestComposition](/docs/architecture/tests/setup/composition.md), [ISessionManager](/docs/architecture/core/ports/outbound/session_manager.md)
- **Scope Slug:** `test-suite-integrity`

## Goal
Make the suite's three non-determinisms impossible, replace the two latency assertions that CI skips with measurements that stay meaningful under `xdist`, and stop a hand-enumerated port double from turning every additive Protocol member into a maintenance chore.

## Context
- Three measured non-determinisms, each with a different cause. `test_file_system_adapter_recursion.py` leaks a working directory under `pytest-xdist`, so a sibling test's relative path resolves against the wrong root depending on worker scheduling. A sibling test in `test_planning_service_logging.py` passes only through retry exhaustion, which means it asserts the retry outcome rather than the behaviour it names. A preflight acceptance test failed once in roughly 2,200 runs because it reads ambient stdin and stderr state, and the CLI's prompt gating derives presence from `ISystemEnvironment.isatty()` — the very signal such a test must inject rather than inherit.
- The two latency budgets are `test_context_service_performance.py:18` and `test_tree_generator_performance.py:11`. Both assert wall-clock budgets from `perf_counter()` and both carry a `GITHUB_ACTIONS == "true"` skipif, so CI never guards either regression while a developer run reports failures caused by machine load. The same class of budget on the validator was already repaired, which is why these are the remainder rather than the pattern.
- The milestone proposes thread CPU time as the remedy, and it is right for exactly half the cases. Context assembly and tree generation are dominated by filesystem reads, so `time.thread_time()` measures almost nothing and the assertion becomes vacuous — a green test that can no longer fail. The honest remedies are therefore per-test: CPU time where the work is CPU-bound, and a structural budget (call counts against the filesystem port) where it is I/O-bound, because the regression both modules guard is redundant I/O, not slow arithmetic.
- `test_session_manager_contract.py` enumerates `ISessionManager`'s members by hand, so every additive Protocol member breaks it manually. The repository forbids bare dynamic doubles and global patching and permits mocks only for unverifiable external side effects, so the remedy is not autospec-by-default: it is a harness helper that derives the member set from the Protocol itself and asserts the fake answers all of it, which tolerates additions and still fails a missing member.
- Poka-Yoke: a harness helper is what stops the next budget test from reaching for `perf_counter`, and the conformance helper is what stops the next contract test from enumerating members. Neither is enforceable by a lint, so both are harness deliverables rather than `Env` ones.
- Overlaps: [06-03](./06-03-shared-harness-doubles.md) extracts shared doubles into `tests/harness/setup/`, and this slice's helpers belong beside them; [07-03](./07-03-bounded-edit-matcher.md) adds a budget test of its own and should consume the same helper.

## Scenarios

> As a maintainer, I want a test that cannot depend on which worker ran it first.

```gherkin
Given a test that changes the working directory
When it runs under any xdist worker distribution
Then a snapshot fixture restores the original directory afterwards
And a sibling test resolving a relative path sees the project root
```

> As a maintainer, I want a latency budget that still fails on the regression it names.

```gherkin
Given an I/O-bound path whose budget asserts filesystem calls
When the code starts reading each file twice
Then the budget test fails
And it does not fail because the machine was busy
```

> As a maintainer, I want a new port member to break my fake, not my test file.

```gherkin
Given a Protocol member added to ISessionManager
When the conformance helper inspects the fake
Then it fails naming the unimplemented member
And no test file needed an edit to produce that failure
```

## Edge Cases
- **CWD and `xdist`**: If a fixture snapshots the directory per test, then a second test that also changes it inside the same process still races; the fixture serializes on a module-level guard and fails loudly on nested changes rather than silently interleaving.
- **Restore on failure**: If the test raises, then the snapshot fixture still restores, because a leaked directory poisons every later test in that worker.
- **CPU-bound versus I/O-bound**: If a budget measures CPU time on a path that is almost entirely I/O, then the assertion is vacuous; the slice states which of the two modules uses which remedy and refuses the one-size rule.
- **Call-count brittleness**: If a structural budget counts every filesystem call, then an unrelated additional stat call fails it; the budget counts the specific calls the regression would duplicate, named on the test.
- **CI skipif decision**: If the skipif stays, then the module is marked advisory and the decision is recorded in `## Implementation Notes`; if it goes, then the budget is sized against the slowest runner in the matrix rather than against a developer laptop.
- **Retry-exhaustion test**: If the double returns a fresh generation per call, then fixing the double may reveal the test asserted nothing; it is rewritten to advance one generation and assert the logged outcome, and the coverage it claimed moves to the retry module that owns retry behaviour.
- **Ambient-state acceptance test**: If the test needs a non-terminal run, then it injects a `force_terminal=False` environment capability rather than relying on `CliRunner` defaults, per the Terminal & Environmental Gates law.
- **Protocol-derived conformance**: If a member has a default implementation, then the helper still requires the fake to answer it, because a default on the Protocol is not a behaviour the fake inherits.
- **Fake that is a real implementation**: If a test uses a real service as its double, then the conformance helper is not applied, because asserting conformance of a conforming object proves nothing about the fake.
- **Helper discoverability**: If the helper lives inside a suite, then the next test cannot find it; it lives in `tests/harness/setup/` beside the shared doubles and is documented on both harness pages.

## Key Unknowns
- [ ] [Harness] Whether the preflight flake reproduces under a deterministic replay of its ambient state. Design Sensitivity: if it reproduces → the injected double is a targeted fix with a regression test that pins the ambient combination; if it does not reproduce → the fix is still the injected capability, and the slice records that the failure mode is inferred from the observed symptom rather than demonstrated, because pretending to a reproduced root cause would be worse than naming the inference.

## Impact
1. `[NEW]` A CWD-snapshot fixture in `tests/harness/setup/` with a nested-change guard and an unconditional finalizer.
2. `[MIGRATE]` `test_file_system_adapter_recursion.py` — uses the fixture instead of managing the directory itself.
3. `[MIGRATE]` `test_planning_service_logging.py` — a single-generation `get_completion` double, with the retry assertion moved to the retry module that owns it.
4. `[MIGRATE]` The preflight acceptance test — an injected non-terminal environment capability instead of ambient state.
5. `[NEW]` A latency-budget helper in `tests/harness/setup/` exposing CPU-time and call-count assertions, with the choice documented per use.
6. `[MIGRATE]` `test_context_service_performance.py` and `test_tree_generator_performance.py` — the honest measurement for each, and a recorded decision on the `GITHUB_ACTIONS` skipif.
7. `[NEW]` `assert_protocol_conformance(fake, protocol)` in `tests/harness/setup/`, deriving the member set from the Protocol.
8. `[MIGRATE]` `test_session_manager_contract.py` — the derived check replaces the hand-written enumeration.
9. `[MIGRATE]` `TestEnvironment` and `TestComposition` pages — record the three helpers and when each applies.

## Deliverables
- [ ] **Harness** — Land the CWD-snapshot fixture, the latency-budget helper, and the conformance helper, each documented with the case it exists for.
- [ ] **Migration** — Convert the three flaky modules, both budget modules, and the contract test onto the helpers.
- [ ] **Wiring** — Run the affected modules under repeated `xdist` distributions and record the decision on the CI skipif.
- [ ] **Cleanup** — Record the helpers on both harness pages and delete the local directory management and member enumeration they replace.

## Implementation Notes

## Verification
1. **Flake gone:**
   Run the recursion, logging, and preflight modules 50 times under `-p xdist -n 4`.
   Verify no failure and no leftover directory change.
2. **Budget still bites:**
   Introduce a duplicate filesystem read on the context path on a scratch branch and run the budget test.
   Verify it fails, then revert.
3. **Conformance follows the Protocol:**
   Add a member to `ISessionManager` on a scratch branch without touching any test.
   Verify the conformance helper fails naming that member.
