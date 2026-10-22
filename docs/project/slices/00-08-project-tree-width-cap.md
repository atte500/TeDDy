# Slice: Compact Tree Notices and Per-Directory Width Cap
- **Status:** In Progress
- **Milestone:** N/A (ad-hoc)
- **Depends On:** [00-07-project-tree-depth-anchoring.md](/docs/project/slices/00-07-project-tree-depth-anchoring.md)
- **Specs:** [context-payload-format.md](/docs/project/specs/context-payload-format.md)
- **Prototype:** [07-bare-marker-and-width-cap.py](/spikes/context-tree-token-budget/07-bare-marker-and-width-cap.py), [08-final-section-render.py](/spikes/context-tree-token-budget/08-final-section-render.py)
- **Component Docs:** [repo_tree_generator.md](/docs/architecture/core/ports/outbound/repo_tree_generator.md), [local_repo_tree_generator.md](/docs/architecture/adapters/outbound/local_repo_tree_generator.md), [context_service.md](/docs/architecture/core/services/context_service.md), [config_service.md](/docs/architecture/core/ports/outbound/config_service.md)
- **Scope Slug:** `tree-width-cap`

## Goal
Cut the context tree payload on wide repositories and make every withheld directory cost one short notice, while naming both limits once per section.

## Context
- `LocalRepoTreeGenerator._depth_limit_marker` renders `[... directory not expanded (depth limit N): X folders, Y files]`, which costs 19 tokens against 8 for `[X folders, Y files]`.
- `UNREADABLE_MARKER` renders `[... directory not expanded (unreadable): 0 folders, 0 files]`, which states a count for a directory that was never scanned.
- `LocalRepoTreeGenerator._collect_directory` scans each directory once and recurses while iterating. `_depth_limit_marker` rescans for its counts, so one scan can serve both limits.
- `ContextService._format_content` owns the `## Project Structure` heading and its fence, so only the service can place a line between them.
- `IRepoTreeGenerator` declares `generate_tree` alone, so the service cannot read either limit from the port today.
- `ContextConfig` declares `max_tree_depth: int = 4`, bounded by the `_FieldSpec("context.max_tree_depth", "context", "max_tree_depth", int, minimum=0)` entry in `_SCHEMA_FIELDS`. This slice lowers the default to 3 and adds `max_tree_width: int = 20` with a spec entry carrying `minimum=1`.
- The bundled config carries one inline comment after each value, so the depth and width lines each need a comment, and the width comment must name the root exemption.
- Both `__main__._ensure_project_initialized` and `registries/infrastructure.py` forward only `context.max_tree_depth`, and both need to forward `context.max_tree_width`.
- `__main__` also hardcodes a depth fallback of 4, so the fallback must follow the new default.
- The harness `with_real_tree_generator` binds its default to `DEFAULT_APP_CONFIG.context.max_tree_depth`, so the depth change reaches every fixture that omits an explicit depth.
- Measured here: the raw depth-4 tree costs 2500 tokens and the packaged depth-3 tree costs 841 tokens, so depth 3 is the dominant saving.
- Measured here: a width cap of 20 never fires at depth 3 on this repository, because the widest expanded folder holds 10 entries. The cap is a safety net for wide or shallow repositories, where the depth limit cannot collapse one flat folder.
- Measured here: width drives the cost, because a flat folder of 200 files costs 1007 tokens at depth 2.
- Measured here: depth 3 hides the slice, spec, milestone, release, and debug filename lists, while folder names and every template stay visible and one `git ls-files` recovers the rest.
- Only `README.md`, `docs/project/PROJECT.md`, and `docs/architecture/ARCHITECTURE.md` reach the payload verbatim, so the tree remains the only cheap index of the other strategic documents.

## Scenarios

> As an agent, I want one short notice per withheld directory so that a capped tree costs few tokens.

```gherkin
Given a directory at the depth limit holds 12 visible files
When the project tree renders at depth 3
Then that directory renders [0 folders, 12 files]
And no section for its children appears
```

> As a maintainer, I want one wide folder collapsed so that it cannot dominate the payload.

```gherkin
Given a directory inside the depth limit holds 25 files
When the project tree renders with a width cap of 20
Then that directory renders [0 folders, 25 files]
And its sibling folders list their entries normally
```

