# Milestone 5: Quality Gate & Debt Reconciliation

- **Status:** Planned
- **Specs:** TBD

## Goal (The "Why")
To clean up the codebase by eliminating unnecessary quality bypasses, removing dead code and redundant tests, and fixing pre-existing quality gate violations that block pre-commit and CI. This ensures the quality gates can run cleanly and the codebase is maintainable.

## Proposed Solution (The "What")
Audit and fix all unnecessary inline quality suppression comments (`# noqa`, `# pylint: disable`, `# type: ignore`). Deprecate and remove `--console` mode and all related dead code paths. Remove tests that duplicate coverage without adding behavioral value. Fix the three known Mypy errors and the C901 complexity issue that currently require `--no-verify` to commit. Audit Git history for bypass commits and verify their justification.

## Guidelines (The "How")
- **Test Harness Strategy:**
    - **Quality Bypass Audit:** Use `git grep` to find all inline suppression comments. Verify each is necessary or remove it.
    - **Dead Code Removal:** Remove `--console` CLI flag and all related code paths. Verify no regressions via full test suite.
    - **Redundant Test Audit:** Review acceptance tests against unit tests. Remove tests that duplicate coverage without adding behavioral value. Run full suite to confirm no coverage gaps.
    - **Mypy Fixes:** Add type annotations and fix return type mismatches. Run Mypy to confirm clean pass.
    - **C901 Fix:** Refactor parser method. Run Ruff to confirm complexity below threshold.
- **Poka-Yoke:** Add a CI check that fails if new inline quality bypasses are introduced without justification comment.

## Technical Specifications
- **Files to Fix (Mypy):**
    - `src/teddy_executor/core/services/action_executor.py:191` — Fix return type mismatch.
    - `src/teddy_executor/core/services/session_orchestrator.py:251` — Fix union-attr on DataclassInstance.
    - `src/teddy_executor/adapters/outbound/openrouter_hydrator.py:17` — Add type annotations.
- **File to Refactor (C901):**
    - `src/teddy_executor/core/services/markdown_plan_parser.py` — `parse` method (complexity 10, threshold 9). Extract preamble stripping, normalization, and AST validation steps.
- **Dead Code to Remove:**
    - `--console` CLI flag in `cli.py` and related handlers.
    - Any code paths gated behind `--console` mode checks.
- **Quality Bypass Audit Scope:**
    - Search for `# noqa`, `# pylint: disable`, `# type: ignore` across `src/` and `tests/`.
    - For each occurrence, determine if it is still necessary. Remove unnecessary ones. Log as debt any that cannot be removed due to external constraints.

## Vertical Slices
> Slice definitions will be created by the Architect during the Design phase. The following high-level breakdown is anticipated:
>
> 1. Inline quality bypass audit and cleanup
> 2. `--console` mode deprecation and dead code removal
> 3. Redundant test identification and removal
> 4. Mypy error fixes (3 files)
> 5. C901 complexity refactor (markdown_plan_parser.py)
> 6. Git history bypass audit
> 7. CI enforcement for future quality bypasses
