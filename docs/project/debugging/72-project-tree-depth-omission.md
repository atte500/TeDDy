# Bug: Project Tree Depth Setting Is Ignored and No Omission Mode Exists
- **Status:** Resolved
- **Milestone:** N/A (ad-hoc debugging)
- **Vertical Slice:** [00-05-workspace-config-improvements.md](/docs/project/slices/00-05-workspace-config-improvements.md), [00-06-typed-config-schema.md](/docs/project/slices/00-06-typed-config-schema.md)
- **Specs:** [context-payload-format.md](/docs/project/specs/context-payload-format.md)

## Symptoms
A workspace with `.teddy/config.yaml` containing `context.max_tree_depth: 1` and a nested tree `folder1/folder2/folder3/folder4` still renders every level in `teddy context` and in the `input.md` of `teddy start`. The expected omission marker `[... directory not expanded (depth limit 1): X folders, Y files]` never appears.

The user also asks what a negative depth does and requests a way to omit the project tree entirely.

Minimal reproduction steps:
1. Create a workspace with `folder1/file1`, `folder1/folder2/file2`, `folder1/folder2/folder3/file3`, `folder1/folder2/folder3/folder4/file4`.
2. Set `context.max_tree_depth: 1` in `.teddy/config.yaml`.
3. Run `teddy context --no-copy` and inspect the project tree section.
4. Run `teddy start` with a message that captures `input.md`, then inspect its project tree section.

## Context & Scope
### Regressing Delta
Commit `e16c2f1b` wired `context.max_tree_depth` into the composition-root factory in `src/teddy_executor/registries/infrastructure.py`. The pre-existing re-registration in `src/teddy_executor/__main__.py` (`_ensure_project_initialized`, line 189) still constructs `LocalRepoTreeGenerator` with `root_dir` only, so the later registration drops the configured depth. The probe confirms the ordering: the factory yields depth `1`, and the anchoring step replaces it with depth `0`.

### Environmental Triggers
A workspace whose `.teddy/config.yaml` sets a positive `context.max_tree_depth`, reached through any command that calls `_ensure_project_initialized` (`context`, `start`, `resume`, `execute`). The defect is platform independent.

### Ruled Out
- `LocalRepoTreeGenerator` depth cap logic: the adapter renders one omission marker for a directory at or beyond a positive limit. Verified by reading `src/teddy_executor/adapters/outbound/local_repo_tree_generator.py`.
- Missing config-key declaration: `context.max_tree_depth` is declared in the bundled `config.yaml` with default `4`, appears in `ContextConfig`, and carries a schema bound of `minimum=0`.
- Missing composition-root wiring: `src/teddy_executor/registries/infrastructure.py` passes `get_setting("context.max_tree_depth", 0)` to the generator factory.
- Config resolution: the first MRE read the configured value `1` through the resolved `IConfigService`, so the adapter layer and the typed schema return the user value.

## Diagnostic Analysis
### Causal Model
Verified observations only:
- The adapter caps recursion when `_max_depth > 0` and renders the omission marker at the limit.
- The adapter treats `_max_depth == 0` as unlimited depth.
- The composition root registers a transient factory that supplies the configured depth.
- `__main__._ensure_project_initialized` re-registers `IRepoTreeGenerator` with `root_dir` only, because its `is_override` check treats a transient factory registration as not an override.
- The later registration wins, so the resolved generator carries `_max_depth == 0`.
- The schema rejects a negative depth with `ConfigurationError` at `minimum=0`, so a negative value cannot reach the adapter through typed-config validation.

### Discrepancies
- [x] With `context.max_tree_depth: 1`, the rendered tree should truncate at depth 1 and show an omission marker, but the full tree renders. (Resolved: the project-anchoring re-registration overrides the depth-aware factory with a bare adapter that defaults to unlimited depth.)
- [x] There is no supported value that omits the project tree entirely, because `0` means unlimited and negative values are rejected. (Resolved: the user accepted a new contract because no released version depends on the old meaning and v0.2 may carry the break. `0` will mean zero depth and render one omission notice. Every non-negative depth is a literal cap, so a user who wants the whole tree supplies a number above the real nesting depth. No code constant reserves a specific large value as unlimited. See the Accepted Contract Change under Solution.)
- [x] `read.max_lines` never reaches the anchored filesystem adapter, so agent READ actions silently use the default cap of `1000`. (Resolved: the bare registration predates the configuration wiring, so the loss was accidental. Restoring the cap requires decoupling session-internal reads first, because they share the capped `read_file`. Deferred to a separate slice.)

