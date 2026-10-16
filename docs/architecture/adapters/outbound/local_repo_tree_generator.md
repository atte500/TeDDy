# Component Design: LocalRepoTreeGenerator
- **Status:** Implemented
- **Source:** [`src/teddy_executor/adapters/outbound/local_repo_tree_generator.py`](/src/teddy_executor/adapters/outbound/local_repo_tree_generator.py)

## Purpose
Implements the `IRepoTreeGenerator` outbound port. It walks the repository, filters paths through `.gitignore` and `.teddyignore` rules, and renders a recursive `ls -R`-style tree string.

## Consumers
- [`ContextService`](../../core/services/context_service.md): Generates the project-structure section of the context payload.
- [Composition Root](/src/teddy_executor/container.py): Constructs the generator with the project root.

## Dependencies
- **`filesystem_helpers`** (`teddy_executor.adapters.outbound.filesystem_helpers`): Loads the ignore spec and walks the tree recursively.
- **`pathspec`** (external): Matches paths against the combined ignore patterns, imported lazily through the helper.

## Class Invariants
- `root_resolution`: The root directory is resolved to an absolute path at construction.
- `ignore_spec_cached`: The ignore specification is loaded once at construction.
- `teddyignore_precedence`: `.teddyignore` patterns load after `.gitignore` patterns, so a negation there re-includes an excluded path.
- `posix_output`: Directory headers always use forward slashes, independent of the host separator.
- `symlink_exclusion`: Symlinked directories never appear as directory sections.

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
