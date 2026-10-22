# Slice: Project Tree Depth Anchoring and Zero-Depth Contract
- **Status:** In Progress
- **Milestone:** N/A (ad-hoc)
- **Depends On:** [00-05-workspace-config-improvements.md](/docs/project/slices/00-05-workspace-config-improvements.md), [00-06-typed-config-schema.md](/docs/project/slices/00-06-typed-config-schema.md)
- **Specs:** [context-payload-format.md](/docs/project/specs/context-payload-format.md)
- **Prototype:** [replica_main.py](/spikes/debug/project-tree-depth-omission/replica_main.py), [03-fixed-anchoring-mre.py](/spikes/debug/project-tree-depth-omission/03-fixed-anchoring-mre.py)
- **Component Docs:** [config_service.md](/docs/architecture/core/ports/outbound/config_service.md), [repo_tree_generator.md](/docs/architecture/core/ports/outbound/repo_tree_generator.md), [local_repo_tree_generator.md](/docs/architecture/adapters/outbound/local_repo_tree_generator.md), [yaml_config_adapter.md](/docs/architecture/adapters/outbound/yaml_config_adapter.md), [session_loop_guard.md](/docs/architecture/core/ports/outbound/session_loop_guard.md)
- **Scope Slug:** `tree-depth-anchoring`

## Goal
Make `context.max_tree_depth` reach the tree generator through every CLI command and redefine depth zero as a literal cap that renders one auditable omission notice. Remove all legacy configuration support.

## Context
- `_ensure_project_initialized` (`src/teddy_executor/__main__.py`) re-registers `IRepoTreeGenerator` with `root_dir` only, so the constructor default overrides the configured depth.
- The composition-root factory (`src/teddy_executor/registries/infrastructure.py`) already supplies `context.max_tree_depth`, but the anchoring re-registration wins.
- `LocalRepoTreeGenerator` treats `_max_depth == 0` as unlimited and defaults to `0`, so an omitted argument suppresses the tree.
- `context.max_tree_depth` is a declared key with `minimum=0` and default `4`, so the typed schema already rejects a negative value.
- `YamlConfigAdapter._migrate_legacy_execution_keys` is live and copies `execution.*` values to canonical groups.
- `ProductionSessionLoopGuard._read_config` still consults a dead `yolo_guardrails.*` fallback through an `_UNSET` sentinel.
- The shared harness `with_real_tree_generator` passes `max_depth=0` explicitly, so a literal-cap contract collapses any fixture that omits an explicit depth.
- The session read cap stays untouched: the `IFileSystemManager` anchoring registration remains bare until the read-path decoupling slice lands.

## Scenarios

> As a developer, I want a configured tree depth to truncate the context payload so that a deep repository stays auditable and small.

```gherkin
Given a workspace whose .teddy/config.yaml sets context.max_tree_depth to 1
When project anchoring runs for a CLI command
Then the resolved tree generator uses depth 1
And the rendered project tree shows an omission notice
And a folder at depth 2 is absent
```

> As a developer, I want depth zero to render one notice so that the tree section stays present but collapses.

```gherkin
Given a workspace whose .teddy/config.yaml sets context.max_tree_depth to 0
When the project tree renders
Then exactly one omission notice for the project root appears
And no child entry is listed
```

> As a user upgrading from v0.1, I want legacy keys to be ignored so that the shipped defaults apply.

```gherkin
Given a v0.1 config that sets execution.max_output_lines to 999
When the config resolves execute.max_output_lines
Then the bundled default 100 applies
```

## Edge Cases
- **Depth zero renders one notice**: If `max_depth` is 0, then the root renders exactly one omission notice, because zero is a literal cap.
- **Omitted constructor depth keeps a real tree**: If a caller omits `max_depth`, then the adapter defaults to 4, because an accidental omission must not suppress the tree.
- **Negative depth rejected**: If a user sets a negative `context.max_tree_depth`, then the typed schema raises `ConfigurationError`, because `minimum=0` stays.
- **Empty directory at the limit**: If a directory at the limit has no visible children, then no marker renders, because an empty directory is not an omission.
- **Unreadable directory at the limit**: If a directory at the limit is unreadable, then the unreadable marker renders, because the two states must stay distinguishable.
- **Legacy guardrails key ignored**: If config carries only `yolo_guardrails.max_turns`, then the guard uses `guardrails.max_turns` default, because the fallback is gone.
- **Legacy execution key ignored**: If config carries `execution.max_output_lines`, then the canonical reader resolves the bundled default, because the migration is gone.