### Investigation History
1. Read the adapter, the config schema, the bundled config, the existing depth tests, and the component design. Observed that the adapter cap works for positive depth and that the setting is wired at the composition root. Concluded that the defect lies upstream of the adapter.
2. Ran the first MRE through the real container and the real anchoring step. Observed configured depth `1`, resolved generator depth `0`, and a full tree with no omission marker. Concluded that the resolved value is `0`, not the user's `1`.
3. Inspected every `IRepoTreeGenerator` registration. Found the depth-aware factory in `registries/infrastructure.py` and a competing bare registration in `__main__.py`. Concluded that a duplicate registration discards the configured depth.
4. Ran the second MRE before and after the anchoring step. The probe isolated the override to `_ensure_project_initialized` and confirmed that the configured depth survives the factory but not the anchoring step.
5. Built a sandbox replica of the anchoring step that forwards `root_dir` together with the configured tree depth and read cap through lazy factories, then drove the real container through it. Observed depth `1`, read cap `7`, a present depth-limit marker, and an absent `folder2`, so the replica fix is empirically proven without touching `src/`.
6. Audited the blast radius. The anchoring function has five production callers (`start`, `init`, `context`, `resume`, `execute`) and is monkeypatched by several acceptance tests. The fix stays inside `__main__._ensure_project_initialized`, so no shared port or signature changes and no migration path is required.
7. Traced the `read.max_lines` loss. The bare filesystem registration entered in commit `9ea7ca14`, before the configuration wiring existed, so the missing argument was an accident rather than a deliberate protection. Every session-internal read of `plan.md`, `report.md`, and prompt files uses the capped `read_file`, while context assembly uses the uncapped `read_files_in_vault`. Restoring the configured cap in the anchoring step would therefore cap session turn contents at the user value.
8. Ran a probe against a filesystem adapter with a cap of 7 lines. `read_file` returned 7 lines of a 20-line plan, and `read_raw_file` returned all 20 lines, which proves the two paths diverge and confirms the session-read risk.
9. Inventoried every production `get_setting` call with an AST walk, then compared each literal key and fallback against the declared schema. Observed two undeclared keys, several fallbacks that diverge from schema defaults, inconsistent `0` sentinel meanings, and missing range bounds on most numeric keys.
10. Probed the legacy `yolo_guardrails` fallback with a config that sets `yolo_guardrails.max_turns: 3`. The renamed `guardrails.max_turns` read returned the schema default `150`, the `_UNSET` sentinel did not survive, and the legacy value stayed ignored, which proves the migration fallback is dead under the typed schema.
11. Enumerated every construction site, every `max_tree_depth` encoding, and every legacy config marker. Observed that the `execution.*` key migration in `YamlConfigAdapter._migrate_legacy_execution_keys` is live and covered by `test_yaml_config_adapter_legacy_migration.py`, while the `yolo_guardrails.*` runtime fallback is dead. Observed no production `9999` or other large sentinel. Only the adapter guard, the constructor default, one spec, two component designs, the bundled comment, and five tests encode the old `0 = unlimited` meaning.

## Solution
### Root Cause
The project-anchoring step re-registers `IFileSystemManager`, `IRepoTreeGenerator`, and `IConfigService` so the adapters resolve against the detected project root. Its `is_override` check treats the composition root's transient factories as not an override, so the re-registration always runs, and each re-registration supplies `root_dir` only. The concrete-adapter registrations therefore fall back to the constructor defaults. For the tree generator the default `max_depth` of `0` means unlimited, so `context.max_tree_depth` is silently discarded. For the filesystem adapter the default `max_read_lines` of `1000` replaces the configured `read.max_lines`.

### Fix Scope
The tree-depth defect is self-contained and was proven in the sandbox replica. The fix redirects the anchored tree-generator registration to a lazy factory that forwards `root_dir` and `context.max_tree_depth`.

The `read.max_lines` loss is a separate defect. Git history shows the bare filesystem registration entered before the configuration wiring, so the loss was accidental. However, every session-internal read of `plan.md`, `report.md`, and prompt files flows through the capped `read_file`, and only context assembly uses the uncapped `read_files_in_vault`. A probe confirmed that a cap of 7 lines truncates a 20-line session plan. Restoring `read.max_lines` in the anchoring step would therefore cap session turn contents at the user value. Safe restoration requires routing session-internal reads through an uncapped path first, which touches several session services and exceeds the small-fix bound. That work belongs in a separate slice.

