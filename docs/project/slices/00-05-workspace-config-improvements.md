# Slice: Workspace Configuration Improvements
- **Status:** In Progress
- **Milestone:** N/A (ad-hoc)
- **Depends On:** None
- **Specs:** [Context Payload Format](/docs/project/specs/context-payload-format.md)
- **Prototype:** None
- **Component Docs:** [IConfigService](/docs/architecture/core/ports/outbound/config_service.md), [IRepoTreeGenerator](/docs/architecture/core/ports/outbound/repo_tree_generator.md)
- **Scope Slug:** `workspace-config`

## Goal
Deliver three approved configuration improvements in one slice so a user gets a working tree depth limit, honest key groups for EXECUTE and EDIT settings, and a single `workspace` group that controls git initialization, hook installation, and the start-only fast-forward pull. The slice also repairs the drifted `config_service.md` data contract so consumers read the real key names.

## Context

- `LocalRepoTreeGenerator.generate_tree()` takes no parameters and recurses the full tree. The constructor accepts only `root_dir`.
- `IConfigService.get_setting(key, default)` reads a dict; there is no schema.
- `execution.*` currently holds two EXECUTE keys and one EDIT key:
    - `execution.default_timeout_seconds` (EXECUTE)
    - `execution.max_output_lines` (EXECUTE)
    - `execution.similarity_threshold` (EDIT)
- `_run_health_checks()` runs `_ensure_commit_hooks()` and `_check_git_initialized()` unconditionally. Both are invoked through `_run_startup_preamble`, which `handle_new_session` and `handle_resume_session` both call.
- No git pull behavior exists at session start. The conclusion path runs `git pull --rebase` via `make push`.
- `config_service.md` lists `max_execute_lines`, `max_read_lines`, and `prune_preceding_on_non_green`. None match the bundled `config.yaml`, which uses `execution.max_output_lines`, `read.max_lines`, and `auto_pruning.prune_failure_history`.
- Users persist values to `.teddy/config.yaml`. That file survives upgrades because the bundled loader layers the user file over the baseline. A hard rename silently reverts a tuned value.

## Scenarios

> As a maintainer, I want a working tree depth limit so a large repository does not inflate the context payload, and I want the truncation to be honest rather than silent.

```gherkin
Given a repository with max_tree_depth of 2
When the context payload is generated
Then directories below depth 2 render as specific sections
And each truncated directory shows a single-name section like:
  [... directory not expanded (depth limit 2): 3 folders, 12 files]
```

```gherkin
Given a repository with max_tree_depth of 0
When the context payload is generated
Then the tree is rendered without a depth limit
And no omission marker appears
```

> As a maintainer, I want EXECUTE settings under `execute.*` and the EDIT setting under `edit.*`, so I can predict the group without reading the file.

```gherkin
Given a user who has customized execution.similarity_threshold in their .teddy/config.yaml
When the code loads the new schema with edit.similarity_threshold as the canonical key
Then the resolver returns the user's old value via the legacy fallback
And the user's .teddy/config.yaml is untouched
```

> As a user, I want a workspace that stays in sync at session start, and I want to be able to opt out of each startup step individually.

```gherkin
Given workspace.init is true and CWD has no .git
When teddy start runs
Then git init executes and the user sees a green notification
And teddy resume later shows the same behavior

Given workspace.pre-commit is false
When teddy start runs and no hooks are installed yet
Then no installation runs and the user sees:
  ⚠ Pre-commit hook installation is disabled. The post-commit test gate will not run.

Given workspace.pull is true and the current branch can fast-forward
When teddy start runs after the health checks
Then the branch fast-forwards and the user sees a short success line
And teddy resume never runs a pull
```

## Edge Cases

