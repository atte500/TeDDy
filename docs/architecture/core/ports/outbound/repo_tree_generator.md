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
- **Limits:** The port exposes two read-only properties. `max_depth` is the maximum directory nesting depth, and `max_tree_width` is the maximum visible entries listed for a non-root directory.
- **Omission notice:** A withheld directory renders the single line `[X folders, Y files]`. `X` and `Y` count only the visible immediate children after ignore rules, and any count of one uses the lowercase singular noun. A directory is withheld at or beyond the depth limit, or when a non-root directory holds more visible entries than the width cap. An unreadable directory renders `[unreadable]` with no counts, because a failed scan has no count to state.
- **Depth limit:** The adapter accepts a non-negative depth limit at construction and defaults to the schema default 3. Every non-negative value is a literal cap, so counting is zero-based from the repository root and a limit of one renders only the root section. Zero collapses the tree to one omission notice for the root, because zero is a literal cap.
- **Width cap:** The adapter accepts a positive width cap at construction and defaults to the schema default 20. The cap is a maximum, so a directory holding exactly the cap count expands. The project root is exempt, because it is the only place where a top-level file is named. A withheld directory omits its descendant sections, because names without their parent folder cannot be mapped.

## Operations

### `generate_tree() -> str`
- **Preconditions:** None.
- **Postconditions:** Returns a multi-line string of the file tree, excluding paths matched by ignore rules. Every directory at or beyond the depth limit, and every non-root directory above the width cap, renders one compact omission notice instead of expanding, so truncation is never silent. An unreadable directory renders `[unreadable]`. The project root is exempt from the width cap. A depth limit of zero renders one omission notice for the root and lists no child entry.