### Affected Components
- `src/teddy_executor/__main__.py` (`_ensure_project_initialized`): replace the anchored `IRepoTreeGenerator` concrete registration with a lazy factory that forwards `root_dir` and `context.max_tree_depth`. Leave the `IFileSystemManager` registration unchanged so the session read cap stays at the constructor default until the decoupling slice lands.
- `src/teddy_executor/registries/infrastructure.py`: unchanged. The composition-root factory already supplies the configured depth.
- Upstream callers: `start`, `init`, `context`, `resume`, and `execute` in `src/teddy_executor/__main__.py`. None change.
- Downstream adapters: `LocalRepoTreeGenerator`. Its contract stays the same, so no migration is required.
- Regression test: a new test that runs the anchoring step and asserts the resolved tree depth equals the configured value and that the rendered tree shows the depth-limit marker.
- Deferred: `read.max_lines` restoration, blocked on decoupling session-internal reads from the agent READ cap.

### Accepted Contract Change: Zero Depth Is a Literal Cap
The user accepted a new contract because no released version depends on the old meaning and v0.2 may carry the break. `context.max_tree_depth: 0` now means zero depth and renders a single omission notice, so the tree collapses to one auditable line. Every non-negative depth is a literal cap. A user who wants the whole tree supplies a number above the real nesting depth, and no code constant reserves a specific large value such as `9999` as an unlimited sentinel. The schema keeps `minimum=0`, so zero stays valid and a negative value stays rejected.

This contract invalidates the adapter `_max_depth > 0` guard, which treats zero as unlimited. The guard must be removed so `depth >= self._max_depth` always applies. The zero constructor default would then suppress every tree for any caller that omits the argument, so the default must become the schema default `4` and the argument stays optional. A default of `4` keeps the test harness and every existing caller working while an omitted argument still renders a real tree. The bundled config comment, the spec `## Project Structure` section, the two component-design depth contracts, and the config-service key table must all describe the new meaning. Rendering one explicit notice inside `## Project Structure` rather than deleting the heading keeps the payload contract intact and makes the omission auditable.

### Typed-Config Inconsistency Audit
Every production `get_setting` call was inventoried with its literal key and fallback. Each finding below is verified against the schema, the call site, or a probe.

- [x] Undeclared keys are read. `diff_flags` and `research.max_scraper_retries` are read but absent from the schema, so they receive no typed default, no coercion, and no range check. `diff_flags` is guarded with an `isinstance` check and `max_scraper_retries` is coerced with `int`, so neither crashes, but both bypass the typed boundary. `llm.registry_cache_ttl_days` is an `llm.*` passthrough and needs no schema entry.
- [x] Fallbacks diverge from schema defaults. `context.max_tree_depth` falls back to `0` while the schema default is `4`. Because the key is declared, `get_setting` always returns the typed value, so the `0` fallback is dead code that nonetheless documents the old unlimited meaning. `auto_pruning.max_turns_retention` falls back to `0` while the schema default is `10`.
- [x] The `0` sentinel meaning is inconsistent across keys. `truncate_lines` treats `max_lines <= 0` as unlimited. `LocalRepoTreeGenerator` treats `0` as unlimited. The two `auto_pruning` limits treat `<= 0` as off. The two `guardrails` limits fall through `... or default`, so `0` reverts to the default. `read.max_lines` and `execute.max_output_lines` declare `minimum=1`, so `0` is rejected. There is no single convention.
- [x] Most numeric bounds are missing. Only five keys carry bounds: `execute.max_output_lines`, `edit.similarity_threshold`, `read.max_lines`, `context.max_tree_depth`, and `research.max_results`. `execute.default_timeout_seconds`, `guardrails.max_turns`, `guardrails.max_session_cost`, and the `auto_pruning` integers accept any value, so a negative timeout or a negative cost is accepted and makes the guard halt immediately.
- [x] The legacy `yolo_guardrails` fallback is dead. `guardrails.max_turns` is a declared key, so `get_setting` returns the schema default `150` and the sentinel never survives. The probe confirmed the renamed read returns `150` while `yolo_guardrails.max_turns: 3` stays ignored. Because no released version depends on the fallback, the dead branch can be removed.
- [x] Legacy config support is not fully dead. The `execution.*` key migration in `YamlConfigAdapter._migrate_legacy_execution_keys` still copies tuned legacy values to their canonical `execute.*` and `edit.*` groups, and `test_yaml_config_adapter_legacy_migration.py` pins that behaviour with six tests. Only the `yolo_guardrails.*` runtime fallback is unreachable. Because no released version depends on either path, v0.2 may drop both, but the `execution.*` migration is a deliberate, tested feature rather than dead code.
- [x] The user decided to remove all legacy config support. The user will communicate the breaking change to their users directly, so no deprecation window is needed. Both paths go: the live `execution.*` key migration and the dead `yolo_guardrails.*` runtime fallback, together with their tests and the design-doc sentences that advertise them. A v0.1 config now resolves the shipped defaults instead of its tuned legacy values.