> As an agent, I want the section to state both limits once so that the bare notices stay meaningful.

```gherkin
Given a tree rendered at depth 3 with a width cap of 20
When the context payload assembles the Project Structure section
Then an italic line below the heading names both limits
And the fenced tree follows that line
```

## Edge Cases
- **Unreadable directory**: If a directory cannot be scanned, then it renders `[unreadable]` without counts, because a failed scan yields no count.
- **Empty directory**: If a directory holds no visible child, then it renders no section, because an empty directory is not an omission.
- **Exact cap**: If a directory holds exactly the cap count, then it expands, because the cap is a maximum.
- **Root listing**: If the project root exceeds the width cap, then it still lists its entries, because the root is the only place where a top-level file is named. The depth limit applies first, so a depth of zero still withholds the root.
- **Withheld directory drops descendants**: If a directory is withheld, then its child sections are omitted, because names without their parent folder cannot be mapped.
- **Depth zero**: If the depth is zero, then the root renders one `[X folders, Y files]` notice, because zero is a literal cap.
- **Counts after ignore rules**: If an entry matches an ignore file, then it is not counted, because the notice must match the visible listing.
- **Mock without limits**: If a mock tree generator omits a limit, then the subtitle renders a mock repr, so the harness must set integers.

## Key Unknowns
None. The renders, the token ladder, and the four wiring sites are measured.

## Impact
1. `[EXPAND]` `IRepoTreeGenerator` — add `max_depth` and `max_tree_width` read-only properties.
2. `[EXPAND]` `ContextConfig` — lower `max_tree_depth` to 3, add `max_tree_width: int = 20` with a `_FieldSpec` entry carrying `minimum=1`, and update both bundled config values and comments.
3. `[EXPAND]` `LocalRepoTreeGenerator` — accept the width cap and render the compact notices from one scan.
4. `[MIGRATE]` Both tree registrations — forward `context.max_tree_width`, and align the `__main__` depth fallback with the new default.
5. `[MIGRATE]` `ContextService._format_content` — render the italic subtitle from the port limits.
6. `[MIGRATE]` The deep-tree performance fixture — set an explicit depth so it keeps rendering a three-level chain under the default of 3.
7. `[CONTRACT]` The two long notice strings — remove them once the tests and contracts describe the compact ones.

## Deliverables
- [x] **Contract** — Declare `max_depth` and `max_tree_width` read-only properties on `IRepoTreeGenerator` and implement them on `LocalRepoTreeGenerator`. Declare `max_tree_width: int = 20` in `ContextConfig` with the `_FieldSpec("context.max_tree_width", "context", "max_tree_width", int, minimum=1)` entry, and add the bundled width value with the comment `# Max entries listed per directory (the root lists all).` Extend the adapter constructor with the width cap. Keep `max_tree_depth` at 4 so this additive step stays green.
- [x] **Harness** — Set integer limits on every shared mock tree generator from the schema defaults, so the subtitle never renders a mock repr.
- [x] **Wiring** — Forward `context.max_tree_width` in `__main__._ensure_project_initialized` and in `registries/infrastructure.py`. Add an integration regression at the composition seam that resolves the generator on a workspace with a configured width and asserts the resolved limit.
- [ ] **Logic** — Compact the depth notice to `[X folders, Y files]`, render `[unreadable]` for a failed scan, and withhold any non-root directory that holds more visible entries than the width cap. Keep the root listing uncapped and omit the sections of a withheld directory. Rewrite the notice assertions across the four affected test modules in the same commit, and add unit coverage for the width cap, the exact-cap boundary, and the root exemption.
- [ ] **Logic** — Render the italic subtitle between the heading and the fence in the form `*Tree capped at depth {depth} and width {width}: truncated directories show counts only.*`, substituting both limits from the port properties.
- [ ] **Migration** — Lower `max_tree_depth` to 3, align the `__main__` depth fallback literal with 3, and set an explicit `max_depth` in `test_tree_integrity_with_deep_unignored_file` in one commit. Update every remaining literal depth assertion that the new default breaks.
- [ ] **Cleanup** — Update the tree-generator port contract, the adapter contract, the context-service contract, and the config-service key table for the compact notices, the default depth, the width cap, and the subtitle.

