**Status:** Refactoring

## 1. Purpose / Responsibility
`ProjectContext` is a strictly-typed, immutable data transfer object (DTO) that represents the complete, aggregated project context gathered by the `ContextService`. It serves as the definitive data structure passed from the core to any adapter responsible for presenting context to the user or an AI agent.

## 2. Ports
This component is a passive Data Transfer Object and does not implement or use any ports directly. It is the return type for the `IGetContextUseCase` inbound port.

## 3. Implementation Details / Logic
The `ProjectContext` and `ContextItem` models are implemented as Python `@dataclass`es. While `ProjectContext` is immutable (`frozen=True`), `ContextItem` is **mutable** (not frozen) to allow the TUI to manage the `selected` state during the review phase.

## 4. Data Contracts / Methods

### `ContextItem` Dataclass Attributes
- **`path` (`str`):** The relative file path.
- **`token_count` (`int`):** The estimated token size of the file.
- **`git_status` (`str`):** The 2-character git status code (e.g., `M`, `U`, `A`, `D`).
- **`scope` (`str`):** The scope of the file (`Session`, `Turn`, or `System`).
- **`selected` (`bool`):** User-controlled selection state for the NEXT turn. Defaults to `True`.
- **`auto_prune_reason` (`Optional[str]`):** Human-readable reason for pre-deselection (e.g., "Pruned to fit context budget").

### `ProjectContext` Dataclass Attributes (Frozen)
-   **`header` (`str`):** A pre-formatted string containing high-level system information (CWD, OS, etc.).
-   **`content` (`str`):** A pre-formatted string containing the repository file tree and the contents of all requested files.
-   **`items` (`List[ContextItem]`):** A structured list of all context files and their metadata for UI presentation.
-   **`agent_name` (`str`):** The name of the active agent persona (e.g., "Developer").
-   **`system_prompt_tokens` (`int`):** The estimated token size of the agent's system prompt.
-   **`total_window` (`int`):** The total context window (input limit) for the model in use.

### Preconditions
- All attributes (`header`, `content`) must be non-empty strings.

### Postconditions
- An instance of `ProjectContext` is successfully created with the provided data.

### Invariants
- Once instantiated, the `ProjectContext` object is immutable. Its attributes cannot be changed.

### Exception/Error States
- Does not raise exceptions on its own. Type errors will be caught statically by `mypy`.
