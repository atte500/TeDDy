# Slice: Shared Harness Doubles and Contract-Directory Consolidation
- **Status:** Planned
- **Milestone:** [Milestone 6: Cross-Cutting Consolidation](/docs/project/milestones/06-cross-cutting-consolidation.md)
- **Depends On:** None
- **Specs:** None
- **Prototype:** None
- **Component Docs:** [TestEnvironment](/docs/architecture/tests/setup/test_environment.md), [TestComposition](/docs/architecture/tests/setup/composition.md), [IFileSystemManager](/docs/architecture/core/ports/outbound/file_system_manager.md)
- **Scope Slug:** `shared-harness-doubles`

## Goal
Give every test double that has crossed the rule of three one home in `tests/harness/setup/`, close the hole that let three private copies of the same fake accumulate, and finish the contract-test directory consolidation so there is one canonical location per port layer.

## Context
- Measured: the dict-backed `InMemoryFileSystem` fake exists in exactly three modules — `test_session_repository_meta_contract.py`, `test_session_service_turn_meta.py`, and `test_session_lifecycle_resume_message_persistence.py`. No fourth copy has appeared, so the rule of three is met and precisely at its threshold.
- Measured: four `termios` fakes — `test_tty_guards.py`, `test_terminal_cooked_mode_restore.py`, `test_restore_cooked_mode.py`, `test_terminal_quit_key_listener_reader.py` — plus ask-loop editor and tooling fakes across three suites.
- Measured: the contract directory already holds thirteen modules under `tests/suites/unit/core/ports/`, and `test_run_plan_use_case_contract.py` is not among them. The consolidation is therefore a move plus import fixes, not a redesign of where contract tests belong.
- Also duplicated, from the milestone's constraint list: the `tempfile.mkdtemp()` plus `rmtree` lifecycle in `tests/harness/setup/model_registry_cache.py` and `hook_shims.py`; the real-`tmp_path` `MRP.md` resource-root construction in `test_prompt_manager.py` and `test_prompt_resolution.py`; and the session-container doubles in `test_session_replan_loop.py`, `test_session_start_resequencing.py`, and `test_resume_message_threading.py`, which register a bare `Mock(spec=IInitUseCase)` whose `check_drift()` returns a dynamic mock with no `__len__` — a double that violates the contract it stands in for.
- Enforcement gap: nothing detects a new private double. The six existing structural hooks cover DI boundaries, architecture imports, encoding, `/tmp`, POSIX-only patches, and raw CLI invocation, and the banned-mock rule covers `mock.patch` and bare doubles, but a locally declared `class _InMemoryFileSystem` inside a test module passes every gate.
- Poka-Yoke: a shared fixture removes the incentive, and a structural hook removes the possibility of a quiet fourth copy, which is why both are deliverables rather than one.
- Ordering: [06-01](./06-01-literal-helper-single-sourcing.md) touches the expected-path spellings the shared fake will hold, and [05-08](./05-08-litellm-probe-seam.md) extends a sibling double in the same directory, so a concurrent run needs a rebase.

## Scenarios

> As a maintainer, I want one in-memory filesystem, not three.

```gherkin
Given three suites that each declared their own dict-backed filesystem
When the slice completes
Then each imports the shared fake from tests/harness/setup/
And no suite declares a filesystem fake of its own
```

> As a maintainer, I want a contract-violating double to be impossible to write quietly.

```gherkin
Given a test module declaring a class named like an in-memory or fake double
When the structural hook runs
Then it fails naming the module and the class
```

> As a maintainer, I want the straggler contract test beside its peers.

```gherkin
Given test_run_plan_use_case_contract.py in the legacy directory
When it moves into tests/suites/unit/core/ports/inbound/
Then it is collected and passes
And no document still links the old path
```