- **Depth limit of one:** Only the root section appears. Every top-level directory renders as an omission marker. Comment states the limit value (`depth limit 1`).
- **Unreadable truncated directory:** Marker renders `[... directory not expanded (unreadable): 0 folders, 0 files]` so the omission stays explicit.
- **Zero visible children after ignore rules:** The section is skipped, matching the existing `if not names: continue` rule. The marker itself is not emitted for genuinely empty directories, because they are not truncated.
- **Singular counts:** `1 folder, 1 file`. Any count of one uses lowercase singular.
- **Symlinks:** Treated as files, never followed. Depth counting follows the same rule, so a symlink at the limit renders as a name without a marker.
- **Legacy key with a `None` value:** The migration must skip the copy rather than produce a new key with `None`. `_merge_dicts` already prunes `None` overrides.
- **Legacy key inside a non-dict parent:** Migration writes a new nested dict under the new group without touching the legacy parent.
- **User file carries both legacy and new key:** New key wins. Migration is a no-op.
- **`pre-commit` toggle with an existing hook:** Installation is skipped, but the existing hook still runs on the next commit. The toggle gates the installer, not the hook execution.
- **`init` toggle and `.git` present:** No warning, because the workspace is already a repository.
- **Pull on detached HEAD:** Silent skip, no warning.
- **Pull on a dirty tree, diverged branch, or in-progress operation:** One warning line, continue, no merge, no rebase, no stash.
- **Pull with a new untracked file collision, index lock, network failure, or non-zero exit:** One warning line, continue, workspace unchanged.
- **Interactive credential prompt:** Terminate the pull by setting `GIT_TERMINAL_PROMPT=0` and applying a hard 15 second timeout. Print one warning and continue.

## Impact

1. `[EXPAND]` `LocalRepoTreeGenerator.__init__` — Add `max_depth: int = 0`. Behaviour unchanged when zero.
2. `[EXPAND]` `LocalRepoTreeGenerator._collect_directory` — Accept a `depth` counter and emit the omission marker at the limit.
3. `[EXPAND]` `IRepoTreeGenerator.generate_tree` — Postcondition documents the marker and 0-means-unlimited semantics. No signature change.
4. `[EXPAND]` `YamlConfigAdapter._load_user_config` — Run a private `_migrate_legacy_execution_keys(user_config)` before the merge.
5. `[CONTRACT]` `execution.*` — Split into `execute.*` and `edit.*` in `config.yaml`, `action_factory.py`, `validation_rules/helpers.py`, and `registries/infrastructure.py`.
6. `[EXPAND]` `_run_health_checks` — Accept `config_service: IConfigService` and gate `_ensure_commit_hooks` and `_check_git_initialized` on `workspace.pre-commit` and `workspace.init`.
7. `[NEW]` `_pull_workspace_on_start` — New helper invoked only from `handle_new_session`.
8. `[EXPAND]` `config.yaml` — Add `context.max_tree_depth`, `execute.*`, `edit.*`, and `workspace.*`.
9. `[CONTRACT]` `config_service.md` — Correct three wrong key names and add the seven new group entries.
10. `[NEW]` `_warn_disabled_workspace_steps(config_service)` — Emit one warning per disabled gate that has a real consequence.

## Deliverables

### Section A: Configurable Tree Depth with Explained Omission Marker

- [x] **Env** — Add `context.max_tree_depth: 4` to `src/teddy_executor/resources/config/config.yaml` beneath the `read:` block with comment `# Max project tree depth (0 = unlimited).`
- [x] **Contract** — Add `max_depth: int = 0` to `LocalRepoTreeGenerator.__init__` and store it as `self._max_depth`. Document the marker format and 0-means-unlimited semantics in `docs/architecture/core/ports/outbound/repo_tree_generator.md` postconditions.
- [x] **Wiring** — Inject `container.resolve(IConfigService).get_setting("context.max_tree_depth", 0)` at `infrastructure.py:146`.
- [x] **Logic** — Thread a `depth` counter through `_collect_directory`. When `max_depth > 0` and `depth >= max_depth`, emit a section whose names list contains one marker line `[... directory not expanded (depth limit N): X folders, Y files]` and do not recurse. Count only visible immediate children after ignore rules.
- [x] **Logic** — Emit `[... directory not expanded (unreadable): 0 folders, 0 files]` for `PermissionError` instead of the empty-section skip, so truncation is never ambiguous with an empty directory.
- [x] **Harness** — Extend `tests/suites/integration/adapters/outbound/test_local_repo_tree_generator.py` with scenarios for `max_depth=0`, `max_depth=2`, singular versus plural counts, and unreadable directories.
- [x] **Harness** — Extend `tests/suites/integration/adapters/outbound/test_tree_generator_performance.py` with a deep-tree test that proves the depth limit prevents unbounded recursion.

