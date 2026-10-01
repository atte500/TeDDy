# Slice: Session Name Collision Guard

- **Status:** In Progress
- **Milestone:** N/A (ad-hoc, not milestone-tracked)
- **Specs:** [docs/project/tasks/00-19-session-name-collision-guard.md](/docs/project/tasks/00-19-session-name-collision-guard.md)
- **Prototype:** N/A
- **Component Docs:** [docs/architecture/core/ports/outbound/file_system_manager.md](/docs/architecture/core/ports/outbound/file_system_manager.md) | [docs/architecture/core/services/session_service.md](/docs/architecture/core/services/session_service.md)
- **Scope Slug:** `session-collision-guard`

## Business Goal

Prevent silent data corruption of the session audit ledger when two sessions with the same name and timestamp are created concurrently (e.g., multi-agent workflows), including the turn-100 migration path. The guard uses atomic exclusive creation (`mkdir()` without `exist_ok`) so exactly one process wins any race; the loser retries with an incremented trailing `-N` suffix, reusing the existing continuation-name convention.

## Scenarios

### Concurrent session creation

> As a TeDDy user running multi-agent workflows, I want concurrent creation of identically-named sessions to atomically claim distinct roots, so that neither session's audit ledger is silently overwritten.

```gherkin
Given a session root ".teddy/sessions/{timestamp}-{name}" already exists with its full ledger
When create_session is invoked with the same name within the same second
Then the root ".teddy/sessions/{timestamp}-{name}-2" is claimed atomically via exclusive creation
And the first session's session.context, prompt file, and 01/meta.yaml are byte-identical to before
```

### Turn-100 migration collision

> As a TeDDy user running multi-agent workflows, I want the turn-100 migration to claim an unoccupied continuation root, so that two sibling sessions never merge their audit ledgers into one directory.

```gherkin
Given session ".teddy/sessions/{timestamp}-foo" has completed turn 99
And a live sibling session ".teddy/sessions/{timestamp}-foo-2" exists with its full ledger
When "{timestamp}-foo" performs the turn-100 migration
Then the migration target ".teddy/sessions/{timestamp}-foo-3" is claimed atomically
And the sibling's session.context, prompt file, and 01/meta.yaml are byte-identical to before
```

## Edge Cases

- **Occupied suffix chain**: If candidate roots `-2` through `-N` are all occupied, then the retry loop keeps incrementing the suffix until a free root is claimed, in order to guarantee progress under any collision depth.
- **Non-collision OS errors**: If exclusive creation fails with any error other than `FileExistsError` (e.g., permission denied), then the error is re-raised, in order to uphold the Failure Transparency standard.
- **Names ending in `-<digits>`**: If a user-chosen session name ends in `-<digits>` (e.g., "fix 404"), then the retry may increment the trailing digits (pre-existing mis-parse quirk, out of scope), but uniqueness remains guaranteed, in order to keep a single shared mechanism.
- **Post-claim tolerance**: If the session root is atomically claimed, then turn-directory creation (`01/`) keeps the tolerant `mkdir(exist_ok=True)` path, in order to rely on the winner's exclusive ownership of everything under the root.
- **Non-migration turns untouched**: If `create_next_turn` runs with `is_migration=False`, then turn-path resolution and creation behave exactly as before, in order to avoid regression in normal turn transitions.

## Key Unknowns

All uncertainties were resolved during the Task Brief investigation; none block implementation.

- [x] [Technical] Guard mechanism: exists-check-then-retry vs atomic exclusive-create – Atomic exclusive-create (`mkdir()` without `exist_ok`) chosen: check-and-create is a single OS operation, eliminating the TOCTOU race where two processes both observe a free path.
- [x] [Technical] Suffix-convention compatibility with `_calculate_continuation_name` – Verified: the `-(\d+)$` regex handles collision suffixes (`...-foo-2` migrates to `...-foo-3`), so one shared uniqueness mechanism cleanly covers both call sites.
- [x] [Functional] Sub-second timestamps to avoid intra-second collisions – Deliberately rejected to keep session names readable/sortable; the trailing `-N` retry convention covers intra-second collisions instead.
- [x] [Technical] `IFileSystemManager` enforcement style (ABC vs Protocol) – Resolved during Discovery: it is a `typing.Protocol`, not runtime-enforced. Adding a method is runtime-safe for all implementers, and `register_mock` uses `POSIXPathMock(spec=...)`, so spec-based mocks auto-gain the new method. No Green-to-Green re-partitioning required.

## Implementation Plan

