# Component Design: LocalRepoTreeGenerator
- **Status:** Implemented
- **Source:** [`src/teddy_executor/adapters/outbound/local_repo_tree_generator.py`](/src/teddy_executor/adapters/outbound/local_repo_tree_generator.py)

## Purpose
Implements the `IRepoTreeGenerator` outbound port. It traverses the repository once, filters paths through `.gitignore` and `.teddyignore` rules, and renders a recursive `ls -R`-style tree string during that same traversal.

## Consumers
- [`ContextService`](../../core/services/context_service.md): Generates the project-structure section of the context payload.
- [Composition Root](/src/teddy_executor/container.py): Constructs the generator with the project root.

## Dependencies
- **`filesystem_helpers`** (`teddy_executor.adapters.outbound.filesystem_helpers`): Loads the combined ignore spec. The adapter owns its own traversal, because the shared recursive walk also serves `LocalFileSystemAdapter`.
- **`pathspec`** (external): Matches paths against the combined ignore patterns, resolved through the helper.

## Class Invariants
- `root_resolution`: The root directory is resolved to an absolute path at construction.
- `ignore_spec_cached`: The ignore specification is loaded once at construction.
- `teddyignore_precedence`: `.teddyignore` patterns load after `.gitignore` patterns, so a negation there re-includes an excluded path.
- `posix_output`: Directory headers always use forward slashes, independent of the host separator.
- `symlink_exclusion`: Symlinked directories never appear as directory sections.
- `single_pass_traversal`: Each directory is scanned exactly once, and its rendered section is built during that scan, so no second filesystem pass occurs.
- `scan_cache_flags`: Directory and symlink flags come from the `os.scandir` entry cache, so no entry pays an extra stat call.
- `section_order`: Sections sort by their relative path with the root keyed as `.`, which renders a top-level name such as `!important` before the root block.

## Inbound Ports
None — this is an outbound (driven) adapter.

## Outbound Ports
- **`IRepoTreeGenerator`**: The driven contract implemented by this adapter. See the [IRepoTreeGenerator design](../../core/ports/outbound/repo_tree_generator.md).

## Data Contracts
- **`generate_tree` return:** A multi-line `str` in recursive `ls -R` format, where each non-root directory is introduced by a `./relative/path:` header.

## Operations

### `generate_tree() -> str`
- **Preconditions:** None.
- **Postconditions:** Returns the filtered tree as a single string. A file and its parent directories survive only when they are not excluded by the ignore spec. The adapter writes no intermediate files.