### Developer Handoff Scope
The combined work exceeds the small-fix bound, so it goes to the Developer as one slice that delivers the tree-depth fix, the accepted zero-depth contract, and the removal of all legacy config support. The anchoring fix stays proven by the sandbox replica at [replica_main.py](/spikes/debug/project-tree-depth-omission/replica_main.py), and the verification MRE at [03-fixed-anchoring-mre.py](/spikes/debug/project-tree-depth-omission/03-fixed-anchoring-mre.py). The failing baseline reproductions are [01-configured-tree-depth-mre.py](/spikes/debug/project-tree-depth-omission/01-configured-tree-depth-mre.py) and [02-registration-override-mre.py](/spikes/debug/project-tree-depth-omission/02-registration-override-mre.py). The supporting probes are [04-session-read-cap-mre.py](/spikes/debug/project-tree-depth-omission/04-session-read-cap-mre.py), which backs the deferred read cap, and [05-legacy-guardrails-fallback-mre.py](/spikes/debug/project-tree-depth-omission/05-legacy-guardrails-fallback-mre.py), which backs the unreachable legacy fallback.

- `src/teddy_executor/__main__.py` (`_ensure_project_initialized`): register the anchored tree generator through a lazy factory that forwards `root_dir` and `context.max_tree_depth`. Leave the `IFileSystemManager` registration unchanged so session turn contents stay uncapped until the read-path decoupling slice lands.
- `src/teddy_executor/adapters/outbound/local_repo_tree_generator.py`: remove the `_max_depth > 0` guard so zero means zero depth, and set the constructor default to the schema default `4` so an omitted argument no longer suppresses the tree.
- `src/teddy_executor/registries/infrastructure.py`: replace the `0` fallback with the schema default `4`, because a resolution miss must not silently remove the tree.
- `src/teddy_executor/core/domain/models/config_schema.py`: keep `minimum=0` for `context.max_tree_depth`. Optionally add bounds to the unbounded numeric keys and declare or drop the two undeclared keys.
- `src/teddy_executor/resources/config/config.yaml`: change the `context.max_tree_depth` comment to `0 = omit tree; raise the number to show more levels`.
- `docs/project/specs/context-payload-format.md`, `docs/architecture/adapters/outbound/local_repo_tree_generator.md`, `docs/architecture/core/ports/outbound/repo_tree_generator.md`, `docs/architecture/core/ports/outbound/config_service.md`: describe zero depth as one omission notice and remove the `0 = unlimited` wording.
- Regression test: run the anchoring step against a workspace with a non-default depth, then assert the resolved depth equals the configured value, the rendered tree shows the depth-limit marker, and a folder beyond the limit is absent. Add a second test for depth `0` that asserts a single omission notice.
- Tests to update: `tests/suites/unit/adapters/outbound/test_local_repo_tree_generator_depth.py` asserts a default of `0`, which is now wrong, so it must assert the schema default `4`. `tests/suites/integration/adapters/outbound/test_local_repo_tree_generator.py` asserts no marker at depth `0`, which must become a single omission notice. `tests/suites/integration/core/services/test_container_wiring.py` keeps its configured-depth assertion.
- Legacy removal (production): delete `_LEGACY_EXECUTION_KEY_GROUPS` and `_migrate_legacy_execution_keys` from `src/teddy_executor/adapters/outbound/yaml_config_adapter.py`; remove the `yolo_guardrails.*` fallback and the `_UNSET` sentinel from `ProductionSessionLoopGuard._read_config` in `src/teddy_executor/core/services/session_loop_guard.py`.
- Legacy removal (tests): delete `tests/suites/unit/adapters/outbound/test_yaml_config_adapter_legacy_migration.py` and `tests/suites/integration/core/services/test_guardrails_namespace_migration.py`; rewrite the legacy case at `tests/suites/unit/core/services/test_session_loop_guard_configuration.py` to assert that a `yolo_guardrails.*` key is ignored; drop or rewrite the `execution.*` assertions in `tests/suites/unit/adapters/outbound/test_yaml_config_adapter.py` and `test_yaml_config_adapter_layering.py`.
- Legacy removal (docs): remove the legacy sentence from `docs/architecture/adapters/outbound/yaml_config_adapter.md`, and audit `docs/architecture/core/ports/outbound/session_loop_guard.md` and `docs/architecture/core/services/session_loop_guard.md` for the same wording.
- Deferred: `read.max_lines` restoration, blocked on decoupling session-internal reads from the capped `read_file`.
