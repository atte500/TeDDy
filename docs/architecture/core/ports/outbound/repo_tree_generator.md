# Component Design: IRepoTreeGenerator
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/ports/outbound/repo_tree_generator.py`](/src/teddy_executor/core/ports/outbound/repo_tree_generator.py)

## Purpose
Defines the outbound port for producing a textual file tree of the repository. It must honour `.gitignore` and `.teddyignore` rules so the context payload omits irrelevant paths.

## Consumers
- [`ContextService`](../../services/context_service.md): Generates the project-structure section of the context payload.

## Dependencies
None — this port declares no injected dependencies.

## Class Invariants
- `protocol_contract`: The port is a `Protocol`; implementing adapters satisfy the structural contract.

## Inbound Ports
None — this is an outbound (driven) port.

## Outbound Ports
- **`IRepoTreeGenerator`**: The driven contract consumed by `ContextService` and implemented by `LocalRepoTreeGenerator`.

## Data Contracts
- **`generate_tree` return:** A multi-line `str` rendering the file tree.
- **Omission marker:** A truncated directory renders the single line `[... directory not expanded (depth limit N): X folders, Y files]`. `N` is the configured depth limit. `X` and `Y` count only the visible immediate children after ignore rules, and any count of one uses the lowercase singular noun. An unreadable directory renders `[... directory not expanded (unreadable): 0 folders, 0 files]` so the omission stays explicit.
- **Depth limit:** The adapter accepts a non-negative depth limit at construction and defaults to the schema default 4. Every non-negative value is a literal cap, so counting is zero-based from the repository root and a limit of one renders only the root section. Zero collapses the tree to one omission notice for the root, because zero is a literal cap.

## Operations

### `generate_tree() -> str`
- **Preconditions:** None.
- **Postconditions:** Returns a multi-line string of the file tree, excluding paths matched by ignore rules. Every directory at or beyond the depth limit renders an omission marker instead of expanding, so truncation is never silent. A depth limit of zero renders one omission notice for the root and lists no child entry.
