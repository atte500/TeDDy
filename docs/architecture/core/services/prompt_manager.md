# Component Design: PromptManager
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/services/prompt_manager.py`](/src/teddy_executor/core/services/prompt_manager.py)

## Purpose
Implements the `IPromptManager` outbound port. It resolves agent prompts, composes the final system prompt by appending the shared MRP base prompt, resolves the user request for a turn, and persists turn telemetry metadata into `meta.yaml`.

## Consumers
- [`SessionService`](./session_service.md): Calls `fetch_system_prompt` when composing the session-root prompt and `update_meta` when persisting turn telemetry.
- [`PlanningService`](./planning_service.md): Calls `fetch_system_prompt` to build the LLM system prompt.
- [`SessionOrchestrator`](./session_orchestrator.md): Calls `fetch_system_prompt` during the turn transition.
- [`SessionPorts`](/src/teddy_executor/core/domain/models/planning_ports.py): Declares `prompts: IPromptManager` in the session ports bundle.
- [CLI Adapter](../../adapters/inbound/cli.md): Resolves the composed prompt for the `get-prompt` command and the session handlers.
- [Composition Root](/src/teddy_executor/container.py): Registers `PromptManager` against `IPromptManager`.

## Dependencies
- [`IFileSystemManager`](../ports/outbound/file_system_manager.md): Reads agent prompt files and persists `meta.yaml`.
- [`IUserInteractor`](../ports/outbound/user_interactor.md): Optional collaborator for prompting the user when instructions are missing.
- `importlib.resources` (stdlib): Loads the bundled `MRP.md` base prompt through the `Traversable` contract.
- `yaml` (external): Serializes the turn metadata dictionary.

## Class Invariants
- `verbatim_session_prompt`: When a session-root prompt file exists, `fetch_system_prompt` returns it unchanged and never re-composes it.
- `mrp_appended_once`: The MRP base prompt is appended only on the lazy-compose fallback path, after the agent content and separated by a `---` rule.
- `legacy_short_circuit`: A resolved prompt that already carries `<response_format>` is returned unchanged, without the MRP block.
- `single_sourced_assembly`: Both composition entry points delegate to `_assemble_composed_prompt`, so the composed prompt cannot drift.
- `mrp_fail_fast`: A missing `MRP.md` resource raises `FileNotFoundError` rather than returning a degraded prompt.

## Inbound Ports
None — this is a concrete implementation of an outbound port.

## Outbound Ports
- **`IPromptManager`**: The driven contract this service implements. The interface lives in `src/teddy_executor/core/ports/outbound/prompt_manager.py`.

## Data Contracts
- **`meta.yaml` mapping**: `agent_name`, `turn_cost`, `token_count`, `model`, `actual_model`, `finish_reason`.
- **Return of `fetch_system_prompt`**: The composed system prompt string, or an empty string when no agent prompt resolves.

## Operations

### `fetch_system_prompt(agent_name, turn_path) -> str`
- **Preconditions:** `agent_name` is a non-empty string; `turn_path` is the current turn directory.
- **Postconditions:** Returns the session-root prompt verbatim when it exists. Otherwise resolves the agent content from `.teddy/prompts/` and returns the assembled prompt. Returns an empty string when no agent prompt resolves.
- **Exceptions:** `FileNotFoundError` when `MRP.md` must be appended but is missing.

### `compose_system_prompt(agent_name) -> Optional[str]`
- **Preconditions:** `agent_name` is a non-empty string.
- **Postconditions:** Returns the assembled prompt from the canonical `.teddy/prompts/` source without a turn path, or `None` when no content resolves.
- **Exceptions:** `FileNotFoundError` when `MRP.md` must be appended but is missing.

### `resolve_message(user_message, turn_path) -> Optional[str]`
- **Preconditions:** `turn_path` is the current turn directory.
- **Postconditions:** Returns the user message, the turn-one `initial_request.md` content, or an empty string for a continuation signal. Returns `None` for empty interactive input.

### `update_meta(meta, response, token_count, turn_cost, meta_file_path) -> None`
- **Preconditions:** `meta` is a dictionary; `meta_file_path` is writable.
- **Postconditions:** Records cost, token count, the configured model, the actual serving model, and the finish reason, then persists the scrubbed metadata.
