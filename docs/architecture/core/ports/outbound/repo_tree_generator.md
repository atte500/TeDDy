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

## Operations

### `generate_tree() -> str`
- **Preconditions:** None.
- **Postconditions:** Returns a multi-line string of the file tree, excluding paths matched by ignore rules.