## Implementation Notes
- **Partition:** The depth default, the `__main__` fallback literal, and the deep-chain fixture are atomic companions. The schema default stays at 4 until the Migration deliverable lowers it with both companions in one commit, so every earlier commit stays green.
- **Partition:** The compact notice text and the four test-module assertion rewrites form one atomic Logic commit, because a notice change alone fails the existing long-form assertions.
- **Partition:** The Contract deliverable adds the width cap additively and leaves depth at 4, so the port properties, the width field, the adapter width parameter, and the bundled width line carry no ripple.
- **Contract:** `IRepoTreeGenerator` now declares `max_depth` and `max_tree_width` as read-only properties, and `LocalRepoTreeGenerator` implements them over private fields, so the context service can state both limits once per section.
- **Contract:** The adapter constructor gained `max_tree_width`, defaulted to the schema default, and asserts a positive cap. `ContextConfig` gained `max_tree_width: int = 20` with a `_FieldSpec` entry carrying `minimum=1`, so zero is rejected while the depth default stays at 4.
- **Contract:** The bundled config gained `max_tree_width: 20`, aligned to the existing inline-comment column, so the shipped value is visible beside the depth value.
- **Contract:** The bundled `config.yaml` loader moved to `tests/harness/setup/bundled_config.py`, so the notification-toggle and tree-limit contract tests read one resource source of truth.
- **Contract:** The full suite passes with 2127 tests and 5 skips.
- **Harness:** `apply_tree_generator_defaults` in `tests/harness/setup/mocking.py` is the single source of the tree-mock defaults. It sets `generate_tree` to an empty string and both limits to the schema defaults, so the Migration commit that lowers the depth default to 3 moves the harness automatically with no second harness edit.
- **Harness:** `TestEnvironment._register_io_mocks` and the shared `mock_tree_gen` fixture both call the helper, so every shared tree mock states both integers and the subtitle never renders a mock repr.
- **Harness:** The Red run failed only the two new limit assertions, and each printed a child mock unequal to the schema integer. That confirmed the spec-set mock auto-creates a child mock for an unset limit, so a direct integer assignment is the correct fix.
- **Harness:** The full suite passes with 2129 tests and 5 skips.
- **Wiring:** Both tree factories now forward `context.max_tree_width` beside the existing depth. `__main__._ensure_project_initialized` uses the literal fallback 20, and `registries/infrastructure.py` uses `DEFAULT_APP_CONFIG.context.max_tree_width`, so each file mirrors the fallback style it already used for depth.
- **Wiring:** The width anchoring regression sits beside the depth regressions in `test_project_anchoring.py`. The workspace helper gained an optional width, so both depth tests keep their current signatures.
- **Wiring:** The Red run failed only the new width test with 20 against 5, and both depth tests passed. That confirmed the anchored factory forwarded depth alone, so one width argument at each factory is the whole fix.
- **Wiring:** The full suite passes with 2130 tests and 5 skips.

## Verification
1. **Compact notices and subtitle:**
   Run `teddy context --no-copy`.
   Verify the heading is followed by the italic line `*Tree capped at depth 3 and width 20: truncated directories show counts only.*`.
   Verify `./tests/suites/acceptance:` shows `[0 folders, 82 files]` and no child section.
2. **Shipped limits:**
   Inspect `src/teddy_executor/resources/config/config.yaml`.
   Verify `context.max_tree_depth` is `3` and `context.max_tree_width` is `20`, each with an inline comment.
3. **Width cap override:**
   Set `context.max_tree_width: 5` in `.teddy/config.yaml`.
   Run `teddy context --no-copy`.
   Verify every non-root directory above five visible entries shows a notice and no child section.
4. **Root exemption:**
   Set `context.max_tree_width: 1` in `.teddy/config.yaml`.
   Run `teddy context --no-copy`.
   Verify the root listing still names `pyproject.toml` and `Makefile`.
5. **Unreadable directory:**
   Create a directory with mode 000 inside the workspace.
   Run `teddy context --no-copy`.
   Verify the section shows `[unreadable]` for that directory and no fabricated counts.
