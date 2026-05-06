# Bug: Performance Regression in `teddy context`

- **Status:** Unresolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** [00-04-context-management-ui](../slices/00-04-context-management-ui.md)
- **Specs:** [context-management-ui.md](../specs/context-management-ui.md)

## Symptoms
`teddy context` execution time has increased significantly.

## Context & Scope
### Regressing Delta
Commit `02ec83850de9e77ef7ae1a87dbf4755c11087190`: "feat(core): update ContextService to collect file metadata into ContextItem list". This commit introduced synchronous token counting for every file in the context.

### Environmental Triggers
Large repositories with many files. The performance hit scales linearly with the number of files in the context.

### Ruled Out
- `git status -s`: While it's an external call, it's typically sub-100ms for this repo.
- `RepoTreeGenerator`: Proven performant in previous milestones.

## Diagnostic Analysis
### Causal Model
1. `ContextService.get_context()` is called.
2. It gathers system info, git status, and the file tree.
3. It resolves all file paths in the context (defaulting to all tracked files).
4. It reads all file contents into memory.
5. It iterates through each file and calls `ILlmClient.get_text_token_count()`.
6. `LiteLLMAdapter.get_text_token_count()` performs a lazy import of `litellm`.
7. `litellm.token_counter()` is invoked, which has a non-zero overhead per call.
8. `YamlConfigAdapter.get_setting()` is called twice per file (via `_resolve_model` and potentially other logic). If this adapter reads from disk on every call, it adds significant O(N) latency.
9. The cumulative overhead of N synchronous calls and disk I/O causes a noticeable delay in the CLI.
10. `repo_tree_generator.generate_tree()` or `get_context_paths()` may be scanning excessively large directories (like `.teddy/sessions`) or performing unoptimized filesystem crawls.

### Discrepancies
- `litellm.token_counter` overhead (0.35ms) vs `teddy context` actual time (~10ms/file). Conflict: Resolved. The overhead is accumulated across 481 files in a synchronous loop, with each call adding ~6ms of adapter logic (log silencing, etc.), leading to a ~3s delay.

### Investigation History
1. Hypothesis: Synchronous token counting in `ContextService` for every file causes the slowdown.
2. Observation: `profile_context_service.py` shows ~1.2s for 9 items, but `teddy context` (processing more files) takes ~2s. This suggests non-token-counting operations (Tree Gen, FS) are also expensive.
3. Observation: `litellm.token_counter` raw overhead is low (0.35ms), but `LiteLLMAdapter` adds ~6ms per call.
4. Hypothesis: The O(N) synchronous token counting loop in `ContextService.get_context` for the full repository (481 files) is the root cause of the 2-3s delay.

## Solution
### Implemented Fixes
- Optimized `LiteLLMAdapter.get_text_token_count` to use `tiktoken` directly, bypassing the high per-call overhead of `litellm.token_counter`.
- Implemented double-checked locking and caching for `tiktoken` encoding objects in `LiteLLMAdapter`.
- Optimized `ContextService.get_context` to perform token counting only once per unique file path and used `ThreadPoolExecutor.map` for efficient parallel execution.
- Introduced `include_tokens` flag in `ContextService.get_context` to allow bypassing tokenization when not needed.
- Disabled token counting in the `teddy context` CLI command (via `handle_context_gathering`), restoring sub-200ms performance for the common clipboard workflow.

### Prevention
TBD
