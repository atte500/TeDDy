**Status:** Planned
**Introduced in:** [Slice: Refactor `ContextResult` to `ProjectContext`](/docs/project/slices/16-refactor-contextresult-to-projectcontext.md)

## 1. Purpose / Responsibility
`ProjectContext` is a strictly-typed, immutable data transfer object (DTO) that represents the complete, aggregated project context gathered by the `ContextService`. It serves as the definitive data structure passed from the core to any adapter responsible for presenting context to the user or an AI agent.

## 2. Ports
This component is a passive Data Transfer Object and does not implement or use any ports directly. It is the return type for the `IGetContextUseCase` inbound port.

## 3. Implementation Details / Logic
The `ProjectContext` model will be implemented as a Python `@dataclass`. This provides immutability (`frozen=True`), automatic `__init__`, `__repr__`, and other boilerplate methods, ensuring the object is simple, robust, and type-safe.

## 4. Data Contracts / Methods

### `ProjectContext` Dataclass Attributes
-   **`header` (`str`):** A formatted string containing high-level system information and the repository file tree.
-   **`content` (`str`):** A formatted string containing the contents of all requested files from the context vault.

### Preconditions
- All attributes (`header`, `content`) must be non-empty strings.

### Postconditions
- An instance of `ProjectContext` is successfully created with the provided data.

### Invariants
- Once instantiated, the `ProjectContext` object is immutable. Its attributes cannot be changed.

### Exception/Error States
- Does not raise exceptions on its own. Type errors will be caught statically by `mypy`.