## Key Unknowns
None. The case file resolves every unknown and provides a proven replica and verification MRE.

## Impact
1. `[EXPAND]` `__main__._ensure_project_initialized` — register the anchored tree generator through a lazy factory that forwards `root_dir` and `context.max_tree_depth`.
2. `[EXPAND]` `LocalRepoTreeGenerator` — treat every non-negative depth as a literal cap and default the argument to 4.
3. `[MIGRATE]` Test harness `with_real_tree_generator` — raise the default depth to 4 so implicit-default fixtures keep rendering real trees.
4. `[MIGRATE]` Config and guard test modules — move `execution.*` assertions to canonical keys and assert that legacy keys are ignored.
5. `[CONTRACT]` Legacy configuration removal — delete `_LEGACY_EXECUTION_KEY_GROUPS`, `_migrate_legacy_execution_keys`, the `yolo_guardrails` fallback, and the `_UNSET` sentinel.
6. `[CONTRACT]` Documentation — describe depth zero as one omission notice and remove the legacy sentences.

## Deliverables
- [x] **Wiring** — In `_ensure_project_initialized`, register `IRepoTreeGenerator` through a lazy factory that forwards `root_dir` and `context.max_tree_depth`. Add an integration regression test that runs anchoring on a workspace with depth 1 and asserts the resolved depth, the omission marker, and the absence of a deeper folder.
- [ ] **Harness** — Raise `with_real_tree_generator` in `tests/harness/setup/real_adapter_mixin.py` to default `max_depth=4`, because an implicit default must keep rendering a real tree under the literal-cap contract.
- [ ] **Logic** — Remove the `_max_depth > 0` guard and set the constructor default to 4 in `LocalRepoTreeGenerator`. Change the `infrastructure.py` fallback to 4. Update the bundled comment. Assert the new default in the depth unit test, rewrite the zero-depth integration test to expect one notice, and add a zero-depth anchoring regression. Update the container-wiring default literal.
- [ ] **Cleanup** — Remove all legacy configuration support: delete the yaml migration symbols and call, remove the guard `_UNSET` sentinel and `yolo_guardrails` fallback, delete the two legacy test modules, rewrite the guard legacy case to assert the key is ignored, migrate `execution.*` assertions to canonical keys, and add a test that a legacy `execution.*` key resolves the bundled default.
- [ ] **Cleanup** — Align the documentation: describe zero depth in the context payload spec, the tree-generator port and adapter contracts, and the config-service key table, and remove the legacy sentences from the yaml adapter and session-loop-guard designs.

## Implementation Notes
- **Wiring:** The anchored `IRepoTreeGenerator` registration now uses a transient lazy factory that forwards `root_dir` and `context.max_tree_depth` with a fallback of `4`. The factory resolves `IConfigService` at resolve time because the tree registration executes before the config registration in source order.
- **Wiring:** The `IFileSystemManager` anchoring registration stays bare, so session turn contents stay uncapped until the read-path decoupling slice restores `read.max_lines`.
- **Wiring:** The primary regression lives at the composition seam in `test_project_anchoring.py`, because the acceptance harness registers `IRepoTreeGenerator` as a mock that returns an empty tree and cannot observe the depth marker. The harness registers the config and tree ports as instance overrides, so `_ensure_project_initialized` skips the anchored re-registration in acceptance paths and those tests stay green.
- **Wiring:** The full suite passes with 2118 tests and 5 skips.

## Verification
1. **Tree depth cap:**
   Create a scratch repository with `folder1/folder2/folder3/file.txt`. Set `context.max_tree_depth: 1` in `.teddy/config.yaml`. Run `teddy context --no-copy`. Confirm the `## Project Structure` section contains `[... directory not expanded (depth limit 1):` and omits `folder2`.
2. **Zero-depth notice:**
   Set `context.max_tree_depth: 0`. Run `teddy context --no-copy`. Confirm the `## Project Structure` section contains one `depth limit 0` notice and lists no child entry.
3. **Legacy execution key ignored:**
   Add `execution:\n  max_output_lines: 999` to `.teddy/config.yaml`. Run a focused config read or `teddy context --no-copy`. Confirm the resolved `execute.max_output_lines` value is the shipped default `100`.
4. **Legacy guardrails key ignored:**
   Add `yolo_guardrails:\n  max_turns: 3` to `.teddy/config.yaml`. Run `teddy start -y -m "noop"`. Confirm the run is not bounded by three turns and the shipped `guardrails.max_turns` value applies.