### Section B: `execute.*` and `edit.*` Split with Legacy Fallback

- [ ] **Env** — Replace the `execution:` block in `config.yaml`:
    ```yaml
    execute:
      default_timeout_seconds: 60       # Default timeout for EXECUTE actions.
      max_output_lines: 100             # Caps EXECUTE stdout/stderr output lines.

    edit:
      similarity_threshold: 0.95        # EDIT match threshold (1.0 = exact match; ignores relative indentation).
    ```
- [ ] **Contract** — Add `_migrate_legacy_execution_keys(user_config)` as a private method on `YamlConfigAdapter`. For each of `default_timeout_seconds`, `max_output_lines`, and `similarity_threshold`, if `user_config['execution'][key]` is present and the corresponding new key (`execute.<key>` or `edit.<key>`) is absent, copy it into the new location. Skip `None` values. Run this method from `_load_user_config` before the merge.
- [ ] **Migration** — Update production reads: `action_factory.py` reads `execute.default_timeout_seconds` and `edit.similarity_threshold`; `validation_rules/helpers.py` reads `edit.similarity_threshold`; `infrastructure.py` reads `execute.max_output_lines`.
- [ ] **Harness** — Extend `tests/suites/unit/adapters/outbound/test_yaml_config_adapter*.py` with a scenario where a user file carries only the legacy keys, and one where a user file carries both. Assert the new key wins.
- [ ] **Harness** — Extend `tests/suites/unit/core/services/test_action_factory*.py` and `test_validator_edit_resilience.py` with new-key assertions.

### Section C: `workspace` Group with Toggles and Guarded Pull

- [ ] **Env** — Add to `config.yaml`:
    ```yaml
    workspace:
      init: true         # Initialize a missing Git repository (start and resume).
      pre-commit: true   # Install pre-commit and post-commit git hooks (start and resume).
      pull: true         # Fast-forward pull before starting a new session (start only).
    ```
- [ ] **Wiring** — Refactor `_run_health_checks(config_service: IConfigService)` to gate `_ensure_commit_hooks` on `workspace.pre-commit` and `_check_git_initialized` on `workspace.init`. Add `_warn_disabled_workspace_steps(config_service)` that runs when either gate is off and prints exactly one warning line per disabled gate that has a real consequence:
    - `workspace.pre-commit: false` → `⚠ Pre-commit hook installation is disabled. The post-commit test gate will not run.`
    - `workspace.init: false` and `.git` absent → `⚠ Git repository not initialized. Version control actions will fail.`
- [ ] **Wiring** — Add `_pull_workspace_on_start(config_service: IConfigService)`. Call it from `handle_new_session` AFTER `_run_startup_preamble` returns and BEFORE `_determine_session_name`. Do NOT call it from `handle_resume_session`.
- [ ] **Logic** — Implement `_pull_workspace_on_start` per the failure matrix in the Edge Cases section. Detections:
    1. `(Path.cwd() / ".git").exists()` false → silent skip.
    2. `git rev-parse --abbrev-ref --symbolic-full-name @{u}` fails → silent skip (no upstream).
    3. `git symbolic-ref -q HEAD` fails → silent skip (detached HEAD).
    4. `.git/{rebase-merge,rebase-apply,MERGE_HEAD,CHERRY_PICK_HEAD}` present → silent skip.
    5. Tracked changes in worktree (`git status --porcelain` reports tracked lines) → one warning, continue.
    6. Otherwise run `subprocess.run(["git", "pull", "--ff-only"], env={...GIT_TERMINAL_PROMPT:"0"...}, timeout=15, capture_output=True)`. Non-zero exit → one warning line, continue.
    7. Success with fast-forward → one short line naming the number of commits fast-forwarded. Success with zero changes → silent.
- [ ] **Harness** — Add `tests/suites/unit/adapters/inbound/test_workspace_config_toggles.py` covering each warning path and the pull guard for detached HEAD, dirty tree, and diverged branch.
- [ ] **Harness** — Extend `tests/suites/unit/adapters/inbound/test_session_cli_handlers.py` with scenarios proving that `handle_new_session` invokes `_pull_workspace_on_start` and `handle_resume_session` never does.

### Section D: `config_service.md` Corrections and New Keys

