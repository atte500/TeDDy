# Bug: Context Directory Read Failure

- **Status:** Resolved
- **Milestone:** [Milestone 2: Stability & Infrastructure](/docs/project/milestones/02-stability-and-polish.md)
- **Vertical Slice:** N/A
- **Specs:** [Spec: Stability & Bug Fixes](/docs/project/specs/stability-and-bugfixes.md)

## Symptoms
`teddy context` crashes with `IsADirectoryError` when a directory path is included in the context (via `.context` files or `-c` flags).

```text
OSError: Failed to read file at docs/project/slices: Failed to read raw file at docs/project/slices: [Errno 21] Is a directory: '/Users/raphaelatteritano/Desktop/dev/TeDDy/docs/project/slices'
```

## Context & Scope
### Regressing Delta
Work on Milestone 2 "Context Robustness" (Recursive Expansion) is likely incomplete or buggy.

### Environmental Triggers
Including a directory path in `.teddy/init.context`, `<session>/session.context`, or `turn.context`.

### Ruled Out
- `MarkdownPlanParser` (unrelated to context gathering).
- `ExecutionOrchestrator` (the crash happens during context gathering, before execution).

## Diagnostic Analysis
### Causal Model
1. `teddy context` identifies context file paths (e.g., `test.context`).
2. `ContextService.get_context` calls `_resolve_scoped_paths` -> `_resolve_files_to_paths`.
3. `_resolve_files_to_paths` detects `test.context` as a manifest and calls `resolve_paths_from_files`.
4. `resolve_paths_from_files` returns the raw strings from the manifest (e.g., `["docs/slices"]`).
5. `_resolve_files_to_paths` appends these strings to the result list without verifying if they are directories.
6. `LocalFileSystemAdapter.read_files_in_vault` attempts to `read_file("docs/slices")`.
7. `read_file` calls `pathlib.Path.read_text()`, which throws `IsADirectoryError`.

### Discrepancies
- `ContextService` is supposed to expand directories recursively per Spec, but it passed a directory to the reader. (resolved: `_resolve_files_to_paths` logic was shallow; it expanded manifests but didn't validate the results of that expansion against the directory-expansion rule).

### Investigation History
1. [Initial Report]. Observed crash in `teddy context` when processing `docs/project/slices`.
2. [Hypothesis: Manifest Expansion Gap]. `ContextService._resolve_files_to_paths` expands directories passed as top-level arguments, but doesn't check the content of manifests for directories. [Observation: MRE failed with `OSError: [Errno 21] Is a directory`]. [Conclusion: Confirmed. Resolution logic must be recursive or re-evaluate manifest results].

## Solution
### Root Cause
The `ContextService._resolve_files_to_paths` method performed a shallow expansion of `.context` manifest files. It successfully extracted paths from these files but failed to re-evaluate them against the directory-expansion rule. This caused directory paths to be passed to the file-reading layer, which only supports regular files.

### Fix
Refactor `ContextService._resolve_files_to_paths` to use a queue-based Breadth-First Search (BFS) resolution. This ensures that every path—whether provided at the top level or extracted from a manifest—is correctly classified as a manifest, a directory, or a file.

### Prevention
- **Systemic Fix**: Standardize context resolution into a single, recursive utility that ensures all paths are eventually resolved to individual files.
- **Audit**: Verify all callers of `IFileSystemManager.resolve_paths_from_files` to ensure they handle the results safely.
