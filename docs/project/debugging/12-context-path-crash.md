# Bug: Context Path Crash

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** [00-12-fix-context-path-crash](../slices/00-12-fix-context-path-crash.md)
- **Specs:** N/A

## Symptoms
The `teddy start` (and likely `teddy context`) command crashes with `[Errno 63] File name too long`. The error message indicates that a descriptive text block (specifically from a Markdown spec file) is being passed to a filesystem "read" operation as if it were a path.

## Context & Scope
### Regressing Delta
Identified in commit `6e475b190f5282d1b37b5ef9abab6b82733f1497` ("fix(core): optimize context gathering and token counting performance") and `02ec83850de9e77ef7ae1a87dbf4755c11087190` ("feat(core): update ContextService to collect file metadata into ContextItem list"). These commits introduced the use of `resolve_paths_from_files` in `ContextService._resolve_scoped_paths`.

### Environmental Triggers
Occurs when a Markdown file containing long text is included in the project's context list (e.g., `.teddy/context` or `init.context`).

### Ruled Out
- TUI logic (crash happens during context gathering before TUI launch).
- LLM API (crash is local filesystem related).

## Diagnostic Analysis
### Causal Model
1. `ContextService.get_context` is called with a mapping of `Scope -> List[Path]`.
2. `ContextService._resolve_scoped_paths` iterates through each scope and calls `IFileSystemManager.resolve_paths_from_files(files)` on the entire list.
3. `LocalFileSystemAdapter.resolve_paths_from_files` implementation always treats the input `file_paths` as manifest files (like `.context` files). It reads the content of these files and treats each line as a path to another file.
4. If the input list contains a non-manifest file (e.g., `long_spec.md`), the adapter reads its content.
5. Every line in `long_spec.md` is then added to the set of "resolved paths".
6. `ContextService` later calls `read_files_in_vault` with these "paths".
7. `LocalFileSystemAdapter.read_file` is called with a line of text from the spec file as the `path`.
8. The OS returns `[Errno 63] File name too long` because the text exceeds the maximum path length.

### Discrepancies
- `ContextService` treats target files as manifest files. Conflict: `resolve_paths_from_files` should only be used on `.context` files or similar list-based formats. (resolved: Confirmed via MRE that `ContextService` calls `resolve_paths_from_files` on all input paths, leading to type confusion.)

### Investigation History
1. Initial Observation. User reported `Errno 63` with spec file content in the path. Conclusion: `ContextService` logic leak.
2. Code Review. Confirmed `ContextService` calls `resolve_paths_from_files` on all input files.
3. User Clarification. User noted `session.context` is already resolved. Conclusion: The "type confusion" is that `ContextService` treats target content files as manifest files.
4. Reproduction Attempt. Ran `debug/mre_context_crash.py`. Observation: Successfully reproduced `Errno 63` by passing a Markdown file with long text to `get_context`. Conclusion: `ContextService` incorrectly applies `resolve_paths_from_files` to content files.
5. Regressing Delta Isolation. Confirmed via `git log` that the logic was introduced in `6e475b1` and `02ec838` during Milestone 10.
6. Refined Repair. Discovered that treating all files as targets broke cascading context (manifest resolution). Refined `ContextService` to implement a "Nuanced Resolution" strategy based on file naming conventions. Conclusion: Differentiating manifests from targets resolves the conflict.

## Solution
### Implemented Fixes
- Refactored `ContextService._resolve_scoped_paths` to distinguish between **Manifests** and **Targets**.
- Files with the `.context` extension are resolved as manifests via `IFileSystemManager.resolve_paths_from_files`.
- All other files (e.g., `.md`, `.xml`, `.py`) are included as direct targets.
- This ensures that Agent Prompts and CLI-provided files are gathered correctly without redundant resolution attempts that triggered `Errno 63` crashes on long content.

### Prevention
- Updated `tests/suites/unit/core/services/test_context_service.py` with a specific regression test `test_get_context_with_long_content_file_does_not_crash` and a logic check `test_get_context_distinguishes_between_manifests_and_targets`.

### Prevention
- A unit test will be added to `test_context_service.py` to ensure that providing content files in the context mapping does not trigger manifest resolution.
