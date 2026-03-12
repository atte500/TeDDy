# Component: PlanningService
- **Status:** Implemented
- **Introduced in:** [Slice 09-04](/docs/project/slices/09-04-core-session-context-engine.md)

## 1. Purpose / Responsibility

The `PlanningService` is responsible for generating an AI plan based on a user message and the current project context. It orchestrates the gathering of context, the retrieval of agent instructions, and the communication with the Large Language Model.

## 2. Ports

-   **Implements Inbound Port:** `IPlanningUseCase`
-   **Uses Outbound Ports:**
    -   `IGetContextUseCase` (ContextService)
    -   `ILlmClient` (LiteLLMAdapter)
    -   `IFileSystemManager` (to read `system_prompt.xml` and write `plan.md`)
    -   `IConfigService` (to resolve planning model settings)

## 3. Implementation Details / Logic

1.  **Gather Context:** Calls `IGetContextUseCase.get_context()` (with session/turn files if applicable).
2.  **Fetch System Prompt:** Reads the local `system_prompt.xml` from the current turn directory.
3.  **Contextual Hints:** If operating in Turn 01, it injects an alignment hint into the user message to encourage the agent to clarify goals.
4.  **LLM Call:** Passes the formatted context, system prompt, and user message to `ILlmClient.get_completion()`.
5.  **Persistence:** Saves the resulting Markdown response to the turn's `plan.md`.

## 4. Data Contracts / Methods

### `generate_plan(user_message: str, turn_dir: str, context_files: Optional[Dict[str, Sequence[str]]] = None) -> str`

-   **Description:** Generates a new `plan.md` file in the specified directory.
-   **Preconditions:**
    -   `turn_dir` must exist.
    -   `system_prompt.xml` must exist in `turn_dir`.
-   **Postconditions:**
    -   A valid `plan.md` is written to `turn_dir`.
    -   Returns the path to the generated plan.
-   **Exceptions:**
    -   `LlmCommunicationError`: Raised if the LLM client fails.
    -   `FileNotFoundError`: Raised if the system prompt is missing.
