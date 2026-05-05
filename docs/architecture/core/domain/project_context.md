**Status:** Refactoring

## 1. Purpose / Responsibility
`ProjectContext` is a strictly-typed, immutable data transfer object (DTO) that represents the complete, aggregated project context gathered by the `ContextService`. It serves as the definitive data structure passed from the core to any adapter responsible for presenting context to the user or an AI agent.

## 2. Ports
This component is a passive Data Transfer Object and does not implement or use any ports directly. It is the return type for the `IGetContextUseCase` inbound port.

## 3. Implementation Details / Logic
The `ProjectContext` model will be implemented as a Python `@dataclass`. This provides immutability (`frozen=True`), automatic `__init__`, `__repr__`, and other boilerplate methods, ensuring the object is simple, robust, and type-safe.

## 4. Data Contracts / Methods

### `ContextItem` Dataclass Attributes
- **`path` (`str`):** The relative file path.
- **`token_count` (`int`):** The estimated token size of the file.
- **`source_scope` (`str`):** The scope of the file (e.g., `session`, `turn`).
- **`git_status` (`str`):** The 2-character git status code (e.g., `M `, `??`, or empty if tracked/unmodified).
- **`selected` (`bool`):** User-controlled selection state for the NEXT turn.
- **`auto_prune_reason` (`Optional[str]`):** Human-readable reason for pre-deselection (e.g., "Exceeds 15k token limit").

### `ProjectContext` Dataclass Attributes
-   **`header` (`str`):** A pre-formatted string containing high-level system information (CWD, OS, etc.).
-   **`content` (`str`):** A pre-formatted string containing the repository file tree and the contents of all requested files from the context vault.
-   **`items` (`List[ContextItem]`):** A structured list of context files and their metadata for UI presentation.

### Preconditions
- All attributes (`header`, `content`) must be non-empty strings.

### Postconditions
- An instance of `ProjectContext` is successfully created with the provided data.

### Invariants
- Once instantiated, the `ProjectContext` object is immutable. Its attributes cannot be changed.

### Exception/Error States
- Does not raise exceptions on its own. Type errors will be caught statically by `mypy`.