1. **Contract:** extend `IFileSystemManager` with `create_directory_exclusive(path: str) -> bool` (atomic create with parents; `True` on success; `False` iff `FileExistsError`; re-raise everything else) and update the port's contract doc with the atomicity guarantee and session-root-claiming intent.
2. **Harness:** configure happy-path `create_directory_exclusive` defaults (`return_value = True`) on the spec-based `IFileSystemManager` mock in the `mock_fs` fixture (`tests/harness/setup/mocks.py`) and `TestEnvironment._apply_fs_defaults` (`tests/harness/setup/test_environment.py`). Audit finding: there are NO hand-rolled in-memory fakes for this port — the harness exclusively uses `register_mock` (`POSIXPathMock(spec=IFileSystemManager)`), which auto-gains the new Protocol method, so no fake classes need teaching. Collision tests configure occupancy explicitly via `side_effect`.
3. **Adapter:** implement `create_directory_exclusive` in `LocalFileSystemAdapter` via `self._resolve_path(path).mkdir(parents=True)` inside a `try/except FileExistsError` returning `False` (`True` on success); never `exist_ok=True`; no broad except.
4. **Service helper:** add `SessionService._claim_session_root(base_name)` looping candidates `base_name`, `base_name-2`, `base_name-3`, ... against `create_directory_exclusive(f".teddy/sessions/{candidate}")`, returning the first claimed root path.
5. **Consumer wiring (`create_session`):** replace the bare `session_root = f".teddy/sessions/{prefixed_name}"` bootstrap with a `_claim_session_root(f"{timestamp}-{clean_name}")` claim, then derive `turn_dir = f"{session_root}/01"` and create it via the existing tolerant `create_turn_directory` (safe: root is exclusively owned by this process).
6. **Migration wiring (`create_next_turn`):** when `is_migration` is `True`, exclusive-claim the continuation root (base name from `_calculate_continuation_name`) BEFORE `_clone_session_artifacts` runs; use the claimed directory name for `next_dir` and all subsequent persistence (turn dir, meta, context). Non-migration turns unchanged.
7. **Behavioral gate:** sibling-integrity integration test simulating the concurrent-winner scenario for both call sites, asserting sibling ledgers are byte-identical before/after.

**Test Harness strategy:** Red-first unit tests for the port contract (`tests/suites/unit/adapters/outbound/test_file_system_adapter_contract.py`) and for the helper/collision/migration behaviors (`tests/suites/unit/core/services/test_session_service.py`); sibling-integrity integration tests in `tests/suites/integration/core/services/test_session_service.py`. All workspaces use OS-designated temp dirs (`tempfile.mkdtemp()`); doubles injected via Constructor Injection through the existing fakes; strictly bound registration helpers only.

**Green-to-Green audit verdict (Discovery complete):** `IFileSystemManager` is a `typing.Protocol` — not runtime-enforced — so the port addition cannot break implementers at runtime and NO re-partitioning is required. The pre-commit Mypy hook checks staged files only, so the port-only Contract commit stays green; the real adapter implements the method in the immediately-following Logic deliverable. Semantic deduplication check confirmed: keyword matches in `test_session_lifecycle_manager.py` and `test_session_orchestration_integration.py` are incidental (continuation migration flows without collision assertions); no existing coverage of exclusive-create or sibling-collision semantics.

## Deliverables

- [▶] **Contract** - Add `create_directory_exclusive(path: str) -> bool` to the `IFileSystemManager` port and update the port contract doc (atomicity guarantee; session-root-claiming intent).
- [ ] **Harness** - Configure happy-path `create_directory_exclusive` defaults (`return_value = True`) on the spec-based `IFileSystemManager` mock in the `mock_fs` fixture (`tests/harness/setup/mocks.py`) and `TestEnvironment._apply_fs_defaults` (`tests/harness/setup/test_environment.py`).
- [ ] **Logic** - Implement `create_directory_exclusive` in `LocalFileSystemAdapter` (atomic `mkdir(parents=True)` without `exist_ok`; `FileExistsError` returns `False`; other errors re-raised) driven by unit contract tests (TDD).
- [ ] **Logic** - Add `_claim_session_root` suffix-retry helper to `SessionService` driven by unit tests (claims base name when free; retries `-2`, `-3`; stops at first success).
- [ ] **Migration** - Wire `_claim_session_root` into `create_session` (exclusive root claim, then tolerant `01/` creation) with collision unit tests (identical `{timestamp}-{name}` produces a distinct `-2` root; first session's files untouched).
- [ ] **Migration** - Wire exclusive claiming into the `create_next_turn` turn-100 migration path with migration-collision unit tests (occupied continuation root migrates to `-N+1`; claimed name used for all persistence).
- [ ] **Wiring** - Sibling-integrity integration test covering both call sites (pre-existing sibling's `session.context`, prompt file, and `01/meta.yaml` byte-identical before/after the second session's creation/migration).

## Implementation Notes

- **Plan Audit (Orientation):** `IFileSystemManager` confirmed as `typing.Protocol` (not ABC): port additions are runtime-safe, spec-based mocks auto-gain methods, and no Green-to-Green re-partitioning is needed. Harness surface audited: no hand-rolled fakes exist for the port (the only Fake class is the unrelated `FakeHTTPResponse`); the port is provisioned exclusively via `register_mock`/`POSIXPathMock(spec=...)` in the `mocks.py` fixtures and `TestEnvironment._apply_fs_defaults`. Harness deliverable reworded accordingly. Semantic dedup confirmed: no existing collision/exclusive-create coverage; lifecycle-manager and orchestration keyword matches are incidental.

## Verification

1. `uv run pytest tests/suites/unit/adapters/outbound/test_file_system_adapter_contract.py -k exclusive` — new port contract tests pass.
2. `uv run pytest tests/suites/unit/core/services/test_session_service.py -k "collision or continuation"` — retry-loop and migration-collision unit tests pass.
3. `uv run pytest tests/suites/integration/core/services/test_session_service.py` — sibling-integrity integration test passes; existing session tests show no regression.
4. Manual check: create a session, then in a second terminal create a session with the same name within the same second — confirm the second gets a `-2` directory and the first's `session.context`, prompt file, and `01/meta.yaml` are unmodified. (Requires user confirmation before slice completion.)
5. Manual check: force a session to turn 99 while a sibling `-2` session exists — confirm migration targets `-3` and the sibling's ledger is untouched. (Requires user confirmation before slice completion.)
6. Full suite green: `uv run pytest` (post-commit hook enforces this; do not bypass).
