# Slice: Guard the Post-Commit Hook Against Rebase Data Loss
- **Status:** In Progress
- **Milestone:** N/A (ad-hoc)
- **Specs:** N/A
- **Prototype:** N/A
- **Component Docs:** [pre-commit.md](/docs/templates/pre-commit.md), [ARCHITECTURE.md](/docs/architecture/ARCHITECTURE.md)
- **Scope Slug:** `rebase-guard`

## Business Goal

Prevent `git pull --rebase` from silently dropping commits by making the post-commit test gate skip replayed commits during automated git operations, so that `make push` can rebase safely. Source: [task brief](/docs/project/tasks/03-post-commit-rebase-guard.md).

## Scenarios

> As a TeDDy maintainer, I want the post-commit test gate to skip the suite during automated git operations, so that `git pull --rebase` cannot silently drop replayed commits.

```gherkin
Given a git repository with an in-progress rebase (a rebase-merge marker exists under the git dir)
When the post-commit hook runs
Then the hook exits immediately without running the test suite
And no commit is reverted
```

```gherkin
Given a git repository with no in-progress git operation
When the post-commit hook runs
Then the hook proceeds to its normal pre-flight and full test suite
```

## Edge Cases

- **Each marker triggers the guard**: If `rebase-merge`, `rebase-apply`, `MERGE_HEAD`, or `CHERRY_PICK_HEAD` exists under the resolved git dir, then the guard returns `True`.
- **No marker**: If none of the four markers exists, then the guard returns `False` and the suite runs normally.
- **Guard is the first statement**: If the guard returns `True`, then neither the `uv` pre-flight, the `pytest` pre-flight, nor the suite runs.
- **Resolved git dir, not hard-coded `.git`**: If `git rev-parse --git-dir` reports a non-default location (worktree, `GIT_DIR`, custom `core.hooksPath`), then the guard inspects that resolved dir.
- **Templates stay aligned**: If `teddy init templates` copies the bundled template, then the documented guard matches the implemented helper name and markers.

## Key Unknowns

- [x] [Technical] `.githooks/*.py` scripts are loaded in tests via `importlib.util.spec_from_file_location` (see [test_githooks_posix_only_patches.py](/tests/suites/unit/test_githooks_posix_only_patches.py)).
  - **Design Sensitivity:** if a different loading idiom were required → the new test file's loader would change; it does not.
- [x] [Technical] `.pre-commit-config.yaml` wires `post-commit-test-gate` with `stages: [post-commit]` and `entry: uv run python .githooks/post-commit.py`.
  - **Design Sensitivity:** if the entry pointed elsewhere → the guard would need to move; it does not.
- [x] [Functional] No existing test covers the post-commit rebase guard; `test_precommit_hook_skip_guard.py` covers the pre-commit shim skip (a different concern).
  - **Design Sensitivity:** if overlap existed → assertions would be folded into the existing file; they are not.
- [x] [Functional] Both `pre-commit.md` template trees already document the guard sketch with the helper name `_in_progress_git_operation()` and the four markers.
  - **Design Sensitivity:** if they drifted → D3 corrects them; if aligned → D3 is verification-only.

## Implementation Plan

The post-commit hook (`.githooks/post-commit.py`) currently runs the full suite unconditionally and reverts the commit on failure. During `git pull --rebase`, git fires this hook once per replayed commit; a failing replay would trigger the revert and silently drop that commit while the rebase still exits 0. The fix is a guard evaluated as the FIRST statement of `main()`.

**D1 (Logic).** Add a module-level `_in_progress_git_operation() -> bool` helper that resolves the git dir via `git rev-parse --git-dir` and returns `True` if any of `rebase-merge`, `rebase-apply`, `MERGE_HEAD`, or `CHERRY_PICK_HEAD` exists under it. Unit test `tests/suites/unit/test_postcommit_hook_rebase_guard.py` loads the script via `importlib.util.spec_from_file_location` and drives the helper inside a real temp git repo (`tempfile.mkdtemp()` + `git init` + `monkeypatch.chdir`): `False` with no markers, `True` for EACH marker. This is additive (no caller yet) -> Green-to-Green.

**D2 (Wiring).** Call the guard as the FIRST statement of `main()` and `return` immediately when it is `True` (skipping the uv pre-flight, the pytest pre-flight, and the suite). Acceptance test `tests/suites/acceptance/test_postcommit_hook_rebase_guard.py` runs the REAL hook script as a subprocess in a temp git repo with a failing fake `uv` (exits 1) prepended to `PATH`: with a `.git/rebase-merge` marker the hook must exit 0 (the guard short-circuited before touching `uv`); with no marker it must exit 1 (the guard did not over-trigger, so the failing `uv` pre-flight fired). Tracer Bullet / final behavioral gate.

**D3 (Cleanup).** Verify (and correct only real drift in) both `pre-commit.md` template trees so the documented helper name and four markers match the implementation.

**Seams.** `_in_progress_git_operation` is a brand-new module-local function; `main()`'s signature is unchanged. Neither is a Shared Seam (`git grep` for `_in_progress_git_operation` outside the hook has zero hits), so the slice is Green-to-Green with no breaking-sequence partition.

## Deliverables

- [ ] **Logic** - Add `_in_progress_git_operation() -> bool` to `.githooks/post-commit.py` (resolve the git dir via `git rev-parse --git-dir`; `True` iff any of `rebase-merge`, `rebase-apply`, `MERGE_HEAD`, `CHERRY_PICK_HEAD` exists under it). Add `tests/suites/unit/test_postcommit_hook_rebase_guard.py` (load the script via `importlib.util.spec_from_file_location`; `tempfile.mkdtemp()` + `git init` fake git dir; assert `False` with no markers and `True` for EACH marker). Additive, no caller -> Green-to-Green.
- [ ] **Wiring** - Call the guard as the FIRST statement in `main()` and `return` immediately when it is `True` (skip the uv/pytest pre-flight and the suite). Add `tests/suites/acceptance/test_postcommit_hook_rebase_guard.py` running the real script as a subprocess in a temp git repo (rebase marker + failing fake `uv` -> exit 0; no marker + failing fake `uv` -> exit 1). Tracer Bullet / final behavioral gate.
- [ ] **Cleanup** - Verify and align both `pre-commit.md` template trees ([docs/templates/pre-commit.md](/docs/templates/pre-commit.md) and [src/teddy_executor/resources/templates/pre-commit.md](/src/teddy_executor/resources/templates/pre-commit.md)) so the documented helper name and four markers match the implementation; correct only real drift.

## Implementation Notes

## Verification

1. `uv run pytest tests/suites/unit/test_postcommit_hook_rebase_guard.py` passes (False with no markers; True for each of the four markers).
2. `uv run pytest tests/suites/acceptance/test_postcommit_hook_rebase_guard.py` passes.
3. `make test` (full suite, no filters) is GREEN; no pre-existing test regresses.
4. Manual: in a scratch git repository mid-rebase (`git rebase` paused), the hook exits without running the suite; on a normal commit the suite still runs and reverts on failure.
5. Manual: both `pre-commit.md` template trees document the same helper name and four markers as the implementation.
