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
> 8. Report template consolidation: merge the two separate `## Resource Contents` render sites in `execution_report.md.j2` (`report.failed_resources` + the classified `resource_logs` pass) into the single classification pass. They currently cover disjoint execution paths (verified during the execute-mode READ duplication investigation), but a future change bridging the paths could re-introduce the divergent-duplicate-gating bug class. See the `[DEBT]` entry in `docs/project/PROJECT.md`.
> 9. ReportParser inline content extraction: extend `tests/harness/observers/report_parser.py` (currently extracts only `stdout`/`stderr` blocks) with structured extraction of inline fenced content blocks in Action Log entries, so observers can assert on inline render placement without raw-regex fallbacks. See the `[DEBT]` entry in `docs/project/PROJECT.md`.
> 10. Resume-threading signature refactor (PLR0913): split the over-threshold signatures introduced by the append-only `--message/-m` Contract threading — `SessionLifecycleManager.resume` (6 > 5), `_consume_awaiting_reply` (8 > 5), `_handle_planning_and_execution` (6 > 5), and `_orchestrate_session_loop` in `session_cli_handlers.py` — via a resume-options / consumption-context DTO. These are direct consequences of the Task-Brief-prescribed signatures (not defects) but block the pre-commit Ruff hook when the files are staged. See the `[DEBT]` entry in `docs/project/PROJECT.md`.
> 11. Resume state-machine "interrupted-at-a-reply" single source of truth (Bug 57 Systemic Audit): a communication (single-MESSAGE) turn is semantically "awaiting a reply" whether it was stopped by the pipeline OR interrupted interactively, but only the pipeline-stop path records that fact (the `awaiting_reply` turn-meta flag set in `session_orchestrator.py`). `SessionLifecycleManager.resume` therefore has to INFER intent from a missing flag PLUS the pending plan's shape. Unify the two stop paths behind a single source of truth (record the state on BOTH paths) so the resume state machine collapses to one branch instead of a two-factor inference. See the `[DEBT]` entry in `docs/project/PROJECT.md`.
> 12. Non-communication `PENDING_PLAN` reply handling (Bug 57 Systemic Audit): the `PENDING_PLAN` non-awaiting branch calls `orchestrator.execute(plan_path=..., interactive=..., pipeline=...)` WITHOUT forwarding `message`, so any non-communication turn left pending silently drops an injected `resume -m` reply and re-executes. Define the correct consume/forward semantics for a pending NON-communication turn carrying an injected reply (Bug 57 scoped its fix to COMMUNICATION turns — the reported symptom). See the `[DEBT]` entry in `docs/project/PROJECT.md`.
> 13. Unused `InterruptGuard.enter_waiting()` context manager (Bug 58 Systemic Audit): the two-phase guard exposes a public `enter_waiting()` context manager with a dedicated unit test, but a `git grep` census found NO production call site — the WAITING behaviour is provided implicitly by the default `_executing=False` phase, so the context manager is currently dead code. Decide wire-or-remove: either wire it around the interactive prompts / planning LLM call (the originally-intended seam, Task Brief 00-21 Step 8) or delete the member (a Port-contraction change requiring the accompanying test removal). See the `[DEBT]` entry in `docs/project/PROJECT.md`.
> 14. Bespoke surgical YAML line-editor in `YamlConfigAdapter.set_setting` (Bug 63 Systemic Audit): the comment-preserving fix hand-rolls an indentation-aware key-line scanner (`_find_key_line`), a value-token rewriter (`_surgically_set`), a degenerate-root stripper (`_strip_degenerate_root`), and a missing-key inserter (`_find_ancestor`/`_render_key_lines`/`_find_insertion_point`) in `src/teddy_executor/adapters/outbound/yaml_config_adapter.py`. It exists only to preserve `.teddy/config.yaml` comments/formatting without adding `ruamel.yaml` (the standard comment-preserving round-trip library). Re-evaluate consolidating onto `ruamel.yaml` if that dependency is accepted, or if config-mutation needs grow to additional user-editable keys. See the `[DEBT]` entry in `docs/project/PROJECT.md`.
> 15. Path-matching side-effect normalization helper (Bug 66 Systemic Audit): the `ARCHITECTURE.md` "Cross-Platform Path Assertions" directive mandates `POSIXPathMock.find_call_by_path` for path ASSERTIONS but prescribes no idiom for a mocked method's `side_effect` that must conditionally return a value based on a (normalized) path argument. Bug 66's Windows-only failure came from exactly that gap: `POSIXPathMock` normalizes the first string argument (`\` -> `/`) before the side_effect runs, so a raw `==` against an `os.path.expanduser`-derived baseline silently fails only on Windows. Extract a `normalize_path(value)` helper into `tests/harness/setup/mocking.py` (so both `_normalize_args` and every path-matching side-effect single-source the normalization) and extend the `ARCHITECTURE.md` cross-platform directive to state that path-matching side-effects MUST compare against it. See the `[DEBT]` entry in `docs/project/PROJECT.md`.
