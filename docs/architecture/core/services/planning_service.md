# Component: PlanningService
- **Status:** Implemented

## Pure Context Model (Poka-Yoke)
To maintain architectural purity and statelessness, the `PlanningService` follows a "Pure Context" model:
- **Instruction-Free Prompting:** The service MUST NOT inject specific user instructions or "Current Tasks" into the LLM's `messages` list or the `input.md` file.
- **Pure State Snapshot:** `input.md` represents the "Project Reality" at a specific moment. It contains file structures and contents (including `initial_request.md` and previous `report.md` files).
- **Discovery Mechanism:** The agent prompt (System Message) instructs the AI to determine its next action by analyzing the project state, session goal, and latest audit trail (report) within the provided context.

## 1. Purpose / Responsibility

The `PlanningService` is responsible for generating an AI plan based on a user message and the current project context. It orchestrates the gathering of context, the retrieval of agent instructions, and the communication with the Large Language Model. It includes a preflight configuration check to ensure API keys and environment variables are valid before invoking the LLM. It also displays pre-response telemetry (Model, Context Usage, Cost) to the user via the `IUserInteractor`.

## 2. Ports

-   **Implements Inbound Port:** `IPlanningUseCase`
-   **Uses Outbound Ports:**
    -   `IGetContextUseCase` (ContextService)
    -   `ILlmClient` (LiteLLMAdapter)
    -   `IFileSystemManager` (to read `[agent_name].xml` and write `plan.md`)
    -   `IConfigService` (to resolve planning model settings)

## 3. Implementation Details / Logic

0.  **Preflight Check:** Calls `ILlmClient.validate_config()`. If errors are found, raises `ConfigurationError` with the config file path.
1.  **Gather Context:** Calls `IGetContextUseCase.get_context()` (with session/turn files if applicable).
2.  **Fetch System Prompt:** Reads the local `[agent_name].xml` prompt from the current turn directory.
3.  **Contextual Hints:** If operating in Turn 01, it injects an alignment hint into the user message to encourage the agent to clarify goals.
4.  **LLM Call:** Passes the formatted context, system prompt, and user message to `ILlmClient.get_completion()`.
5.  **Persistence:** Saves the resulting Markdown response to the turn's `plan.md`. Updates `meta.yaml` with telemetry (model name, token usage, USD cost). Writes the full context used for the generation to `input.md`.
6.  **Hardening:** Ensures all metadata is cast to primitive types (str, int, float, bool) before serialization to prevent `yaml.dump` from entering infinite recursion hangs when encountering `MagicMock` objects in unit tests.

## 4. Data Contracts / Methods

### `generate_plan(user_message: str, turn_dir: str, context_files: Optional[Dict[str, Sequence[str]]] = None) -> str`

-   **Description:** Generates a new `plan.md` file in the specified directory. **Defensive Design:** If `context_files` is omitted, it auto-resolves session/turn manifests from `turn_dir` via `SessionManager`.
-   **Preconditions:**
    -   `turn_dir` must exist.
    -   The agent prompt file (`[agent_name].xml`) must exist in `turn_dir`.
-   **Postconditions:**
    -   A valid `plan.md` is written to `turn_dir`.
    -   Returns the path to the generated plan.
-   **Exceptions:**
    -   `ConfigurationError`: Raised if API keys or environment variables are missing or invalid.
    -   `LlmCommunicationError`: Raised if the LLM client fails.
    -   `FileNotFoundError`: Raised if the system prompt is missing.