## Edge Cases
- **Divergent semantics**: If one fake models `mkdir(parents=True, exist_ok=True)` and another treats any existing path as an error, then the shared fake models the real adapter's semantics and exposes an explicit knob for the divergent case, because the port's behaviour is the contract and the fakes must not disagree with it.
- **Strict subset**: If one copy's surface is entirely covered by another, then the narrower copy is deleted and its tests migrate, because a shared fake with unused features is what a knob is for and a second copy is not.
- **Unreadable-file simulation**: If a test needs a read that raises, then the shared fake raises the adapter's domain exception rather than an `IOError`, because a double that raises a type the port never raises teaches the wrong contract.
- **Temp-root helper**: If the shared helper is used by a module that must not import the suite's fixtures, then it is a plain function in `tests/harness/setup/`, because a fixture cannot be called directly and a duplicated lifecycle is the defect being removed.
- **Session-container doubles**: If the shared fixture supplies `check_drift()`, then it returns a real list, because the original defect was a dynamic mock with no `__len__` that only failed once a caller counted the result.
- **Move mechanics**: If the contract module moves, then it moves with `git mv` and its import paths are fixed in the same commit, because a copied-then-deleted file loses blame and a stale import surfaces at collection time.
- **Collection parity**: If the move changes the collected count, then something is now silently skipped; the move must assert an identical collected total before and after, because a directory move is the one refactor that can drop cases without failing.
- **Hook false positive**: If a test module declares a local class only to model a plain record, then the hook matches on the double-name pattern and the test renames it, because an ambiguous name is what the hook exists to remove.

## Key Unknowns
- [ ] [Technical] Whether the ask-loop editor/tooling fakes share a contract or merely a name. Design Sensitivity: if they share a contract → one fake plus knobs serves all three suites and the extraction is mechanical; if they model different collaborators → each shared fake is extracted separately within this slice, and the hook's name pattern grows to cover both shapes.

## Impact
1. `[NEW]` A shared in-memory filesystem fake in `tests/harness/setup/`, implementing `IFileSystemManager`'s semantics including parents creation and atomic replace.
2. `[NEW]` A shared `termios` fake, and a shared ask-loop editor/tooling fake, each with the minimal knobs their three suites need.
3. `[NEW]` A shared temp-root helper replacing the duplicated `mkdtemp` + `rmtree` lifecycle in `model_registry_cache.py` and `hook_shims.py`.
4. `[NEW]` A shared MRP resource-root helper used by `test_prompt_manager.py` and `test_prompt_resolution.py`.
5. `[NEW]` A pre-configured session-container/ports fixture whose doubles satisfy their ports, replacing the three bespoke containers.
6. `[NEW]` `.githooks/check_private_test_doubles.py` — a structural check failing on a double class declared inside `tests/suites/`.
7. `[MIGRATE]` `.pre-commit-config.yaml` and the `manual`-stage step list — register the new hook.
8. `[MIGRATE]` `test_run_plan_use_case_contract.py` — moved into `tests/suites/unit/core/ports/inbound/` with all references updated.
9. `[MIGRATE]` `TestEnvironment` and `TestComposition` pages — record the shared doubles and the fixture's contract.

## Deliverables
- [ ] **Interface** — Land the shared doubles and the temp-root and MRP helpers, documenting each knob and why it exists.
- [ ] **Harness** — Add the pre-configured container fixture, unit-test the new hook against a local double and a legitimately renamed record class, and register the hook in the `manual` stage.
- [ ] **Migration** — Replace every private copy with the shared double, delete the duplicates, and move the straggler contract module with its imports.
- [ ] **Wiring** — Prove collection parity across the move and that the full suite stays green.
- [ ] **Cleanup** — Record the shared doubles on both harness pages and note that a double belongs in the harness the moment a third suite needs it.

## Implementation Notes

## Verification
1. **Duplicates gone:**
   Run `git grep -n "class .*InMemoryFileSystem\|class .*FakeFileSystem" -- tests/suites`.
   Verify no hit remains.
2. **Hook bites:**
   Add a private fake class to a scratch test module and run `uv run python .githooks/check_private_test_doubles.py`.
   Verify it exits non-zero naming the module and class.
3. **Collection parity:**
   Compare `uv run pytest --collect-only -q` totals before and after the contract-module move.
   Verify the totals are identical.