- [x] **Cleanup** — Rewrite the `## Data Contracts` bullet in `docs/architecture/core/ports/outbound/config_service.md` so it lists only the real key names. Replace `max_execute_lines` with `execute.max_output_lines` (int, default 100). Replace `max_read_lines` with `read.max_lines` (int, default 1000). Replace `prune_preceding_on_non_green` with `prune_failure_history` (bool). Add `execute.default_timeout_seconds` (float, default 60.0), `edit.similarity_threshold` (float, default 0.95), `context.max_tree_depth` (int, default 4, 0 = unlimited), `workspace.init` (bool), `workspace.pre-commit` (bool), and `workspace.pull` (bool). Verified pre-applied by documentation commit 5f107678 at line 31 of the port document.

## Implementation Notes

- The `context.max_tree_depth` key defaults to `4`. A value of `0` means unlimited, which restores pre-slice behavior for users who dislike the marker.
- The marker string starts with `[...` so it sorts inside the section names list without a special path prefix. It counts as a name, so it composes with the existing render loop unchanged.
- The legacy migration writes into `user_config` before the merge so the user config appears at the new path AND still resolves at the legacy path for any read that still hits it. The comment-preserving writer (`_surgically_set`) never runs during a read, so the user file stays untouched.
- `workspace.pre-commit` gates `pre-commit install` only. Existing hooks still run on the next commit. The unskippable post-commit test gate depends on the hooks being present, which is why disabling this toggle emits a specific warning naming that consequence.
- The pull helper must inherit a minimal environment. Pass `dict(os.environ, GIT_TERMINAL_PROMPT="0")` so an interactive credential prompt cannot block the session even when the caller is non-interactive.
- Timeout must call `process.kill()` on the child when exceeded. A hanging credential prompt cannot block startup.
- `subprocess.run` returns `CompletedProcess`. Check `returncode != 0` and route to the warning path. Route to the success path when `returncode == 0`, and parse `stdout` for the fast-forwarded commit count if the source output is unambiguous. Fallback: print a generic short success line.
- Section A Env deliverable landed as a declarative change: `context.max_tree_depth: 4` sits beneath the `read:` block of the bundled `config.yaml` with the stated comment. A Red probe confirmed the key was absent, and a Green probe read the value `4`. The full suite stayed green, so no consumer regressed from the new top-level group.
- Section D was verified rather than rewritten. The `## Data Contracts` bullet in `config_service.md` already lists `execute.max_output_lines`, `read.max_lines`, `auto_pruning.prune_failure_history`, `execute.default_timeout_seconds`, `edit.similarity_threshold`, `context.max_tree_depth`, `workspace.init`, `workspace.pre-commit`, and `workspace.pull`. Documentation commit 5f107678 applied the correction, so the deliverable is marked complete without further edits.
- Section A Contract deliverable landed in two parts. The constructor now accepts `max_depth: int = 0` and stores `self._max_depth` after a native assertion rejects a negative value. The port document now states the exact omission-marker format, the unreadable-directory marker, and the zero-means-unlimited rule in both the data contracts and the `generate_tree` postconditions. A Red step reproduced `AttributeError` for the missing attribute and `TypeError` for the unexpected keyword. A focused unit module then passed four assertions, and the unfiltered suite passed 1988 tests with 5 skipped, so no caller regressed from the new keyword parameter.
- Section A Wiring deliverable landed at the composition root. The `IRepoTreeGenerator` factory now passes `max_depth=container.resolve(IConfigService).get_setting("context.max_tree_depth", 0)`, so a user override or the bundled default of `4` reaches the adapter. The composition-root test compares the resolved adapter's stored depth to the resolved config value rather than a literal, so it survives any on-disk user override. A Red step failed with `assert 0 == 4` before the factory change. The eager config read during graph construction exposed a latent ordering assumption in three planning-retry tests, which assigned `get_setting.side_effect` after resolving `PlanningPorts`; configuring each mock before graph resolution restored the deterministic Arrange order. The unfiltered suite then passed 1989 tests with 5 skipped.
- Section A depth-limit Logic deliverable landed in the adapter. `_collect_directory` now takes a zero-based `depth` counter. When the configured limit is greater than zero and the depth reaches it, the method returns a single marker name and stops recursing, so a truncated directory renders `[... directory not expanded (depth limit N): X folders, Y files]` and its children never appear. A shared `_iter_visible_entries` helper supplies one ignore-rule scan to both the expansion loop and the marker count, so the two paths cannot drift. The marker uses lowercase singular nouns for a count of one. A genuinely empty truncated directory returns an empty string, so it renders no section. A Red step failed on the missing marker string and the leaked child names while the constructor and zero-depth tests stayed green. The focused module then passed seven tests, and the unfiltered suite passed 1992 tests with 5 skipped. The `PermissionError` skip stays in the shared helper, so the separate unreadable-directory marker remains an open deliverable.
- Section A unreadable-marker Logic deliverable landed in the adapter. The swallowing `_iter_visible_entries` generator became `_scan_visible_entries`, which returns a materialized list of visible children or `None` when the scan raises `PermissionError`. Both call sites act on that distinction: `_collect_directory` returns the module-level `UNREADABLE_MARKER` instead of an empty list, and `_depth_limit_marker` returns the same constant instead of an empty string. A readable empty directory still returns an empty list, so it renders no section. A Red step failed both marker tests on the missing string with no collection errors. The focused modules then passed nine tests, and the unfiltered suite passed 1994 tests with 5 skipped. The constant single-sources the exact string that the port document already specifies, so no documentation change was needed.
- Section A integration Harness deliverable extended the end-to-end tree scenarios. The shared helper `with_real_tree_generator` gained an additive `max_depth: int = 0` parameter and passes it to the adapter constructor. The parameter is non-breaking because every existing caller keeps the zero default, which still means unlimited, so the performance module's deep-path assertions stay valid. The integration module gained four real-filesystem scenarios: a zero depth renders the deep file with no marker, a depth of one renders the singular `1 folder, 1 file` marker and hides the nested child, a depth of two renders the plural `1 folder, 2 files` marker and hides the deepest file, and an unreadable directory renders the explicit marker while the readable sibling still expands. The focused module passed ten tests, and the unfiltered suite passed 1998 tests with 5 skipped.
- Section A performance Harness deliverable added a deep-tree boundedness test that proves the depth limit bounds recursion instead of the full chain. The first attempt built a 200-level chain and failed during Arrange with `OSError: [Errno 63] File name too long`, because macOS rejects a path above roughly 1024 bytes, so the adapter never ran. Shrinking the chain to 20 levels preserved the proof and kept the path well under the ceiling. The test generates with `max_depth=3` and asserts four facts: `leaf_sentinel.txt` never renders, `d003` never renders, `./d000/d001/d002:` renders the `[... directory not expanded (depth limit 3): 1 folder, 1 file]` marker, and `tree.count("./") == 3`. A fixed section count proves boundedness without a flaky wall-clock limit. The test keeps the win32 skip because a 20-level temp chain can still approach MAX_PATH. The focused module passed three tests, and the unfiltered suite passed 1999 tests with 5 skipped. Section A is now complete.

## Verification

1. **Tree depth marker:**
   Create a scratch repo with `context.max_tree_depth: 2` and a nested directory. Run `teddy context --no-copy` and inspect the payload. Confirm a truncated directory shows `[... directory not expanded (depth limit 2): X folders, Y files]`.
2. **Unlimited default:**
   Set `context.max_tree_depth: 0`. Confirm the whole tree renders with no marker.
3. **Legacy fallback:**
   In a test workspace, place `execution.similarity_threshold: 0.80` in `.teddy/config.yaml`. Run `teddy start --pipeline -m "noop"`. Inspect the resolved value via a debug log or a focused unit test. Confirm `edit.similarity_threshold` resolves to `0.80` and `.teddy/config.yaml` is unmodified.
4. **Workspace warnings:**
   Set `workspace.pre-commit: false` and `workspace.init: false`. Run `teddy start`. Confirm both warning lines appear in order.
5. **Start-only pull:**
   In a repository that is one commit behind origin, run `teddy start`. Confirm the fast-forward line appears. Then run `teddy resume`. Confirm no fast-forward line and no pull output.
6. **Graceful failure:**
   Put the current branch and origin into a diverged state. Run `teddy start`. Confirm the session still proceeds and one warning line appears.
