# Task: Guard the Post-Commit Hook Against Rebase Data Loss

## Business Goal

Prevent `git pull --rebase` from silently dropping commits by making the post-commit test gate skip replayed commits during automated git operations, so that `make push` can rebase safely.

## Context

The post-commit test gate (`.githooks/post-commit.py`, wired via `.pre-commit-config.yaml` with `stages: [post-commit]`) runs the full test suite after every commit and reverts the commit with `git reset --soft HEAD~1` on failure. It is the only unskippable gate.

A confirmed defect (verified by spike) exists during `git pull --rebase`: Git fires the `post-commit` hook once per replayed commit. Because the hook reverts on failure, a failing replay silently drops that commit while the rebase still reports success (exit 0). The `pre-commit` hook does NOT fire during a rebase. This makes the deferred-push workflow unsafe, because `make push` runs `git pull --rebase` immediately before pushing.

The fix is a guard at the top of the hook that exits immediately (skipping the suite) whenever an automated git operation is in progress — detected by the presence of `rebase-merge`, `rebase-apply`, `MERGE_HEAD`, or `CHERRY_PICK_HEAD` under the resolved git directory (`git rev-parse --git-dir`). The spike confirmed that with the guard, the hook skips each replay and all local commits survive the rebase.

Per the user's directive, apply the guard to our own local hook AND keep the documentation templates aligned (both template trees) if they need updating.

## Implementation Steps

### Step 1: Add the automated-git-operation guard to the hook
- **File:** [.githooks/post-commit.py](/.githooks/post-commit.py)
- **Change:** Add a helper (e.g. `_in_progress_git_operation() -> bool`) that resolves the git dir via `git rev-parse --git-dir` and returns `True` if any of `rebase-merge`, `rebase-apply`, `MERGE_HEAD`, or `CHERRY_PICK_HEAD` exists under it. Call it as the FIRST statement in `main()` and `return` immediately when it is `True` (skip the uv/pytest pre-flight and the suite). Keep all existing behavior otherwise.

### Step 2: Add a unit test for the guard
- **File:** [tests/suites/unit/test_postcommit_hook_rebase_guard.py](/tests/suites/unit/test_postcommit_hook_rebase_guard.py)
- **Change:** CREATE a unit test following the existing `.githooks/` standalone-script test pattern (see [tests/suites/unit/test_githooks_posix_only_patches.py](/tests/suites/unit/test_githooks_posix_only_patches.py) for how a `.githooks/*.py` module is loaded). Use `tempfile.mkdtemp()` for the fake git dir (project temp-file standard) and assert the guard returns `False` with no markers and `True` for EACH marker (`rebase-merge`, `rebase-apply`, `MERGE_HEAD`, `CHERRY_PICK_HEAD`).

### Step 3: Align the project pre-commit template
- **File:** [docs/templates/pre-commit.md](/docs/templates/pre-commit.md)
- **Change:** Confirm the documented post-commit guard (sketch and the "Guards against automated git operations" bullet) matches the implemented helper name and the four markers; correct any drift.

### Step 4: Mirror the template into the bundled tree
- **File:** [src/teddy_executor/resources/templates/pre-commit.md](/src/teddy_executor/resources/templates/pre-commit.md)
- **Change:** Apply the same correction so the bundled template stays aligned with the project template (the two trees must not drift; `teddy init templates` copies bundled → project).

## Verification

1. Write the guard test first and confirm it fails (RED), then implement the guard and confirm it passes (GREEN).
2. Run `make test` and confirm the full suite passes with no regressions.
3. Manually confirm the guard behavior: in a scratch git repository mid-rebase the hook exits without running the suite; on a normal commit the suite still runs and reverts on failure.
